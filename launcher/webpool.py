"""Local web-server pool for QuakeLogic HVSR Studio.

PHP's built-in web server handles one request at a time per process (and cannot fork
workers on Windows). A long upload or a long engine call would therefore block every other
request — status polls, heartbeats, plots — and the interface would report the local server
as unreachable. This module starts several `php -S` back ends on private ports and serves the
public port through a threaded reverse proxy that hands each request to the least busy back
end. Everything stays on 127.0.0.1.
"""
from __future__ import annotations

import http.client
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
              "transfer-encoding", "upgrade"}


class _LimitedReader:
    """File-like view over exactly `length` bytes of a request body (streamed, not buffered)."""

    def __init__(self, raw, length: int):
        self.raw = raw
        self.remaining = length

    def read(self, size: int = -1) -> bytes:
        if self.remaining <= 0:
            return b""
        if size is None or size < 0 or size > self.remaining:
            size = self.remaining
        chunk = self.raw.read(size)
        self.remaining -= len(chunk)
        return chunk


class WebPool:
    def __init__(self, php: Path, app_root: Path, host: str, port: int, backends: int, env: dict[str, str],
                 log, log_file: Path | None = None):
        self.php = php
        self.app_root = app_root
        self.host = host
        self.port = port
        self.env = env
        self.log = log
        self.log_file = log_file
        self.n_backends = max(1, backends)
        self.processes: list[subprocess.Popen] = []
        self.ports: list[int] = []
        self.inflight: dict[int, int] = {}
        self.lock = threading.Lock()
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    # ---- back ends ---------------------------------------------------------------------
    def _free_port(self, start: int) -> int:
        port = start
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.2)
                if sock.connect_ex((self.host, port)) != 0:
                    return port
            port += 1

    def start(self, popen_kwargs: dict) -> None:
        router = self.app_root / "vendor" / "laravel" / "framework" / "src" / "Illuminate" / "Foundation" / "resources" / "server.php"
        next_port = self.port + 1
        handle = self.log_file.open("ab") if self.log_file else subprocess.DEVNULL
        for _ in range(self.n_backends):
            port = self._free_port(next_port)
            next_port = port + 1
            cmd = [str(self.php), "-S", f"{self.host}:{port}", "-t", str(self.app_root / "public"), str(router)]
            kwargs = dict(popen_kwargs)
            kwargs.update(stdout=handle, stderr=subprocess.STDOUT, env=self.env, cwd=str(self.app_root / "public"))
            self.processes.append(subprocess.Popen(cmd, **kwargs))
            self.ports.append(port)
            self.inflight[port] = 0
        self.log(f"Web back ends on ports {', '.join(str(p) for p in self.ports)}")
        pool = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):  # quiet; PHP logs its own requests
                pass

            def _proxy(self):
                port = pool._pick()
                length = int(self.headers.get("Content-Length") or 0)
                body = _LimitedReader(self.rfile, length) if length > 0 else None
                headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
                headers["Connection"] = "close"
                conn = http.client.HTTPConnection(pool.host, port, timeout=3600)
                try:
                    conn.request(self.command, self.path, body=body, headers=headers)
                    resp = conn.getresponse()
                    self.send_response(resp.status, resp.reason)
                    has_length = False
                    for key, value in resp.getheaders():
                        if key.lower() in HOP_BY_HOP:
                            continue
                        if key.lower() == "content-length":
                            has_length = True
                        self.send_header(key, value)
                    if not has_length:
                        self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    while True:
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        if has_length:
                            self.wfile.write(chunk)
                        else:
                            self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    if not has_length:
                        self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except (OSError, http.client.HTTPException) as exc:
                    try:
                        self.send_error(502, f"Local web back end error: {exc}")
                    except OSError:
                        pass
                finally:
                    conn.close()
                    pool._release(port)

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _proxy

        self.server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.server.daemon_threads = True
        self.server.request_queue_size = 64
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True)
        self.thread.start()

    def _pick(self) -> int:
        with self.lock:
            port = min(self.ports, key=lambda p: self.inflight[p])
            self.inflight[port] += 1
            return port

    def _release(self, port: int) -> None:
        with self.lock:
            self.inflight[port] = max(0, self.inflight[port] - 1)

    # ---- lifecycle ---------------------------------------------------------------------
    def poll(self) -> int | None:
        """Return the exit code of a dead back end, or None while all are alive."""
        for proc in self.processes:
            code = proc.poll()
            if code is not None:
                return code
        return None

    def stop(self, terminate) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        for proc in self.processes:
            terminate(proc, "web server", self.log)
        time.sleep(0.2)
