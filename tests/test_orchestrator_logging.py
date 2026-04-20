import logging
import unittest
from pathlib import Path

import orchestrator_logging


class OrchestratorLoggingTests(unittest.TestCase):
    def test_build_handlers_returns_file_and_console_handlers(self):
        handlers = orchestrator_logging.build_handlers(Path("log/test_orchestrator.txt"))

        self.assertEqual(len(handlers), 2)
        self.assertIsInstance(handlers[0], logging.FileHandler)
        self.assertIsInstance(handlers[1], logging.StreamHandler)
        self.assertIsInstance(handlers[0].formatter, orchestrator_logging.PlainFormatter)
        self.assertIsInstance(
            handlers[1].formatter, orchestrator_logging.ColorConsoleFormatter
        )

        for handler in handlers:
            handler.close()

    def test_console_formatter_colors_ok_warning_and_errors(self):
        formatter = orchestrator_logging.ColorConsoleFormatter(
            "%(levelname)s - %(message)s"
        )

        ok_record = logging.LogRecord(
            name="run_all",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="✓ prepare.py — OK (0.0 сек)",
            args=(),
            exc_info=None,
        )
        warning_record = logging.LogRecord(
            name="run_all",
            level=logging.WARNING,
            pathname=__file__,
            lineno=20,
            msg="⚠ step warning",
            args=(),
            exc_info=None,
        )
        error_record = logging.LogRecord(
            name="run_all",
            level=logging.ERROR,
            pathname=__file__,
            lineno=30,
            msg="✗ step error",
            args=(),
            exc_info=None,
        )

        ok_message = formatter.format(ok_record)
        warning_message = formatter.format(warning_record)
        error_message = formatter.format(error_record)

        self.assertIn(orchestrator_logging.GREEN, ok_message)
        self.assertIn(orchestrator_logging.YELLOW, warning_message)
        self.assertIn(orchestrator_logging.RED, error_message)
        self.assertTrue(ok_message.endswith(orchestrator_logging.RESET))
        self.assertTrue(warning_message.endswith(orchestrator_logging.RESET))
        self.assertTrue(error_message.endswith(orchestrator_logging.RESET))

    def test_file_formatter_does_not_add_ansi_codes(self):
        formatter = orchestrator_logging.PlainFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="run_all",
            level=logging.ERROR,
            pathname=__file__,
            lineno=40,
            msg="✗ trade step error",
            args=(),
            exc_info=None,
        )

        message = formatter.format(record)

        self.assertEqual(message, "ERROR - ✗ trade step error")
        self.assertNotIn("\033[", message)


if __name__ == "__main__":
    unittest.main()
