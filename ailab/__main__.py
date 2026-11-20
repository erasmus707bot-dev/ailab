"""python3 -m ailab status | models <provider> [--refresh]"""
from __future__ import annotations

import json
import sys

from .lab import Lab


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a[0] if a else "status"
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
