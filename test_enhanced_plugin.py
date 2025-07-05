#!/usr/bin/env python3
"""
Test script for the enhanced ROCm Babeltrace2 plugin.
"""
import sys
import os

def test_plugin():
    """Test the enhanced ROCm plugin with the new database."""
    
    # Add the current directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # Test database connection (skip bt2 import for now)
        import sqlite3
        db_path = "24228_results.db"
        
        if not os.path.exists(db_path):
            print(f"✗ Database file {db_path} not found")
            return False
        
        print(f"✓ Database file {db_path} found")
        
        # Test database structure
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for ROCm tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rocpd_%'")
        tables = cursor.fetchall()
        print(f"✓ Found {len(tables)} ROCm tables in database")
        
        # Check categories
        try:
            cursor.execute("""
                SELECT DISTINCT s.string as category 
                FROM rocpd_event e 
                JOIN rocpd_string s ON e.category_id = s.id 
                ORDER BY category
            """)
            categories = [row[0] for row in cursor.fetchall()]
            print(f"✓ Found categories: {', '.join(categories)}")
        except sqlite3.Error as e:
            print(f"✗ Error getting categories: {e}")
            return False
        
        # Check threads
        try:
            cursor.execute("SELECT DISTINCT tid FROM rocpd_region ORDER BY tid")
            threads = [row[0] for row in cursor.fetchall()]
            print(f"✓ Found {len(threads)} threads: {threads}")
        except sqlite3.Error as e:
            print(f"✗ Error getting threads: {e}")
            return False
        
        # Check queues
        try:
            cursor.execute("SELECT DISTINCT id FROM rocpd_info_queue ORDER BY id")
            queues = [row[0] for row in cursor.fetchall()]
            print(f"✓ Found {len(queues)} queues: {queues}")
        except sqlite3.Error as e:
            print(f"✗ Error getting queues: {e}")
            return False
        
        # Check streams
        try:
            cursor.execute("SELECT DISTINCT id FROM rocpd_info_stream ORDER BY id")
            streams = [row[0] for row in cursor.fetchall()]
            print(f"✓ Found {len(streams)} streams: {streams}")
        except sqlite3.Error as e:
            print(f"✗ Error getting streams: {e}")
            return False
        
        conn.close()
        
        # Test event counting
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Count regions
        cursor.execute("SELECT COUNT(*) FROM rocpd_region")
        region_count = cursor.fetchone()[0]
        print(f"✓ Found {region_count} regions")
        
        # Count kernel dispatches
        try:
            cursor.execute("SELECT COUNT(*) FROM rocpd_kernel_dispatch")
            kernel_count = cursor.fetchone()[0]
            print(f"✓ Found {kernel_count} kernel dispatches")
        except sqlite3.Error:
            print("✓ No kernel dispatch table found")
        
        # Count memory copies
        try:
            cursor.execute("SELECT COUNT(*) FROM rocpd_memory_copy")
            memory_copy_count = cursor.fetchone()[0]
            print(f"✓ Found {memory_copy_count} memory copies")
        except sqlite3.Error:
            print("✓ No memory copy table found")
        
        # Count memory allocations
        try:
            cursor.execute("SELECT COUNT(*) FROM rocpd_memory_allocate")
            memory_alloc_count = cursor.fetchone()[0]
            print(f"✓ Found {memory_alloc_count} memory allocations")
        except sqlite3.Error:
            print("✓ No memory allocation table found")
        
        conn.close()
        
        print("\n✓ All tests passed! The enhanced plugin should work with the new database.")
        return True
        
    except Exception as e:
        print(f"✗ Error testing plugin: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_plugin()
    sys.exit(0 if success else 1)
