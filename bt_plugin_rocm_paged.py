# SPDX-License-Identifier: MIT
#
# Streaming ROCpd (SQLite) -> BT2 source component (paged, low-memory)
# - Pages each table with keyset pagination (no fetchall)
# - K-way merge across included tables by timestamp
# - Emits events to be written by sink.ctf.fs
#
# Usage:
#   babeltrace2 run \
#     --plugin-path=. \
#     --component='src:source.rocpd_paged.sqlite' --params='{"db":"path/to/rocpd.sqlite","page_rows":50000}' \
#     --component='ctf:sink.ctf.fs' --params='{"path":"out-ctf"}' \
#     --connect='src:ctf'
#
# Notes:
# - Timestamp column detection prefers: ts_ns, start_ns, ts, start, timestamp
# - ID/row key prefers: id, _id, else uses rowid
# - Unknown/complex columns go to a JSON "row_json" payload field
#
# Requires: Babeltrace 2 Python bindings (`bt2`) with Python plugins enabled.

import bt2
import sqlite3
import json
import heapq
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

# Register plugin: file must be named bt_plugin_*.py and we register a plugin name.
bt2.register_plugin(__name__, "rocpd_paged")

TS_CANDIDATES = ("ts_ns", "start_ns", "ts", "start", "timestamp")
ID_CANDIDATES = ("id", "_id")

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}

def _detect_ts_col(cols: List[str]) -> Optional[str]:
    lower = [c.lower() for c in cols]
    for cand in TS_CANDIDATES:
        if cand in lower:
            return cols[lower.index(cand)]
    return None

def _detect_id_col(cols: List[str]) -> Optional[str]:
    lower = [c.lower() for c in cols]
    for cand in ID_CANDIDATES:
        if cand in lower:
            return cols[lower.index(cand)]
    return None

def _parse_tables_param(val) -> Optional[List[str]]:
    if val is None:
        return None
    if isinstance(val, str):
        return [t.strip() for t in val.split(",") if t.strip()]
    try:
        return [str(x) for x in val]
    except Exception:
        return None

def _list_tables(conn: sqlite3.Connection, include: Optional[List[str]]) -> List[str]:
    if include:
        return include
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [r[0] for r in cur.fetchall()]

class _PagedTableIter:
    """
    Iterate one table using keyset pagination ordered by (ts, id/rowid).
    We SELECT rowid,* to always have rowid available when useful.
    """
    def __init__(self, conn: sqlite3.Connection, table: str, page_rows: int):
        self._conn = conn
        self._table = table
        self._page_rows = max(1, int(page_rows))
        self._buffer: List[sqlite3.Row] = []
        self._exhausted = False

        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        self.columns = cols
        self.ts_col = _detect_ts_col(cols)
        self.id_col = _detect_id_col(cols)
        self._use_rowid = self.id_col is None

        self._last_ts: Optional[int] = None
        self._last_id: Optional[int] = None

        self._open_next_page()

    def _open_next_page(self):
        if self._exhausted:
            return

        where_parts = []
        params: List[Any] = []
        order_terms = []

        # we always select rowid,* so rowid is addressable
        select_cols = "rowid, *"

        if self.ts_col is not None:
            order_terms.append(f"{self.ts_col} ASC")
            order_terms.append(("rowid" if self._use_rowid else f"{self.id_col}") + " ASC")
            if self._last_ts is not None:
                where_parts.append(
                    f"({self.ts_col} > ? OR ({self.ts_col} = ? AND {('rowid' if self._use_rowid else self.id_col)} > ?))"
                )
                params.extend([self._last_ts, self._last_ts, self._last_id if self._last_id is not None else 0])
        else:
            # No timestamp column: just keyset on id/rowid
            if self._use_rowid:
                order_terms.append("rowid ASC")
                if self._last_id is not None:
                    where_parts.append("rowid > ?")
                    params.append(self._last_id)
            else:
                order_terms.append(f"{self.id_col} ASC")
                if self._last_id is not None:
                    where_parts.append(f"{self.id_col} > ?")
                    params.append(self._last_id)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        order_sql = f"ORDER BY {', '.join(order_terms)}" if order_terms else ""
        limit_sql = f"LIMIT {self._page_rows}"

        sql = f"SELECT {select_cols} FROM {self._table} {where_sql} {order_sql} {limit_sql}"
        cur = self._conn.execute(sql, params)
        self._buffer = cur.fetchall()
        if not self._buffer:
            self._exhausted = True

    def __iter__(self):
        return self

    def __next__(self) -> sqlite3.Row:
        if self._exhausted:
            raise StopIteration

        if not self._buffer:
            self._open_next_page()
            if self._exhausted:
                raise StopIteration

        row = self._buffer.pop(0)

        if self.ts_col is not None:
            ts_val = row[self.ts_col]
            self._last_ts = int(ts_val) if ts_val is not None else 0

        if self._use_rowid:
            self._last_id = int(row["rowid"])
        else:
            v = row[self.id_col]
            self._last_id = int(v) if v is not None else 0

        return row

