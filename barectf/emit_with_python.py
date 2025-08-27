# --- file: barectf/emit_with_python.py ---
"""Emit CTF trace from a ROCPD SQLite database using librocpd_barectf.so.

All events which have start and end timestamps are emitted twice: one *_start
event at the start timestamp and one *_end event at the end timestamp. Events
with only a start definition (e.g. marker_core_region_event_start) are emitted
once. Durations are derived from (end - start) if the stored duration is zero
or NULL.
"""

from __future__ import annotations
import argparse, ctypes, os, pathlib, sqlite3, shutil, heapq, sys, threading, itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Sequence, Tuple, Callable

THIS_DIR = pathlib.Path(__file__).resolve().parent
lib = ctypes.CDLL(str(THIS_DIR / "librocpd_barectf.so"))

# Bridge signatures
lib.rocpd_init.argtypes = [ctypes.c_char_p, ctypes.c_uint32]; lib.rocpd_init.restype = ctypes.c_int
lib.rocpd_close.argtypes = []; lib.rocpd_close.restype = None

if not hasattr(lib, 'rocpd_trace_region'):
    raise RuntimeError("Bridge missing rocpd_trace_region")
lib.rocpd_trace_region.argtypes = [
    ctypes.c_uint16, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
    ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
    ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p,
    ctypes.c_char_p, ctypes.c_uint64
]

if hasattr(lib, 'rocpd_trace_kernel_dispatch'):
    lib.rocpd_trace_kernel_dispatch.argtypes = [
        ctypes.c_uint16, ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p,
        ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
        ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
        ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
        ctypes.c_uint64
    ]
if hasattr(lib, 'rocpd_trace_memory_copy'):
    lib.rocpd_trace_memory_copy.argtypes = [
        ctypes.c_uint16, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64,
        ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64,
        ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_uint64
    ]
if hasattr(lib, 'rocpd_trace_memory_allocation'):
    lib.rocpd_trace_memory_allocation.argtypes = [
        ctypes.c_uint16, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p,
        ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_uint64
    ]

AltCols = Dict[str, Sequence[str]]

def list_views(conn: sqlite3.Connection) -> List[str]:
    """Return only view names (user requested using views exclusively)."""
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")]

def to_u64(x) -> int: return 0 if x is None else int(x) & 0xFFFFFFFFFFFFFFFF
def b(s: Optional[str]) -> bytes: return (s or "").encode('utf-8','replace')

def calc_duration(start_ns, end_ns, duration):
    if duration and duration > 0: return int(duration)
    try:
        s = int(start_ns or 0); e = int(end_ns if end_ns is not None else s)
        d = e - s
        return d if d >= 0 else 0
    except Exception:
        return 0

REGION_CATEGORY_MAP = [
    ('hip_compiler', (15,16)),
    ('hip-runtime', (12,13)),
    ('hip_runtime', (12,13)),
    ('hsa_core', (18,19)),
    ('hsa_amd_ext', (21,22)),
    ('marker_core', (24,None)),  # only start defined
]

def collect_regions(conn: sqlite3.Connection, out_events: List[Tuple[int, Tuple]], progress_cb: Optional[Callable[[int], None]] = None, events_added_ref: Optional[List[int]] = None) -> int:
    if 'regions' not in list_views(conn):
        return 0
    cur = conn.cursor()
    cur.execute("SELECT id AS region_id,guid,name,category,nid,pid,tid,event_id,stack_id,parent_stack_id,corr_id AS correlation_id,duration,extdata,call_stack,line_info,start,end FROM regions")
    count = 0
    for (region_id,guid,name,category,nid,pid,tid,event_internal_id,stack_id,parent_stack_id,correlation_id,duration,extdata,call_stack,line_info,start_ns,end_ns) in cur:
        start_ns = start_ns or 0
        end_ns = end_ns if end_ns is not None else start_ns
        duration = calc_duration(start_ns, end_ns, duration)
        cat_lc = (category or '').lower()
        start_id, end_id = 12,13  # default hip_runtime pair
        for key,(sid,eid) in REGION_CATEGORY_MAP:
            if key in cat_lc:
                start_id,end_id = sid,eid; break
        # Store tuples: (timestamp, (type, eid, args...))
        out_events.append((int(start_ns), ('region', start_id, region_id, guid, name, category, nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata, call_stack, line_info)))
        count += 1
        if progress_cb: progress_cb(1);
        if end_id is not None:
            out_events.append((int(end_ns), ('region', end_id, region_id, guid, name, category, nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata, call_stack, line_info)))
            count += 1
            if progress_cb: progress_cb(1)
    return count

