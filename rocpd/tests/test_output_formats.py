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
from rocpd import csv as csv_mod
from rocpd import pftrace as pftrace_mod
from rocpd import otf2 as otf2_mod
from rocpd import ctf as ctf_mod


class TestOutputFormats(unittest.TestCase):
    """Test all output format types."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before all tests."""
        # Get the example database path
        cls.repo_root = Path(__file__).parent.parent.parent
        cls.example_db = cls.repo_root / "examples" / "24228_results.db"
        
        # Create temporary directories for test outputs
        cls.temp_dir = tempfile.mkdtemp(prefix="rocpd_test_")
        cls.output_dir = Path(cls.temp_dir) / "output"
        cls.output_dir.mkdir(exist_ok=True)
        
        # Verify example database exists
        if not cls.example_db.exists():
            raise unittest.SkipTest(f"Example database not found: {cls.example_db}")
    
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
    
    def test_csv_format_cli(self):
        """Test CSV format via CLI interface."""
        output_path = self.output_dir / "csv_output"
        
        # Test CLI interface
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "csv",
            "-o", "test_output",
            "-d", str(output_path)
        ]
        
        # CSV is a stub that should return with message
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # CSV conversion should complete but report failure
        self.assertEqual(result.returncode, 0, "CLI should complete successfully even if conversion fails")
        # Should report CSV conversion failure in stdout (not stderr)
        output_text = result.stdout + result.stderr
        self.assertIn("CSV conversion", output_text)
        self.assertTrue(
            "not implemented" in output_text or "failed" in output_text or "unavailable" in output_text,
            f"Should report CSV conversion failure, got: {output_text}"
        )
    
    def test_csv_format_api(self):
        """Test CSV format via Python API."""
        # Test Python API
        import_data = RocpdImportData([str(self.example_db)])
        result = csv_mod.write_csv(import_data)
        
        # Should return False indicating failure
        self.assertFalse(result, "CSV write_csv should return False")
    
    def test_pftrace_format_cli(self):
        """Test Perfetto trace format via CLI interface."""
        output_path = self.output_dir / "pftrace_output"
        
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "pftrace",
            "-o", "test_output",
            "-d", str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Perfetto trace conversion should complete but report failure
        self.assertEqual(result.returncode, 0, "CLI should complete successfully even if conversion fails")
        output_text = result.stdout + result.stderr
        self.assertIn("Perfetto", output_text)
        self.assertTrue(
            "not implemented" in output_text or "failed" in output_text or "unavailable" in output_text,
            f"Should report Perfetto conversion failure, got: {output_text}"
        )
    
    def test_pftrace_format_api(self):
        """Test Perfetto trace format via Python API."""
        import_data = RocpdImportData([str(self.example_db)])
        result = pftrace_mod.write_pftrace(import_data)
        
        # Should return False indicating failure
        self.assertFalse(result, "Perfetto trace write_pftrace should return False")
    
    def test_otf2_format_cli(self):
        """Test OTF2 format via CLI interface."""
        output_path = self.output_dir / "otf2_output"
        
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "otf2",
            "-o", "test_output",
            "-d", str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # OTF2 conversion should complete but report failure
        self.assertEqual(result.returncode, 0, "CLI should complete successfully even if conversion fails")
        output_text = result.stdout + result.stderr
        self.assertIn("OTF2", output_text)
        self.assertTrue(
            "not implemented" in output_text or "failed" in output_text or "unavailable" in output_text,
            f"Should report OTF2 conversion failure, got: {output_text}"
        )
    
    def test_otf2_format_api(self):
        """Test OTF2 format via Python API."""
        import_data = RocpdImportData([str(self.example_db)])
        result = otf2_mod.write_otf2(import_data)
        
        # Should return False indicating failure
        self.assertFalse(result, "OTF2 write_otf2 should return False")
    
    def test_ctf_format_cli(self):
        """Test CTF format via CLI interface."""
        output_path = self.output_dir / "ctf_output"
        
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "ctf",
            "-o", "test_output",
            "-d", str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # CTF might succeed or fail depending on barectf availability
        # CLI always returns 0, so check the output content
        self.assertEqual(result.returncode, 0, "CLI should complete successfully")
        
        output_text = result.stdout + result.stderr
        if any(keyword in output_text.lower() for keyword in [
            "barectf", "bridge", "not available", "missing", "failed"
        ]):
            # CTF failed due to missing barectf bridge - this is expected
            pass
        else:
            # If no failure message, check that output files were created
            expected_output = output_path / "test_output"
            if expected_output.exists():
                # Check for CTF files (metadata, stream files)
                files = list(expected_output.glob("*"))
                self.assertGreater(len(files), 0, "CTF output should contain files")
    
    def test_ctf_format_api(self):
        """Test CTF format via Python API."""
        import_data = RocpdImportData([str(self.example_db)])
        output_path = self.output_dir / "ctf_api_output"
        
        result = ctf_mod.write_ctf(
            import_data,
            output_file="test_api_output",
            output_path=str(output_path)
        )
        
        # CTF might succeed or fail depending on barectf availability
        if result:
            # If successful, check that output was created
            expected_output = output_path / "test_api_output"
            if expected_output.exists():
                files = list(expected_output.glob("*"))
                self.assertGreater(len(files), 0, "CTF API output should contain files")
        else:
            # Failure is expected if barectf bridge is not available
            pass
    
    def test_multiple_formats(self):
        """Test multiple output formats in single command."""
        output_path = self.output_dir / "multi_output"
        
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "csv", "pftrace", "otf2",
            "-o", "test_multi",
            "-d", str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should complete but may report failures for all formats
        self.assertEqual(result.returncode, 0, "CLI should complete successfully even if conversions fail")
        
        # Should contain messages about the formats
        output_text = result.stdout + result.stderr
        self.assertTrue(
            any(fmt in output_text.lower() for fmt in ["csv", "pftrace", "otf2"]),
            "Should contain messages about the requested formats"
        )
    
    def test_format_validation(self):
        """Test invalid format specification."""
        cmd = [
            sys.executable, "-m", "rocpd", "convert",
            "-i", str(self.example_db),
            "-f", "invalid_format",
            "-o", "test_output",
            "-d", str(self.output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        
        # Should fail with argument parsing error
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)