import argparse
import logging
import signal
import sys
import time
from typing import List, Optional
from mimictype.config import MimicConfig
from mimictype.core.clipboard import ClipboardReader
from mimictype.core.daemon import MimicDaemon
from mimictype.core.engine import TyperEngine
from mimictype.core.ipc import IPCClient
from mimictype.core.listener import HotkeyListener


def render_progress_bar(current: int, total: int, width: int = 30) -> str:
    if total <= 0:
        return "[------------------------------] 0%"
    pct = min(1.0, current / total)
    filled = int(round(width * pct))
    bar = "=" * filled + (">" if filled < width else "") + " " * (width - filled - (1 if filled < width else 0))
    return f"[{bar}] {int(pct * 100)}%"


def run_direct_typing(args, cfg: MimicConfig):
    # Get text to type
    text_to_type = None
    explicit_text = getattr(args, "text_override", None)
    if explicit_text is None:
        explicit_text = getattr(args, "text", None)

    if getattr(args, "stdin", False):
        text_to_type = sys.stdin.read()
    elif explicit_text is not None:
        text_to_type = explicit_text
    else:
        text_to_type = ClipboardReader.get_text()

    if not text_to_type:
        print("mimictype: No text found in clipboard or arguments.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] MimicType v0.1.0 (Target: {cfg.wpm} WPM | Humanizer: {'ON' if cfg.humanizer.enabled else 'OFF'})")
    print(f"[*] Text length: {len(text_to_type)} characters.")
    print("    [!] Emergency Kill Switch active: Press ESC or Ctrl+C at any time to abort.\n")

    # Countdown delay to allow switching to target window
    delay = getattr(args, "delay", 3.0)
    if delay > 0:
        whole = int(delay)
        frac = delay - whole
        print(f"[*] Switch focus to target window! Typing begins in {delay:.1f}s:")
        for sec in range(whole, 0, -1):
            sys.stdout.write(f"\r    [{sec}...] ")
            sys.stdout.flush()
            time.sleep(1.0)
        if frac > 0:
            time.sleep(frac)
        sys.stdout.write("\r    [Typing started!]\n\n")
        sys.stdout.flush()

    start_time = time.time()
    typos_count = 0
    backspaces_count = 0

    try:
        with TyperEngine(config=cfg) as engine:
            # Connect local emergency escape listener on physical keyboard
            def emergency_stop():
                sys.stdout.write("\n[!] ESC pressed on physical keyboard! Aborting typing...\n")
                sys.stdout.flush()
                engine.abort()

            hotkey_listener = HotkeyListener(
                on_emergency_stop=emergency_stop,
                ignore_device_names=[cfg.device.name, "mimictype"],
            )
            hotkey_listener.start()

            # Signal handler for terminal Ctrl+C
            def handle_sigint(sig, frame):
                sys.stdout.write("\n[!] Interrupted by terminal signal. Releasing keys...\n")
                sys.stdout.flush()
                engine.abort()
                sys.exit(130)

            signal.signal(signal.SIGINT, handle_sigint)
            signal.signal(signal.SIGTERM, handle_sigint)

            def on_progress(curr, total, char):
                elapsed = max(0.1, time.time() - start_time)
                # Calculate real-time typed WPM (5 chars = 1 word)
                live_wpm = int((curr / 5.0) / (elapsed / 60.0))
                p_bar = render_progress_bar(curr, total)
                sys.stdout.write(f"\r  {p_bar} ({curr}/{total}) | {live_wpm} WPM | Time: {elapsed:.1f}s")
                sys.stdout.flush()

            def on_event(event_type, desc):
                nonlocal typos_count, backspaces_count
                if event_type == "typo":
                    typos_count += 1
                elif event_type == "backspace":
                    backspaces_count += 1

            try:
                success = engine.type_text(text_to_type, on_progress=on_progress, on_event=on_event)
            finally:
                hotkey_listener.stop()

            total_elapsed = time.time() - start_time
            print()
            if success:
                print(f"\n[+] Completed successfully in {total_elapsed:.1f}s!")
                if typos_count > 0:
                    print(f"    (Simulated {typos_count} human typos and auto-corrected them via {backspaces_count} Backspaces)")
            else:
                print(f"\n[!] Typing aborted at {total_elapsed:.1f}s.")
    except PermissionError:
        print("\nmimictype: Permission denied accessing /dev/uinput.", file=sys.stderr)
        print("Ensure your user has write access to /dev/uinput via a udev rule (run ./install.sh or see docs/USAGE.md).", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nmimictype error: {e}", file=sys.stderr)
        sys.exit(1)


def run_daemon(args, cfg: MimicConfig):
    hotkey = getattr(args, "hotkey", "ctrl+alt+v")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    daemon = MimicDaemon(config=cfg, hotkey=hotkey)

    def handle_sigint(sig, frame):
        print("\nStopping daemon...")
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    try:
        daemon.start()
    except RuntimeError as e:
        print(f"mimictype: {e}", file=sys.stderr)
        sys.exit(1)


def run_ipc_command(command: str, payload=None):
    resp = IPCClient.send(command, payload)
    if resp is None:
        print("mimictype daemon is not running.", file=sys.stderr)
        sys.exit(1)
    print(resp)


SUBCOMMANDS = ("daemon", "trigger", "stop", "status")


def _build_subcommand_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mimictype",
        description="Natural Keystroke Dynamics & uinput Virtual Keyboard for Linux.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_daemon = subparsers.add_parser(
        "daemon",
        help="Run background daemon with global hotkey and IPC socket.",
    )
    p_daemon.add_argument(
        "--hotkey",
        type=str,
        default="ctrl+alt+v",
        help="Global activation hotkey (default: ctrl+alt+v)",
    )
    p_daemon.add_argument(
        "-w",
        "--wpm",
        type=int,
        default=None,
        help="Target typing speed in Words Per Minute.",
    )
    p_daemon.add_argument(
        "--preset",
        type=str,
        choices=["natural", "fast", "careful", "instant"],
        help="Typing preset",
    )
    p_daemon.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to custom config YAML.",
    )

    p_trigger = subparsers.add_parser(
        "trigger",
        help="Send signal to running daemon to type clipboard immediately.",
    )
    p_trigger.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Optional text to type (default: clipboard)",
    )

    subparsers.add_parser(
        "stop",
        help="Stop/abort current typing in running daemon.",
    )
    subparsers.add_parser(
        "status",
        help="Get status of running daemon.",
    )
    return parser