def collect_kernel_dispatch(conn: sqlite3.Connection, out_events: List[Tuple[int, Tuple]], progress_cb: Optional[Callable[[int], None]] = None) -> int:
    if not hasattr(lib,'rocpd_trace_kernel_dispatch'): return 0
    if 'kernels' not in list_views(conn): return 0
    cur = conn.cursor()
    cur.execute("""SELECT id,guid,tid,category,region,name,nid,pid,
                        agent_abs_index,agent_log_index,agent_type_index,agent_type,
                        code_object_id,kernel_id,dispatch_id,stream_id,queue_id,
                        queue,stream,start,end,duration,
                        grid_x,grid_y,grid_z,workgroup_x,workgroup_y,workgroup_z,
                        lds_size,scratch_size,static_lds_size,static_scratch_size,
                        stack_id,parent_stack_id,corr_id FROM kernels""")
    count=0
    for r in cur.fetchall():
        (kid,guid,tid,category,region,name,nid,pid,a_abs,a_log,a_type_idx,a_type,
         code_obj,kernel_sym,dispatch_id,stream_id,queue_id,queue_name,stream_name,
         start_ns,end_ns,duration,grid_x,grid_y,grid_z,wgx,wgy,wgz,lds_size,scratch_size,
         static_lds,static_scratch,stack_id,parent_stack_id,corr_id) = r
        start_ns = start_ns or 0; end_ns = end_ns if end_ns is not None else start_ns
        duration = calc_duration(start_ns,end_ns,duration)
        out_events.append((int(start_ns), ('kernel', 3, kid,guid,tid,category,region,name,nid,pid,a_abs,a_log,a_type_idx,a_type,code_obj,kernel_sym,dispatch_id,stream_id,queue_id,queue_name,stream_name,grid_x,grid_y,grid_z,wgx,wgy,wgz,lds_size,scratch_size,static_lds,static_scratch,stack_id,parent_stack_id,corr_id,duration)))
        if progress_cb: progress_cb(1)
        out_events.append((int(end_ns), ('kernel', 4, kid,guid,tid,category,region,name,nid,pid,a_abs,a_log,a_type_idx,a_type,code_obj,kernel_sym,dispatch_id,stream_id,queue_id,queue_name,stream_name,grid_x,grid_y,grid_z,wgx,wgy,wgz,lds_size,scratch_size,static_lds,static_scratch,stack_id,parent_stack_id,corr_id,duration)))
        if progress_cb: progress_cb(1)
        count += 2
    return count

def collect_memcpy_view(conn: sqlite3.Connection, out_events: List[Tuple[int, Tuple]], progress_cb: Optional[Callable[[int], None]] = None) -> int:
    if not hasattr(lib,'rocpd_trace_memory_copy'): return 0
    if 'memory_copies' not in list_views(conn): return 0
    cur = conn.cursor()
    cur.execute("""SELECT id,guid,category,nid,pid,tid,start,end,duration,
                        name,region_name,stream_id,queue_id,stream_name,queue_name,size,
                        dst_device,dst_agent_abs_index,dst_agent_log_index,dst_agent_type_index,dst_agent_type,dst_address,
                        src_device,src_agent_abs_index,src_agent_log_index,src_agent_type_index,src_agent_type,src_address,
                        stack_id,parent_stack_id,corr_id FROM memory_copies""")
    count=0
    for r in cur.fetchall():
        (copy_id,guid,category,nid,pid,tid,start_ns,end_ns,duration,name,region_name,stream_id,queue_id,stream_name,queue_name,size,dst_device,dst_a_abs,dst_a_log,dst_a_type_idx,dst_a_type,dst_addr,
         src_device,src_a_abs,src_a_log,src_a_type_idx,src_a_type,src_addr,stack_id,parent_stack_id,corr_id) = r
        start_ns = start_ns or 0; end_ns = end_ns if (end_ns is not None and end_ns>=start_ns) else start_ns
        duration = calc_duration(start_ns,end_ns,duration)
        out_events.append((int(start_ns), ('memcpy', 6, copy_id,guid,category,nid,pid,tid,name,region_name,stream_id,queue_id,stream_name,queue_name,size,dst_device,dst_a_abs,dst_a_log,dst_a_type_idx,dst_a_type,dst_addr,src_device,src_a_abs,src_a_log,src_a_type_idx,src_a_type,src_addr,stack_id,parent_stack_id,corr_id,duration)))
        if progress_cb: progress_cb(1)
        out_events.append((int(end_ns), ('memcpy', 7, copy_id,guid,category,nid,pid,tid,name,region_name,stream_id,queue_id,stream_name,queue_name,size,dst_device,dst_a_abs,dst_a_log,dst_a_type_idx,dst_a_type,dst_addr,src_device,src_a_abs,src_a_log,src_a_type_idx,src_a_type,src_addr,stack_id,parent_stack_id,corr_id,duration)))
        if progress_cb: progress_cb(1)
        count += 2
    return count