class _KMerge:
    """
    K-way merge across tables, ordering by timestamp (fallback 0).
    Yields (ts, table_name, row_dict)
    """
    def __init__(self, table_iters: Dict[str, _PagedTableIter]):
        self._iters = table_iters
        self._heap: List[Tuple[int, int, str, Dict[str, Any]]] = []
        self._seq = 0
        self._prime()

    def _prime(self):
        for tname, it in self._iters.items():
            try:
                row = next(it)
            except StopIteration:
                continue
            rowd = _row_to_dict(row)
            ts = 0
            if it.ts_col is not None:
                val = rowd.get(it.ts_col)
                ts = int(val) if isinstance(val, (int, float)) and val is not None else 0
            heapq.heappush(self._heap, (ts, self._seq, tname, rowd))
            self._seq += 1

    def __iter__(self):
        return self

    def __next__(self) -> Tuple[int, str, Dict[str, Any]]:
        if not self._heap:
            raise StopIteration
        ts, _, tname, rowd = heapq.heappop(self._heap)
        it = self._iters[tname]
        try:
            nxt = next(it)
            rowd2 = _row_to_dict(nxt)
            ts2 = 0
            if it.ts_col is not None:
                val = rowd2.get(it.ts_col)
                ts2 = int(val) if isinstance(val, (int, float)) and val is not None else 0
            heapq.heappush(self._heap, (ts2, self._seq, tname, rowd2))
            self._seq += 1
        except StopIteration:
            pass
        return ts, tname, rowd

def _make_payload_fc(trace_cls: bt2._TraceClass, sample_row: Dict[str, Any]) -> bt2._StructureFieldClass:
    members: List[Tuple[str, bt2._FieldClass]] = []
    for k, v in sample_row.items():
        if k == "rowid":
            continue
        if isinstance(v, bool):
            members.append((k, trace_cls.create_bool_field_class()))
        elif isinstance(v, int):
            members.append((k, trace_cls.create_signed_integer_field_class(64)))
        elif isinstance(v, float):
            members.append((k, trace_cls.create_real_field_class()))
        elif isinstance(v, str):
            members.append((k, trace_cls.create_string_field_class()))
        # bytes/other -> omit; captured in row_json
    members.append(("row_json", trace_cls.create_string_field_class()))
    return trace_cls.create_structure_field_class(members=members)

