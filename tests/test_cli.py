import unittest
from unittest.mock import MagicMock, patch

from mimictype import cli


class TestCLIParserAndDispatch(unittest.TestCase):
    def test_direct_text_positional(self):
        args = cli.parse_args(["Hello world"])
        self.assertIsNone(args.subcommand)
        self.assertEqual(args.text, "Hello world")

    def test_direct_flags_only(self):
        args = cli.parse_args(["-w", "333", "-d", "3"])
        self.assertIsNone(args.subcommand)
        self.assertEqual(args.wpm, 333)
        self.assertEqual(args.delay, 3.0)
        self.assertIsNone(args.text)

    def test_direct_literal_subcommand_word(self):
        args_dashdash = cli.parse_args(["--", "daemon"])
        self.assertIsNone(args_dashdash.subcommand)
        self.assertEqual(args_dashdash.text, "daemon")

        args_flag = cli.parse_args(["--text", "trigger", "-d", "0"])
        self.assertIsNone(args_flag.subcommand)
        self.assertEqual(args_flag.text_override, "trigger")
        self.assertEqual(args_flag.delay, 0.0)

    def test_trigger_preserves_text(self):
        args = cli.parse_args(["trigger", "текст"])
        self.assertEqual(args.subcommand, "trigger")
        self.assertEqual(args.text, "текст")

        args_empty = cli.parse_args(["trigger"])
        self.assertEqual(args_empty.subcommand, "trigger")
        self.assertIsNone(args_empty.text)

    def test_daemon_stop_status_subcommands(self):
        args_daemon = cli.parse_args(
            ["daemon", "--hotkey", "ctrl+alt+t", "-w", "90", "--preset", "fast"]
        )
        self.assertEqual(args_daemon.subcommand, "daemon")
        self.assertEqual(args_daemon.hotkey, "ctrl+alt+t")
        self.assertEqual(args_daemon.wpm, 90)
        self.assertEqual(args_daemon.preset, "fast")

        self.assertEqual(cli.parse_args(["stop"]).subcommand, "stop")
        self.assertEqual(cli.parse_args(["status"]).subcommand, "status")

    def test_main_dispatches_trigger_with_text(self):
        with patch("mimictype.cli.run_ipc_command") as mock_ipc:
            cli.main(["trigger", "текст"])
            mock_ipc.assert_called_once_with("TYPE", {"text": "текст"})

    def test_main_dispatches_trigger_without_text(self):
        with patch("mimictype.cli.run_ipc_command") as mock_ipc:
            cli.main(["trigger"])
            mock_ipc.assert_called_once_with("TYPE", None)

    def test_main_dispatches_direct_typing(self):
        with patch("mimictype.cli.run_direct_typing") as mock_direct:
            cli.main(["Hello world", "-w", "120", "-d", "0.5"])
            mock_direct.assert_called_once()
            args, cfg = mock_direct.call_args[0]
            self.assertEqual(args.text, "Hello world")
            self.assertEqual(args.delay, 0.5)
            self.assertEqual(cfg.wpm, 120)

    def test_fractional_delay_sleeps_remainder(self):
        args = cli.parse_args(["Hello", "-d", "0.25"])
        cfg = cli.MimicConfig()
        mock_engine = MagicMock()
        mock_engine.type_text.return_value = True
        mock_engine.__enter__.return_value = mock_engine
        mock_engine.__exit__.return_value = False

        with (
            patch("mimictype.cli.TyperEngine", return_value=mock_engine),
            patch("mimictype.cli.HotkeyListener") as mock_listener_cls,
            patch("mimictype.cli.time.sleep") as mock_sleep,
        ):
            cli.run_direct_typing(args, cfg)
            mock_sleep.assert_called_once_with(0.25)
            mock_listener_cls.return_value.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
