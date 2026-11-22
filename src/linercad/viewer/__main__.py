"""Background Viewer entry point (H3): started by autostart after a build / edit.

python -m linercad.viewer --background --dir <drawing> --port 0 --idle-timeout <seconds>
"""

from __future__ import annotations

import argparse

from . import serve


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m linercad.viewer")
    p.add_argument("--background", action="store_true", help="run detached (no browser)")
    p.add_argument("--dir", required=True, help="drawing directory")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--idle-timeout", type=float, default=None)
    args = p.parse_args(argv)
    serve(args.dir, args.port, False, idle_timeout=args.idle_timeout, background=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
