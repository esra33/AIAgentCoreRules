"""Loopback HTTP server for a single Mermaid file."""

import argparse
import errno
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import stat
import tempfile
import threading

from diagram import edit, parse


MAX_REQUEST = 16 * 1024 * 1024
STATIC = {"/": ("index.html", "text/html"), "/editor.js": ("editor.js", "text/javascript"),
          "/editor.css": ("editor.css", "text/css")}


class Conflict(Exception):
    pass


def file_revision(data, info):
    fingerprint = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    digest = hashlib.sha256(repr(fingerprint).encode())
    digest.update(data)
    return digest.hexdigest()


def snapshot(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as file:
        info = os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EINVAL, "Expected a regular Mermaid file.", path)
        data = file.read()
    revision = file_revision(data, info)
    return data.decode("utf-8-sig"), revision, info, data.startswith(b"\xef\xbb\xbf")


def save_snapshot(path):
    try:
        return snapshot(path)
    except UnicodeError as error:
        raise Conflict from error
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ELOOP, errno.EINVAL, errno.ENOTDIR):
            raise Conflict from error
        raise


def replace(path, source, revision):
    _, current, info, bom = save_snapshot(path)
    if revision != current:
        raise Conflict
    data = source.encode("utf-8-sig" if bom else "utf-8")
    file = tempfile.NamedTemporaryFile(dir=path.parent, prefix=".mermaid-graph-", delete=False)
    temporary = Path(file.name)
    try:
        with file:
            file.write(data)
            file.flush()
            os.fchmod(file.fileno(), stat.S_IMODE(info.st_mode))
            os.fsync(file.fileno())
            if save_snapshot(path)[1] != revision:
                raise Conflict
            os.replace(temporary, path)
            return file_revision(data, os.fstat(file.fileno()))
    finally:
        temporary.unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="application/json"):
        if content_type == "application/json":
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") == self.server.host

    def do_GET(self):
        if not self.valid_host():
            self.respond(403, {"error": "Use the loopback URL printed by the launcher."})
            return
        if self.path == "/api/health":
            self.respond(200, self.server.identity)
        elif self.path == "/api/diagram":
            try:
                source, revision, _, _ = snapshot(self.server.file)
                self.respond(200, {"source": source, "revision": revision,
                                   "file": str(self.server.file), **parse(source)})
            except (OSError, UnicodeError) as error:
                self.respond(500, {"error": str(error)})
        elif self.path in STATIC:
            filename, content_type = STATIC[self.path]
            self.respond(200, Path(__file__).with_name(filename).read_bytes(), content_type)
        else:
            self.respond(404, {"error": "Not found."})

    def read_draft(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_REQUEST or self.headers.get_content_type() != "application/json":
            raise ValueError("Expected a JSON draft within the 16 MiB request limit.")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict) or not isinstance(payload.get("source"), str):
            raise ValueError("Expected a source string.")
        return payload

    def editor_request(self):
        if self.valid_host() and self.headers.get("Origin") == "http://" + self.server.host and (
                self.headers.get("X-Mermaid-Editor") == "1"):
            return True
        self.respond(403, {"error": "A same-origin editor request is required."})
        return False

    def do_POST(self):
        if not self.editor_request():
            return
        if self.path == "/api/parse":
            try:
                self.respond(200, parse(self.read_draft()["source"]))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
        elif self.path == "/api/edit":
            try:
                payload = self.read_draft()
                change = payload.get("change")
                if not isinstance(change, dict):
                    raise ValueError("Expected a visual edit.")
                source = edit(payload["source"], change)
                self.respond(200, {"source": source, **parse(source)})
            except ValueError as error:
                self.respond(400, {"error": str(error)})
        else:
            self.respond(404, {"error": "Not found."})

    def do_PUT(self):
        if not self.editor_request():
            return
        if self.path != "/api/diagram":
            self.respond(404, {"error": "Not found."})
            return
        try:
            payload = self.read_draft()
            revision = payload.get("revision")
            if not isinstance(revision, str):
                raise ValueError("Expected the loaded file revision.")
            with self.server.write_lock:
                revision = replace(self.server.file, payload["source"], revision)
            self.respond(200, {"revision": revision})
        except Conflict:
            self.respond(409, {"error": "The file changed on disk. Your draft is still in the source pane. Copy it before reloading."})
        except ValueError as error:
            self.respond(400, {"error": str(error)})
        except OSError as error:
            self.respond(500, {"error": str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("instance")
    args = parser.parse_args()
    path = args.file.resolve(strict=True)
    if path.suffix.lower() != ".mmd" or not path.is_file():
        parser.error("Expected an existing .mmd file.")
    snapshot(path)
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server.file = path
        server.host = f"127.0.0.1:{server.server_port}"
        server.identity = {"file": str(path), "pid": os.getpid(), "instance": args.instance}
        server.write_lock = threading.Lock()
        print(f"http://{server.host}/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
