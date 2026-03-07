"""
Unit tests for the centralized configuration module.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config


class TestConfig(unittest.TestCase):
    """Verify default values and types from config.py."""

    def test_flask_host(self):
        self.assertEqual(config.FLASK_HOST, "0.0.0.0")

    def test_flask_port_is_int(self):
        self.assertIsInstance(config.FLASK_PORT, int)
        self.assertEqual(config.FLASK_PORT, 5000)

    def test_max_upload_size(self):
        self.assertEqual(config.MAX_UPLOAD_SIZE_MB, 500)
        self.assertEqual(config.MAX_CONTENT_LENGTH, 500 * 1024 * 1024)

    def test_ollama_defaults(self):
        self.assertEqual(config.OLLAMA_URL, "http://localhost:11434")
        self.assertEqual(config.OLLAMA_MODEL, "llama3.2:3b")

    def test_algorithm_timeout(self):
        self.assertIsInstance(config.ALGORITHM_TIMEOUT, int)
        self.assertGreater(config.ALGORITHM_TIMEOUT, 0)

    def test_sft_default_model(self):
        self.assertIn("TinyLlama", config.SFT_DEFAULT_MODEL)

    def test_interaction_history_file_path(self):
        self.assertTrue(config.INTERACTION_HISTORY_FILE.endswith(".json"))


if __name__ == "__main__":
    unittest.main()
