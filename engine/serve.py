#!/usr/bin/env python3
"""Local preview server without caching: python3 engine/serve.py [port]  (default 8790).
Serves engine/ so compositions open as http://127.0.0.1:8790/<project>-ch1.html#t=12.5
(#t= seeks the timeline to that second)."""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
ThreadingHTTPServer(("127.0.0.1", port), partial(NoCache, directory=str(Path(__file__).resolve().parent))).serve_forever()