@bt2.plugin_component_class
class sqlite(bt2._UserSourceComponent):
    """
    Streaming ROCpd SQLite reader (paged).

    Params:
      db         : path to SQLite file (required)
      page_rows  : page size per table (default 50000)
      tables     : optional list or comma-separated string of table names
      packet_events : rotate packets every N events (default 200000)
      assume_ns  : if true, timestamps are already ns (default true)
    """
    def __init__(self, config, params, obj):
        self._db = params.get("db")
        if not self._db:
            raise ValueError('Parameter "db" is required')
        self._page_rows = int(params.get("page_rows", 50000))
        self._packet_events = int(params.get("packet_events", 200000))
        self._tables_param = _parse_tables_param(params.get("tables"))
        self._assume_ns = bool(params.get("assume_ns", True))
        self._out = self._add_output_port("ctf")  # name used in --connect

    def _user_message_iterator(self, port):
        return _Iter(self)

class _Iter(bt2._UserMessageIterator):
    def __init__(self, comp: sqlite):
        super().__init__()
        # Open DB read-only; row_factory -> dict-like rows
        self._conn = sqlite3.connect(f"file:{comp._db}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row

        self._page_rows = comp._page_rows
        self._packet_events = max(1, comp._packet_events)

        # 1 GHz clock fits ns timestamps directly
        freq = 1_000_000_000

        # Metadata (trace/clock/stream)
        self._trace_cls = self._create_trace_class()
        self._clk_cls = self._create_clock_class(frequency=freq, name="rocpd_clk")
        self._stream_cls = self._create_stream_class(default_clock_class=self._clk_cls, supports_packets=True)

        self._trace = self._trace_cls()
        self._stream = self._trace.create_stream(self._stream_cls)
        self._packet = self._stream.create_packet()

        self._evt_cls: Dict[str, bt2._EventClass] = {}

        tables = _list_tables(self._conn, comp._tables_param)
        self._iters: Dict[str, _PagedTableIter] = {t: _PagedTableIter(self._conn, t, self._page_rows) for t in tables}
        self._merge = _KMerge(self._iters)

        self._msg_q: List[bt2._Message] = []
        self._msg_q.append(self._create_stream_beginning_message(self._stream))
        self._msg_q.append(self._create_packet_beginning_message(self._packet))

        self._done = False
        self._ev_count = 0
        self._assume_ns = comp._assume_ns

    def _finalize(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __next__(self):
        if self._msg_q:
            return self._msg_q.pop(0)

        if self._done:
            raise StopIteration

        try:
            ts, table, row = next(self._merge)
        except StopIteration:
            self._msg_q.append(self._create_packet_end_message(self._packet))
            self._msg_q.append(self._create_stream_end_message(self._stream))
            self._done = True
            return self._msg_q.pop(0)

        # Build event class lazily per table (payload schema from first row)
        evt_cls = self._evt_cls.get(table)
        if evt_cls is None:
            payload_fc = _make_payload_fc(self._trace_cls, row)
            evt_cls = self._stream_cls.create_event_class(name=table, payload_field_class=payload_fc)
            self._evt_cls[table] = evt_cls

        # Timestamp: treat as ns ticks on a 1 GHz clock
        clk_val = int(ts) if self._assume_ns else int(ts)  # if not ns, still ticks at 1 GHz

        # Create event in current packet with a default clock snapshot
        msg = self._create_event_message(evt_cls, self._packet, default_clock_snapshot=clk_val)

        # Fill payload (best-effort type mapping); always include row_json
        payload = msg.event.payload_field
        for name in payload:
            if name == "row_json":
                continue
            if name in row and row[name] is not None:
                try:
                    payload[name] = row[name]
                except Exception:
                    pass
        try:
            payload["row_json"] = json.dumps(row, default=str, ensure_ascii=False)
        except Exception:
            payload["row_json"] = "{}"

        # Packet rotation to bound sink buffers and encourage flush
        self._ev_count += 1
        if (self._ev_count % self._packet_events) == 0:
            self._msg_q.append(msg)
            self._msg_q.append(self._create_packet_end_message(self._packet))
            self._packet = self._stream.create_packet()
            self._msg_q.append(self._create_packet_beginning_message(self._packet))
            return self._msg_q.pop(0)

        return msg
