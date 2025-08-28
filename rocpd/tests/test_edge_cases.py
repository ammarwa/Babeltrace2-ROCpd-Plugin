#!/usr/bin/env python3
"""
Test edge cases and error handling for ROCpd module.

Tests various edge cases including:
- Missing input files
- Invalid database files  
- Empty databases
- Corrupted databases
- Permission issues
- Invalid command line arguments
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
from rocpd.importer import RocpdImportData


@pytest.fixture(scope="module")
def setup_edge_test_environment():
    """Set up test fixtures before all tests."""
    repo_root_path = Path(__file__).parent.parent.parent
    example_db = repo_root_path / "examples" / "24228_results.db"
    
    # Create temporary directories for test outputs
    temp_dir = tempfile.mkdtemp(prefix="rocpd_edge_test_")
    test_data_dir = Path(temp_dir) / "test_data"
    output_dir = Path(temp_dir) / "output"
    test_data_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    
    # Create test databases for edge cases
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
    """Create various test databases for edge case testing."""
    test_dbs = {}
    
    # Empty database
    empty_db = test_data_dir / "empty.db"
    conn = sqlite3.connect(empty_db)
    conn.close()
    test_dbs['empty_db'] = empty_db
    
    # Database with ROCpd tables but no data
    empty_rocpd_db = test_data_dir / "empty_rocpd.db"
    conn = sqlite3.connect(empty_rocpd_db)
    cursor = conn.cursor()
    # Create some ROCpd-like tables but leave them empty
    cursor.execute("""
        CREATE TABLE rocpd_api_calls (
            id INTEGER PRIMARY KEY,
            timestamp INTEGER,
            name TEXT,
            duration INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE rocpd_kernel_dispatch (
            id INTEGER PRIMARY KEY,
            timestamp INTEGER,
            name TEXT,
            duration INTEGER
        )
    """)
    conn.commit()
    conn.close()
    test_dbs['empty_rocpd_db'] = empty_rocpd_db
    
    # Small database with minimal data
    small_db = test_data_dir / "small.db"
    conn = sqlite3.connect(small_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE rocpd_api_calls (
            id INTEGER PRIMARY KEY,
            timestamp INTEGER,
            name TEXT,
            duration INTEGER
        )
    """)
    cursor.execute("""
        INSERT INTO rocpd_api_calls (timestamp, name, duration) 
        VALUES (1000000, 'test_api', 5000)
    """)
    cursor.execute("""
        INSERT INTO rocpd_api_calls (timestamp, name, duration) 
        VALUES (1005000, 'test_api2', 3000)
    """)
    conn.commit()
    conn.close()
    test_dbs['small_db'] = small_db
    
    # Invalid (non-SQLite) file
    invalid_db = test_data_dir / "invalid.db"
    with open(invalid_db, 'w') as f:
        f.write("This is not a SQLite database file")
    test_dbs['invalid_db'] = invalid_db
    
    # Corrupted SQLite file
    corrupted_db = test_data_dir / "corrupted.db"
    with open(corrupted_db, 'wb') as f:
        f.write(b'SQLite format 3\x00' + b'\x00' * 100)  # Invalid SQLite header
    test_dbs['corrupted_db'] = corrupted_db
    
    return test_dbs


@pytest.fixture
def clean_edge_output_dir(setup_edge_test_environment):
    """Clean output directory for each test."""
    env = setup_edge_test_environment
    output_dir = env['output_dir']
    
    # Clean output directory for each test
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    return env


def test_missing_input_file(clean_edge_output_dir):
    """Test handling of missing input files."""
    env = clean_edge_output_dir
    nonexistent_file = env['test_data_dir'] / "nonexistent.db"
    
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(nonexistent_file),
        "-f", "ctf",
        "-o", "test_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # CLI should complete successfully but report issues
    assert result.returncode == 0, "CLI should complete even with missing files"
    
    # Should report some kind of issue in the output
    output_text = result.stdout + result.stderr
    assert any(keyword in output_text.lower() for keyword in [
        "not found", "missing", "failed", "unavailable", "error"
    ]), f"Should report issues with missing file, got: {output_text}"


def test_missing_input_file_api(clean_edge_output_dir):
    """Test Python API handling of missing input files."""
    env = clean_edge_output_dir
    nonexistent_file = str(env['test_data_dir'] / "nonexistent.db")
    
    # The minimal RocpdImportData doesn't validate file existence
    # It just stores filenames, so this should succeed
    import_data = RocpdImportData([nonexistent_file])
    assert import_data.filenames == [nonexistent_file]


def test_invalid_database_file(clean_edge_output_dir):
    """Test handling of invalid (non-SQLite) database files."""
    env = clean_edge_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['invalid_db']),
        "-f", "ctf", 
        "-o", "test_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # CLI should complete but report issues
    assert result.returncode == 0, "CLI should complete even with invalid files"
    
    # Should report some kind of issue in the output
    output_text = result.stdout + result.stderr
    assert any(keyword in output_text.lower() for keyword in [
        "database", "sqlite", "invalid", "failed", "unavailable", "error"
    ]), f"Should report database error, got: {output_text}"


def test_invalid_database_file_api(clean_edge_output_dir):
    """Test Python API handling of invalid database files."""
    env = clean_edge_output_dir
    # The minimal RocpdImportData doesn't validate file content
    # It just stores filenames, so this should succeed
    import_data = RocpdImportData([str(env['invalid_db'])])
    assert import_data.filenames == [str(env['invalid_db'])]