def collect_memalloc_view(conn: sqlite3.Connection, out_events: List[Tuple[int, Tuple]], progress_cb: Optional[Callable[[int], None]] = None) -> int:
    if not hasattr(lib,'rocpd_trace_memory_allocation'): return 0
    if 'memory_allocations' not in list_views(conn): return 0
    cur = conn.cursor()
    cur.execute("""SELECT id,guid,category,nid,pid,tid,type AS allocation_type,level,agent_name,agent_abs_index,agent_log_index,agent_type_index,agent_type,
                        address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,start,end,duration FROM memory_allocations""")
    count=0
    for r in cur.fetchall():
        (alloc_id,guid,category,nid,pid,tid,allocation_type,level,agent_name,a_abs,a_log,a_type_idx,a_type,address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,start_ns,end_ns,duration)=r
        start_ns = start_ns or 0; end_ns = end_ns if end_ns is not None else start_ns
        duration = calc_duration(start_ns,end_ns,duration)
        out_events.append((int(start_ns), ('memalloc', 9, alloc_id,guid,category,nid,pid,tid,allocation_type,level,agent_name,a_abs,a_log,a_type_idx,a_type,address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,duration)))
        if progress_cb: progress_cb(1)
        out_events.append((int(end_ns), ('memalloc', 10, alloc_id,guid,category,nid,pid,tid,allocation_type,level,agent_name,a_abs,a_log,a_type_idx,a_type,address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,duration)))
        if progress_cb: progress_cb(1)
        count += 2
    return count

def collect_counter_collection(conn: sqlite3.Connection, out_events: List[Tuple[int, Tuple]], progress_cb: Optional[Callable[[int], None]] = None) -> int:
    # Optional; only if a counters view exists (name guess based on schema). Single emission (no start/end pair).
    view_names = set(list_views(conn))
    candidate = None
    for name in ('counters_collection','counter_collection','counters'):
        if name in view_names:
            candidate = name; break
    if not candidate or not hasattr(lib,'rocpd_trace_counter_collection'):
        return 0
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT id,guid,dispatch_id,kernel_id,event_id,correlation_id,stack_id,parent_stack_id,pid,tid,agent_id,agent_abs_index,agent_log_index,agent_type_index,agent_type,queue_id,grid_size_x,grid_size_y,grid_size_z,name,kernel_region,workgroup_size_x,workgroup_size_y,workgroup_size_z,lds_block_size,scratch_size,vgpr_count,accum_vgpr_count,sgpr_count,counter_name,counter_symbol,component,description,block,expression,value_type,counter_id,value,start,end,is_constant,is_derived,duration,category,nid,extdata,code_object_id FROM {candidate}")
    except Exception:
        return 0
    count=0
    for row in cur.fetchall():
        (*fields, start_ns, end_ns, is_constant, is_derived, duration, category, nid, extdata, code_object_id) = row
        start_ns = start_ns or 0
        duration = calc_duration(start_ns, end_ns, duration)
        out_events.append((int(start_ns), ('counter', tuple(row[:-3]) + (duration, category, nid, extdata, code_object_id))))
        count += 1
        if progress_cb: progress_cb(1)
    return count

def _parallel_counts(db_path: str, views_present: set) -> dict:
    """Execute COUNT(*) queries in parallel threads (one connection per thread)."""
    queries = {}
    if 'regions' in views_present:
        queries['regions'] = "SELECT COUNT(*) FROM regions"
        queries['marker_core'] = "SELECT COUNT(*) FROM regions WHERE lower(category) LIKE '%marker_core%'"
    if 'kernels' in views_present:
        queries['kernels'] = "SELECT COUNT(*) FROM kernels"
    if 'memory_copies' in views_present:
        queries['memory_copies'] = "SELECT COUNT(*) FROM memory_copies"
    if 'memory_allocations' in views_present:
        queries['memory_allocations'] = "SELECT COUNT(*) FROM memory_allocations"
    for name in ('counters_collection','counter_collection','counters'):
        if name in views_present:
            queries['counters'] = f"SELECT COUNT(*) FROM {name}"
            break
    results = {k:0 for k in queries}
    if not queries:
        return results
    def run_query(item):
        key, sql = item
        try:
            with sqlite3.connect(db_path) as c:
                cur = c.execute(sql)
                v = cur.fetchone()
                return key, int(v[0] or 0)
        except Exception:
            return key, 0
    max_workers = min(len(queries), (os.cpu_count() or 4)) or 1
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futs = [exe.submit(run_query, kv) for kv in queries.items()]
        for f in as_completed(futs):
            k,v = f.result()
            results[k]=v
    return results

