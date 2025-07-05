#!/usr/bin/env python3
"""
Simplified Enhanced ROCm Babeltrace2 plugin with single output port.
"""
from typing import Dict, List, Optional, Any, Iterator, Set
from dataclasses import dataclass
import sqlite3
import os

# Import babeltrace2 library
import bt2

# Register the plugin
bt2.register_plugin(__name__, "rocm")

# ROCm profiler categories from rocprofiler-sdk (enhanced with full list)
ROCM_CATEGORIES = {
    'HSA_CORE_API': 'HSA Core API',
    'HSA_AMD_EXT_API': 'HSA AMD Extension API',
    'HSA_IMAGE_EXT_API': 'HSA Image Extension API',
    'HSA_FINALIZE_EXT_API': 'HSA Finalize Extension API',
    'HIP_RUNTIME_API': 'HIP Runtime API',
    'HIP_RUNTIME_API_EXT': 'HIP Runtime API Extended',
    'HIP_COMPILER_API': 'HIP Compiler API',
    'HIP_COMPILER_API_EXT': 'HIP Compiler API Extended',
    'MARKER_CORE_API': 'Marker Core API',
    'MARKER_CONTROL_API': 'Marker Control API',
    'MARKER_NAME_API': 'Marker Name API',
    'MEMORY_COPY': 'Memory Copy',
    'MEMORY_ALLOCATION': 'Memory Allocation',
    'KERNEL_DISPATCH': 'Kernel Dispatch',
    'SCRATCH_MEMORY': 'Scratch Memory',
    'CORRELATION_ID_RETIREMENT': 'Correlation ID Retirement',
    'RCCL_API': 'RCCL API',
    'OMPT': 'OpenMP Tools',
    'RUNTIME_INITIALIZATION': 'Runtime Initialization',
    'ROCDECODE_API': 'ROCDecode API',
    'ROCDECODE_API_EXT': 'ROCDecode API Extended',
    'ROCJPEG_API': 'ROCJPEG API',
    'HIP_STREAM': 'HIP Stream',
    'KFD_EVENT_PAGE_MIGRATE': 'KFD Event Page Migrate',
    'KFD_EVENT_PAGE_FAULT': 'KFD Event Page Fault',
    'KFD_EVENT_QUEUE': 'KFD Event Queue',
    'KFD_EVENT_UNMAP_FROM_GPU': 'KFD Event Unmap From GPU',
    'KFD_EVENT_DROPPED_EVENTS': 'KFD Event Dropped Events',
    'KFD_PAGE_MIGRATE': 'KFD Page Migrate',
    'KFD_PAGE_FAULT': 'KFD Page Fault',
    'KFD_QUEUE': 'KFD Queue'
}

@dataclass
class RocmEventData:
    """Data class for ROCm event information."""
    name: str
    timestamp: int
    duration: Optional[int] = None
    category: Optional[str] = None
    pid: Optional[int] = None
    tid: Optional[int] = None
    agent_id: Optional[int] = None
    queue_id: Optional[int] = None
    stream_id: Optional[int] = None
    channel_id: Optional[str] = None
    event_args: Optional[Dict[str, Any]] = None


