import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from citedlog.logfile import Log
from citedlog.scenario import LOG_NAME, log_text, truth

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def log():
    return Log(log_text(), LOG_NAME)


@pytest.fixture(scope="session")
def answer_key():
    return truth()


class FakeOllama:
    """A stand-in for `ollama serve`: records requests and answers with a canned reply."""

    def __init__(self, status=200, body=None, delay=0.0):
        self.status, self.body, self.delay = status, body, delay
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                outer.requests.append({"path": self.path, "json": json.loads(self.rfile.read(length))})
                if outer.delay:
                    import time

                    time.sleep(outer.delay)
                payload = json.dumps(outer.body).encode()
                try:
                    self.send_response(outer.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake_ollama():
    return FakeOllama