def _emit_event(ev: Tuple, ts: int):
    etype = ev[0]
    ts_u64 = ctypes.c_uint64(to_u64(ts))
    if etype == 'region':
        (_t, eid, region_id, guid, name, category, nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata, call_stack, line_info) = ev
        lib.rocpd_trace_region(ctypes.c_uint16(eid), ctypes.c_int64(region_id or 0), ctypes.c_char_p(b(guid)), ctypes.c_char_p(b(name)), ctypes.c_char_p(b(category)), ctypes.c_int64(nid or 0), ctypes.c_int64(pid or 0), ctypes.c_int64(tid or 0), ctypes.c_int64(event_internal_id or 0), ctypes.c_int64(stack_id or 0), ctypes.c_int64(parent_stack_id or 0), ctypes.c_int64(correlation_id or 0), ctypes.c_int64(duration or 0), ctypes.c_char_p(b(extdata)), ctypes.c_char_p(b(call_stack)), ctypes.c_char_p(b(line_info)), ts_u64)
    elif etype == 'kernel':
        (_t, eid, kid,guid,tid,category,region,name,nid,pid,a_abs,a_log,a_type_idx,a_type,code_obj,kernel_sym,dispatch_id,stream_id,queue_id,queue_name,stream_name,grid_x,grid_y,grid_z,wgx,wgy,wgz,lds_size,scratch_size,static_lds,static_scratch,stack_id,parent_stack_id,corr_id,duration) = ev
        lib.rocpd_trace_kernel_dispatch(ctypes.c_uint16(eid), ctypes.c_int64(kid or 0), ctypes.c_char_p(b(guid)), ctypes.c_int64(tid or 0), ctypes.c_char_p(b(category or '')), ctypes.c_char_p(b(region or '')), ctypes.c_char_p(b(name or 'kernel')), ctypes.c_int64(nid or 0), ctypes.c_int64(pid or 0), ctypes.c_int64(a_abs or 0), ctypes.c_int64(a_log or 0), ctypes.c_int64(a_type_idx or 0), ctypes.c_char_p(b(a_type or '')), ctypes.c_int64(code_obj or 0), ctypes.c_int64(kernel_sym or 0), ctypes.c_int64(dispatch_id or 0), ctypes.c_int64(stream_id or 0), ctypes.c_int64(queue_id or 0), ctypes.c_char_p(b(queue_name or '')), ctypes.c_char_p(b(stream_name or '')), ctypes.c_int64(grid_x or 0), ctypes.c_int64(grid_y or 0), ctypes.c_int64(grid_z or 0), ctypes.c_int64(wgx or 0), ctypes.c_int64(wgy or 0), ctypes.c_int64(wgz or 0), ctypes.c_int64(lds_size or 0), ctypes.c_int64(scratch_size or 0), ctypes.c_int64(static_lds or 0), ctypes.c_int64(static_scratch or 0), ctypes.c_int64(stack_id or 0), ctypes.c_int64(parent_stack_id or 0), ctypes.c_int64(corr_id or 0), ctypes.c_int64(duration or 0), ts_u64)
    elif etype == 'memcpy':
        (_t, eid, copy_id,guid,category,nid,pid,tid,name,region_name,stream_id,queue_id,stream_name,queue_name,size,dst_device,dst_a_abs,dst_a_log,dst_a_type_idx,dst_a_type,dst_addr,src_device,src_a_abs,src_a_log,src_a_type_idx,src_a_type,src_addr,stack_id,parent_stack_id,corr_id,duration) = ev
        lib.rocpd_trace_memory_copy(ctypes.c_uint16(eid), ctypes.c_int64(copy_id or 0), ctypes.c_char_p(b(guid)), ctypes.c_char_p(b(category or '')), ctypes.c_int64(nid or 0), ctypes.c_int64(pid or 0), ctypes.c_int64(tid or 0), ctypes.c_char_p(b(name or 'memcpy')), ctypes.c_char_p(b(region_name or '')), ctypes.c_int64(stream_id or 0), ctypes.c_int64(queue_id or 0), ctypes.c_char_p(b(stream_name or '')), ctypes.c_char_p(b(queue_name or '')), ctypes.c_int64(size or 0), ctypes.c_char_p(b(dst_device or '')), ctypes.c_int64(dst_a_abs or 0), ctypes.c_int64(dst_a_log or 0), ctypes.c_int64(dst_a_type_idx or 0), ctypes.c_char_p(b(dst_a_type or '')), ctypes.c_int64(dst_addr or 0), ctypes.c_char_p(b(src_device or '')), ctypes.c_int64(src_a_abs or 0), ctypes.c_int64(src_a_log or 0), ctypes.c_int64(src_a_type_idx or 0), ctypes.c_char_p(b(src_a_type or '')), ctypes.c_int64(src_addr or 0), ctypes.c_int64(stack_id or 0), ctypes.c_int64(parent_stack_id or 0), ctypes.c_int64(corr_id or 0), ctypes.c_int64(duration or 0), ts_u64)
    elif etype == 'memalloc':
        (_t, eid, alloc_id,guid,category,nid,pid,tid,allocation_type,level,agent_name,a_abs,a_log,a_type_idx,a_type,address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,duration) = ev
        lib.rocpd_trace_memory_allocation(ctypes.c_uint16(eid), ctypes.c_int64(alloc_id or 0), ctypes.c_char_p(b(guid)), ctypes.c_char_p(b(category or '')), ctypes.c_int64(nid or 0), ctypes.c_int64(pid or 0), ctypes.c_int64(tid or 0), ctypes.c_char_p(b(allocation_type or '')), ctypes.c_char_p(b(level or '')), ctypes.c_char_p(b(agent_name or '')), ctypes.c_int64(a_abs or 0), ctypes.c_int64(a_log or 0), ctypes.c_int64(a_type_idx or 0), ctypes.c_char_p(b(a_type or '')), ctypes.c_int64(address or 0), ctypes.c_int64(size or 0), ctypes.c_int64(queue_id or 0), ctypes.c_char_p(b(queue_name or '')), ctypes.c_int64(stream_id or 0), ctypes.c_char_p(b(stream_name or '')), ctypes.c_int64(stack_id or 0), ctypes.c_int64(parent_stack_id or 0), ctypes.c_int64(corr_id or 0), ctypes.c_int64(duration or 0), ts_u64)
    elif etype == 'counter':
        # Not yet emitting counters (pending full mapping of fields to bridge function)
        pass