class RocmSourceIterator(bt2._UserMessageIterator):
    """Iterator for the ROCm source component."""
    
    def __init__(self, config, output_port):
        """Initialize the iterator."""
        self._db_path = output_port.user_data['db_path']
        self._trace_class = output_port.user_data['trace_class']
        self._stream_classes = output_port.user_data['stream_classes']
        self._event_classes = output_port.user_data['event_classes']
        self._clock_class = output_port.user_data['clock_class']
        
        # Create trace and stream instances
        self._trace = self._trace_class()
        
        # Create streams for different categories/channels
        self._streams = {}
        self._channels = {}
        
        # Initialize database connection
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        
        # State management
        self._state = "stream_beginning"
        self._current_events = []
        self._event_index = 0
        self._sent_stream_beginning = set()
        self._current_stream = None
        
        # Get database UUID and GUID for table names
        self._uuid, self._guid = self._get_db_metadata()
        
        # Load all events
        self._load_events()
    
    def _get_db_metadata(self) -> tuple:
        """Get UUID and GUID from database metadata."""
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rocpd_%_%'")
            tables = cursor.fetchall()
            if tables:
                table_name = tables[0][0]
                uuid = table_name.split('_', 2)[-1]
                return uuid, uuid
        except sqlite3.Error:
            pass
        return '0000b6ad_2bac_7bac_82e7_5f0563eafa7f', '0000b6ad_2bac_7bac_82e7_5f0563eafa7f'
    
    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            return cursor.fetchone() is not None
        except sqlite3.Error:
            return False
    
    def _get_channel_id(self, event_data: RocmEventData) -> str:
        """Get channel ID based on category, thread_id, queue_id, or stream_id."""
        category = event_data.category or 'unknown'
        
        if event_data.tid is not None:
            return f"{category}_thread_{event_data.tid}"
        elif event_data.queue_id is not None:
            return f"{category}_queue_{event_data.queue_id}"
        elif event_data.stream_id is not None:
            return f"{category}_stream_{event_data.stream_id}"
        else:
            return f"{category}_default_{event_data.pid or 0}"
    
    def _get_or_create_stream(self, event_data: RocmEventData):
        """Get or create a stream for the given event data."""
        channel_id = self._get_channel_id(event_data)
        
        if channel_id not in self._streams:
            # Use the default stream class for all streams
            stream_class = self._stream_classes['default']
            
            # Create the stream
            stream = self._trace.create_stream(stream_class)
            self._streams[channel_id] = stream
            
            # Store channel info
            self._channels[channel_id] = {
                'category': event_data.category,
                'channel_id': channel_id,
                'tid': event_data.tid,
                'queue_id': event_data.queue_id,
                'stream_id': event_data.stream_id
            }
        
        return self._streams[channel_id]
    
    def _load_events(self):
        """Load all events from the database."""
        self._current_events = []
        
        # Load different types of events
        self._load_region_events()
        self._load_kernel_dispatch_events()
        self._load_memory_copy_events()
        self._load_memory_allocation_events()
        
        # Sort events by timestamp
        self._current_events.sort(key=lambda x: x.timestamp)
        
        print(f"Loaded {len(self._current_events)} events from database")
    
    def _load_region_events(self):
        """Load region events from the database."""
        try:
            cursor = self._conn.cursor()
            
            query = f"""
            SELECT 
                r.start, r.end, r.nid, r.pid, r.tid,
                s1.string as region_name,
                COALESCE(s2.string, 'unknown') as category,
                COALESCE(p.command, 'unknown') as process_name,
                COALESCE(t.name, 'unknown') as thread_name,
                r.extdata,
                e.correlation_id,
                e.call_stack,
                e.line_info
            FROM rocpd_region r
            JOIN rocpd_string s1 ON r.name_id = s1.id
            LEFT JOIN rocpd_event e ON r.event_id = e.id
            LEFT JOIN rocpd_string s2 ON e.category_id = s2.id
            LEFT JOIN rocpd_info_process p ON r.pid = p.id
            LEFT JOIN rocpd_info_thread t ON r.tid = t.id
            ORDER BY r.start
            """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                category = row['category']
                duration = row['end'] - row['start']
                
                # Create comprehensive event args
                common_args = {
                    'region_name': row['region_name'],
                    'category': category,
                    'process_name': row['process_name'],
                    'thread_name': row['thread_name'],
                    'pid': row['pid'],
                    'tid': row['tid'],
                    'nid': row['nid'],
                    'correlation_id': row['correlation_id'] or 0,
                    'extdata': row['extdata'] or '{}',
                    'call_stack': row['call_stack'] or '{}',
                    'line_info': row['line_info'] or '{}'
                }
                
                # Region start event
                start_args = common_args.copy()
                start_args.update({
                    'event_type': 'region_start',
                    'duration': 0
                })
                
                self._current_events.append(RocmEventData(
                    name=f"{row['region_name']}_start",
                    timestamp=row['start'],
                    category=category,
                    pid=row['pid'],
                    tid=row['tid'],
                    event_args=start_args
                ))
                
                # Region end event
                end_args = common_args.copy()
                end_args.update({
                    'event_type': 'region_end',
                    'duration': duration
                })
                
                self._current_events.append(RocmEventData(
                    name=f"{row['region_name']}_end",
                    timestamp=row['end'],
                    category=category,
                    pid=row['pid'],
                    tid=row['tid'],
                    event_args=end_args
                ))
                
        except sqlite3.Error as e:
            print(f"Error loading region events: {e}")
    
    def _load_kernel_dispatch_events(self):
        """Load kernel dispatch events from the database."""
        try:
            cursor = self._conn.cursor()
            
            query = f"""
            SELECT 
                k.start, k.end, k.nid, k.pid, k.tid, k.agent_id,
                k.dispatch_id, k.queue_id, k.stream_id,
                k.workgroup_size_x, k.workgroup_size_y, k.workgroup_size_z,
                k.grid_size_x, k.grid_size_y, k.grid_size_z,
                ks.kernel_name, ks.display_name,
                'KERNEL_DISPATCH' as category
            FROM rocpd_kernel_dispatch k
            JOIN rocpd_info_kernel_symbol ks ON k.kernel_id = ks.id
            ORDER BY k.start
            """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                kernel_name = row['kernel_name'] or row['display_name'] or 'unknown_kernel'
                
                # Kernel dispatch start event
                self._current_events.append(RocmEventData(
                    name=f"kernel_dispatch_start",
                    timestamp=row['start'],
                    category='KERNEL_DISPATCH',
                    pid=row['pid'],
                    tid=row['tid'],
                    agent_id=row['agent_id'],
                    queue_id=row['queue_id'],
                    stream_id=row['stream_id'],
                    event_args={
                        'kernel_name': kernel_name,
                        'dispatch_id': row['dispatch_id'],
                        'queue_id': row['queue_id'] or 0,
                        'stream_id': row['stream_id'] or 0,
                        'workgroup_size': f"{row['workgroup_size_x']}x{row['workgroup_size_y']}x{row['workgroup_size_z']}",
                        'grid_size': f"{row['grid_size_x']}x{row['grid_size_y']}x{row['grid_size_z']}",
                        'event_type': 'kernel_dispatch_start',
                        'duration': 0
                    }
                ))
                
                # Kernel dispatch end event
                self._current_events.append(RocmEventData(
                    name=f"kernel_dispatch_end",
                    timestamp=row['end'],
                    category='KERNEL_DISPATCH',
                    pid=row['pid'],
                    tid=row['tid'],
                    agent_id=row['agent_id'],
                    queue_id=row['queue_id'],
                    stream_id=row['stream_id'],
                    event_args={
                        'kernel_name': kernel_name,
                        'dispatch_id': row['dispatch_id'],
                        'event_type': 'kernel_dispatch_end',
                        'duration': row['end'] - row['start']
                    }
                ))
                
        except sqlite3.Error as e:
            print(f"Error loading kernel dispatch events: {e}")
    
    def _load_memory_copy_events(self):
        """Load memory copy events from the database."""
        try:
            cursor = self._conn.cursor()
            
            query = f"""
            SELECT 
                m.start, m.end, m.nid, m.pid, m.tid,
                m.size, m.dst_agent_id, m.src_agent_id,
                m.queue_id, m.stream_id,
                s.string as name,
                'MEMORY_COPY' as category
            FROM rocpd_memory_copy m
            JOIN rocpd_string s ON m.name_id = s.id
            ORDER BY m.start
            """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                # Memory copy start event
                self._current_events.append(RocmEventData(
                    name=f"memory_copy_start",
                    timestamp=row['start'],
                    category='MEMORY_COPY',
                    pid=row['pid'],
                    tid=row['tid'],
                    queue_id=row['queue_id'],
                    stream_id=row['stream_id'],
                    event_args={
                        'copy_name': row['name'],
                        'size': row['size'] or 0,
                        'dst_agent_id': row['dst_agent_id'] or 0,
                        'src_agent_id': row['src_agent_id'] or 0,
                        'queue_id': row['queue_id'] or 0,
                        'stream_id': row['stream_id'] or 0,
                        'event_type': 'memory_copy_start',
                        'duration': 0
                    }
                ))
                
                # Memory copy end event
                self._current_events.append(RocmEventData(
                    name=f"memory_copy_end",
                    timestamp=row['end'],
                    category='MEMORY_COPY',
                    pid=row['pid'],
                    tid=row['tid'],
                    queue_id=row['queue_id'],
                    stream_id=row['stream_id'],
                    event_args={
                        'copy_name': row['name'],
                        'size': row['size'] or 0,
                        'event_type': 'memory_copy_end',
                        'duration': row['end'] - row['start']
                    }
                ))
                
        except sqlite3.Error as e:
            print(f"Error loading memory copy events: {e}")
    
    def _load_memory_allocation_events(self):
        """Load memory allocation events from the database."""
        try:
            cursor = self._conn.cursor()
            
            query = f"""
            SELECT 
                m.start, m.end, m.nid, m.pid, m.tid,
                m.size, m.agent_id,
                s.string as name,
                'MEMORY_ALLOCATION' as category
            FROM rocpd_memory_allocate m
            JOIN rocpd_string s ON m.name_id = s.id
            ORDER BY m.start
            """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                # Memory allocation start event
                self._current_events.append(RocmEventData(
                    name=f"memory_allocation_start",
                    timestamp=row['start'],
                    category='MEMORY_ALLOCATION',
                    pid=row['pid'],
                    tid=row['tid'],
                    agent_id=row['agent_id'],
                    event_args={
                        'allocation_name': row['name'],
                        'size': row['size'] or 0,
                        'agent_id': row['agent_id'] or 0,
                        'event_type': 'memory_allocation_start',
                        'duration': 0
                    }
                ))
                
                # Memory allocation end event
                self._current_events.append(RocmEventData(
                    name=f"memory_allocation_end",
                    timestamp=row['end'],
                    category='MEMORY_ALLOCATION',
                    pid=row['pid'],
                    tid=row['tid'],
                    agent_id=row['agent_id'],
                    event_args={
                        'allocation_name': row['name'],
                        'size': row['size'] or 0,
                        'event_type': 'memory_allocation_end',
                        'duration': row['end'] - row['start']
                    }
                ))
                
        except sqlite3.Error as e:
            print(f"Error loading memory allocation events: {e}")
    
    def __next__(self):
        """Return the next message."""
        if self._state == "stream_beginning":
            if self._current_events:
                # Get first event to determine which stream to begin
                first_event = self._current_events[0]
                self._current_stream = self._get_or_create_stream(first_event)
                self._state = "events"
                return self._create_stream_beginning_message(self._current_stream)
            else:
                self._state = "done"
                raise StopIteration
        
        elif self._state == "events":
            if self._event_index < len(self._current_events):
                event_data = self._current_events[self._event_index]
                self._event_index += 1
                
                # Get or create stream for this event
                stream = self._get_or_create_stream(event_data)
                
                # If this is a different stream, we need to send stream beginning
                if stream != self._current_stream:
                    self._current_stream = stream
                    return self._create_stream_beginning_message(stream)
                
                # Determine event class based on event category and name
                event_class_name = self._get_event_class_name_by_category(event_data)
                event_class = self._event_classes.get(event_class_name)
                
                if event_class is None:
                    # Fall back to generic event if specific class not found
                    event_class_name = "generic_event"
                    event_class = self._event_classes.get(event_class_name)
                
                if event_class is None:
                    # Skip unknown event types
                    return self.__next__()
                
                # Create event message
                msg = self._create_event_message(
                    event_class,
                    stream,
                    default_clock_snapshot=event_data.timestamp
                )
                
                # Set event fields
                if event_data.event_args:
                    for key, value in event_data.event_args.items():
                        if key in msg.event.payload_field:
                            if value is not None:
                                msg.event.payload_field[key] = value
                
                return msg
            else:
                self._state = "stream_end"
                return self.__next__()
        
        elif self._state == "stream_end":
            if self._current_stream:
                stream = self._current_stream
                self._current_stream = None
                self._state = "done"
                return self._create_stream_end_message(stream)
            else:
                self._state = "done"
                raise StopIteration
        
        else:
            raise StopIteration
    
    def _get_event_class_name_by_category(self, event_data: RocmEventData) -> str:
        """Get the event class name based on event category and name."""
        if hasattr(event_data, 'category') and event_data.category:
            category = event_data.category.lower()
            
            # Map categories to specific event types
            if category == 'hip_runtime_api_ext':
                return 'region_event'
            elif category == 'hip_compiler_api_ext':
                return 'region_event'
            elif category == 'kernel_dispatch':
                return 'kernel_dispatch_event'
            elif category == 'memory_copy':
                return 'memory_copy_event'
            elif category == 'memory_allocation':
                return 'memory_allocation_event'
            elif "region" in event_data.name:
                return 'region_event'
        
        # Fall back to generic event
        return 'generic_event'
    
    def __del__(self):
        """Cleanup database connection."""
        if hasattr(self, '_conn'):
            self._conn.close()


