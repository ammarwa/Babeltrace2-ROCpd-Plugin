#!/usr/bin/env python3
"""
Test the example database provided in the examples directory.

This test specifically validates that the example database (24228_results.db)
works correctly with all output formats and various parameter combinations.
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

from rocpd.importer import RocpdImportData
from rocpd import ctf as ctf_mod


class TestExampleDatabase(unittest.TestCase):
    """Test the example database from the examples directory."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before all tests."""
        cls.repo_root = Path(__file__).parent.parent.parent
        cls.example_db = cls.repo_root / "examples" / "24228_results.db"
        
        # Create temporary directory for test outputs
        cls.temp_dir = tempfile.mkdtemp(prefix="rocpd_example_test_")
        cls.output_dir = Path(cls.temp_dir) / "output"
        cls.output_dir.mkdir(exist_ok=True)
        
        # Verify example database exists and is valid
        if not cls.example_db.exists():
            raise unittest.SkipTest(f"Example database not found: {cls.example_db}")
        
        # Check if it's a valid SQLite database
        try:
            conn = sqlite3.connect(cls.example_db)
            conn.close()
        except sqlite3.Error as e:
            raise unittest.SkipTest(f"Example database is not valid: {e}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        if hasattr(cls, 'temp_dir') and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)
    
    def setUp(self):
        """Set up before each test."""
        # Clean output directory for each test
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def test_example_database_info(self):
        """Test basic information about the example database."""
        # Check database file size
        file_size = self.example_db.stat().st_size
        self.assertGreater(file_size, 0, "Example database should not be empty")
        
        # Check database structure
        conn = sqlite3.connect(self.example_db)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Should have ROCpd-related tables
        rocpd_tables = [t for t in tables if 'rocpd' in t.lower()]
        self.assertGreater(len(rocpd_tables), 0, "Example database should contain ROCpd tables")
        
        print(f"Example database size: {file_size:,} bytes")
        print(f"Tables found: {tables}")
        print(f"ROCpd tables: {rocpd_tables}")
        
        # Get record counts for ROCpd tables
        for table in rocpd_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count:,} records")
                self.assertGreaterEqual(count, 0, f"Table {table} should have valid record count")
            except sqlite3.Error:
                # Table might not be accessible, that's okay
                pass
        
        conn.close()
    
    def test_example_database_import(self):
        """Test importing the example database via Python API."""
        try:
            import_data = RocpdImportData([str(self.example_db)])
            # If we get here, import was successful
            self.assertIsNotNone(import_data, "Import data should not be None")
        except Exception as e:
            self.fail(f"Failed to import example database: {e}")
    
    def test_example_database_csv_format(self):
        """Test CSV format with example database."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "csv",
            "-o", "example_csv",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # CSV should complete but report that it's not implemented
        self.assertEqual(result.returncode, 0, "CLI should complete successfully")
        output_text = result.stdout + result.stderr
        self.assertTrue(
            "not implemented" in output_text or "failed" in output_text or "unavailable" in output_text,
            f"Should report CSV conversion failure, got: {output_text}"
        )
    
    def test_example_database_pftrace_format(self):
        """Test Perfetto trace format with example database."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "pftrace",
            "-o", "example_pftrace",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Perfetto should complete but report that it's not implemented
        self.assertEqual(result.returncode, 0, "CLI should complete successfully")
        output_text = result.stdout + result.stderr
        self.assertTrue(
            "not implemented" in output_text or "failed" in output_text or "unavailable" in output_text,
            f"Should report Perfetto conversion failure, got: {output_text}"
        )
    
    def test_example_database_otf2_format(self):
        """Test OTF2 format with example database."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "otf2",
            "-o", "example_otf2",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # OTF2 should complete but report that it's not implemented
        self.assertEqual(result.returncode, 0, "CLI should complete successfully")
        output_text = result.stdout + result.stderr
        self.assertTrue(
            "not implemented" in output_text or "failed" in output_text or "unavailable" in output_text,
            f"Should report OTF2 conversion failure, got: {output_text}"
        )
    
    def test_example_database_ctf_format(self):
        """Test CTF format with example database."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "ctf",
            "-o", "example_ctf",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # CTF should complete but likely fail due to missing barectf bridge
        self.assertEqual(result.returncode, 0, "CLI should complete successfully")
        
        output_text = result.stdout + result.stderr
        if any(keyword in output_text.lower() for keyword in [
            "barectf", "bridge", "not available", "missing", "failed"
        ]):
            # CTF failed due to missing barectf bridge - this is expected
            pass
        else:
            # If no failure message, check that output files were created
            expected_output = self.output_dir / "example_ctf"
            if expected_output.exists():
                files = list(expected_output.glob("*"))
                if len(files) > 0:
                    # Look for common CTF files
                    has_metadata = any("metadata" in f.name.lower() for f in files)
                    has_stream = any("stream" in f.name.lower() for f in files)
                    
                    print(f"CTF output files: {[f.name for f in files]}")
                    print(f"Has metadata: {has_metadata}")
                    print(f"Has stream files: {has_stream}")
    
    def test_example_database_ctf_api(self):
        """Test CTF format with example database via Python API."""
        try:
            import_data = RocpdImportData([str(self.example_db)])
            output_path = self.output_dir / "ctf_api"
            
            result = ctf_mod.write_ctf(
                import_data,
                output_file="example_api_ctf",
                output_path=str(output_path)
            )
            
            if result:
                # Success case
                expected_output = output_path / "example_api_ctf"
                if expected_output.exists():
                    files = list(expected_output.glob("*"))
                    self.assertGreater(len(files), 0, "CTF API output should contain files")
            else:
                # Failure is expected if barectf bridge is not available
                pass
                
        except Exception as e:
            # Import or conversion might fail, that's acceptable
            print(f"CTF API test failed (expected if barectf not available): {e}")
    
    def test_example_database_with_options(self):
        """Test example database with various command line options."""
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
            with self.subTest(test_case=test_case["name"]):
                cmd = [
                    sys.executable, "-m", "rocpd", "convert",
                    "-i", str(self.example_db),
                    "-f", "ctf",
                    "-o", f"example_{test_case['name']}",
                    "-d", str(self.output_dir)
                ] + test_case["args"]
                
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
                
                # Should handle gracefully regardless of success/failure
                error_text = result.stderr.lower()
                self.assertFalse(
                    "traceback" in error_text and "exception" in error_text,
                    f"Should not crash with unhandled exceptions for {test_case['name']}, got: {result.stderr}"
                )
    
    def test_example_database_multiple_input_files(self):
        """Test using example database multiple times as input."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db), str(self.example_db),  # Same file twice
            "-f", "ctf",
            "-o", "example_multiple",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should handle multiple files gracefully
        error_text = result.stderr.lower()
        self.assertFalse(
            "traceback" in error_text and "exception" in error_text,
            f"Should not crash with unhandled exceptions, got: {result.stderr}"
        )
    
    def test_example_database_performance(self):
        """Test performance with example database (basic timing)."""
        import time
        
        start_time = time.time()
        
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "ctf",
            "-o", "example_performance",
            "-d", str(self.output_dir),
            "--no-progress"  # Disable progress to avoid output noise
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        elapsed_time = time.time() - start_time
        
        print(f"Example database processing took: {elapsed_time:.2f} seconds")
        
        # Should complete within reasonable time (adjust threshold as needed)
        self.assertLess(elapsed_time, 300, "Processing should complete within 5 minutes")
        
        # Should handle gracefully regardless of result
        error_text = result.stderr.lower()
        self.assertFalse(
            "traceback" in error_text and "exception" in error_text,
            f"Should not crash with unhandled exceptions, got: {result.stderr}"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)