def _progress_printer(total: int, enabled: bool, label: str = "", *, incremental: bool=False, thread_safe: bool=False):
    if not enabled or total == 0:
        def noop(_):
            pass
        return noop, (lambda: None)

    bar_width = 40
    last_printed = {'pct': -1}
    current = {'done': 0}
    lock = threading.Lock() if thread_safe else None

    def _render():
        done = current['done']
        pct = int(done * 100 / total) if total else 100
        if pct == last_printed['pct']:
            return
        last_printed['pct'] = pct
        filled = int(bar_width * pct / 100)
        bar = '#' * filled + '-' * (bar_width - filled)
        prefix = f"{label} " if label else ""
        sys.stderr.write(f"\r{prefix}[{bar}] {pct:3d}% ({done}/{total})")
        sys.stderr.flush()

    def update(val: int):
        if total <= 0:
            return
        if lock: lock.acquire()
        try:
            if incremental:
                current['done'] += val
            else:
                current['done'] = val
            if current['done'] > total:
                current['done'] = total
            _render()
        finally:
            if lock: lock.release()

    def finish():
        if lock: lock.acquire()
        try:
            current['done'] = total
            _render()
            sys.stderr.write('\n')
            sys.stderr.flush()
        finally:
            if lock: lock.release()

    return update, finish

def emit_events(events: List[Tuple[int, Tuple]], *, debug: bool=False, debug_n: int=5, sort_events: bool=True, split_on_decrease: bool=False, base_stream_path: pathlib.Path=None, packet_bytes: int=262144, show_progress: bool=True) -> int:
    if not events:
        return 0
    if sort_events:
        events.sort(key=lambda x: x[0])
    first_ts_global = events[0][0]
    total = 0
    segment_idx = 0
    prev_ts = None

    def open_stream(idx: int):
        stream_file = base_stream_path if idx == 0 else base_stream_path.parent / f"{base_stream_path.name}_{idx}"
        rc = lib.rocpd_init(os.fspath(stream_file).encode(), ctypes.c_uint32(packet_bytes))
        if rc != 0:
            raise SystemError(f'rocpd_init failed for segment {idx} ({rc})')
        return stream_file

    def close_stream():
        lib.rocpd_close()

    open_stream(segment_idx)
    progress_update, progress_finish = _progress_printer(len(events), show_progress, label="Emit", incremental=True)
    try:
        for ts, payload in events:
            # Split if requested and time goes backwards
            if split_on_decrease and prev_ts is not None and ts < prev_ts:
                close_stream()
                segment_idx += 1
                open_stream(segment_idx)
            adj_ts = ts
            _emit_event(payload, adj_ts)
            prev_ts = ts
            total += 1
            progress_update(1)
    finally:
        close_stream()
        progress_finish()

    if debug:
        last_ts = events[-1][0]
        sample = events[:debug_n]
        print(f"[debug] total_events={total} first_ts={first_ts_global} last_ts={last_ts} segments={segment_idx+1} sample={[ (t,p[0]) for t,p in sample ]}")
    return total

# --- Streaming (low-memory) path helpers ---

def _iter_regions(conn: sqlite3.Connection, chunk: int):
    if 'regions' not in list_views(conn):
        return
    cur = conn.cursor(); cur.execute("SELECT id AS region_id,guid,name,category,nid,pid,tid,event_id,stack_id,parent_stack_id,corr_id AS correlation_id,duration,extdata,call_stack,line_info,start,end FROM regions")
    while True:
        rows = cur.fetchmany(chunk)
        if not rows: break
        for (region_id,guid,name,category,nid,pid,tid,event_internal_id,stack_id,parent_stack_id,correlation_id,duration,extdata,call_stack,line_info,start_ns,end_ns) in rows:
            start_ns = start_ns or 0
            end_ns = end_ns if end_ns is not None else start_ns
            duration2 = calc_duration(start_ns,end_ns,duration)
            cat_lc = (category or '').lower(); start_id,end_id = 12,13
            for key,(sid,eid) in REGION_CATEGORY_MAP:
                if key in cat_lc: start_id,end_id = sid,eid; break
            yield int(start_ns), ('region', start_id, region_id, guid, name, category, nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration2, extdata, call_stack, line_info)
            if end_id is not None:
                yield int(end_ns), ('region', end_id, region_id, guid, name, category, nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration2, extdata, call_stack, line_info)

