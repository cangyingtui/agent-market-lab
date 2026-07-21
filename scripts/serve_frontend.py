from __future__ import annotations

import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SpaStaticHandler(SimpleHTTPRequestHandler):
    def send_head(self):  # type: ignore[override]
        parsed_path = unquote(urlparse(self.path).path)
        target = Path(self.translate_path(parsed_path))
        if not target.exists() and not Path(parsed_path).suffix:
            self.path = "/index.html"
        return super().send_head()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(f"{self.address_string()} - {format % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve frontend/dist with SPA route fallback")
    parser.add_argument("--root", default="frontend/dist", help="Static frontend build directory")
    parser.add_argument("--host", default=os.getenv("FRONTEND_STATIC_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("FRONTEND_STATIC_PORT", "5173")))
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    index = root / "index.html"
    if not index.exists():
        raise SystemExit(f"Missing {index}. Run frontend build before starting the static server.")

    handler = partial(SpaStaticHandler, directory=str(root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {root} at http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping frontend static server", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
