from __future__ import annotations

import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.pipeline import TestEngineerPipeline


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FRONTEND = ROOT / "frontend"
pipeline = TestEngineerPipeline()


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "AITestEngineerCopilot/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.write_json({"status": "ok", "service": "ai-test-engineer-copilot"})
            return

        if parsed.path == "/api/sample":
            self.write_json(
                {
                    "spec": (DATA / "sample_network_card_spec.md").read_text(encoding="utf-8"),
                    "logs": (DATA / "sample_validation_log.txt").read_text(encoding="utf-8"),
                }
            )
            return

        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/analyze":
            self.write_json({"error": "Not found"}, status=404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.write_json({"error": "Invalid JSON"}, status=400)
            return

        spec = str(payload.get("spec", ""))
        logs = str(payload.get("logs", ""))
        result = pipeline.analyze(spec, logs)
        self.write_json(result.to_dict())

    def serve_static(self, request_path: str) -> None:
        if request_path in {"", "/"}:
            file_path = FRONTEND / "index.html"
        else:
            relative = unquote(request_path.lstrip("/"))
            if relative.startswith("frontend/"):
                relative = relative[len("frontend/") :]
            file_path = FRONTEND / relative

        try:
            resolved = file_path.resolve()
            resolved.relative_to(FRONTEND.resolve())
        except ValueError:
            self.write_json({"error": "Invalid path"}, status=400)
            return

        if not resolved.exists() or not resolved.is_file():
            self.write_json({"error": "Not found"}, status=404)
            return

        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        body = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), format % args))


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), DemoHandler)
    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    print(f"AI Test Engineer Copilot running at http://{display_host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
