"""python3 -m ailab status | models <provider> [--refresh] | serve [--port N] [--host 127.0.0.1]"""
from __future__ import annotations

import json
import sys

from .lab import Lab


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a[0] if a else "status"
    if cmd == "serve":
        from .server import serve                                  # noqa: PLC0415
        port = int(a[a.index("--port") + 1]) if "--port" in a else None
        host = a[a.index("--host") + 1] if "--host" in a else "127.0.0.1"
        return serve(host, port)
    lab = Lab()
    if cmd == "status":
        print(json.dumps(lab.status(), indent=1))
        return 0
    if cmd == "models" and len(a) >= 2:
        r = lab.list_models(a[1], refresh="--refresh" in a)
        print(f"{r['provider']}: {len(r['models'])} models ({r['source']})")
        for m in r["models"][:200]:
            print(" ", m["id"])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
