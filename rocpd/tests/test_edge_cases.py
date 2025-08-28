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
from rocpd.importer import RocpdImportData


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before all tests."""
        cls.repo_root = Path(__file__).parent.parent.parent
        cls.example_db = cls.repo_root / "examples" / "24228_results.db"
        
        # Create temporary directories for test outputs
        cls.temp_dir = tempfile.mkdtemp(prefix="rocpd_edge_test_")
        cls.test_data_dir = Path(cls.temp_dir) / "test_data"
        cls.output_dir = Path(cls.temp_dir) / "output"
        cls.test_data_dir.mkdir(exist_ok=True)
        cls.output_dir.mkdir(exist_ok=True)
        
        # Create test databases for edge cases
        cls._create_test_databases()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        if hasattr(cls, 'temp_dir') and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)
    
    @classmethod
    def _create_test_databases(cls):
        """Create various test databases for edge case testing."""
        # Empty database
        cls.empty_db = cls.test_data_dir / "empty.db"
        conn = sqlite3.connect(cls.empty_db)
        conn.close()
        
        # Database with ROCpd tables but no data
        cls.empty_rocpd_db = cls.test_data_dir / "empty_rocpd.db"
        conn = sqlite3.connect(cls.empty_rocpd_db)
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
        
        # Small database with minimal data
        cls.small_db = cls.test_data_dir / "small.db"
        conn = sqlite3.connect(cls.small_db)
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
        
        # Invalid (non-SQLite) file
        cls.invalid_db = cls.test_data_dir / "invalid.db"
        with open(cls.invalid_db, 'w') as f:
            f.write("This is not a SQLite database file")
        
        # Corrupted SQLite file
        cls.corrupted_db = cls.test_data_dir / "corrupted.db"
        with open(cls.corrupted_db, 'wb') as f:
            f.write(b'SQLite format 3\x00' + b'\x00' * 100)  # Invalid SQLite header
    
    def setUp(self):
        """Set up before each test."""
        # Clean output directory for each test
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def test_missing_input_file(self):
        """Test handling of missing input files."""
        nonexistent_file = self.test_data_dir / "nonexistent.db"
        
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(nonexistent_file),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should fail with appropriate error message
        self.assertNotEqual(result.returncode, 0)
        # Error message should mention the missing file
        error_text = result.stderr.lower()
        self.assertTrue(
            "not found" in error_text or 
            "no such file" in error_text or
            "does not exist" in error_text,
            f"Should report missing file error, got: {result.stderr}"
        )
    
    def test_missing_input_file_api(self):
        """Test Python API handling of missing input files."""
        nonexistent_file = str(self.test_data_dir / "nonexistent.db")
        
        with self.assertRaises((FileNotFoundError, ValueError, OSError)):
            RocpdImportData([nonexistent_file])
    
    def test_invalid_database_file(self):
        """Test handling of invalid (non-SQLite) database files."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.invalid_db),
            "-f", "ctf", 
            "-o", "test_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should fail with database error
        self.assertNotEqual(result.returncode, 0)
        error_text = result.stderr.lower()
        self.assertTrue(
            "database" in error_text or 
            "sqlite" in error_text or
            "invalid" in error_text,
            f"Should report database error, got: {result.stderr}"
        )
    
    def test_invalid_database_file_api(self):
        """Test Python API handling of invalid database files."""
        with self.assertRaises((sqlite3.DatabaseError, sqlite3.OperationalError, ValueError)):
            RocpdImportData([str(self.invalid_db)])
    
    def test_corrupted_database_file(self):
        """Test handling of corrupted SQLite database files."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.corrupted_db),
            "-f", "ctf",
            "-o", "test_output", 
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should fail with database error
        self.assertNotEqual(result.returncode, 0)
        error_text = result.stderr.lower()
        self.assertTrue(
            "database" in error_text or
            "corrupted" in error_text or
            "malformed" in error_text,
            f"Should report corrupted database error, got: {result.stderr}"
        )
    
    def test_corrupted_database_file_api(self):
        """Test Python API handling of corrupted database files."""
        with self.assertRaises((sqlite3.DatabaseError, sqlite3.OperationalError)):
            RocpdImportData([str(self.corrupted_db)])
    
    def test_empty_database_file(self):
        """Test handling of empty database files."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.empty_db),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # May succeed or fail depending on implementation
        # If it fails, should be due to missing ROCpd tables
        if result.returncode != 0:
            error_text = result.stderr.lower()
            self.assertTrue(
                "table" in error_text or
                "rocpd" in error_text or
                "empty" in error_text,
                f"Should report table/schema error for empty database, got: {result.stderr}"
            )
    
    def test_empty_rocpd_database(self):
        """Test handling of database with ROCpd tables but no data."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.empty_rocpd_db),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should handle empty tables gracefully
        # Result depends on implementation - may succeed with empty output or fail
        if result.returncode == 0:
            # If successful, output should exist but may be minimal
            pass
        else:
            # If it fails, should be graceful
            error_text = result.stderr.lower()
            self.assertFalse(
                "traceback" in error_text or "exception" in error_text,
                f"Should fail gracefully without exceptions, got: {result.stderr}"
            )
    
    def test_small_database(self):
        """Test handling of small database with minimal data."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should handle small databases gracefully
        # May succeed or fail depending on barectf availability
        if result.returncode != 0:
            # Should not crash with exceptions
            error_text = result.stderr.lower()
            self.assertFalse(
                "traceback" in error_text,
                f"Should not crash with exceptions, got: {result.stderr}"
            )
    
    def test_missing_required_arguments(self):
        """Test handling of missing required command line arguments."""
        # Missing input file
        cmd = [sys.executable, "-m", "rocpd", "convert", "-f", "ctf"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required", result.stderr.lower())
        
        # Missing format
        cmd = [sys.executable, "-m", "rocpd", "convert", "-i", str(self.small_db)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required", result.stderr.lower())
    
    def test_invalid_output_directory(self):
        """Test handling of invalid output directory."""
        # Try to write to a file instead of directory
        invalid_output = self.test_data_dir / "invalid.db"  # This is a file, not directory
        
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(invalid_output)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should fail with appropriate error
        if result.returncode != 0:
            error_text = result.stderr.lower()
            self.assertTrue(
                "directory" in error_text or
                "path" in error_text or
                "permission" in error_text,
                f"Should report path/directory error, got: {result.stderr}"
            )
    
    def test_multiple_input_files_with_missing(self):
        """Test multiple input files where some are missing."""
        nonexistent_file = self.test_data_dir / "nonexistent.db"
        
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db), str(nonexistent_file),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should fail due to missing file
        self.assertNotEqual(result.returncode, 0)
        error_text = result.stderr.lower()
        self.assertTrue(
            "not found" in error_text or 
            "no such file" in error_text or
            "does not exist" in error_text,
            f"Should report missing file error, got: {result.stderr}"
        )
    
    def test_multiple_valid_input_files(self):
        """Test multiple valid input files."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.small_db), str(self.empty_rocpd_db),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should handle multiple files gracefully
        # May succeed or fail depending on barectf availability
        if result.returncode != 0:
            # Should not crash with exceptions
            error_text = result.stderr.lower()
            self.assertFalse(
                "traceback" in error_text,
                f"Should not crash with exceptions, got: {result.stderr}"
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)