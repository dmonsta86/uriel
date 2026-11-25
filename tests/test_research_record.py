"""Exercise the same record lifecycle on Markdown and a mock ETAPI server."""
from __future__ import annotations
import json
import threading
import tempfile
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from uriel.record_store import Folder, Trilium, RecordError, digest, note_body, parse_structured, signature
from uriel import research_record as rr
from uriel import record_transfer as tr
from uriel.cli import main


class MockETAPI(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, value=None, status=200, binary=False):
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream" if binary else "application/json")
        self.end_headers()
        if value is not None:
            self.wfile.write(value if binary else json.dumps(value).encode("utf-8"))

    def handle_request(self):
        if self.headers.get("Authorization") != "synthetic-test-token":
            return self.send(status=401)
        path = urlsplit(self.path)
        parts = path.path.split("/")[2:]
        method = self.command
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        server = self.server
        if parts == ["app-info"]:
            return self.send({"appVersion": "mock"})
        if parts == ["create-note"] and method == "POST":
            value = json.loads(raw)
            note_id = value["noteId"]
            if note_id in server.notes:
                return self.send(status=409)
            server.notes[note_id] = {"noteId": note_id, "title": value["title"], "parentNoteIds": [value["parentNoteId"]], "attributes": [], "utcDateModified": "1"}
            server.content[note_id] = value["content"].encode("utf-8")
            return self.send({"note": server.notes[note_id]}, 201)
        if parts == ["attributes"] and method == "POST":
            value = json.loads(raw)
            server.notes[value["noteId"]]["attributes"].append(value)
            return self.send(value, 201)
        if parts == ["notes"]:
            project = parse_qs(path.query)["search"][0].split("=")[1]
            rows = [n for n in server.notes.values() if any(a["name"] == "urielProject" and a["value"] == project for a in n["attributes"])]
            return self.send({"results": rows})
        if parts[0] == "notes":
            note_id = parts[1]
            if note_id not in server.notes:
                return self.send(status=404)
            if len(parts) == 2:
                return self.send(server.notes[note_id])
            if parts[2] == "content":
                if method == "PUT":
                    server.content[note_id] = raw
                    server.notes[note_id]["utcDateModified"] += "1"
                    return self.send(status=204)
                return self.send(server.content[note_id], binary=True)
            if parts[2] == "revision":
                server.revisions.append(server.content[note_id])
                return self.send(status=204)
            if parts[2] == "attachments":
                return self.send([a for a in server.attachments.values() if a["ownerId"] == note_id])
        if parts == ["attachments"] and method == "POST":
            value = json.loads(raw)
            aid = str(len(server.attachments) + 1)
            value["attachmentId"] = aid
            server.attachments[aid] = value
            return self.send(value, 201)
        if parts[0] == "attachments" and len(parts) == 3:
            if method == "PUT":
                server.blobs[parts[1]] = raw
                return self.send(status=204)
            return self.send(server.blobs[parts[1]], binary=True)
        return self.send(status=404)

    do_GET = do_POST = do_PUT = handle_request


class ResearchRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Folder(self.root / "record")
        rr.initialize(self.store, "demo", "Does the simulated offset exceed 5 units?\n", "evidence-neutral")

    def seed(self, store):
        rr.add_record(store, "control", {"kind": "source", "sha256": digest("synthetic control"), "provenance": "synthetic control", "original_text": "synthetic control"})
        rr.add_record(store, "offset", {"kind": "lead", "idea": "simulated offset", "aliases": ["shift"], "status": "queued", "owner": "unassigned"})
        pred = rr.freeze(store, "prediction", {"lead": "offset", "hypothesis": "offset 5", "control_source": "control",
                 "control_result": "zero offset", "effect_size": 5, "effect_derivation": "synthetic input 5", "unit": "units",
                 "acceptance_criteria": "null when estimate is zero and sensitivity below 5"})
        return parse_structured(pred["content"])

    def result(self):
        return {"lead": "offset", "source": "control", "result": "zero", "unit": "units", "mode": "evidence-neutral",
                "prediction": "prediction", "observed_at": datetime.now(timezone.utc).isoformat(),
                "null": True, "effect_estimate": 0, "sensitivity": 1, "sensitivity_basis": "synthetic precision",
                "control_reproduced": True, "control_evidence": "control trace", "acceptance_met": True,
                "acceptance_evidence": "estimate zero", "audit": {k: {"pass": True, "reason": "synthetic fixture condition"} for k in rr.AUDIT}}

    def conclusion(self, classification="Closed"):
        return {"lead": "offset", "result": "result", "classification": classification, "mode": "evidence-neutral",
                "coincidence": False, "multi_factor": False, "logical_steps": ["reproduce control", "compare offset"], "alternatives": ["no offset"],
                "workarounds": ["none necessary"], "would_change": "new calibrated test", "thoroughness": "one synthetic test", "reviewer": "reviewer"}

    def test_lifecycle_power_audit_and_duplicate_guard(self):
        pred = self.seed(self.store)
        self.assertTrue(rr.valid_prediction(pred))
        row = self.result()
        self.assertEqual(rr.audit_negative(pred, row)["classification"], "Closed")
        for field in rr.AUDIT:
            bad = dict(row, audit=dict(row["audit"], **{field: {"pass": False, "reason": "not resolved"}}))
            self.assertNotEqual(rr.audit_negative(pred, bad)["classification"], "Closed", field)
        weak = dict(row, sensitivity=6)
        self.assertEqual(rr.audit_negative(pred, weak)["disposition"], "underpowered")
        self.assertEqual(rr.audit_negative(pred, dict(weak, upper_limit=6, limit_scope="observed offset"))["classification"], "Upper limit only")
        self.assertNotEqual(rr.audit_negative(None, row)["classification"], "Closed")
        task = {"owner": "session-one", "question": "test offset", "inputs": ["control"], "prediction": "prediction",
                "deliverable": "result", "verification": "recompute", "duplicate_review": "reviewed related lead",
                "reused": "control", "changes": "offset", "missing": "none"}
        attest = {k: {"confirmed": True, "evidence": "synthetic check", "by": "reviewer"} for k in
                  ("tree read", "duplicate search reviewed", "reused changes and gaps stated")}
        receipt = tr.checklist(self.store, "mid-before", attest, lead="offset", prediction="prediction")
        self.assertTrue(receipt["complete"], receipt)
        task["checklist"] = receipt["key"]
        rr.start_task(self.store, "offset", task)
        with self.assertRaises(RecordError):
            rr.start_task(self.store, "offset", dict(task, owner="session-two"))
        self.assertTrue(any(m["status"] == "already running" for m in rr.check_before_push(self.store, "shift")["matches"]))
        row.update(owner="session-one", verification="recomputed fixture", observed_at=datetime.now(timezone.utc).isoformat())
        rr.add_result(self.store, "result", row)
        with self.assertRaises(RecordError):
            rr.conclude(self.store, "wrong", self.conclusion("Untested"))
        with self.assertRaises(RecordError):
            rr.conclude(self.store, "self-review", dict(self.conclusion(), reviewer="session-one"))
        rr.conclude(self.store, "conclusion", self.conclusion())
        self.assertTrue(any(m["status"] == "already closed" for m in rr.check_before_push(self.store, "shift")["matches"]))
        self.assertEqual(rr.summary(self.store)["leads"]["offset"]["status"], "done")
        self.assertEqual(rr.check_before_push(self.store, "unrelated")["status"], "nothing found")
        attest.update({k: {"confirmed": True, "evidence": "synthetic review", "by": "reviewer"} for k in
                       ("current picture unchanged with reason", "contradictions listed for author")})
        after = tr.checklist(self.store, "mid-after", attest, lead="offset", result="result", prior=receipt["key"])
        self.assertTrue(after["complete"], after)
        self.assertFalse(tr.checklist(self.store, "mid-before", attest, lead="wrong", prediction="prediction")["complete"])
        self.assertNotEqual(rr.audit_negative(pred, dict(row, effect_estimate=5))["classification"], "Closed")

    def test_exploratory_result_and_labels(self):
        self.seed(self.store)
        row = self.result()
        row.pop("prediction")
        result = parse_structured(rr.add_result(self.store, "result", row)["content"])
        self.assertTrue(result["exploratory"])
        with self.assertRaises(RecordError):
            rr.conclude(self.store, "bad", self.conclusion())
        with self.assertRaises(ValueError):
            rr.add_record(self.store, "bad-claim", {"kind": "claim", "statement": "measurement", "label": "direct observation"})
        rr.add_record(self.store, "claim", {"kind": "claim", "statement": "synthetic measurement", "label": "direct observation", "instrument": "simulation", "uncertainty": "1 unit", "evidence": ["control"]})
        self.assertFalse(tr.checklist(self.store, "pre-submission")["complete"])

    def test_folder_revision_conflict_move_and_zip(self):
        first = self.store.get("current")
        rr.rewrite(self.store, "current", "First picture.", signature(first))
        old = self.store.get("current")
        path = self.store.root / old["locator"]
        moved = self.store.root / "renamed.md"
        path.rename(moved)
        report = rr.rewrite(self.store, "current", "New picture.", signature(old))
        self.assertEqual(report["status"], "conflict")
        self.assertEqual(note_body(self.store.get("current")["content"]), "First picture.")
        self.assertTrue(tr.verify(self.store)["verified"])
        self.assertTrue(tr.verify(self.store)["unresolved_conflicts"])
        baseline = tr.verify(self.store)["baseline"]
        rr.rewrite(self.store, "current", "New picture.", signature(self.store.get("current")))
        self.assertFalse(tr.verify(self.store, baseline)["verified"])
        z = self.root / "export.zip"
        tr.export_zip(self.store, z)
        clone = Folder(self.root / "clone")
        tr.import_zip(clone, z)
        self.assertEqual(note_body(clone.get("current")["content"]), "New picture.")
        self.assertTrue(all(r["status"] == "already present" for r in tr.import_zip(clone, z)))

    def test_import_preview_dedup_and_attachment(self):
        csv = self.root / "data.csv"
        csv.write_bytes(b"x,y\r\n1,2\r\n")
        pdf = self.root / "report.pdf"
        pdf.write_bytes(b"%PDF synthetic bytes")
        plan = tr.import_plan([csv, pdf])
        self.assertEqual(len(self.store.list()), 10)
        tr.apply_import(self.store, plan)
        self.assertEqual(len(self.store.list()), 12)
        self.assertTrue(all(r["status"] == "already imported" for r in tr.apply_import(self.store, plan)))
        self.assertTrue(tr.verify(self.store)["verified"])
        alias = self.root / "same.csv"
        alias.write_bytes(csv.read_bytes())
        tr.apply_import(self.store, tr.import_plan([alias]))
        self.assertEqual(len([r for r in rr.records(self.store).values() if r.get("kind") == "source"]), 2)
        csv.write_bytes(b"changed")
        with self.assertRaises(RecordError):
            tr.apply_import(self.store, plan)

    def test_mock_etapi_create_propose_update_move_verify(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), MockETAPI)
        server.notes, server.content, server.attachments, server.blobs, server.revisions = {}, {}, {}, {}, []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        live = Trilium("http://127.0.0.1:" + str(server.server_port), "demo", token="synthetic-test-token")
        self.assertTrue(live.connect()["connected"])
        rr.initialize(live, "demo", "Exact wording", "evidence-neutral")
        self.assertEqual(len(live.list()), 10)
        current = live.get("current")
        proposal = rr.rewrite(live, "current", "Proposed", signature(current))
        self.assertEqual(proposal["status"], "review required")
        self.assertEqual(live.get("current")["sha256"], current["sha256"])
        live.exclusive_write = True
        updated = rr.rewrite(live, "current", "First picture", signature(current))
        self.assertEqual(updated["status"], "updated")
        self.assertTrue(server.revisions)
        baseline = tr.verify(live)["baseline"]
        old = live.get("current")
        server.notes[live.id("current")]["parentNoteIds"] = ["human-moved"]
        server.notes[live.id("current")]["title"] = "Renamed by human"
        conflict = rr.rewrite(live, "current", "Do not overwrite", signature(old))
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(live.get("current")["parents"], ["human-moved"])
        self.assertEqual(note_body(live.get("current")["content"]), "First picture")
        self.assertFalse(tr.verify(live, baseline)["verified"])
        pdf = self.root / "test.pdf"
        pdf.write_bytes(b"%PDF synthetic")
        tr.apply_import(live, tr.import_plan([pdf]))
        self.assertTrue(tr.verify(live)["verified"])

    def test_cli_init_and_verify(self):
        question = self.root / "question.txt"
        question.write_bytes(b"Verbatim question")
        root = str(self.root / "cli")
        self.assertEqual(main(["record", "init", "--folder", root, "--project", "cli-demo", "--mode", "exploratory", "--question-file", str(question)]), 0)
        self.assertEqual(main(["record", "verify", "--folder", root]), 0)

if __name__ == "__main__":
    unittest.main()