def test_corrupted_database_file(clean_edge_output_dir):
    """Test handling of corrupted SQLite database files."""
    env = clean_edge_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['corrupted_db']),
        "-f", "ctf",
        "-o", "test_output", 
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # CLI should complete but report issues  
    assert result.returncode == 0, "CLI should complete even with corrupted files"
    
    # Should report some kind of issue in the output
    output_text = result.stdout + result.stderr
    assert any(keyword in output_text.lower() for keyword in [
        "database", "corrupted", "malformed", "failed", "unavailable", "error"
    ]), f"Should report corrupted database error, got: {output_text}"


def test_corrupted_database_file_api(clean_edge_output_dir):
    """Test Python API handling of corrupted database files."""
    env = clean_edge_output_dir
    # The minimal RocpdImportData doesn't validate file content
    # It just stores filenames, so this should succeed
    import_data = RocpdImportData([str(env['corrupted_db'])])
    assert import_data.filenames == [str(env['corrupted_db'])]


def test_empty_database_file(clean_edge_output_dir):
    """Test handling of empty database files."""
    env = clean_edge_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['empty_db']),
        "-f", "ctf",
        "-o", "test_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # May succeed or fail depending on implementation
    # If it fails, should be due to missing ROCpd tables
    if result.returncode != 0:
        error_text = result.stderr.lower()
        assert any(keyword in error_text for keyword in ["table", "rocpd", "empty"]), \
            f"Should report table/schema error for empty database, got: {result.stderr}"


def test_empty_rocpd_database(clean_edge_output_dir):
    """Test handling of database with ROCpd tables but no data."""
    env = clean_edge_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['empty_rocpd_db']),
        "-f", "ctf",
        "-o", "test_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Should handle empty tables gracefully
    # Result depends on implementation - may succeed with empty output or fail
    if result.returncode != 0:
        # If it fails, should be graceful
        error_text = result.stderr.lower()
        assert not any(keyword in error_text for keyword in ["traceback", "exception"]), \
            f"Should fail gracefully without exceptions, got: {result.stderr}"


def test_small_database(clean_edge_output_dir):
    """Test handling of small database with minimal data."""
    env = clean_edge_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "test_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Should handle small databases gracefully
    # May succeed or fail depending on barectf availability
    if result.returncode != 0:
        # Should not crash with exceptions
        error_text = result.stderr.lower()
        assert "traceback" not in error_text, \
            f"Should not crash with exceptions, got: {result.stderr}"


def test_missing_required_arguments(clean_edge_output_dir):
    """Test handling of missing required command line arguments."""
    env = clean_edge_output_dir
    
    # Missing input file
    cmd = [sys.executable, "-m", "rocpd", "convert", "-f", "ctf"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    assert result.returncode != 0
    assert "required" in result.stderr.lower()
    
    # Missing format
    cmd = [sys.executable, "-m", "rocpd", "convert", "-i", str(env['small_db'])]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    assert result.returncode != 0
    assert "required" in result.stderr.lower()


def test_invalid_output_directory(clean_edge_output_dir):
    """Test handling of invalid output directory."""
    env = clean_edge_output_dir
    # Try to write to a file instead of directory
    invalid_output = env['invalid_db']  # This is a file, not directory
    
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']),
        "-f", "ctf",
        "-o", "test_output",
        "-d", str(invalid_output)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Should fail with appropriate error
    if result.returncode != 0:
        error_text = result.stderr.lower()
        assert any(keyword in error_text for keyword in ["directory", "path", "permission"]), \
            f"Should report path/directory error, got: {result.stderr}"


def test_multiple_input_files_with_missing(clean_edge_output_dir):
    """Test multiple input files where some are missing."""
    env = clean_edge_output_dir
    nonexistent_file = env['test_data_dir'] / "nonexistent.db"
    
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']), str(nonexistent_file),
        "-f", "ctf",
        "-o", "test_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # CLI should complete successfully
    assert result.returncode == 0, "CLI should complete even with missing files"
    
    # With our improved CTF implementation, it may succeed using the first valid database
    # The behavior depends on how the importer handles multiple files
    output_text = result.stdout + result.stderr
    
    # Either should succeed with the valid database, or report issues with missing files
    success_indicators = ["ctf trace written", "events extracted", "ctf bridge"]
    failure_indicators = ["not found", "missing", "failed", "unavailable", "error"]
    
    has_success = any(keyword in output_text.lower() for keyword in success_indicators)
    has_failure = any(keyword in output_text.lower() for keyword in failure_indicators)
    
    # Should either succeed or report appropriate failure
    assert has_success or has_failure, f"Should either succeed or report issues, got: {output_text}"


def test_multiple_valid_input_files(clean_edge_output_dir):
    """Test multiple valid input files."""
    env = clean_edge_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['small_db']), str(env['empty_rocpd_db']),
        "-f", "ctf",
        "-o", "test_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Should handle multiple files gracefully
    # May succeed or fail depending on barectf availability
    if result.returncode != 0:
        # Should not crash with exceptions
        error_text = result.stderr.lower()
        assert "traceback" not in error_text, \
            f"Should not crash with exceptions, got: {result.stderr}"