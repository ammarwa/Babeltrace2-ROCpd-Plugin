#!/usr/bin/env python3
"""
Test script for the ROCm Babeltrace2 plugin.

This script creates a mock ROCm profiler database and demonstrates
how to use the plugin to read and convert the data.
"""

import sqlite3
import os
import tempfile
import uuid
import time
from typing import Dict, List

def create_mock_rocm_database(db_path: str) -> None:
    """Create a mock ROCm profiler database for testing."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Generate UUID for table names
    test_uuid = str(uuid.uuid4()).replace('-', '')
    test_guid = str(uuid.uuid4()).replace('-', '')
    
    # Create metadata table
    cursor.execute(f'''
        CREATE TABLE rocpd_metadata{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL,
            value TEXT NOT NULL
        )
    ''')
    
    # Insert metadata
    cursor.execute(f'INSERT INTO rocpd_metadata{test_uuid} (tag, value) VALUES (?, ?)', 
                   ('schema_version', '3'))
    cursor.execute(f'INSERT INTO rocpd_metadata{test_uuid} (tag, value) VALUES (?, ?)', 
                   ('uuid', test_uuid))
    cursor.execute(f'INSERT INTO rocpd_metadata{test_uuid} (tag, value) VALUES (?, ?)', 
                   ('guid', test_guid))
    
    # Create string table
    cursor.execute(f'''
        CREATE TABLE rocpd_string{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            string TEXT NOT NULL UNIQUE
        )
    ''')
    
    # Insert strings
    strings = [
        'main_region',
        'gpu_computation',
        'memory_transfer',
        'vector_add',
        'matrix_multiply',
        'DeviceToHost',
        'HostToDevice',
        'cpu_track',
        'gpu_track'
    ]
    
    string_ids = {}
    for i, s in enumerate(strings):
        cursor.execute(f'INSERT INTO rocpd_string{test_uuid} (string) VALUES (?)', (s,))
        string_ids[s] = i + 1
    
    # Create info tables
    cursor.execute(f'''
        CREATE TABLE rocpd_info_node{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            hash BIGINT NOT NULL UNIQUE,
            machine_id TEXT NOT NULL,
            system_name TEXT,
            hostname TEXT
        )
    ''')
    
    cursor.execute(f'INSERT INTO rocpd_info_node{test_uuid} (hash, machine_id, system_name, hostname) VALUES (?, ?, ?, ?)',
                   (12345, 'test_machine', 'Linux', 'test_host'))
    
    cursor.execute(f'''
        CREATE TABLE rocpd_info_process{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            ppid INTEGER,
            start BIGINT,
            end BIGINT,
            command TEXT,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id)
        )
    ''')
    
    cursor.execute(f'INSERT INTO rocpd_info_process{test_uuid} (nid, pid, ppid, start, end, command) VALUES (?, ?, ?, ?, ?, ?)',
                   (1, 1234, 5678, 1000000000, 2000000000, 'test_app'))
    
    cursor.execute(f'''
        CREATE TABLE rocpd_info_thread{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            tid INTEGER NOT NULL,
            name TEXT,
            start BIGINT,
            end BIGINT,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id)
        )
    ''')
    
    cursor.execute(f'INSERT INTO rocpd_info_thread{test_uuid} (nid, pid, tid, name, start, end) VALUES (?, ?, ?, ?, ?, ?)',
                   (1, 1, 1234, 'main_thread', 1000000000, 2000000000))
    
    cursor.execute(f'''
        CREATE TABLE rocpd_info_agent{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            type TEXT CHECK (type IN ('CPU', 'GPU')),
            name TEXT,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id)
        )
    ''')
    
    cursor.execute(f'INSERT INTO rocpd_info_agent{test_uuid} (nid, pid, type, name) VALUES (?, ?, ?, ?)',
                   (1, 1, 'CPU', 'CPU_Agent'))
    cursor.execute(f'INSERT INTO rocpd_info_agent{test_uuid} (nid, pid, type, name) VALUES (?, ?, ?, ?)',
                   (1, 1, 'GPU', 'GPU_Agent'))
    
    # Create queue and stream tables
    cursor.execute(f'''
        CREATE TABLE rocpd_info_queue{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            name TEXT,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id)
        )
    ''')
    
    cursor.execute(f'INSERT INTO rocpd_info_queue{test_uuid} (nid, pid, name) VALUES (?, ?, ?)',
                   (1, 1, 'default_queue'))
    
    cursor.execute(f'''
        CREATE TABLE rocpd_info_stream{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            name TEXT,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id)
        )
    ''')
    
    cursor.execute(f'INSERT INTO rocpd_info_stream{test_uuid} (nid, pid, name) VALUES (?, ?, ?)',
                   (1, 1, 'default_stream'))
    
    # Create kernel symbol table
    cursor.execute(f'''
        CREATE TABLE rocpd_info_kernel_symbol{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            kernel_name TEXT,
            display_name TEXT,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id)
        )
    ''')
    
    cursor.execute(f'INSERT INTO rocpd_info_kernel_symbol{test_uuid} (nid, pid, kernel_name, display_name) VALUES (?, ?, ?, ?)',
                   (1, 1, 'vector_add', 'vector_add_kernel'))
    cursor.execute(f'INSERT INTO rocpd_info_kernel_symbol{test_uuid} (nid, pid, kernel_name, display_name) VALUES (?, ?, ?, ?)',
                   (1, 1, 'matrix_multiply', 'matrix_multiply_kernel'))
    
    # Create region table
    cursor.execute(f'''
        CREATE TABLE rocpd_region{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            tid INTEGER NOT NULL,
            start BIGINT NOT NULL,
            end BIGINT NOT NULL,
            name_id INTEGER NOT NULL,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id),
            FOREIGN KEY (tid) REFERENCES rocpd_info_thread{test_uuid} (id),
            FOREIGN KEY (name_id) REFERENCES rocpd_string{test_uuid} (id)
        )
    ''')
    
    # Insert region events
    base_time = 1000000000
    cursor.execute(f'INSERT INTO rocpd_region{test_uuid} (nid, pid, tid, start, end, name_id) VALUES (?, ?, ?, ?, ?, ?)',
                   (1, 1, 1, base_time, base_time + 5000000, string_ids['main_region']))
    cursor.execute(f'INSERT INTO rocpd_region{test_uuid} (nid, pid, tid, start, end, name_id) VALUES (?, ?, ?, ?, ?, ?)',
                   (1, 1, 1, base_time + 1000000, base_time + 4000000, string_ids['gpu_computation']))
    
    # Create kernel dispatch table
    cursor.execute(f'''
        CREATE TABLE rocpd_kernel_dispatch{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            tid INTEGER,
            agent_id INTEGER NOT NULL,
            kernel_id INTEGER NOT NULL,
            dispatch_id INTEGER NOT NULL,
            queue_id INTEGER NOT NULL,
            stream_id INTEGER NOT NULL,
            start BIGINT NOT NULL,
            end BIGINT NOT NULL,
            workgroup_size_x INTEGER NOT NULL,
            workgroup_size_y INTEGER NOT NULL,
            workgroup_size_z INTEGER NOT NULL,
            grid_size_x INTEGER NOT NULL,
            grid_size_y INTEGER NOT NULL,
            grid_size_z INTEGER NOT NULL,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id),
            FOREIGN KEY (tid) REFERENCES rocpd_info_thread{test_uuid} (id),
            FOREIGN KEY (agent_id) REFERENCES rocpd_info_agent{test_uuid} (id),
            FOREIGN KEY (kernel_id) REFERENCES rocpd_info_kernel_symbol{test_uuid} (id),
            FOREIGN KEY (queue_id) REFERENCES rocpd_info_queue{test_uuid} (id),
            FOREIGN KEY (stream_id) REFERENCES rocpd_info_stream{test_uuid} (id)
        )
    ''')
    
    # Insert kernel dispatch events
    cursor.execute(f'''INSERT INTO rocpd_kernel_dispatch{test_uuid} 
                       (nid, pid, tid, agent_id, kernel_id, dispatch_id, queue_id, stream_id, 
                        start, end, workgroup_size_x, workgroup_size_y, workgroup_size_z,
                        grid_size_x, grid_size_y, grid_size_z) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (1, 1, 1, 2, 1, 1, 1, 1, base_time + 1500000, base_time + 3500000, 
                    256, 1, 1, 1024, 1, 1))
    
    cursor.execute(f'''INSERT INTO rocpd_kernel_dispatch{test_uuid} 
                       (nid, pid, tid, agent_id, kernel_id, dispatch_id, queue_id, stream_id, 
                        start, end, workgroup_size_x, workgroup_size_y, workgroup_size_z,
                        grid_size_x, grid_size_y, grid_size_z) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (1, 1, 1, 2, 2, 2, 1, 1, base_time + 2000000, base_time + 3000000, 
                    16, 16, 1, 64, 64, 1))
    
    # Create memory copy table
    cursor.execute(f'''
        CREATE TABLE rocpd_memory_copy{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER NOT NULL,
            tid INTEGER,
            start BIGINT NOT NULL,
            end BIGINT NOT NULL,
            name_id INTEGER NOT NULL,
            dst_agent_id INTEGER,
            src_agent_id INTEGER,
            size INTEGER NOT NULL,
            queue_id INTEGER,
            stream_id INTEGER,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id),
            FOREIGN KEY (tid) REFERENCES rocpd_info_thread{test_uuid} (id),
            FOREIGN KEY (name_id) REFERENCES rocpd_string{test_uuid} (id),
            FOREIGN KEY (dst_agent_id) REFERENCES rocpd_info_agent{test_uuid} (id),
            FOREIGN KEY (src_agent_id) REFERENCES rocpd_info_agent{test_uuid} (id),
            FOREIGN KEY (queue_id) REFERENCES rocpd_info_queue{test_uuid} (id),
            FOREIGN KEY (stream_id) REFERENCES rocpd_info_stream{test_uuid} (id)
        )
    ''')
    
    # Insert memory copy events
    cursor.execute(f'''INSERT INTO rocpd_memory_copy{test_uuid} 
                       (nid, pid, tid, start, end, name_id, dst_agent_id, src_agent_id, 
                        size, queue_id, stream_id) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (1, 1, 1, base_time + 500000, base_time + 800000, string_ids['HostToDevice'], 
                    2, 1, 1048576, 1, 1))
    
    cursor.execute(f'''INSERT INTO rocpd_memory_copy{test_uuid} 
                       (nid, pid, tid, start, end, name_id, dst_agent_id, src_agent_id, 
                        size, queue_id, stream_id) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (1, 1, 1, base_time + 4200000, base_time + 4500000, string_ids['DeviceToHost'], 
                    1, 2, 1048576, 1, 1))
    
    # Create track table
    cursor.execute(f'''
        CREATE TABLE rocpd_track{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            nid INTEGER NOT NULL,
            pid INTEGER,
            tid INTEGER,
            name_id INTEGER,
            FOREIGN KEY (nid) REFERENCES rocpd_info_node{test_uuid} (id),
            FOREIGN KEY (pid) REFERENCES rocpd_info_process{test_uuid} (id),
            FOREIGN KEY (tid) REFERENCES rocpd_info_thread{test_uuid} (id),
            FOREIGN KEY (name_id) REFERENCES rocpd_string{test_uuid} (id)
        )
    ''')
    
    cursor.execute(f'INSERT INTO rocpd_track{test_uuid} (nid, pid, tid, name_id) VALUES (?, ?, ?, ?)',
                   (1, 1, 1, string_ids['cpu_track']))
    cursor.execute(f'INSERT INTO rocpd_track{test_uuid} (nid, pid, tid, name_id) VALUES (?, ?, ?, ?)',
                   (1, 1, 1, string_ids['gpu_track']))
    
    # Create sample table
    cursor.execute(f'''
        CREATE TABLE rocpd_sample{test_uuid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT DEFAULT '{test_guid}' NOT NULL,
            track_id INTEGER NOT NULL,
            timestamp BIGINT NOT NULL,
            FOREIGN KEY (track_id) REFERENCES rocpd_track{test_uuid} (id)
        )
    ''')
    
    # Insert sample events
    for i in range(10):
        cursor.execute(f'INSERT INTO rocpd_sample{test_uuid} (track_id, timestamp) VALUES (?, ?)',
                       (1, base_time + i * 100000))
        cursor.execute(f'INSERT INTO rocpd_sample{test_uuid} (track_id, timestamp) VALUES (?, ?)',
                       (2, base_time + i * 100000 + 50000))
    
    # Create views for easier access
    cursor.execute(f'''
        CREATE VIEW rocpd_metadata AS
        SELECT * FROM rocpd_metadata{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_string AS
        SELECT * FROM rocpd_string{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_region AS
        SELECT * FROM rocpd_region{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_kernel_dispatch AS
        SELECT * FROM rocpd_kernel_dispatch{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_memory_copy AS
        SELECT * FROM rocpd_memory_copy{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_sample AS
        SELECT * FROM rocpd_sample{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_track AS
        SELECT * FROM rocpd_track{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_info_node AS
        SELECT * FROM rocpd_info_node{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_info_process AS
        SELECT * FROM rocpd_info_process{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_info_thread AS
        SELECT * FROM rocpd_info_thread{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_info_agent AS
        SELECT * FROM rocpd_info_agent{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_info_queue AS
        SELECT * FROM rocpd_info_queue{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_info_stream AS
        SELECT * FROM rocpd_info_stream{test_uuid}
    ''')
    
    cursor.execute(f'''
        CREATE VIEW rocpd_info_kernel_symbol AS
        SELECT * FROM rocpd_info_kernel_symbol{test_uuid}
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"Created mock ROCm database: {db_path}")
    print(f"Database UUID: {test_uuid}")
    print(f"Database GUID: {test_guid}")


def test_plugin_basic():
    """Test basic plugin functionality."""
    print("\\n=== Testing ROCm Babeltrace2 Plugin ===")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Create mock database
        create_mock_rocm_database(db_path)
        
        # Test database content
        print("\\n--- Database Content ---")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables: {[table[0] for table in tables]}")
        
        # Count events (use views instead of UUID-suffixed tables)
        cursor.execute("SELECT COUNT(*) FROM rocpd_region")
        region_count = cursor.fetchone()[0]
        print(f"Region events: {region_count}")
        
        cursor.execute("SELECT COUNT(*) FROM rocpd_kernel_dispatch")
        kernel_count = cursor.fetchone()[0]
        print(f"Kernel dispatch events: {kernel_count}")
        
        cursor.execute("SELECT COUNT(*) FROM rocpd_memory_copy")
        memory_count = cursor.fetchone()[0]
        print(f"Memory copy events: {memory_count}")
        
        cursor.execute("SELECT COUNT(*) FROM rocpd_sample")
        sample_count = cursor.fetchone()[0]
        print(f"Sample events: {sample_count}")
        
        conn.close()
        
        # Print usage instructions
        print("\\n--- Usage Instructions ---")
        print(f"To use this database with the ROCm plugin:")
        print(f"1. Install babeltrace2 with Python bindings")
        print(f"2. Run the following command:")
        print(f"   babeltrace2 --plugin-path=. -c source.rocm.RocmSource --params='db-path={db_path}' -c sink.text.pretty")
        print(f"")
        print(f"Alternative commands:")
        print(f"# Convert to CTF format:")
        print(f"babeltrace2 --plugin-path=. -c source.rocm.RocmSource --params='db-path={db_path}' -c sink.ctf.fs --params='path=/tmp/rocm_trace'")
        print(f"")
        print(f"# Filter by time range:")
        print(f"babeltrace2 --plugin-path=. -c source.rocm.RocmSource --params='db-path={db_path}' -c filter.utils.trimmer --params='begin=1000000000,end=1003000000' -c sink.text.pretty")
        print(f"")
        print(f"Database file: {db_path}")
        print(f"Keep this file for testing the plugin!")
        
    except Exception as e:
        print(f"Error: {e}")
        # Clean up on error
        if os.path.exists(db_path):
            os.unlink(db_path)
        raise


if __name__ == "__main__":
    test_plugin_basic()
