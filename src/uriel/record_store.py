"""Research-record backends. The note tree is authoritative; no shadow database."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

SECTIONS = {
    "question": "Question", "current": "Current picture", "leads": "Leads",
    "conclusions": "Conclusions register", "ruled-out": "Ruled out",
    "gaps": "Gaps and tensions", "decisions": "Decisions and direction history",
    "sources": "Sources and data", "manuscript": "Manuscript",
}
KEY = re.compile(r"[a-z0-9][a-z0-9-]{0,95}\Z")
HEADER = re.compile(r"^<!-- uriel-key:([a-z0-9-]+) -->\n")


class RecordError(ValueError):
    """A refused record operation."""


def key(value):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise RecordError("Use a stable lowercase key (letters, digits and hyphens).")
    return value


def digest(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"))


def note_text(identity, title, body):
    if not isinstance(title, str) or not title.strip() or "\n" in title or "\r" in title:
        raise RecordError("Note title must be a single nonempty line.")
    return "<!-- uriel-key:" + key(identity) + " -->\n# " + title + "\n\n" + body


def validate_content(identity, content):
    match = HEADER.match(content)
    if not match or match[1] != key(identity):
        raise RecordError("Stable content key mismatch.")
    note_body(content)
    return content


def note_body(content):
    parts = content.split("\n\n", 1)
    if not HEADER.match(content) or len(parts) != 2:
        raise RecordError("Missing or damaged record header.")
    return parts[1]


def structured(value):
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2,
                                     sort_keys=True, allow_nan=False) + "\n```\n"


def parse_structured(content):
    body = note_body(content).strip()
    if not body.startswith("```json\n") or not body.endswith("\n```"):
        raise RecordError("Expected a JSON record in a Markdown code block.")
    value = json.loads(body[8:-4])
    if not isinstance(value, dict):
        raise RecordError("Expected a record object.")
    return value


def snapshot(identity, content, revision, parents, title, locator):
    return {"key": identity, "content": content, "sha256": digest(content),
            "revision": revision, "parents": sorted(parents), "title": title,
            "locator": locator}


def signature(note):
    return {name: note[name] for name in ("key", "sha256", "revision", "parents", "title", "locator")}


class Folder:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self):
        result = {}
        for path in sorted(self.root.rglob("*.md")):
            if path.is_symlink() or not path.is_file() or self.root not in path.resolve().parents:
                continue
            content = path.read_bytes().decode("utf-8")
            match = HEADER.match(content)
            if not match:
                continue
            identity = match[1]
            if identity in result:
                raise RecordError("Duplicate stable key: " + identity)
            rel = path.relative_to(self.root)
            result[identity] = snapshot(identity, content, str(path.stat().st_mtime_ns),
                                        [rel.parent.as_posix()], content.splitlines()[1][2:], rel.as_posix())
        return result

    def get(self, identity):
        return self.list().get(key(identity))

    @contextmanager
    def locked(self):
        lock = self.root / ".uriel-write-lock"
        try:
            lock.mkdir()
        except FileExistsError:
            raise RecordError("Another writer holds the folder lock; inspect before clearing a stale lock.")
        try:
            yield
        finally:
            lock.rmdir()

    def create(self, identity, title, body, parent="project", content=None):
        with self.locked():
            return self._create(identity, title, body, parent, content=content)

    def _create(self, identity, title, body, parent, content=None):
        if self.get(identity):
            raise RecordError("Record already exists: " + identity)
        if identity == "project":
            directory = self.root
        else:
            if not self.get(parent):
                raise RecordError("Missing parent: " + parent)
            directory = self.root / (parent if parent != "project" else "")
        directory.mkdir(exist_ok=True)
        if self.root != directory.resolve() and self.root not in directory.resolve().parents:
            raise RecordError("Parent escapes folder.")
        path = directory / (key(identity) + ".md")
        with path.open("xb") as stream:
            stream.write((note_text(identity, title, body) if content is None else validate_content(identity, content)).encode("utf-8"))
        return self.get(identity)

    def update(self, identity, body, expected):
        with self.locked():
            current = self.get(identity)
            if current is None:
                raise RecordError("Missing record: " + identity)
            if signature(current) != expected:
                conflict = "conflict-" + digest(canonical([identity, expected, body]))[:24]
                if not self.get(conflict):
                    self._create(conflict, "Conflict: " + identity,
                                 structured({"target": identity, "expected": expected,
                                             "human": current, "proposed": body}), "decisions")
                return {"status": "conflict", "key": conflict}
            path = self.root / current["locator"]
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                tmp = Path(stream.name)
                stream.write(note_text(identity, current["title"], body).encode("utf-8"))
            try:
                if signature(self.get(identity)) != expected:
                    raise RecordError("Record changed during write; retry with the original expectation.")
                os.replace(tmp, path)
            finally:
                if tmp.exists():
                    tmp.unlink()
            return {"status": "updated", "note": self.get(identity)}

    def attachment(self, identity, name, data):
        if name in ("", ".", "..") or Path(name).name != name or "/" in name or "\\" in name or ":" in name:
            raise RecordError("Unsafe attachment name.")
        target = self.root / "attachments" / key(identity)
        path = target / name
        if target.resolve().parent != (self.root / "attachments").resolve() or self.root not in target.resolve().parents or path.is_symlink():
            raise RecordError("Unsafe attachment path.")
        target.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != data:
                raise RecordError("Attachment conflict.")
        else:
            with path.open("xb") as stream:
                stream.write(data)
        return digest(data)

    def read_attachment(self, identity, name):
        if name in ("", ".", "..") or Path(name).name != name or "/" in name or "\\" in name or ":" in name:
            raise RecordError("Unsafe attachment name.")
        path = self.root / "attachments" / key(identity) / name
        if self.root not in path.resolve().parents or path.is_symlink():
            raise RecordError("Unsafe attachment path.")
        return path.read_bytes()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RecordError("ETAPI redirects are refused to protect credentials.")


class Trilium:
    def __init__(self, url, project, parent="root", token=None, exclusive_write=False):
        url = url.rstrip("/")
        parsed = urlsplit(url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise RecordError("Use an HTTP(S) ETAPI server URL without credentials.")
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise RecordError("Plain HTTP is restricted to loopback; use HTTPS for remote ETAPI.")
        self.url = url if url.endswith("/etapi") else url + "/etapi"
        self.project = key(project)
        self.parent = parent
        self.token = token or os.environ.get("URIEL_ETAPI_TOKEN")
        if not self.token:
            raise RecordError("Set URIEL_ETAPI_TOKEN in the environment.")
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.exclusive_write = exclusive_write

    def request(self, method, path, value=None, raw=None, mime="text/plain", missing=False):
        headers = {"Authorization": self.token}
        if value is not None:
            raw = canonical(value).encode("utf-8")
            mime = "application/json"
        if raw is not None:
            headers["Content-Type"] = mime
        req = Request(self.url + path, data=raw, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as response:
                return response.read()
        except HTTPError as exc:
            if missing and exc.code == 404:
                return None
            raise RecordError("ETAPI request failed: HTTP " + str(exc.code)) from None

    def json(self, method, path, value=None, missing=False):
        response = self.request(method, path, value, missing=missing)
        return json.loads(response) if response else None

    def connect(self):
        return {"connected": bool(self.json("GET", "/app-info")), "url": self.url}

    def id(self, identity):
        return "u" + digest(self.project + ":" + key(identity))[:19]

    def read_id(self, note_id):
        meta = self.json("GET", "/notes/" + quote(note_id, safe=""), missing=True)
        if meta is None:
            return None
        attrs = {}
        for attr in meta.get("attributes", []):
            if attr.get("type") == "label" and attr.get("noteId", note_id) == note_id and attr["name"] in ("urielKey", "urielProject"):
                if attr["name"] in attrs:
                    raise RecordError("Duplicate stable identity label.")
                attrs[attr["name"]] = attr.get("value")
        identity = attrs.get("urielKey")
        if attrs.get("urielProject") != self.project or not identity or self.id(identity) != note_id:
            raise RecordError("Stable labels or note identity do not match: " + note_id)
        content = self.request("GET", "/notes/" + note_id + "/content").decode("utf-8")
        if not HEADER.match(content) or HEADER.match(content)[1] != identity:
            raise RecordError("Stable content key does not match: " + note_id)
        again = self.json("GET", "/notes/" + note_id)
        if meta != again:
            raise RecordError("Note changed while reading: " + note_id)
        revision = meta.get("utcDateModified") or meta.get("dateModified")
        if not revision:
            raise RecordError("ETAPI response lacks a revision timestamp.")
        return snapshot(identity, content, revision, meta.get("parentNoteIds", []),
                        meta["title"], note_id)

    def get(self, identity):
        return self.read_id(self.id(identity))

    def list(self):
        query = urlencode({"search": "#urielProject=" + self.project, "includeArchivedNotes": "true"})
        found = self.json("GET", "/notes?" + query)
        rows = {}
        for meta in found["results"]:
            row = self.read_id(meta["noteId"])
            if row["key"] in rows:
                raise RecordError("Duplicate stable key: " + row["key"])
            rows[row["key"]] = row
        return rows

    def create(self, identity, title, body, parent="project", content=None):
        if self.get(identity):
            raise RecordError("Record already exists: " + identity)
        note_id = self.id(identity)
        parent_id = self.parent if identity == "project" else self.id(parent)
        self.json("POST", "/create-note", {
            "noteId": note_id, "parentNoteId": parent_id, "title": title,
            "type": "code", "mime": "text/x-markdown", "content": note_text(identity, title, body) if content is None else validate_content(identity, content)})
        for name, value in (("urielProject", self.project), ("urielKey", identity)):
            self.json("POST", "/attributes", {"noteId": note_id, "type": "label",
                                              "name": name, "value": value, "isInheritable": False})
        return self.get(identity)

    def update(self, identity, body, expected):
        current = self.get(identity)
        if not current:
            raise RecordError("Missing record: " + identity)
        if signature(current) != expected:
            conflict = "conflict-" + digest(canonical([identity, expected, body]))[:24]
            if not self.get(conflict):
                self.create(conflict, "Conflict: " + identity,
                            structured({"target": identity, "expected": expected,
                                        "human": current, "proposed": body}), "decisions")
            return {"status": "conflict", "key": conflict}
        if not self.exclusive_write:
            proposal = "proposal-" + digest(canonical([identity, expected, body]))[:24]
            if not self.get(proposal):
                self.create(proposal, "Proposed edit: " + identity,
                            structured({"target": identity, "expected": expected,
                                        "previous": current, "proposed": body}), "decisions")
            return {"status": "review required", "key": proposal,
                    "target": current["locator"], "reason": "ETAPI cannot atomically compare and update. Apply the proposal in the note after checking its revision."}
        # ETAPI has no conditional content PUT. Compare again immediately before writing.
        if signature(self.get(identity)) != expected:
            raise RecordError("Note changed during write; retry with the original expectation.")
        self.request("POST", "/notes/" + self.id(identity) + "/revision")
        if signature(self.get(identity)) != expected:
            raise RecordError("Note changed after revision backup; retry with original expectation.")
        self.request("PUT", "/notes/" + self.id(identity) + "/content",
                     raw=note_text(identity, current["title"], body).encode("utf-8"))
        return {"status": "updated", "note": self.get(identity)}

    def attachment(self, identity, name, data):
        owner = self.id(identity)
        existing = self.json("GET", "/notes/" + owner + "/attachments")
        for row in existing:
            if row.get("title") == name:
                if self.request("GET", "/attachments/" + row["attachmentId"] + "/content") != data:
                    raise RecordError("Attachment conflict.")
                return digest(data)
        row = self.json("POST", "/attachments", {"ownerId": owner, "role": "file",
                                                 "mime": "application/pdf", "title": name, "position": 10})
        self.request("PUT", "/attachments/" + row["attachmentId"] + "/content",
                     raw=data, mime="application/octet-stream")
        return digest(data)

    def read_attachment(self, identity, name):
        rows = self.json("GET", "/notes/" + self.id(identity) + "/attachments")
        matches = [row for row in rows if row.get("title") == name]
        if len(matches) != 1:
            raise RecordError("Attachment missing or ambiguous.")
        return self.request("GET", "/attachments/" + matches[0]["attachmentId"] + "/content")
