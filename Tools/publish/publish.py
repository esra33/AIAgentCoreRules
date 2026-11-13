#!/usr/bin/env python3
"""Publish an explicitly reviewed Git change through one resumable, noninteractive CLI."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


class Blocked(ValueError):
    """A prerequisite failed; completed work remains available for resumption."""


def run(arguments, cwd, *, raw=False, timeout=60):
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GH_PROMPT_DISABLED="1")
    try:
        result = subprocess.run(arguments, cwd=cwd, env=environment, capture_output=True,
                                timeout=timeout, check=False)
    except FileNotFoundError as error:
        raise Blocked(f"{arguments[0]} is missing; install GitHub CLI (gh) and run gh auth login" if arguments[0] == "gh" else f"{arguments[0]} is missing; install it before publishing") from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Blocked(f"{arguments[0]} unavailable or timed out; check installation, authentication and network") from error
    if result.returncode:
        # Tool stderr can contain credential-bearing URLs. Never echo it into agent context.
        guidance = "run gh auth login and verify repository access" if arguments[0] == "gh" else "check authentication, permissions and repository state"
        raise Blocked(f"{arguments[0]} {arguments[1]} failed (exit {result.returncode}); {guidance}")
    return result.stdout if raw else result.stdout.decode("utf-8", errors="replace").strip()


def git(repo, *arguments, raw=False):
    return run(["git", *arguments], repo, raw=raw)


def gh(repo, *arguments):
    return run(["gh", *arguments], repo)


def read_request(path):
    request = json.loads(path.read_text())
    required = {"repo", "branch", "expected_head", "base", "files", "commit_message", "pr_title", "body_file"}
    if not isinstance(request, dict) or not required.issubset(request) or set(request) - required - {"feature"}:
        raise Blocked("request requires repo, branch, expected_head, base, files, commit_message, pr_title, body_file; only feature is optional")
    for key in required - {"files"}:
        if not isinstance(request[key], str) or not request[key].strip() or "\x00" in request[key]:
            raise Blocked(f"invalid request {key}")
    if not Path(request["repo"]).is_absolute():
        raise Blocked("repo must be an absolute checkout path")
    request["repo"] = str(Path(request["repo"]).resolve())
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", request["expected_head"]):
        raise Blocked("expected_head must be a full commit SHA")
    files = request["files"]
    if not isinstance(files, list) or not files or any(not isinstance(item, str) or not item or
            Path(item).is_absolute() or ".." in Path(item).parts or item.startswith(":") or
            "\x00" in item or item in {".", ".."} for item in files) or len(set(files)) != len(files):
        raise Blocked("files must be unique literal repository-relative file paths")
    request["body_file"] = str((path.parent / request["body_file"]).resolve())
    body = Path(request["body_file"]).read_text()
    if not body.strip():
        raise Blocked("PR body must not be empty")
    if "feature" in request:
        feature = request["feature"]
        if not isinstance(feature, dict) or set(feature) != {"directory", "task_id", "batch", "phase", "session"}:
            raise Blocked("feature requires directory, task_id, batch, phase, session")
        if type(feature["batch"]) is not int or feature["batch"] < 1 or not re.fullmatch(r"T\d+", feature["task_id"]) or not re.fullmatch(r"V\d+", feature["phase"]):
            raise Blocked("invalid feature task_id, batch or phase")
        if not isinstance(feature["session"], str) or not feature["session"]:
            raise Blocked("feature session must be an existing session folder name")
        feature["directory"] = str((path.parent / feature["directory"]).resolve())
    fingerprint = hashlib.sha256(json.dumps({"request": request, "body": body}, sort_keys=True).encode()).hexdigest()
    return request, fingerprint


def atomic_json(path, value):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".publish-")
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def publication_lock(directory):
    with (directory / "agent-publish.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Blocked("another publisher is running in this checkout") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def changed_paths(repo, *arguments):
    return set(git(repo, "--literal-pathspecs", "diff", "--name-only", "--no-renames", "-z", *arguments, raw=True).decode().rstrip("\x00").split("\x00")) - {""}


def feature_command(request, operation, payload=None):
    feature = request["feature"]
    tool = Path(__file__).resolve().parents[1] / "feature-state" / "feature_state.py"
    command = [sys.executable, "-B", str(tool), "get", feature["directory"]]
    state = json.loads(run(command, request["repo"]))
    if operation == "get":
        return state
    with tempfile.TemporaryDirectory(prefix="agent-publish-feature-") as temporary:
        path = Path(temporary) / "payload.json"
        path.write_text(json.dumps(payload(state)))
        return json.loads(run([sys.executable, "-B", str(tool), operation, feature["directory"],
                               "--payload", str(path), "--revision", str(state["revision"])], request["repo"]))


def validate_feature(request, pr=None):
    if "feature" not in request:
        return
    feature = request["feature"]
    state = feature_command(request, "get")
    batch = state["batches"].get(feature["task_id"])
    if not batch or batch.get("branch") != request["branch"] or batch.get("base") != request["base"]:
        raise Blocked("feature batch branch/base must match the publishing request")
    if batch.get("merged", 0) != feature["batch"] - 1 or len(batch.get("plan", [])) < feature["batch"]:
        raise Blocked("feature batch is not the current approved batch")
    if batch.get("open_pr") and (not pr or batch["open_pr"] != pr["number"]):
        raise Blocked("feature has a different open PR")


def record_feature(request, pr):
    if "feature" not in request:
        return
    feature = request["feature"]
    validate_feature(request, pr)
    def batch_payload(state):
        value = dict(state["batches"][feature["task_id"]])
        value["open_pr"] = pr["number"]
        value["prs"] = list(dict.fromkeys([*value.get("prs", []), pr["number"]]))
        return {"task_id": feature["task_id"], "value": value}
    feature_command(request, "batch", batch_payload)
    feature_command(request, "pr", lambda state: {"phase": feature["phase"], "number": pr["number"]})
    feature_command(request, "checkpoint", lambda state: {"sessions": list(dict.fromkeys([*state["sessions"], feature["session"]]))})


class Publisher:
    def __init__(self, request, fingerprint, request_path):
        self.request = request
        self.repo = request["repo"]
        self.step = "preflight"
        self.request_path = request_path
        root = git(self.repo, "rev-parse", "--show-toplevel")
        if Path(root).resolve() != Path(self.repo):
            raise Blocked("repo must name the checkout root")
        self.metadata = Path(git(self.repo, "rev-parse", "--absolute-git-dir"))
        self.journal_path = self.metadata / "agent-publish" / (fingerprint + ".json")
        self.journal = json.loads(self.journal_path.read_text()) if self.journal_path.exists() else {}
        self.pr = None
        self.base_sha = None

    def save(self, **values):
        self.journal.update(values)
        self.journal_path.parent.mkdir(exist_ok=True)
        atomic_json(self.journal_path, self.journal)

    def result(self, status, message=None):
        result = {"status": status, "step": self.step, "sha": self.journal.get("sha"),
                  "branch": self.request["branch"], "url": self.journal.get("url"),
                  "resume": [sys.executable, str(Path(__file__).resolve()), "publish", "--request", str(self.request_path)]}
        if message:
            result["message"] = message
        return result

    def find_pr(self):
        request = self.request
        prs = json.loads(gh(self.repo, "pr", "list", "--repo", self.repository, "--state", "all",
                            "--head", request["branch"], "--base", request["base"],
                            "--json", "number,url,state,headRefOid"))
        opened = [pr for pr in prs if pr["state"] == "OPEN"]
        if len(opened) > 1:
            raise Blocked("multiple open pull requests match this branch/base")
        if opened:
            return opened[0]
        if any(pr["state"] == "CLOSED" for pr in prs):
            raise Blocked("branch/base has a closed unmerged PR; reconcile its batch before publishing")
        previous = next((pr for pr in prs if pr["number"] == self.journal.get("pr")), None)
        if previous:
            if self.journal.get("complete"):
                return previous
            raise Blocked("published PR was merged before feature recording completed; reconcile feature state")
        return None

    def preflight(self):
        request = self.request
        if git(self.repo, "branch", "--show-current") != request["branch"] or request["branch"] == request["base"]:
            raise Blocked("checkout must be on the requested non-base branch")
        git(self.repo, "check-ref-format", "--branch", request["branch"])
        git(self.repo, "check-ref-format", "--branch", request["base"])
        for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
            if (self.metadata / marker).exists():
                raise Blocked("finish the in-progress Git operation before publishing")
        if git(self.repo, "ls-files", "-u"):
            raise Blocked("resolve index conflicts before publishing")
        allowed = set(request["files"])
        if changed_paths(self.repo, "--cached") - allowed:
            raise Blocked("unrelated staged files must be unstaged before publishing")
        for item in allowed:
            target = Path(self.repo) / item
            if target.is_dir() or not target.parent.resolve().is_relative_to(Path(self.repo)):
                raise Blocked("files must name exact files within the checkout")
        head = git(self.repo, "rev-parse", "HEAD")
        expected = self.journal.get("sha", request["expected_head"])
        if head != expected:
            if not self.journal.get("sha") and self.journal.get("tree") and git(self.repo, "rev-parse", "HEAD^") == request["expected_head"] and git(self.repo, "rev-parse", "HEAD^{tree}") == self.journal["tree"] and git(self.repo, "log", "-1", "--format=%B") == request["commit_message"].strip():
                self.journal["sha"] = head
            else:
                raise Blocked("HEAD changed; create a fresh reviewed request with the correct expected_head")
        if self.journal.get("sha") and (changed_paths(self.repo, "HEAD", "--", *request["files"]) or git(self.repo, "ls-files", "--others", "--exclude-standard", "--", *request["files"])):
            raise Blocked("published files changed after the recorded commit; create a fresh request")
        origin = git(self.repo, "remote", "get-url", "origin")
        push_urls = git(self.repo, "remote", "get-url", "--push", "--all", "origin").splitlines()
        if push_urls != [origin]:
            raise Blocked("origin must have exactly one push URL matching its fetch URL")
        match = re.fullmatch(r"(?:git@github\.com:|https://github\.com/|ssh://git@github\.com/)([^/\s]+/[^/\s]+?)(?:\.git)?", origin)
        if not match:
            raise Blocked("origin must be a credential-free GitHub SSH or HTTPS repository URL")
        self.repository = match[1]
        gh(self.repo, "auth", "status")
        actual = json.loads(gh(self.repo, "repo", "view", self.repository, "--json", "nameWithOwner"))
        if actual["nameWithOwner"].lower() != self.repository.lower():
            raise Blocked("GitHub repository identity does not match origin")
        refs = git(self.repo, "ls-remote", "--heads", "origin", "refs/heads/" + request["base"])
        if not refs:
            raise Blocked("base branch does not exist on origin")
        self.base_sha = refs.split()[0]
        git(self.repo, "cat-file", "-e", self.base_sha + "^{commit}")
        if changed_paths(self.repo, self.base_sha, "HEAD") - allowed:
            raise Blocked("branch diff against current remote base contains files outside the reviewed request")
        self.pr = self.find_pr()
        if not (self.pr and self.pr["state"] == "MERGED" and self.journal.get("complete")):
            validate_feature(request, self.pr)

    def commit(self):
        if self.journal.get("sha"):
            return
        request = self.request
        self.step = "commit"
        git(self.repo, "--literal-pathspecs", "add", "--", *request["files"])
        if changed_paths(self.repo, "--cached") - set(request["files"]):
            raise Blocked("index changed concurrently; refusing commit")
        if not changed_paths(self.repo, "--cached"):
            self.save(sha=git(self.repo, "rev-parse", "HEAD"))
            return
        self.save(tree=git(self.repo, "write-tree"))
        with tempfile.TemporaryDirectory(prefix="agent-publish-message-") as temporary:
            message = Path(temporary) / "message.txt"
            message.write_text(request["commit_message"])
            git(self.repo, "commit", "--file", str(message))
        if git(self.repo, "rev-parse", "HEAD^{tree}") != self.journal["tree"] or git(self.repo, "rev-parse", "HEAD^") != request["expected_head"]:
            raise Blocked("commit hook or concurrent process changed the reviewed tree/parent; refusing push")
        self.save(sha=git(self.repo, "rev-parse", "HEAD"))

    def publish(self):
        self.preflight()
        if self.journal.get("complete"):
            self.step = "merged" if self.pr and self.pr["state"] == "MERGED" else "complete"
            return self.result("complete")
        self.commit()
        self.step = "push"
        if git(self.repo, "rev-parse", "HEAD") != self.journal["sha"]:
            raise Blocked("HEAD changed concurrently; refusing push")
        git(self.repo, "push", "--no-follow-tags", "--set-upstream", "origin", "HEAD:refs/heads/" + self.request["branch"])
        self.save(pushed=True)
        self.step = "pull_request"
        self.pr = self.find_pr()
        if self.pr is None:
            try:
                gh(self.repo, "pr", "create", "--repo", self.repository, "--base", self.request["base"],
                   "--head", self.request["branch"], "--title", self.request["pr_title"],
                   "--body-file", self.request["body_file"])
            except Blocked:
                self.pr = self.find_pr()
                if self.pr is None:
                    raise
            self.pr = self.find_pr()
        if self.pr is None or self.pr.get("headRefOid") != self.journal["sha"]:
            raise Blocked("PR head does not match the published commit; retry after reconciling remote state")
        self.save(url=self.pr["url"], pr=self.pr["number"])
        self.step = "feature_state"
        record_feature(self.request, self.pr)
        self.save(complete=True)
        self.step = "complete"
        return self.result("complete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "publish", "status"))
    parser.add_argument("--request", type=Path, required=True, help="JSON request; check/status never mutate")
    arguments = parser.parse_args()
    publisher = None
    try:
        path = arguments.request.resolve()
        request, fingerprint = read_request(path)
        publisher = Publisher(request, fingerprint, path)
        if arguments.command == "publish":
            with publication_lock(publisher.metadata):
                # Reload under the checkout lock: another call may just have completed.
                publisher = Publisher(request, fingerprint, path)
                result = publisher.publish()
        else:
            publisher.preflight()
            if publisher.pr:
                publisher.journal.update(url=publisher.pr["url"], pr=publisher.pr["number"])
            publisher.step = "complete" if publisher.journal.get("complete") else "preflight"
            result = publisher.result("complete" if publisher.journal.get("complete") else "ready")
        print(json.dumps(result))
        return 0
    except (Blocked, OSError, ValueError, KeyError, TypeError) as error:
        result = publisher.result("blocked", str(error)) if publisher else {"status": "blocked", "step": "request", "message": str(error)}
        print(json.dumps(result))
        return 1


if __name__ == "__main__":
    sys.exit(main())
