"""Exercise the queue cleanup against a real HTTP API, without GitHub credentials."""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "queue_cleanup", Path(__file__).parents[1] / "scripts/cancel_stale_queue_runs.py"
)


def test_cleanup_cancels_only_deleted_queue_refs():
    spec = SPEC
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append(("GET", self.path))
            if "/actions/" in self.path:
                runs = (
                    [
                        {"id": 1, "head_branch": "gh-readonly-queue/dev/pr-1-old"},
                        {"id": 2, "head_branch": "gh-readonly-queue/dev/pr-2-live"},
                        {"id": 3, "head_branch": "dev"},
                    ]
                    if "status=queued" in self.path and "page=1&" in self.path
                    else []
                )
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"workflow_runs": runs}).encode())
            else:
                self.send_response(404 if self.path.endswith("pr-1-old") else 200)
                self.end_headers()
                self.wfile.write(b"{}")

        def do_POST(self):
            requests.append(("POST", self.path))
            self.send_response(202)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        client = module.Client("owner/repo", "synthetic", f"http://127.0.0.1:{server.server_port}")
        assert module.cleanup(client) == [1]
        assert not any(path.endswith("/git/ref/heads/dev") for _, path in requests)
        assert [p for method, p in requests if method == "POST"] == [
            "/repos/owner/repo/actions/runs/1/cancel"
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_api_permission_failure_is_not_a_missing_ref():
    spec = SPEC
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from urllib.error import HTTPError

    with pytest.raises(HTTPError):
        module.is_missing_ref_error(HTTPError("http://example.invalid", 403, "forbidden", {}, None))
