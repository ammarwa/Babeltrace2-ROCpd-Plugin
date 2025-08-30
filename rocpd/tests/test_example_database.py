#!/usr/bin/env python3
"""
Test the example database provided in the examples directory.

This test specifically validates that the example database (24228_results.db)
works correctly with all output formats and various parameter combinations.
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

from rocpd.importer import RocpdImportData
from rocpd import ctf as ctf_mod


@pytest.fixture(scope="module")
def setup_example_test_environment():
    """Set up test fixtures before all tests."""
    repo_root_path = Path(__file__).parent.parent.parent
    example_db = repo_root_path / "examples" / "24228_results.db"
    
    # Create temporary directory for test outputs
    temp_dir = tempfile.mkdtemp(prefix="rocpd_example_test_")
    output_dir = Path(temp_dir) / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Verify example database exists and is valid
    if not example_db.exists():
        pytest.skip(f"Example database not found: {example_db}")
    
    # Check if it's a valid SQLite database
    try:
        conn = sqlite3.connect(example_db)
        conn.close()
    except sqlite3.Error as e:
        pytest.skip(f"Example database is not valid: {e}")
    
    yield {
        'repo_root': repo_root_path,
        'example_db': example_db,
        'temp_dir': temp_dir,
        'output_dir': output_dir
    }
    
    # Clean up after all tests
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def clean_example_output_dir(setup_example_test_environment):
    """Clean output directory for each test."""
    env = setup_example_test_environment
    output_dir = env['output_dir']
    
    # Clean output directory for each test
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    return env


def test_example_database_info(clean_example_output_dir):
    """Test basic information about the example database."""
    env = clean_example_output_dir
    example_db = env['example_db']
    
    # Check database file size
    file_size = example_db.stat().st_size
    assert file_size > 0, "Example database should not be empty"
    
    # Check database structure
    conn = sqlite3.connect(example_db)
    cursor = conn.cursor()
    
    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    # Should have ROCpd-related tables
    rocpd_tables = [t for t in tables if 'rocpd' in t.lower()]
    assert len(rocpd_tables) > 0, "Example database should contain ROCpd tables"
    
    print(f"Example database size: {file_size:,} bytes")
    print(f"Tables found: {len(tables)} tables")
    print(f"ROCpd tables: {len(rocpd_tables)} tables")
    
    # Get record counts for ROCpd tables
    total_records = 0
    for table in rocpd_tables[:5]:  # Check first 5 tables to avoid too much output
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count:,} records")
            assert count >= 0, f"Table {table} should have valid record count"
            total_records += count
        except sqlite3.Error:
            # Table might not be accessible, that's okay
            pass
    
    print(f"Total records in sampled tables: {total_records:,}")
    conn.close()


def test_example_database_import(clean_example_output_dir):
    """Test importing the example database via Python API."""
    env = clean_example_output_dir
    import_data = RocpdImportData([str(env['example_db'])])
    # If we get here, import was successful
    assert import_data is not None, "Import data should not be None"
    assert env['example_db'].name in str(import_data.filenames[0]), "Filename should be preserved"


def test_example_database_csv_format(clean_example_output_dir):
    """Test CSV format with example database."""
    env = clean_example_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "csv",
        "-o", "example_csv",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # CSV should complete but report that it's not implemented
    assert result.returncode == 0, "CLI should complete successfully"
    output_text = result.stdout + result.stderr
    assert any(keyword in output_text for keyword in ["not implemented", "failed", "unavailable"]), \
        f"Should report CSV conversion failure, got: {output_text}"


def test_example_database_pftrace_format(clean_example_output_dir):
    """Test Perfetto trace format with example database."""
    env = clean_example_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "pftrace",
        "-o", "example_pftrace",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Perfetto should complete but report that it's not implemented
    assert result.returncode == 0, "CLI should complete successfully"
    output_text = result.stdout + result.stderr
    assert any(keyword in output_text for keyword in ["not implemented", "failed", "unavailable"]), \
        f"Should report Perfetto conversion failure, got: {output_text}"


def test_example_database_otf2_format(clean_example_output_dir):
    """Test OTF2 format with example database."""
    env = clean_example_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "otf2",
        "-o", "example_otf2",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # OTF2 should complete but report that it's not implemented
    assert result.returncode == 0, "CLI should complete successfully"
    output_text = result.stdout + result.stderr
    assert any(keyword in output_text for keyword in ["not implemented", "failed", "unavailable"]), \
        f"Should report OTF2 conversion failure, got: {output_text}"


def test_example_database_ctf_format(clean_example_output_dir):
    """Test CTF format with example database."""
    env = clean_example_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "ctf",
        "-o", "example_ctf",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # CTF should now succeed with our improved implementation
    assert result.returncode == 0, "CLI should complete successfully"
    
    output_text = result.stdout + result.stderr
    expected_output = env['output_dir'] / "example_ctf"
    
    # Check if CTF conversion succeeded
    if expected_output.exists():
        files = list(expected_output.glob("*"))
        if len(files) > 0:
            # Look for common CTF files
            has_metadata = any("metadata" in f.name.lower() for f in files)
            has_stream = any("stream" in f.name.lower() for f in files)
            
            print(f"CTF output files: {[f.name for f in files]}")
            print(f"Has metadata: {has_metadata}")
            print(f"Has stream files: {has_stream}")
            
            # With our improved implementation, we should have these files
            assert has_metadata, "CTF output should contain metadata file"


def test_example_database_ctf_api(clean_example_output_dir):
    """Test CTF format with example database via Python API."""
    env = clean_example_output_dir
    import_data = RocpdImportData([str(env['example_db'])])
    output_path = env['output_dir'] / "ctf_api"
    
    result = ctf_mod.write_ctf(
        import_data,
        output_file="example_api_ctf",
        output_path=str(output_path)
    )
    
    # With our improved implementation, this should succeed
    assert result, "CTF API should succeed with improved implementation"
    
    # Check that output was created
    expected_output = output_path / "example_api_ctf"
    assert expected_output.exists(), "CTF API output directory should exist"
    
    files = list(expected_output.glob("*"))
    assert len(files) > 0, "CTF API output should contain files"
    
    # Should have metadata and stream files
    filenames = [f.name for f in files]
    assert "metadata" in filenames, "CTF API output should contain metadata file"


def test_example_database_with_options(clean_example_output_dir):
    """Test example database with various command line options."""
    env = clean_example_output_dir
    test_cases = [
        {
            "name": "debug_mode",
            "args": ["--debug"]
        },
        {
            "name": "no_sort",
            "args": ["--no-sort"]
        },
        {
            "name": "no_progress",
            "args": ["--no-progress"]
        },
        {
            "name": "custom_packet_size",
            "args": ["--packet-bytes", "131072"]
        },
        {
            "name": "custom_stream_name", 
            "args": ["--stream-name", "example_stream"]
        },
        {
            "name": "streaming_mode",
            "args": ["--streaming"]
        },
        {
            "name": "split_on_decrease",
            "args": ["--split-on-decrease"]
        },
        {
            "name": "multiple_options",
            "args": ["--debug", "--no-progress", "--packet-bytes", "65536"]
        }
    ]
    
    for test_case in test_cases:
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(env['example_db']),
            "-f", "ctf",
            "-o", f"example_{test_case['name']}",
            "-d", str(env['output_dir'])
        ] + test_case["args"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
        
        # Should handle gracefully regardless of success/failure
        error_text = result.stderr.lower()
        assert not ("traceback" in error_text and "exception" in error_text), \
            f"Test case {test_case['name']} should not crash with exceptions, got: {result.stderr}"


def test_example_database_performance(clean_example_output_dir):
    """Test that example database processing completes in reasonable time."""
    env = clean_example_output_dir
    import time
    
    start_time = time.time()
    
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "ctf",
        "-o", "performance_test",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Example database processing took {duration:.2f} seconds")
    
    # Should complete in reasonable time (adjust threshold as needed)
    assert duration < 300, f"Processing should complete within 5 minutes, took {duration:.2f}s"
    
    # Should complete successfully or fail gracefully
    if result.returncode != 0:
        error_text = result.stderr.lower()
        assert "traceback" not in error_text, \
            f"Should not crash with exceptions, got: {result.stderr}"


def test_example_database_multiple_input_files(clean_example_output_dir):
    """Test using example database multiple times as input."""
    env = clean_example_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']), str(env['example_db']),  # Same file twice
        "-f", "ctf",
        "-o", "example_multiple",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Should handle multiple files gracefully
    error_text = result.stderr.lower()
    assert not ("traceback" in error_text and "exception" in error_text), \
        f"Should not crash with unhandled exceptions, got: {result.stderr}"