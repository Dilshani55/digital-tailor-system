#!/usr/bin/env python3
"""
test_official_image_acquisition.py

Unit tests for Milestone M7 official Fashionpedia image acquisition and verification pipeline.

Runs with:
python -m unittest discover -s ai_training/tests -p "test_*.py" -v
"""

import json
import os
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import MagicMock, patch
from PIL import Image

from ai_training.scripts.download_fashionpedia_images import download_file, compute_sha256
from ai_training.scripts.extract_fashionpedia_images import validate_archive_paths, validate_zip_file
from ai_training.scripts.verify_fashionpedia_images import verify_image_file


class TestOfficialImageAcquisition(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_unsafe_zip_path_rejection(self):
        """Test that ZIP members with '..' traversal or absolute paths are rejected."""
        zip_path = os.path.join(self.temp_dir, "unsafe.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../etc/passwd", b"unsafe content")
            zf.writestr("safe_folder/image.jpg", b"dummy image bytes")

        with zipfile.ZipFile(zip_path, "r") as zf:
            is_safe, err_msg, members = validate_archive_paths(zf)
            self.assertFalse(is_safe)
            self.assertIn("unsafe path", err_msg.lower())

    def test_corrupt_zip_detection(self):
        """Test that zipfile testzip() catches corrupted ZIP archives."""
        corrupt_zip = os.path.join(self.temp_dir, "corrupt.zip")
        with open(corrupt_zip, "wb") as f:
            f.write(b"PK\x03\x04 corrupt zip bytes data 1234567890")

        is_valid, summary = validate_zip_file(corrupt_zip)
        self.assertFalse(is_valid)
        self.assertIn("error", summary)

    def test_exact_dimension_match(self):
        """Test that matching image dimensions yield exact_match."""
        img_path = os.path.join(self.temp_dir, "sample.jpg")
        img = Image.new("RGB", (640, 480), color="red")
        img.save(img_path, format="JPEG")

        status, dec_w, dec_h, details = verify_image_file(img_path, expected_w=640, expected_h=480)
        self.assertEqual(status, "exact_match")
        self.assertEqual(dec_w, 640)
        self.assertEqual(dec_h, 480)

    def test_width_height_mismatch(self):
        """Test that mismatching image dimensions yield dimension mismatches."""
        img_path = os.path.join(self.temp_dir, "mismatch.jpg")
        img = Image.new("RGB", (640, 480), color="blue")
        img.save(img_path, format="JPEG")

        # Width mismatch
        status, dec_w, dec_h, details = verify_image_file(img_path, expected_w=800, expected_h=480)
        self.assertEqual(status, "width_mismatch")

        # Height mismatch
        status, dec_w, dec_h, details = verify_image_file(img_path, expected_w=640, expected_h=600)
        self.assertEqual(status, "height_mismatch")

    def test_missing_image_handling(self):
        """Test that non-existent file path yields missing_file."""
        missing_path = os.path.join(self.temp_dir, "nonexistent.jpg")
        status, dec_w, dec_h, details = verify_image_file(missing_path, expected_w=100, expected_h=100)
        self.assertEqual(status, "missing_file")

    def test_corrupt_image_handling(self):
        """Test that corrupted image bytes yield corrupt_file."""
        corrupt_img = os.path.join(self.temp_dir, "bad_image.jpg")
        with open(corrupt_img, "wb") as f:
            f.write(b"not an image file bytes")

        status, dec_w, dec_h, details = verify_image_file(corrupt_img, expected_w=100, expected_h=100)
        self.assertEqual(status, "corrupt_file")

    @patch("urllib.request.urlopen")
    @patch("ai_training.scripts.download_fashionpedia_images.fetch_head_metadata")
    def test_download_resume_logic(self, mock_head, mock_urlopen):
        """Test HTTP Range resume logic with a mocked server response."""
        mock_head.return_value = {
            "total_size": 100,
            "supports_range": True,
            "etag": "mock-etag",
            "last_modified": "Sat, 06 Jun 2020 06:21:33 GMT",
            "http_status": 200,
        }

        # Create a partial .part file with 40 bytes
        part_path = os.path.join(self.temp_dir, "test.zip.part")
        with open(part_path, "wb") as f:
            f.write(b"X" * 40)

        mock_resp = MagicMock()
        mock_resp.status = 206
        mock_resp.read.side_effect = [b"Y" * 60, b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        target_zip = os.path.join(self.temp_dir, "test.zip")
        success, meta = download_file(
            url="https://s3.amazonaws.com/ifashionist-dataset/images/val_test2020.zip",
            target_zip_path=target_zip,
            allow_resume=True,
            chunk_size=1024,
        )

        self.assertTrue(success)
        self.assertTrue(os.path.exists(target_zip))
        self.assertEqual(os.path.getsize(target_zip), 100)
        self.assertEqual(meta["file_size"], 100)


if __name__ == "__main__":
    unittest.main()
