#!/usr/bin/env python3
"""
Enhanced ROCm Babeltrace2 plugin (without bt2 dependency for testing).
This version can be used to understand the database structure and event processing logic.
"""
from typing import Dict, List, Optional, Any, Iterator, Set
from dataclasses import dataclass
import sqlite3
import os

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


class RocmDataExtractor:
    """Extract and process ROCm data from database."""
    
    def __init__(self, db_path: str):
        """Initialize the data extractor."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.uuid = self._get_uuid()
        
    def _get_uuid(self) -> str:
        """Get UUID from database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rocpd_%_%'")
            tables = cursor.fetchall()
            if tables:
                table_name = tables[0][0]
                uuid = table_name.split('_', 2)[-1]
                return uuid
        except sqlite3.Error:
            pass
        return '0000b6ad_2bac_7bac_82e7_5f0563eafa7f'
    
    def get_categories(self) -> List[str]:
        """Get all categories from the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT DISTINCT s.string as category 
                FROM rocpd_event e 
                JOIN rocpd_string s ON e.category_id = s.id 
                ORDER BY category
            """)
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []
    
    def get_threads(self) -> List[int]:
        """Get all thread IDs from the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT tid FROM rocpd_region ORDER BY tid")
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []
    
    def get_queues(self) -> List[int]:
        """Get all queue IDs from the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT id FROM rocpd_info_queue ORDER BY id")
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []
    
    def get_streams(self) -> List[int]:
        """Get all stream IDs from the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT id FROM rocpd_info_stream ORDER BY id")
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []
    
    def get_events_by_category(self, category: str = None) -> List[RocmEventData]:
        """Get events filtered by category."""
        events = []
        
        if category is None or category == 'all':
            # Load all categories
            for cat in self.get_categories():
                events.extend(self._load_region_events(cat))
            events.extend(self._load_kernel_dispatch_events())
            events.extend(self._load_memory_copy_events())
            events.extend(self._load_memory_allocation_events())
        else:
            # Load specific category
            if category in ['HIP_RUNTIME_API_EXT', 'HIP_COMPILER_API_EXT', 'HSA_CORE_API', 'HSA_AMD_EXT_API', 'MARKER_CORE_API']:
                events.extend(self._load_region_events(category))
            elif category == 'KERNEL_DISPATCH':
                events.extend(self._load_kernel_dispatch_events())
            elif category == 'MEMORY_COPY':
                events.extend(self._load_memory_copy_events())
            elif category == 'MEMORY_ALLOCATION':
                events.extend(self._load_memory_allocation_events())
        
        # Sort by timestamp
        events.sort(key=lambda x: x.timestamp)
        return events
    
    def _load_region_events(self, category: str = None) -> List[RocmEventData]:
        """Load region events from the database."""
        events = []
        try:
            cursor = self.conn.cursor()
            
            category_filter = ""
            if category:
                category_filter = f"AND s2.string = '{category}'"
            
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
            WHERE 1=1 {category_filter}
            ORDER BY r.start
            LIMIT 100
            """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                duration = row['end'] - row['start']
                
                # Region start event
                events.append(RocmEventData(
                    name=f"{row['region_name']}_start",
                    timestamp=row['start'],
                    category=row['category'],
                    pid=row['pid'],
                    tid=row['tid'],
                    duration=0,
                    event_args={
                        'region_name': row['region_name'],
                        'category': row['category'],
                        'process_name': row['process_name'],
                        'thread_name': row['thread_name'],
                        'event_type': 'region_start'
                    }
                ))
                
                # Region end event
                events.append(RocmEventData(
                    name=f"{row['region_name']}_end",
                    timestamp=row['end'],
                    category=row['category'],
                    pid=row['pid'],
                    tid=row['tid'],
                    duration=duration,
                    event_args={
                        'region_name': row['region_name'],
                        'category': row['category'],
                        'event_type': 'region_end'
                    }
                ))
                
        except sqlite3.Error as e:
            print(f"Error loading region events: {e}")
        
        return events
    
    def _load_kernel_dispatch_events(self) -> List[RocmEventData]:
        """Load kernel dispatch events from the database."""
        events = []
        try:
            cursor = self.conn.cursor()
            query = """
            SELECT 
                k.start, k.end, k.nid, k.pid, k.tid, k.agent_id,
                k.dispatch_id, k.queue_id, k.stream_id,
                k.workgroup_size_x, k.workgroup_size_y, k.workgroup_size_z,
                k.grid_size_x, k.grid_size_y, k.grid_size_z,
                ks.kernel_name, ks.display_name
            FROM rocpd_kernel_dispatch k
            JOIN rocpd_info_kernel_symbol ks ON k.kernel_id = ks.id
            ORDER BY k.start
            LIMIT 50
            """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                kernel_name = row['kernel_name'] or row['display_name'] or 'unknown_kernel'
                
                # Kernel dispatch start event
                events.append(RocmEventData(
                    name="kernel_dispatch_start",
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
                        'event_type': 'kernel_dispatch_start'
                    }
                ))
                
                # Kernel dispatch end event
                events.append(RocmEventData(
                    name="kernel_dispatch_end",
                    timestamp=row['end'],
                    category='KERNEL_DISPATCH',
                    pid=row['pid'],
                    tid=row['tid'],
                    agent_id=row['agent_id'],
                    queue_id=row['queue_id'],
                    stream_id=row['stream_id'],
                    duration=row['end'] - row['start'],
                    event_args={
                        'kernel_name': kernel_name,
                        'event_type': 'kernel_dispatch_end'
                    }
                ))
                
        except sqlite3.Error as e:
            print(f"Error loading kernel dispatch events: {e}")
        
        return events
    
    def _load_memory_copy_events(self) -> List[RocmEventData]:
        """Load memory copy events from the database."""
        events = []
        try:
            cursor = self.conn.cursor()
            query = """
            SELECT 
                m.start, m.end, m.nid, m.pid, m.tid,
                m.size, m.dst_agent_id, m.src_agent_id,
                m.queue_id, m.stream_id,
                s.string as name
            FROM rocpd_memory_copy m
            JOIN rocpd_string s ON m.name_id = s.id
            ORDER BY m.start
            LIMIT 50
            """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                # Memory copy start event
                events.append(RocmEventData(
                    name="memory_copy_start",
                    timestamp=row['start'],
                    category='MEMORY_COPY',
                    pid=row['pid'],
                    tid=row['tid'],
                    queue_id=row['queue_id'],
                    stream_id=row['stream_id'],
                    event_args={
                        'copy_name': row['name'],
                        'size': row['size'],
                        'event_type': 'memory_copy_start'
                    }
                ))
                
                # Memory copy end event
                events.append(RocmEventData(
                    name="memory_copy_end",
                    timestamp=row['end'],
                    category='MEMORY_COPY',
                    pid=row['pid'],
                    tid=row['tid'],
                    queue_id=row['queue_id'],
                    stream_id=row['stream_id'],
                    duration=row['end'] - row['start'],
                    event_args={
                        'copy_name': row['name'],
                        'event_type': 'memory_copy_end'
                    }
                ))
                
        except sqlite3.Error as e:
            print(f"Error loading memory copy events: {e}")
        
        return events
    
    def _load_memory_allocation_events(self) -> List[RocmEventData]:
        """Load memory allocation events from the database."""
        events = []
        try:
            cursor = self.conn.cursor()
            
            # Check if name_id column exists in the memory allocation table
            cursor.execute("PRAGMA table_info(rocpd_memory_allocate)")
            columns = [col[1] for col in cursor.fetchall()]
            has_name_id = 'name_id' in columns
            
            if has_name_id:
                query = """
                SELECT 
                    m.start, m.end, m.nid, m.pid, m.tid,
                    m.size, m.agent_id, m.address as ptr,
                    s.string as name
                FROM rocpd_memory_allocate m
                JOIN rocpd_string s ON m.name_id = s.id
                ORDER BY m.start
                LIMIT 50
                """
            else:
                query = """
                SELECT 
                    m.start, m.end, m.nid, m.pid, m.tid,
                    m.size, m.agent_id, m.address as ptr,
                    'memory_allocation' as name
                FROM rocpd_memory_allocate m
                ORDER BY m.start
                LIMIT 50
                """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                # Memory allocation start event
                events.append(RocmEventData(
                    name="memory_allocation_start",
                    timestamp=row['start'],
                    category='MEMORY_ALLOCATION',
                    pid=row['pid'],
                    tid=row['tid'],
                    agent_id=row['agent_id'],
                    event_args={
                        'allocation_name': row['name'],
                        'size': row['size'],
                        'event_type': 'memory_allocation_start'
                    }
                ))
                
                # Memory allocation end event
                events.append(RocmEventData(
                    name="memory_allocation_end",
                    timestamp=row['end'],
                    category='MEMORY_ALLOCATION',
                    pid=row['pid'],
                    tid=row['tid'],
                    agent_id=row['agent_id'],
                    duration=row['end'] - row['start'],
                    event_args={
                        'allocation_name': row['name'],
                        'event_type': 'memory_allocation_end'
                    }
                ))
                
        except sqlite3.Error as e:
            print(f"Error loading memory allocation events: {e}")
        
        return events
    
    def get_channel_id(self, event_data: RocmEventData) -> str:
        """Get channel ID based on thread_id, queue_id, or stream_id."""
        if event_data.tid is not None:
            return f"thread_{event_data.tid}"
        elif event_data.queue_id is not None:
            return f"queue_{event_data.queue_id}"
        elif event_data.stream_id is not None:
            return f"stream_{event_data.stream_id}"
        else:
            return f"default_{event_data.pid or 0}"
    
    def analyze_streams_by_category(self):
        """Analyze how events should be split into streams by category and channel."""
        categories = self.get_categories()
        
        print("Stream Analysis:")
        print("=" * 50)
        
        for category in categories:
            print(f"\nCategory: {category}")
            events = self.get_events_by_category(category)
            
            # Group by channel
            channels = {}
            for event in events:
                channel_id = self.get_channel_id(event)
                if channel_id not in channels:
                    channels[channel_id] = []
                channels[channel_id].append(event)
            
            print(f"  Total events: {len(events)}")
            print(f"  Channels: {len(channels)}")
            
            for channel_id, channel_events in channels.items():
                print(f"    {channel_id}: {len(channel_events)} events")
                if channel_events:
                    # Show time range
                    start_time = min(e.timestamp for e in channel_events)
                    end_time = max(e.timestamp for e in channel_events)
                    print(f"      Time range: {start_time} - {end_time}")
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Main function to demonstrate the enhanced plugin capabilities."""
    db_path = "24228_results.db"
    
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return
    
    extractor = RocmDataExtractor(db_path)
    
    print("Enhanced ROCm Plugin Analysis")
    print("=" * 50)
    
    # Show database info
    categories = extractor.get_categories()
    threads = extractor.get_threads()
    queues = extractor.get_queues()
    streams = extractor.get_streams()
    
    print(f"Categories: {categories}")
    print(f"Threads: {len(threads)} ({threads[:5]}...)")
    print(f"Queues: {len(queues)} ({queues})")
    print(f"Streams: {len(streams)} ({streams[:10]}...)")
    
    # Analyze stream organization
    extractor.analyze_streams_by_category()
    
    # Show sample events
    print("\nSample Events:")
    print("=" * 50)
    
    for category in categories[:3]:  # Show first 3 categories
        print(f"\n{category} Events:")
        events = extractor.get_events_by_category(category)
        for event in events[:5]:  # Show first 5 events
            print(f"  {event.name} @ {event.timestamp} (channel: {extractor.get_channel_id(event)})")
    
    extractor.close()


if __name__ == "__main__":
    main()
