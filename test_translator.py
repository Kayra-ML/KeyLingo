#!/usr/bin/env python3
"""
Test suite for macOS Global Translator.
Verifies config parsing, error sanitization, safety logic, and hotkey state machine.
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add translator dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    Config,
    DeepLService,
    ClipboardManager,
    TranslationCoordinator,
    GlobalHotkeyListener,
    VK_LEFT_ARROW,
    VK_RIGHT_ARROW,
    MAGIC_EVENT_TAG
)


class TestConfig(unittest.TestCase):
    def test_e_keycodes_parsing(self):
        with patch.dict(os.environ, {"E_KEYCODES": "10,50, 99", "DEEPL_AUTH_KEY": "fake-key"}):
            cfg = Config()
            self.assertIn(10, cfg.e_keycodes)
            self.assertIn(50, cfg.e_keycodes)
            self.assertIn(99, cfg.e_keycodes)
            self.assertIn("é", cfg.e_chars)


class TestDeepLService(unittest.TestCase):
    def test_key_sanitization(self):
        secret_key = "abc12345-secret-key"
        service = DeepLService.__new__(DeepLService)
        service.auth_key = secret_key
        
        raw_error = f"HTTP 403 Forbidden with auth token {secret_key} on endpoint"
        sanitized = service.sanitize_error(raw_error)
        self.assertNotIn(secret_key, sanitized)
        self.assertIn("[REDACTED_API_KEY]", sanitized)


class TestTranslationCoordinator(unittest.TestCase):
    def setUp(self):
        self.mock_deepl = MagicMock()
        self.coordinator = TranslationCoordinator(self.mock_deepl)

    @patch("main.ClipboardManager.get_text")
    @patch("main.ClipboardManager.set_text")
    @patch("main.ClipboardManager.get_change_count")
    def test_empty_input_does_nothing(self, mock_count, mock_set, mock_get):
        # When clipboard doesn't change after Cmd+C (empty field)
        mock_count.return_value = 10
        mock_get.return_value = ""
        
        self.coordinator.keyboard.select_all = MagicMock()
        self.coordinator.keyboard.copy = MagicMock()
        self.coordinator.keyboard.paste = MagicMock()

        self.coordinator._execute_flow("TR->EN")
        
        # DeepL should not be called
        self.mock_deepl.translate.assert_not_called()
        # Paste should not be called
        self.coordinator.keyboard.paste.assert_not_called()

    @patch("main.ClipboardManager.get_text")
    @patch("main.ClipboardManager.set_text")
    @patch("main.ClipboardManager.get_change_count")
    def test_api_failure_preserves_original_text(self, mock_count, mock_set, mock_get):
        original_text = "bu silinmemesi gereken orijinal metin"
        # Mock change count increments (something was copied)
        mock_count.side_effect = [10, 11, 11]
        mock_get.side_effect = ["old_clip", original_text]
        
        # API returns None (failure)
        self.mock_deepl.translate.return_value = None

        self.coordinator.keyboard.select_all = MagicMock()
        self.coordinator.keyboard.copy = MagicMock()
        self.coordinator.keyboard.paste = MagicMock()

        self.coordinator._execute_flow("TR->EN")

        # Crucial safety check: paste was NOT called! Text is intact!
        self.coordinator.keyboard.paste.assert_not_called()
        # Old clipboard was restored
        mock_set.assert_called_with("old_clip")

    @patch("main.ClipboardManager.get_text")
    @patch("main.ClipboardManager.set_text")
    @patch("main.ClipboardManager.get_change_count")
    def test_successful_translation_flow(self, mock_count, mock_set, mock_get):
        original_clipboard = "önceki pano içeriği"
        user_input_text = "Merhaba dünya"
        translated_output = "Hello world"

        mock_count.side_effect = [10, 11, 11]
        mock_get.side_effect = [original_clipboard, user_input_text]
        self.mock_deepl.translate.return_value = translated_output

        self.coordinator.keyboard.select_all = MagicMock()
        self.coordinator.keyboard.copy = MagicMock()
        self.coordinator.keyboard.paste = MagicMock()

        self.coordinator._execute_flow("TR->EN")

        # API called with TR -> EN-US
        self.mock_deepl.translate.assert_called_with(
            user_input_text, source_lang="TR", target_lang="EN-US"
        )
        # Paste was called
        self.coordinator.keyboard.paste.assert_called_once()
        # Clipboard was restored to original after pasting
        self.assertEqual(mock_set.call_args_list[-1][0][0], original_clipboard)


class TestGlobalHotkeyListenerLogic(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.e_keycodes = {10, 50}
        self.config.e_chars = {"é", "É"}
        self.mock_coord = MagicMock()
        self.listener = GlobalHotkeyListener(self.config, self.mock_coord)

    def test_is_trigger_key_detection(self):
        # Keycode 10 should be trigger
        self.assertTrue(self.listener.is_trigger_key(10, '"', 0))
        # Char 'é' should be trigger
        self.assertTrue(self.listener.is_trigger_key(14, 'é', 0))
        # Unrelated key should not be trigger
        self.assertFalse(self.listener.is_trigger_key(40, 'k', 0))
        # Cmd + E should not be trigger (system shortcut)
        import Quartz
        self.assertFalse(self.listener.is_trigger_key(10, 'é', Quartz.kCGEventFlagMaskCommand))


if __name__ == "__main__":
    unittest.main()
