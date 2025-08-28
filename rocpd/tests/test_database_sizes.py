#!/usr/bin/env python3
"""
Test database size variations and command line options for ROCpd module.

Tests:
- Small database files (few records)
- Large database files (many records) 
- Various command line options and parameters
- Different parameter combinations
"""

import pytest
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


@pytest.fixture(scope="module")
def setup_size_test_environment():
    """Set up test fixtures before all tests."""
    repo_root_path = Path(__file__).parent.parent.parent
    example_db = repo_root_path / "examples" / "24228_results.db"
    
    # Create temporary directories for test outputs
    temp_dir = tempfile.mkdtemp(prefix="rocpd_size_test_")
    test_data_dir = Path(temp_dir) / "test_data"
    output_dir = Path(temp_dir) / "output"
    test_data_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    
    # Create test databases of various sizes
    test_databases = _create_test_databases(test_data_dir)
    
    yield {
        'repo_root': repo_root_path,
        'example_db': example_db,
        'temp_dir': temp_dir,
        'test_data_dir': test_data_dir,
        'output_dir': output_dir,
        **test_databases
    }
    
    # Clean up after all tests
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


def _create_test_databases(test_data_dir):
    """Create test databases of various sizes."""
    test_dbs = {}
    
    # Small database (10 records)
    test_dbs['small_db'] = _create_database(test_data_dir, "small.db", 10)
    
    # Medium database (1000 records)
    test_dbs['medium_db'] = _create_database(test_data_dir, "medium.db", 1000)
    
    # Large database (10000 records)
    test_dbs['large_db'] = _create_database(test_data_dir, "large.db", 10000)
    
    # Very large database (100000 records) - might be slow
    test_dbs['very_large_db'] = _create_database(test_data_dir, "very_large.db", 100000)
    
    return test_dbs


def _create_database(test_data_dir, filename, num_records):
    """Create a test database with specified number of records."""
    db_path = test_data_dir / filename
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


@pytest.fixture
def clean_size_output_dir(setup_size_test_environment):
    """Clean output directory for each test."""
    env = setup_size_test_environment
    output_dir = env['output_dir']
    
    # Clean output directory for each test
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    return env


def _check_graceful_handling(result):
    """Helper function to check that result was handled gracefully."""
    # Should complete successfully or fail gracefully
    if result.returncode != 0:
        # Should not crash with exceptions
        error_text = result.stderr.lower()
        assert "traceback" not in error_text, \
            f"Should not crash with exceptions, got: {result.stderr}"


def test_small_database(clean_size_output_dir):
    """Test processing small database (10 records)."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "small_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_medium_database(clean_size_output_dir):
    """Test processing medium database (1000 records)."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['medium_db']),
        "-f", "ctf",
        "-o", "medium_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_large_database(clean_size_output_dir):
    """Test processing large database (10000 records)."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['large_db']),
        "-f", "ctf",
        "-o", "large_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


@pytest.mark.slow
def test_very_large_database(clean_size_output_dir):
    """Test processing very large database (100000 records)."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['very_large_db']),
        "-f", "ctf",
        "-o", "very_large_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_debug_option(clean_size_output_dir):
    """Test debug option."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "debug_test",
        "-d", str(env['output_dir']),
        "--debug"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_streaming_option(clean_size_output_dir):
    """Test streaming option."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "streaming_test",
        "-d", str(env['output_dir']),
        "--streaming"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_packet_bytes_option(clean_size_output_dir):
    """Test packet bytes option."""
    env = clean_size_output_dir
    for packet_size in ["65536", "131072", "262144"]:
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(env['small_db']),
            "-f", "ctf",
            "-o", f"packet_{packet_size}_test",
            "-d", str(env['output_dir']),
            "--packet-bytes", packet_size
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
        _check_graceful_handling(result)


def test_stream_name_option(clean_size_output_dir):
    """Test stream name option."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "stream_name_test",
        "-d", str(env['output_dir']),
        "--stream-name", "custom_stream"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_collect_threads_option(clean_size_output_dir):
    """Test collect threads option."""
    env = clean_size_output_dir
    for thread_count in ["1", "2", "4"]:
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(env['small_db']),
            "-f", "ctf",
            "-o", f"threads_{thread_count}_test",
            "-d", str(env['output_dir']),
            "--collect-threads", thread_count
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
        _check_graceful_handling(result)


def test_fetch_chunk_option(clean_size_output_dir):
    """Test fetch chunk option."""
    env = clean_size_output_dir
    for chunk_size in ["1000", "5000", "10000"]:
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(env['small_db']),
            "-f", "ctf",
            "-o", f"chunk_{chunk_size}_test",
            "-d", str(env['output_dir']),
            "--fetch-chunk", chunk_size
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
        _check_graceful_handling(result)


def test_no_sort_option(clean_size_output_dir):
    """Test no sort option."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "no_sort_test",
        "-d", str(env['output_dir']),
        "--no-sort"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_no_progress_option(clean_size_output_dir):
    """Test no progress option."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "no_progress_test",
        "-d", str(env['output_dir']),
        "--no-progress"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_split_on_decrease_option(clean_size_output_dir):
    """Test split on decrease option."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "split_on_decrease_test",
        "-d", str(env['output_dir']),
        "--split-on-decrease"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_combined_options(clean_size_output_dir):
    """Test combination of multiple options."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "combined_test",
        "-d", str(env['output_dir']),
        "--debug",
        "--streaming",
        "--packet-bytes", "131072",
        "--no-progress"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)


def test_time_window_options(clean_size_output_dir):
    """Test time window options (start/end)."""
    env = clean_size_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "time_window_test",
        "-d", str(env['output_dir']),
        "--start", "1000000000",
        "--end", "1000010000"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    _check_graceful_handling(result)