def _iter_kernels(conn: sqlite3.Connection, chunk: int):
    if not hasattr(lib,'rocpd_trace_kernel_dispatch') or 'kernels' not in list_views(conn): return
    cur = conn.cursor(); cur.execute("""SELECT id,guid,tid,category,region,name,nid,pid,
                        agent_abs_index,agent_log_index,agent_type_index,agent_type,
                        code_object_id,kernel_id,dispatch_id,stream_id,queue_id,
                        queue,stream,start,end,duration,
                        grid_x,grid_y,grid_z,workgroup_x,workgroup_y,workgroup_z,
                        lds_size,scratch_size,static_lds_size,static_scratch_size,
                        stack_id,parent_stack_id,corr_id FROM kernels""")
    while True:
        rows = cur.fetchmany(chunk)
        if not rows: break
        for r in rows:
            (kid,guid,tid,category,region,name,nid,pid,a_abs,a_log,a_type_idx,a_type,
             code_obj,kernel_sym,dispatch_id,stream_id,queue_id,queue_name,stream_name,
             start_ns,end_ns,duration,grid_x,grid_y,grid_z,wgx,wgy,wgz,lds_size,scratch_size,
             static_lds,static_scratch,stack_id,parent_stack_id,corr_id) = r
            start_ns = start_ns or 0; end_ns = end_ns if end_ns is not None else start_ns
            duration2 = calc_duration(start_ns,end_ns,duration)
            yield int(start_ns), ('kernel', 3, kid,guid,tid,category,region,name,nid,pid,a_abs,a_log,a_type_idx,a_type,code_obj,kernel_sym,dispatch_id,stream_id,queue_id,queue_name,stream_name,grid_x,grid_y,grid_z,wgx,wgy,wgz,lds_size,scratch_size,static_lds,static_scratch,stack_id,parent_stack_id,corr_id,duration2)
            yield int(end_ns), ('kernel', 4, kid,guid,tid,category,region,name,nid,pid,a_abs,a_log,a_type_idx,a_type,code_obj,kernel_sym,dispatch_id,stream_id,queue_id,queue_name,stream_name,grid_x,grid_y,grid_z,wgx,wgy,wgz,lds_size,scratch_size,static_lds,static_scratch,stack_id,parent_stack_id,corr_id,duration2)

def _iter_memcpy(conn: sqlite3.Connection, chunk: int):
    if not hasattr(lib,'rocpd_trace_memory_copy') or 'memory_copies' not in list_views(conn): return
    cur = conn.cursor(); cur.execute("""SELECT id,guid,category,nid,pid,tid,start,end,duration,
                        name,region_name,stream_id,queue_id,stream_name,queue_name,size,
                        dst_device,dst_agent_abs_index,dst_agent_log_index,dst_agent_type_index,dst_agent_type,dst_address,
                        src_device,src_agent_abs_index,src_agent_log_index,src_agent_type_index,src_agent_type,src_address,
                        stack_id,parent_stack_id,corr_id FROM memory_copies""")
    while True:
        rows = cur.fetchmany(chunk)
        if not rows: break
        for r in rows:
            (copy_id,guid,category,nid,pid,tid,start_ns,end_ns,duration,name,region_name,stream_id,queue_id,stream_name,queue_name,size,dst_device,dst_a_abs,dst_a_log,dst_a_type_idx,dst_a_type,dst_addr,
             src_device,src_a_abs,src_a_log,src_a_type_idx,src_a_type,src_addr,stack_id,parent_stack_id,corr_id) = r
            start_ns = start_ns or 0; end_ns = end_ns if (end_ns is not None and end_ns>=start_ns) else start_ns
            duration2 = calc_duration(start_ns,end_ns,duration)
            yield int(start_ns), ('memcpy', 6, copy_id,guid,category,nid,pid,tid,name,region_name,stream_id,queue_id,stream_name,queue_name,size,dst_device,dst_a_abs,dst_a_log,dst_a_type_idx,dst_a_type,dst_addr,src_device,src_a_abs,src_a_log,src_a_type_idx,src_a_type,src_addr,stack_id,parent_stack_id,corr_id,duration2)
            yield int(end_ns), ('memcpy', 7, copy_id,guid,category,nid,pid,tid,name,region_name,stream_id,queue_id,stream_name,queue_name,size,dst_device,dst_a_abs,dst_a_log,dst_a_type_idx,dst_a_type,dst_addr,src_device,src_a_abs,src_a_log,src_a_type_idx,src_a_type,src_addr,stack_id,parent_stack_id,corr_id,duration2)

def _iter_memalloc(conn: sqlite3.Connection, chunk: int):
    if not hasattr(lib,'rocpd_trace_memory_allocation') or 'memory_allocations' not in list_views(conn): return
    cur = conn.cursor(); cur.execute("""SELECT id,guid,category,nid,pid,tid,type AS allocation_type,level,agent_name,agent_abs_index,agent_log_index,agent_type_index,agent_type,
                        address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,start,end,duration FROM memory_allocations""")
    while True:
        rows = cur.fetchmany(chunk)
        if not rows: break
        for r in rows:
            (alloc_id,guid,category,nid,pid,tid,allocation_type,level,agent_name,a_abs,a_log,a_type_idx,a_type,address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,start_ns,end_ns,duration)=r
            start_ns = start_ns or 0; end_ns = end_ns if end_ns is not None else start_ns
            duration2 = calc_duration(start_ns,end_ns,duration)
            yield int(start_ns), ('memalloc', 9, alloc_id,guid,category,nid,pid,tid,allocation_type,level,agent_name,a_abs,a_log,a_type_idx,a_type,address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,duration2)
            yield int(end_ns), ('memalloc', 10, alloc_id,guid,category,nid,pid,tid,allocation_type,level,agent_name,a_abs,a_log,a_type_idx,a_type,address,size,queue_id,queue_name,stream_id,stream_name,stack_id,parent_stack_id,corr_id,duration2)

