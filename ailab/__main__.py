"""python3 -m ailab status | doctor | secretscan [path] | models <provider> [--refresh] | roster | serve [--port N] [--host 127.0.0.1]"""
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
    if cmd == "doctor":
        from .preview import Preview                               # noqa: PLC0415
        pv = Preview()
        try:
            r = pv.doctor()
        finally:
            pv.close()
        print(("✅ preview sandbox OK " if r["ok"] else "❌ preview sandbox FAILED ") + json.dumps(r))
        return 0 if r["ok"] else 1
    if cmd == "secretscan":
        from pathlib import Path                                   # noqa: PLC0415
        from .config import REPO                                   # noqa: PLC0415
        from .secretscan import scan                               # noqa: PLC0415
        r = scan(Path(a[1]) if len(a) > 1 else REPO)
        for hit in r["hits"]:
            print(f"🔑 {hit['where']} — {hit['why']}")
        print(("✅ secret scan clean" if r["ok"] else f"❌ {len(r['hits'])} possible secret(s) — nothing was printed")
              + f" ({r['files']} files + git history)")
        return 0 if r["ok"] else 1
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
    if cmd == "roster":
        from .roster import status                                 # noqa: PLC0415
        for r in status(lab):
            mark = "✅" if r["state"].startswith("ready") else "⬇️" if r["provider"] == "ollama" else "🔑"
            print(f"{mark} {r['provider']:10} {r['model']:34} {r['state']}" + (f" — {r['todo']}" if r["todo"] else ""))
            print(f"   {r['job']} · {r['price']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
