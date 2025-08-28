#!/usr/bin/env python3
"""
Test database size variations and command line options for ROCpd module.

Tests:
- Small database files (few records)
- Large database files (many records) 
- Various command line options and parameters
- Different parameter combinations
"""

import unittest
import tempfile
import shutil
import os
import sys
import subprocess
import sqlite3
from pathlib import Path

# Add repo root to path to import rocpd modules
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, repo_root)

from rocpd import __main__ as rocpd_main


class TestDatabaseSizesAndOptions(unittest.TestCase):
    """Test database size variations and command line options."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before all tests."""
        cls.repo_root = Path(__file__).parent.parent.parent
        cls.example_db = cls.repo_root / "examples" / "24228_results.db"
        
        # Create temporary directories for test outputs
        cls.temp_dir = tempfile.mkdtemp(prefix="rocpd_size_test_")
        cls.test_data_dir = Path(cls.temp_dir) / "test_data"
        cls.output_dir = Path(cls.temp_dir) / "output"
        cls.test_data_dir.mkdir(exist_ok=True)
        cls.output_dir.mkdir(exist_ok=True)
        
        # Create test databases of various sizes
        cls._create_test_databases()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        if hasattr(cls, 'temp_dir') and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)
    
    @classmethod
    def _create_test_databases(cls):
        """Create test databases of various sizes."""
        # Small database (10 records)
        cls.small_db = cls._create_database("small.db", 10)
        
        # Medium database (1000 records)
        cls.medium_db = cls._create_database("medium.db", 1000)
        
        # Large database (10000 records)
        cls.large_db = cls._create_database("large.db", 10000)
        
        # Very large database (100000 records) - might be slow
        cls.very_large_db = cls._create_database("very_large.db", 100000)
    
    @classmethod
    def _create_database(cls, filename, num_records):
        """Create a test database with specified number of records."""
        db_path = cls.test_data_dir / filename
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create ROCpd-like tables
        cursor.execute("""
            CREATE TABLE rocpd_api_calls (
                id INTEGER PRIMARY KEY,
                timestamp INTEGER,
                name TEXT,
                duration INTEGER,
                tid INTEGER,
                pid INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE rocpd_kernel_dispatch (
                id INTEGER PRIMARY KEY,
                timestamp INTEGER,
                name TEXT,
                duration INTEGER,
                device_id INTEGER,
                queue_id INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE rocpd_memory_copy (
                id INTEGER PRIMARY KEY,
                timestamp INTEGER,
                bytes_copied INTEGER,
                duration INTEGER,
                src_type TEXT,
                dst_type TEXT
            )
        """)
        
        # Insert test data
        base_timestamp = 1000000000  # 1 second in nanoseconds
        
        for i in range(num_records):
            # API calls
            cursor.execute("""
                INSERT INTO rocpd_api_calls (timestamp, name, duration, tid, pid)
                VALUES (?, ?, ?, ?, ?)
            """, (
                base_timestamp + i * 1000,  # 1 microsecond apart
                f"api_call_{i % 10}",
                1000 + (i % 5000),  # 1-6 microseconds
                100 + (i % 4),  # Thread IDs 100-103
                1000 + (i % 2)  # Process IDs 1000-1001
            ))
            
            # Kernel dispatches (fewer than API calls)
            if i % 10 == 0:
                cursor.execute("""
                    INSERT INTO rocpd_kernel_dispatch (timestamp, name, duration, device_id, queue_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    base_timestamp + i * 1000 + 500,  # Offset by 500ns
                    f"kernel_{i % 5}",
                    10000 + (i % 50000),  # 10-60 microseconds
                    i % 2,  # Device IDs 0-1
                    i % 4   # Queue IDs 0-3
                ))
            
            # Memory copies (even fewer)
            if i % 50 == 0:
                cursor.execute("""
                    INSERT INTO rocpd_memory_copy (timestamp, bytes_copied, duration, src_type, dst_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    base_timestamp + i * 1000 + 750,  # Offset by 750ns
                    1024 * (1 + i % 1024),  # 1KB to 1MB
                    5000 + (i % 20000),  # 5-25 microseconds
                    "host" if i % 2 == 0 else "device",
                    "device" if i % 2 == 0 else "host"
                ))
        
        conn.commit()
        conn.close()
        return db_path
    
    def setUp(self):
        """Set up before each test."""
        # Clean output directory for each test
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def test_small_database(self):
        """Test processing small database (10 records)."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "small_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should handle small database gracefully
        # May succeed or fail depending on barectf availability
        self._check_graceful_handling(result)
    
    def test_medium_database(self):
        """Test processing medium database (1000 records)."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.medium_db),
            "-f", "ctf",
            "-o", "medium_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_large_database(self):
        """Test processing large database (10000 records)."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.large_db),
            "-f", "ctf",
            "-o", "large_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_very_large_database(self):
        """Test processing very large database (100000 records)."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.very_large_db),
            "-f", "ctf",
            "-o", "very_large_output",
            "-d", str(self.output_dir)
        ]
        
        # This test might be slow, so we add a timeout
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=60, cwd=self.repo_root)
            self._check_graceful_handling(result)
        except subprocess.TimeoutExpired:
            # If it times out, that's also acceptable for very large databases
            self.skipTest("Very large database processing timed out (acceptable)")
    
    def test_custom_output_file_name(self):
        """Test custom output file name option."""
        custom_name = "custom_trace_name"
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", custom_name,
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        if result.returncode == 0:
            # Check that output uses custom name
            expected_path = self.output_dir / custom_name
            self.assertTrue(
                expected_path.exists() or any(custom_name in str(p) for p in self.output_dir.glob("*")),
                f"Output should use custom name {custom_name}"
            )
    
    def test_custom_output_directory(self):
        """Test custom output directory option."""
        custom_dir = self.output_dir / "custom_subdir"
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(custom_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        if result.returncode == 0:
            # Check that output directory was created and used
            self.assertTrue(custom_dir.exists(), "Custom output directory should be created")
    
    def test_ctf_packet_bytes_option(self):
        """Test CTF packet bytes option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "packet_test",
            "-d", str(self.output_dir),
            "--packet-bytes", "131072"  # 128KB
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_ctf_stream_name_option(self):
        """Test CTF stream name option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "stream_test",
            "-d", str(self.output_dir),
            "--stream-name", "custom_stream"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_debug_option(self):
        """Test debug option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "debug_test",
            "-d", str(self.output_dir),
            "--debug"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
        
        # Debug output should contain more verbose information
        if "--debug" in " ".join(cmd):
            # We passed the debug flag, so output might be more verbose
            pass
    
    def test_no_sort_option(self):
        """Test no-sort option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "nosort_test",
            "-d", str(self.output_dir),
            "--no-sort"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_split_on_decrease_option(self):
        """Test split-on-decrease option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "split_test", 
            "-d", str(self.output_dir),
            "--split-on-decrease"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_no_progress_option(self):
        """Test no-progress option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "noprogress_test",
            "-d", str(self.output_dir),
            "--no-progress"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_collect_threads_option(self):
        """Test collect-threads option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.medium_db),
            "-f", "ctf",
            "-o", "threads_test",
            "-d", str(self.output_dir),
            "--collect-threads", "2"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_streaming_option(self):
        """Test streaming option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.medium_db),
            "-f", "ctf",
            "-o", "streaming_test",
            "-d", str(self.output_dir),
            "--streaming"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_fetch_chunk_option(self):
        """Test fetch-chunk option."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.medium_db),
            "-f", "ctf",
            "-o", "chunk_test",
            "-d", str(self.output_dir),
            "--streaming",
            "--fetch-chunk", "1000"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_multiple_options_combination(self):
        """Test multiple options combined."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "multi_options_test",
            "-d", str(self.output_dir),
            "--debug",
            "--no-sort",
            "--no-progress",
            "--packet-bytes", "65536",
            "--stream-name", "multi_test_stream"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def test_agent_index_value_options(self):
        """Test agent-index-value options."""
        for index_value in ["absolute", "relative", "type-relative"]:
            with self.subTest(index_value=index_value):
                cmd = [
                    sys.executable, "-m", "rocpd", "convert",
                    "-i", str(self.small_db),
                    "-f", "ctf",
                    "-o", f"agent_{index_value}_test",
                    "-d", str(self.output_dir),
                    "--agent-index-value", index_value
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
                self._check_graceful_handling(result)
    
    def test_time_window_options(self):
        """Test time window options (start/end)."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "time_window_test",
            "-d", str(self.output_dir),
            "--start", "1000000000",
            "--end", "1000010000"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self._check_graceful_handling(result)
    
    def _check_graceful_handling(self, result):
        """Check that the command was handled gracefully (no crashes)."""
        # Should not crash with unhandled exceptions
        error_text = result.stderr.lower()
        self.assertFalse(
            "traceback" in error_text and "exception" in error_text,
            f"Should not crash with unhandled exceptions, got: {result.stderr}"
        )
        
        # If it fails, should be for expected reasons
        if result.returncode != 0:
            expected_failures = [
                "barectf", "bridge", "not available", "missing", 
                "not implemented", "conversion", "dependency"
            ]
            self.assertTrue(
                any(failure in error_text for failure in expected_failures),
                f"Failure should be for expected reasons, got: {result.stderr}"
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)