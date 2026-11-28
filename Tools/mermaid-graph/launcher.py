"""Generate Mermaid class diagrams and manage their loopback editors."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler


LOOPBACK = re.compile(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})/")
OPENER = build_opener(ProxyHandler({}))


def healthy(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("url"), str):
        return False
    match = LOOPBACK.fullmatch(entry["url"])
    if not match or int(match[1]) > 65535:
        return False
    if type(entry.get("pid")) is not int or entry["pid"] <= 1 or not entry.get("instance"):
        return False
    try:
        with OPENER.open(entry["url"] + "api/health", timeout=1) as response:
            identity = json.load(response)
        return identity == {key: entry[key] for key in ("file", "pid", "instance")}
    except (OSError, ValueError, KeyError):
        return False


def start(path, log_path, save):
    instance = secrets.token_hex(24)
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-B", str(Path(__file__).with_name("server.py")), path, instance],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    try:
        for _ in range(60):
            if process.poll() is not None:
                break
            with log_path.open() as log:
                url = log.readline().strip()
            entry = {"file": path, "pid": process.pid, "url": url, "instance": instance}
            if healthy(entry):
                save(entry)
                return url
            time.sleep(0.1)
        raise RuntimeError(f"Editor startup failed. See {log_path}")
    except BaseException:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        raise


def control(action, target):
    if action == "start":
        path = Path(target).expanduser().resolve(strict=True)
        if path.suffix.lower() != ".mmd" or not path.is_file():
            raise ValueError("Expected an existing .mmd file.")
    else:
        path = Path(target).expanduser().resolve() if target else None
    runtime = Path.home() / ".mermaid-graph"
    os.umask(0o077)
    runtime.mkdir(exist_ok=True)
    registry = runtime / "servers.json"
    with (runtime / "launcher.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            entries = json.loads(registry.read_text())
        except (FileNotFoundError, ValueError):
            entries = {}
        if not isinstance(entries, dict):
            entries = {}
        active = {key: entry for key, entry in entries.items()
                  if isinstance(entry, dict) and key == entry.get("file") and healthy(entry)}

        def save(entry=None):
            if entry:
                active[entry["file"]] = entry
            temporary = registry.with_suffix(".tmp")
            temporary.write_text(json.dumps(active, indent=2) + "\n")
            temporary.replace(registry)

        if active != entries:
            save()
        if action == "list":
            for file, entry in sorted(active.items()):
                print(f'pid {entry["pid"]}  {entry["url"]}  {file}')
            if not active:
                print("No active Mermaid editors")
        elif action == "start":
            key = str(path)
            if key in active:
                print(active[key]["url"])
            else:
                log_path = runtime / (hashlib.sha256(os.fsencode(path)).hexdigest() + ".log")
                print(start(key, log_path, save))
        else:
            matches = [entry for key, entry in active.items()
                       if key == str(path) or target == str(entry["pid"])
                       or target.rstrip("/") == entry["url"].rstrip("/")]
            if len(matches) != 1 or not healthy(matches[0]):
                raise RuntimeError(f"No unique active Mermaid editor matches {target}")
            entry = matches[0]
            try:
                os.kill(entry["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
            for _ in range(40):
                if not healthy(entry):
                    del active[entry["file"]]
                    save()
                    print(f'Stopped {entry["file"]}')
                    return
                time.sleep(0.1)
            raise RuntimeError("Editor did not stop. Registry entry retained.")


def main():
    if sys.argv[1:2] == ["scaffold"]:
        from scaffold import main as scaffold_main

        return scaffold_main(sys.argv[2:])
    parser = argparse.ArgumentParser(
        description=__doc__, epilog="Run scaffold --help to preview or create Unity C# from a diagram.")
    parser.add_argument("action", choices=("create", "generate", "start", "list", "stop"))
    parser.add_argument("target", nargs="?")
    parser.add_argument("output", nargs="?")
    args = parser.parse_args()
    if args.action == "generate":
        if not args.target or not args.output:
            parser.error("Use generate <source-directory> <output-path>.")
    elif args.action == "create":
        if not args.target or args.output:
            parser.error("Use create <destination-directory>.")
    elif args.output or (args.action == "list") == bool(args.target):
        parser.error("Use start <file.mmd>, list, or stop <file.mmd|PID|URL>.")
    try:
        if args.action == "generate":
            from generator import generate

            print(generate(args.target, args.output))
        elif args.action == "create":
            from generator import create

            print(create(args.target))
        else:
            control(args.action, args.target)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
