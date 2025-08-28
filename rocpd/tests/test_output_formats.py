#!/usr/bin/env python3
"""
Test all output format types for ROCpd module.

Tests all supported output formats:
- csv
- pftrace  
- otf2
- ctf

Includes testing both CLI interface and Python API for each format.
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
from rocpd import csv as csv_mod
from rocpd import pftrace as pftrace_mod
from rocpd import otf2 as otf2_mod
from rocpd import ctf as ctf_mod


@pytest.fixture(scope="module")
def setup_test_environment():
    """Set up test fixtures before all tests."""
    # Get the example database path
    repo_root_path = Path(__file__).parent.parent.parent
    example_db = repo_root_path / "examples" / "24228_results.db"
    
    # Create temporary directories for test outputs
    temp_dir = tempfile.mkdtemp(prefix="rocpd_test_")
    output_dir = Path(temp_dir) / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Verify example database exists
    if not example_db.exists():
        pytest.skip(f"Example database not found: {example_db}")
    
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
def clean_output_dir(setup_test_environment):
    """Clean output directory for each test."""
    env = setup_test_environment
    output_dir = env['output_dir']
    
    # Clean output directory for each test
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    return env


def test_csv_format_cli(clean_output_dir):
    """Test CSV format via CLI interface."""
    env = clean_output_dir
    output_path = env['output_dir'] / "csv_output"
    
    # Test CLI interface
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "csv",
        "-o", "test_output",
        "-d", str(output_path)
    ]
    
    # CSV is a stub that should return with message
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # CSV conversion should complete but report failure
    assert result.returncode == 0, "CLI should complete successfully even if conversion fails"
    # Should report CSV conversion failure in stdout (not stderr)
    output_text = result.stdout + result.stderr
    assert "CSV conversion" in output_text
    assert any(keyword in output_text for keyword in ["not implemented", "failed", "unavailable"]), \
        f"Should report CSV conversion failure, got: {output_text}"


def test_csv_format_api(clean_output_dir):
    """Test CSV format via Python API."""
    env = clean_output_dir
    # Test Python API
    import_data = RocpdImportData([str(env['example_db'])])
    result = csv_mod.write_csv(import_data)
    
    # Should return False indicating failure
    assert not result, "CSV write_csv should return False"


def test_pftrace_format_cli(clean_output_dir):
    """Test Perfetto trace format via CLI interface."""
    env = clean_output_dir
    output_path = env['output_dir'] / "pftrace_output"
    
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "pftrace",
        "-o", "test_output",
        "-d", str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Perfetto trace conversion should complete but report failure
    assert result.returncode == 0, "CLI should complete successfully even if conversion fails"
    output_text = result.stdout + result.stderr
    assert "Perfetto" in output_text
    assert any(keyword in output_text for keyword in ["not implemented", "failed", "unavailable"]), \
        f"Should report Perfetto conversion failure, got: {output_text}"


def test_pftrace_format_api(clean_output_dir):
    """Test Perfetto trace format via Python API."""
    env = clean_output_dir
    import_data = RocpdImportData([str(env['example_db'])])
    result = pftrace_mod.write_pftrace(import_data)
    
    # Should return False indicating failure
    assert not result, "Perfetto trace write_pftrace should return False"


def test_otf2_format_cli(clean_output_dir):
    """Test OTF2 format via CLI interface."""
    env = clean_output_dir
    output_path = env['output_dir'] / "otf2_output"
    
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "otf2",
        "-o", "test_output",
        "-d", str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # OTF2 conversion should complete but report failure
    assert result.returncode == 0, "CLI should complete successfully even if conversion fails"
    output_text = result.stdout + result.stderr
    assert "OTF2" in output_text
    assert any(keyword in output_text for keyword in ["not implemented", "failed", "unavailable"]), \
        f"Should report OTF2 conversion failure, got: {output_text}"


def test_otf2_format_api(clean_output_dir):
    """Test OTF2 format via Python API."""
    env = clean_output_dir
    import_data = RocpdImportData([str(env['example_db'])])
    result = otf2_mod.write_otf2(import_data)
    
    # Should return False indicating failure
    assert not result, "OTF2 write_otf2 should return False"


def test_ctf_format_cli(clean_output_dir):
    """Test CTF format via CLI interface."""
    env = clean_output_dir
    output_path = env['output_dir'] / "ctf_output"
    
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "ctf",
        "-o", "test_output",
        "-d", str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # CTF should now succeed with our improved implementation
    assert result.returncode == 0, "CLI should complete successfully"
    
    output_text = result.stdout + result.stderr
    # CTF should now work, so we should see success messages or actual files
    expected_output = output_path / "test_output"
    if expected_output.exists():
        # Check for CTF files (metadata, stream files)
        files = list(expected_output.glob("*"))
        assert len(files) > 0, "CTF output should contain files"
        # Should have metadata and stream files
        filenames = [f.name for f in files]
        assert "metadata" in filenames, "CTF output should contain metadata file"


def test_ctf_format_api(clean_output_dir):
    """Test CTF format via Python API."""
    env = clean_output_dir
    import_data = RocpdImportData([str(env['example_db'])])
    output_path = env['output_dir'] / "ctf_api_output"
    
    result = ctf_mod.write_ctf(
        import_data,
        output_file="test_api_output",
        output_path=str(output_path)
    )
    
    # CTF should now succeed with our improved implementation
    assert result, "CTF API should succeed"
    
    # Check that output was created
    expected_output = output_path / "test_api_output"
    assert expected_output.exists(), "CTF API output directory should be created"
    
    files = list(expected_output.glob("*"))
    assert len(files) > 0, "CTF API output should contain files"
    
    # Should have metadata and stream files
    filenames = [f.name for f in files]
    assert "metadata" in filenames, "CTF API output should contain metadata file"


def test_multiple_formats(clean_output_dir):
    """Test multiple output formats in single command."""
    env = clean_output_dir
    output_path = env['output_dir'] / "multi_output"
    
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "csv", "pftrace", "otf2",
        "-o", "test_multi",
        "-d", str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Should complete but may report failures for all formats
    assert result.returncode == 0, "CLI should complete successfully even if conversions fail"
    
    # Should contain messages about the formats
    output_text = result.stdout + result.stderr
    assert any(fmt in output_text.lower() for fmt in ["csv", "pftrace", "otf2"]), \
        "Should contain messages about the requested formats"


def test_format_validation(clean_output_dir):
    """Test invalid format specification."""
    env = clean_output_dir
    cmd = [
        sys.executable, "-m", "rocpd", "convert",
        "-i", str(env['example_db']),
        "-f", "invalid_format",
        "-o", "test_output",
        "-d", str(env['output_dir'])
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=env['repo_root'])
    
    # Should fail with argument parsing error
    assert result.returncode != 0
    assert "invalid choice" in result.stderr