def _build_direct_parser() -> argparse.ArgumentParser:
    epilog = (
        "subcommands:\n"
        "  daemon    Run background daemon with global hotkey and IPC socket\n"
        "  trigger   Send text or clipboard trigger to running daemon\n"
        "  stop      Stop/abort current typing in running daemon\n"
        "  status    Get status of running daemon\n\n"
        "examples:\n"
        "  mimictype                       Type clipboard after 3s delay\n"
        '  mimictype "Hello world"         Type inline string directly\n'
        "  mimictype -w 333 -d 3           Type clipboard at 333 WPM\n"
        '  mimictype trigger "текст"       Tell daemon to type inline text\n'
    )
    parser = argparse.ArgumentParser(
        prog="mimictype",
        usage="%(prog)s [options] [text]\n       %(prog)s {daemon,trigger,stop,status} [subcommand-options]",
        description="Natural Keystroke Dynamics & uinput Virtual Keyboard for Linux.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Text string to type directly (default: clipboard)",
    )
    parser.add_argument(
        "--text",
        dest="text_override",
        type=str,
        default=None,
        help="Explicit text string (useful if text starts with '-' or matches a subcommand)",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=3.0,
        help="Seconds before typing begins (default: 3.0)",
    )
    parser.add_argument(
        "-w",
        "--wpm",
        type=int,
        default=None,
        help="Target typing speed in WPM (e.g. 65)",
    )
    parser.add_argument(
        "--preset",
        type=str,
        choices=["natural", "fast", "careful", "instant"],
        help="Speed and dynamics preset",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read text to type from standard input",
    )
    parser.add_argument(
        "--no-humanizer",
        action="store_true",
        help="Disable simulated typos and mistakes",
    )
    parser.add_argument(
        "--error-rate",
        type=float,
        default=None,
        help="Typo error probability (e.g. 0.02 for 2%%)",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to custom configuration YAML",
    )
    return parser


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] in SUBCOMMANDS:
        return _build_subcommand_parser().parse_args(raw_args)

    args = _build_direct_parser().parse_args(raw_args)
    args.subcommand = None
    return args


def main(argv: Optional[List[str]] = None):
    args = parse_args(argv)

    # Handle IPC subcommands
    if args.subcommand == "stop":
        run_ipc_command("STOP")
        return
    elif args.subcommand == "status":
        run_ipc_command("STATUS")
        return
    elif args.subcommand == "trigger":
        payload = {"text": args.text} if args.text is not None else None
        run_ipc_command("TYPE", payload)
        return

    # Load configuration
    cfg = MimicConfig.load(getattr(args, "config", None))
    if getattr(args, "preset", None):
        cfg.apply_preset(args.preset)
    if getattr(args, "wpm", None):
        cfg.wpm = args.wpm
    if getattr(args, "no_humanizer", False):
        cfg.humanizer.enabled = False
    if getattr(args, "error_rate", None) is not None:
        cfg.humanizer.error_rate = args.error_rate

    # Handle daemon mode
    if args.subcommand == "daemon":
        run_daemon(args, cfg)
        return

    # Handle direct mode
    run_direct_typing(args, cfg)


if __name__ == "__main__":
    main()