def _iter_counters(conn: sqlite3.Connection, chunk: int):
    view_names = set(list_views(conn))
    candidate=None
    for name in ('counters_collection','counter_collection','counters'):
        if name in view_names: candidate=name; break
    if not candidate or not hasattr(lib,'rocpd_trace_counter_collection'): return
    cur = conn.cursor();
    try:
        cur.execute(f"SELECT id,guid,dispatch_id,kernel_id,event_id,correlation_id,stack_id,parent_stack_id,pid,tid,agent_id,agent_abs_index,agent_log_index,agent_type_index,agent_type,queue_id,grid_size_x,grid_size_y,grid_size_z,name,kernel_region,workgroup_size_x,workgroup_size_y,workgroup_size_z,lds_block_size,scratch_size,vgpr_count,accum_vgpr_count,sgpr_count,counter_name,counter_symbol,component,description,block,expression,value_type,counter_id,value,start,end,is_constant,is_derived,duration,category,nid,extdata,code_object_id FROM {candidate}")
    except Exception:
        return
    while True:
        rows = cur.fetchmany(chunk)
        if not rows: break
        for row in rows:
            (*fields, start_ns, end_ns, is_constant, is_derived, duration, category, nid, extdata, code_object_id) = row
            start_ns = start_ns or 0
            duration2 = calc_duration(start_ns, end_ns, duration)
            yield int(start_ns), ('counter', tuple(row[:-3]) + (duration2, category, nid, extdata, code_object_id))

