import argparse
import signal
import sys
import time
from mimictype.config import MimicConfig
from mimictype.core.clipboard import ClipboardReader
from mimictype.core.engine import TyperEngine


def main():
    parser = argparse.ArgumentParser(
        prog="mimictype",
        description="Natural Keystroke Dynamics & uinput Virtual Keyboard for Linux.",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=3.0,
        help="Seconds to wait before typing starts (allows focusing target window). Default: 3.0",
    )
    parser.add_argument(
        "-w",
        "--wpm",
        type=int,
        default=None,
        help="Target typing speed in Words Per Minute (e.g. 65).",
    )
    parser.add_argument(
        "-t",
        "--text",
        type=str,
        default=None,
        help="Text string to type directly (if omitted, reads from system clipboard).",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read text to type from standard input.",
    )
    parser.add_argument(
        "--no-humanizer",
        action="store_true",
        help="Disable simulated human typos and corrections.",
    )
    parser.add_argument(
        "--error-rate",
        type=float,
        default=None,
        help="Typo error probability (e.g. 0.02 for 2%).",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to custom configuration YAML file.",
    )

    args = parser.parse_args()

    # Load configuration
    cfg = MimicConfig.load(args.config)
    if args.wpm is not None:
        cfg.wpm = args.wpm
    if args.no_humanizer:
        cfg.humanizer.enabled = False
    if args.error_rate is not None:
        cfg.humanizer.error_rate = args.error_rate

    # Get input text
    text_to_type = None
    if args.stdin:
        text_to_type = sys.stdin.read()
    elif args.text is not None:
        text_to_type = args.text
    else:
        text_to_type = ClipboardReader.get_text()

    if not text_to_type:
        print(
            "mimictype: No text found in clipboard or arguments.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[*] MimicType initialized (Target: {cfg.wpm} WPM)")
    print(
        f"[*] Text length: {len(text_to_type)} characters. Preparing to type..."
    )

    # Countdown delay
    if args.delay > 0:
        remaining = int(args.delay)
        print(f"[*] Focus target input window! Starting in {args.delay:.1f}s:")
        for sec in range(remaining, 0, -1):
            sys.stdout.write(f"\r    [{sec}...] ")
            sys.stdout.flush()
            time.sleep(1.0)
        sys.stdout.write("\r    [Typing started!]\n")
        sys.stdout.flush()

    try:
        with TyperEngine(config=cfg) as engine:
            # Handle Ctrl+C safely
            def handle_sigint(sig, frame):
                print(
                    "\n[!] Interrupted by user. Releasing keys and stopping..."
                )
                engine.abort()
                sys.exit(130)

            signal.signal(signal.SIGINT, handle_sigint)
            signal.signal(signal.SIGTERM, handle_sigint)

            success = engine.type_text(text_to_type)
            if success:
                print("[+] Typing completed successfully.")
            else:
                print("[!] Typing aborted.")
    except PermissionError:
        print(
            "mimictype: Permission denied accessing /dev/uinput.",
            file=sys.stderr,
        )
        print(
            "Ensure your user has access to /dev/uinput (e.g. member of 'input' group or udev rule).",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"mimictype error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