@bt2.plugin_component_class
class RocmSource(bt2._UserSourceComponent, message_iterator_class=RocmSourceIterator):
    """Source component for reading ROCm profiler SQLite3 databases."""
    
    @classmethod
    def _user_get_supported_mip_versions(cls, params, obj, log_level):
        """Declare supported MIP versions."""
        return [1]  # Support MIP version 1
    
    def __init__(self, config, params, obj):
        """Initialize the source component."""
        # Get database path from parameters
        self._db_path = str(params.get('db-path', '24228_results.db'))
        
        if not self._db_path:
            raise ValueError("Database path parameter 'db-path' is required")
        
        if not os.path.exists(self._db_path):
            raise FileNotFoundError(f"Database file not found: {self._db_path}")
        
        # Create trace class
        self._trace_class = super()._create_trace_class()
        
        # Create clock class
        self._clock_class = self._create_clock_class(
            name="rocm_clock",
            description="ROCm profiler clock",
            frequency=1_000_000_000  # Nanoseconds
        )
        
        # Create stream classes
        self._stream_classes = self._create_stream_classes()
        
        # Create event classes
        self._event_classes = self._create_event_classes()
        
        # Create single output port
        self._add_output_port("out", {
            'db_path': self._db_path,
            'trace_class': self._trace_class,
            'stream_classes': self._stream_classes,
            'event_classes': self._event_classes,
            'clock_class': self._clock_class
        })
    
    def _create_stream_classes(self) -> Dict[str, Any]:
        """Create stream classes."""
        stream_classes = {}
        
        # Create a default stream class for all events
        default_stream_class = self._trace_class.create_stream_class(
            name="rocm_stream",
            default_clock_class=self._clock_class
        )
        stream_classes['default'] = default_stream_class
        
        return stream_classes
    
    def _create_clock_class(self, name: str, description: str, frequency: int):
        """Create a clock class for ROCm events."""
        clock_class = super()._create_clock_class(
            name=name,
            description=description,
            frequency=frequency
        )
        return clock_class

    def _create_event_classes(self) -> Dict[str, Any]:
        """Create event classes for different ROCm event types."""
        event_classes = {}
        
        # Create a comprehensive field class for region events
        def create_region_field_class():
            fc = self._trace_class.create_structure_field_class()
            fc.append_member("region_name", self._trace_class.create_string_field_class())
            fc.append_member("event_type", self._trace_class.create_string_field_class())
            fc.append_member("category", self._trace_class.create_string_field_class())
            fc.append_member("process_name", self._trace_class.create_string_field_class())
            fc.append_member("thread_name", self._trace_class.create_string_field_class())
            fc.append_member("pid", self._trace_class.create_signed_integer_field_class(64))
            fc.append_member("tid", self._trace_class.create_signed_integer_field_class(64))
            fc.append_member("nid", self._trace_class.create_signed_integer_field_class(64))
            fc.append_member("correlation_id", self._trace_class.create_signed_integer_field_class(64))
            fc.append_member("duration", self._trace_class.create_signed_integer_field_class(64))
            fc.append_member("extdata", self._trace_class.create_string_field_class())
            fc.append_member("call_stack", self._trace_class.create_string_field_class())
            fc.append_member("line_info", self._trace_class.create_string_field_class())
            return fc
        
        # Region event class
        region_event_class = self._stream_classes['default'].create_event_class(
            name="region_event",
            payload_field_class=create_region_field_class()
        )
        event_classes["region_event"] = region_event_class
        
        # Kernel dispatch event class
        kernel_payload_fc = self._trace_class.create_structure_field_class()
        kernel_payload_fc.append_member("kernel_name", self._trace_class.create_string_field_class())
        kernel_payload_fc.append_member("event_type", self._trace_class.create_string_field_class())
        kernel_payload_fc.append_member("dispatch_id", self._trace_class.create_signed_integer_field_class(64))
        kernel_payload_fc.append_member("queue_id", self._trace_class.create_signed_integer_field_class(64))
        kernel_payload_fc.append_member("stream_id", self._trace_class.create_signed_integer_field_class(64))
        kernel_payload_fc.append_member("workgroup_size", self._trace_class.create_string_field_class())
        kernel_payload_fc.append_member("grid_size", self._trace_class.create_string_field_class())
        kernel_payload_fc.append_member("duration", self._trace_class.create_signed_integer_field_class(64))
        kernel_event_class = self._stream_classes['default'].create_event_class(
            name="kernel_dispatch_event",
            payload_field_class=kernel_payload_fc
        )
        event_classes["kernel_dispatch_event"] = kernel_event_class
        
        # Memory copy event class
        memory_payload_fc = self._trace_class.create_structure_field_class()
        memory_payload_fc.append_member("copy_name", self._trace_class.create_string_field_class())
        memory_payload_fc.append_member("event_type", self._trace_class.create_string_field_class())
        memory_payload_fc.append_member("size", self._trace_class.create_signed_integer_field_class(64))
        memory_payload_fc.append_member("dst_agent_id", self._trace_class.create_signed_integer_field_class(64))
        memory_payload_fc.append_member("src_agent_id", self._trace_class.create_signed_integer_field_class(64))
        memory_payload_fc.append_member("queue_id", self._trace_class.create_signed_integer_field_class(64))
        memory_payload_fc.append_member("stream_id", self._trace_class.create_signed_integer_field_class(64))
        memory_payload_fc.append_member("duration", self._trace_class.create_signed_integer_field_class(64))
        memory_event_class = self._stream_classes['default'].create_event_class(
            name="memory_copy_event",
            payload_field_class=memory_payload_fc
        )
        event_classes["memory_copy_event"] = memory_event_class
        
        # Memory allocation event class
        allocation_payload_fc = self._trace_class.create_structure_field_class()
        allocation_payload_fc.append_member("allocation_name", self._trace_class.create_string_field_class())
        allocation_payload_fc.append_member("event_type", self._trace_class.create_string_field_class())
        allocation_payload_fc.append_member("size", self._trace_class.create_signed_integer_field_class(64))
        allocation_payload_fc.append_member("agent_id", self._trace_class.create_signed_integer_field_class(64))
        allocation_payload_fc.append_member("duration", self._trace_class.create_signed_integer_field_class(64))
        allocation_event_class = self._stream_classes['default'].create_event_class(
            name="memory_allocation_event",
            payload_field_class=allocation_payload_fc
        )
        event_classes["memory_allocation_event"] = allocation_event_class
        
        # Generic event class
        generic_payload_fc = self._trace_class.create_structure_field_class()
        generic_payload_fc.append_member("event_type", self._trace_class.create_string_field_class())
        generic_event_class = self._stream_classes['default'].create_event_class(
            name="generic_event",
            payload_field_class=generic_payload_fc
        )
        event_classes["generic_event"] = generic_event_class
        
        return event_classes
    
    @staticmethod
    def _user_query(priv_executor, obj, query, params):
        """Handle query requests."""
        if query == "babeltrace.support-info":
            # Support SQLite3 files that contain ROCm profiler tables
            input_value = params.get('input')
            if not input_value:
                return {'weight': 0.0}
            
            # Check if it's a file path
            if not isinstance(input_value, str):
                return {'weight': 0.0}
            
            # Check if file exists and is SQLite
            if not os.path.exists(input_value):
                return {'weight': 0.0}
            
            try:
                # Quick check if it's a SQLite database with ROCm tables
                conn = sqlite3.connect(input_value)
                cursor = conn.cursor()
                
                # Check for ROCm-specific tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rocpd_%'")
                rocm_tables = cursor.fetchall()
                
                conn.close()
                
                if rocm_tables:
                    return {'weight': 1.0}  # Perfect match
                else:
                    return {'weight': 0.0}  # Not a ROCm database
                    
            except Exception:
                return {'weight': 0.0}
        
        elif query == "babeltrace.mip-version":
            # Declare MIP version support
            return 1  # Support MIP version 1
        
        return None