def streaming_emit(db_path: str, *, base_stream_path: pathlib.Path, packet_bytes: int, sort_events: bool, split_on_decrease: bool, show_progress: bool, expected_total: int, fetch_chunk: int, debug: bool=False, debug_n: int=5) -> int:
    conn = sqlite3.connect(db_path)
    views_present = set(list_views(conn))
    iterators = []
    if 'regions' in views_present: iterators.append(_iter_regions(conn, fetch_chunk))
    if 'kernels' in views_present: iterators.append(_iter_kernels(conn, fetch_chunk))
    if 'memory_copies' in views_present: iterators.append(_iter_memcpy(conn, fetch_chunk))
    if 'memory_allocations' in views_present: iterators.append(_iter_memalloc(conn, fetch_chunk))
    # counters last
    it_cnt = _iter_counters(conn, fetch_chunk)
    if it_cnt: iterators.append(it_cnt)

    total_emitted = 0
    prev_ts = None
    segment_idx = 0
    lib.rocpd_init(os.fspath(base_stream_path).encode(), ctypes.c_uint32(packet_bytes))
    progress_update, progress_finish = _progress_printer(expected_total, show_progress, label="Stream", incremental=True)
    try:
        if not sort_events:
            for it in iterators:
                for ts, payload in it:
                    if split_on_decrease and prev_ts is not None and ts < prev_ts:
                        lib.rocpd_close(); segment_idx += 1
                        lib.rocpd_init(os.fspath(base_stream_path.parent / f"{base_stream_path.name}_{segment_idx}").encode(), ctypes.c_uint32(packet_bytes))
                    _emit_event(payload, ts)
                    prev_ts = ts; total_emitted += 1; progress_update(1)
        else:
            # heap merge
            heap = []
            counter = itertools.count()
            # Prime
            for it in iterators:
                try:
                    first = next(it)
                except StopIteration:
                    continue
                heapq.heappush(heap, (first[0], next(counter), first[1], it))
            while heap:
                ts, _seq, payload, it = heapq.heappop(heap)
                if split_on_decrease and prev_ts is not None and ts < prev_ts:
                    lib.rocpd_close(); segment_idx += 1
                    lib.rocpd_init(os.fspath(base_stream_path.parent / f"{base_stream_path.name}_{segment_idx}").encode(), ctypes.c_uint32(packet_bytes))
                _emit_event(payload, ts)
                prev_ts = ts; total_emitted += 1; progress_update(1)
                try:
                    nxt = next(it)
                    heapq.heappush(heap, (nxt[0], next(counter), nxt[1], it))
                except StopIteration:
                    pass
    finally:
        lib.rocpd_close(); progress_finish(); conn.close()
    if debug:
        print(f"[debug] streaming total_events={total_emitted} segments={segment_idx+1}")
    return total_emitted

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--packet-bytes', type=int, default=262144)
    ap.add_argument('--metadata-src', default=str(THIS_DIR / 'gen' / 'metadata'))
    ap.add_argument('--stream-name', default='stream')
    ap.add_argument('--debug', action='store_true', help='Print debug info about timestamps and ordering')
    ap.add_argument('--no-sort', action='store_true', help='Do not sort events; emit in collection order (use with --split-on-decrease)')
    ap.add_argument('--split-on-decrease', action='store_true', help='Start a new stream file when a timestamp decreases (implies potential non-monotonic DB order)')
    ap.add_argument('--no-progress', action='store_true', help='Disable progress bar output')
    ap.add_argument('--collect-threads', type=int, default=1, help='Number of threads to use for collection (per view)')
    ap.add_argument('--streaming', action='store_true', help='Low-memory streaming mode (no full in-memory event list)')
    ap.add_argument('--fetch-chunk', type=int, default=2048, help='Row batch size for streaming mode fetchmany()')
    args = ap.parse_args()

    print("Preparing for Conversion...")

    out_dir = pathlib.Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    # Copy metadata first
    try:
        src = pathlib.Path(args.metadata_src); dst = out_dir / 'metadata'
        if src.is_file():
            if not dst.exists() or src.read_bytes() != dst.read_bytes():
                shutil.copy2(src,dst)
    except Exception as e:
        print(f"Warning: metadata copy failed: {e}")

    stream_path = out_dir / args.stream_name
    events: List[Tuple[int, Tuple]] = []  # only used in non-streaming mode
    # Precompute expected total events using parallel COUNT(*) queries
    expected_total = 0
    try:
        conn = sqlite3.connect(args.db)
        with conn:
            views_present = set(list_views(conn))
            counts = _parallel_counts(args.db, views_present)
            reg_count = counts.get('regions',0)
            marker_only = counts.get('marker_core',0)
            expected_total += reg_count * 2 - marker_only
            expected_total += counts.get('kernels',0) * 2
            expected_total += counts.get('memory_copies',0) * 2
            expected_total += counts.get('memory_allocations',0) * 2
            expected_total += counts.get('counters',0)

            print("Finished Preparation Step!")
            print("Collecting Events from ROCpd Database...")

            if args.streaming:
                # Streaming path: collection+emission combined after we exit 'with conn'
                pass
            else:
                collect_threads = max(1, args.collect_threads)
                if collect_threads == 1:
                    collect_progress_update, collect_progress_finish = _progress_printer(expected_total, not args.no_progress, label="Collect", incremental=True)
                    collect_regions(conn, events, collect_progress_update)
                    collect_kernel_dispatch(conn, events, collect_progress_update)
                    collect_memcpy_view(conn, events, collect_progress_update)
                    collect_memalloc_view(conn, events, collect_progress_update)
                    collect_counter_collection(conn, events, collect_progress_update)
                    collect_progress_finish()
                else:
                    collect_progress_update, collect_progress_finish = _progress_printer(expected_total, not args.no_progress, label="Collect", incremental=True, thread_safe=True)
                    tasks = []
                    def task_wrapper(view_name, func):
                        local_events: List[Tuple[int, Tuple]] = []
                        try:
                            with sqlite3.connect(args.db) as c2:
                                func(c2, local_events, collect_progress_update)
                        except Exception:
                            pass
                        return local_events
                    if 'regions' in views_present: tasks.append(('regions', collect_regions))
                    if 'kernels' in views_present: tasks.append(('kernels', collect_kernel_dispatch))
                    if 'memory_copies' in views_present: tasks.append(('memory_copies', collect_memcpy_view))
                    if 'memory_allocations' in views_present: tasks.append(('memory_allocations', collect_memalloc_view))
                    for name in ('counters_collection','counter_collection','counters'):
                        if name in views_present: tasks.append((name, collect_counter_collection)); break
                    with ThreadPoolExecutor(max_workers=min(collect_threads, len(tasks))) as exe:
                        futures = [exe.submit(task_wrapper, n, f) for n,f in tasks]
                        for fut in futures: events.extend(fut.result())
                    collect_progress_finish()

                    print("Finished Collection Step!")

        print("Emitting Events to CTF Trace...")
        if args.streaming:
            total = streaming_emit(
                args.db,
                base_stream_path=stream_path,
                packet_bytes=args.packet_bytes,
                sort_events=not args.no_sort,
                split_on_decrease=args.split_on_decrease,
                show_progress=not args.no_progress,
                expected_total=expected_total,
                fetch_chunk=args.fetch_chunk,
                debug=args.debug,
                debug_n=5,
            )
        else:
            total = emit_events(
                events,
                debug=args.debug,
                sort_events=not args.no_sort,
                split_on_decrease=args.split_on_decrease,
                base_stream_path=stream_path,
                packet_bytes=args.packet_bytes,
                show_progress=not args.no_progress,
            )
    finally:
        # Ensure closed if an exception occurred before internal emitter closed.
        try:
            lib.rocpd_close()
        except Exception:
            pass
    mode_desc = []
    if args.no_sort: mode_desc.append('original-order')
    else: mode_desc.append('sorted')
    if args.split_on_decrease: mode_desc.append('split-on-decrease')
    print(f"Emitted {total} events to {args.out} ({', '.join(mode_desc)})")

if __name__ == '__main__':
    main()
