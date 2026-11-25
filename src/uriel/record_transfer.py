"""Import, export, verification and checklists for research records."""
from __future__ import annotations
import json
import zipfile
from pathlib import Path
from .record_store import SECTIONS, RecordError, canonical, digest, key, note_body, parse_structured, signature, structured
from .research_record import KINDS, MODES, now, obj, records, valid_prediction, valid_result, audit_negative, check_before_push
from .claim_types import validate_evidence_label
from .paper_preflight import analyze_text

def verify(store, baseline=None, notes=None):
    notes = store.list() if notes is None else notes
    issues = []
    for k in ("project", *SECTIONS):
        if k not in notes:
            issues.append({"key": k, "issue": "missing required note"})
    if "project" in notes and "question" in notes:
        if digest(note_body(notes["question"]["content"])) != parse_structured(notes["project"]["content"])["question_sha256"]:
            issues.append({"key": "question", "issue": "verbatim drift"})
    rows = records(store, notes=notes)
    hashes = {}
    for k, row in rows.items():
        kind = row.get("kind")
        if kind == "prediction" and not valid_prediction(row):
            issues.append({"key": k, "issue": "prediction hash drift"})
        if kind in ("result", "conclusion") and not valid_result(row):
            issues.append({"key": k, "issue": "record hash drift"})
        if kind == "conclusion" and row.get("result"):
            result = rows.get(row["result"], {})
            if result.get("record_sha256") != row.get("result_sha256") or not valid_result(result):
                issues.append({"key": k, "issue": "linked result drift"})
            if row.get("classification") == "Closed":
                pred = rows.get(result.get("prediction")) if not result.get("exploratory") else None
                if audit_negative(pred, result)["classification"] != "Closed":
                    issues.append({"key": k, "issue": "closed result no longer passes audit"})
        if kind == "source":
            try:
                raw = store.read_attachment(k, row["attachment"]) if row.get("attachment") else row.get("original_text")
                if raw is None or digest(raw) != row["sha256"]:
                    issues.append({"key": k, "issue": "source hash missing or drifted"})
                if row["sha256"] in hashes:
                    issues.append({"key": k, "issue": "duplicate source bytes", "canonical": hashes[row["sha256"]]})
                hashes[row["sha256"]] = k
            except (OSError, RecordError, KeyError):
                issues.append({"key": k, "issue": "source bytes missing"})
        if kind == "source-alias" and (row.get("source") not in rows or rows[row["source"]].get("sha256") != row.get("sha256")):
            issues.append({"key": k, "issue": "source provenance link drift"})
    conflicts = [k for k in notes if k.startswith("conflict-")]
    resolved = {r.get("conflict") for r in rows.values() if r.get("kind") == "decision" and r.get("resolution") and r.get("reviewer")}
    pending = sorted(set(conflicts) - resolved)
    snapshots = {k: signature(n) for k, n in notes.items()}
    if baseline is not None:
        for k in sorted(set(baseline) | set(snapshots)):
            if baseline.get(k) != snapshots.get(k):
                issues.append({"key": k, "issue": "revision, content, placement or identity drift"})
    return {"verified": not issues, "issues": issues, "unresolved_conflicts": pending, "baseline": snapshots}

def import_plan(paths):
    items = []
    for name in paths:
        path = Path(name)
        raw = path.read_bytes()
        ext = path.suffix.lower()
        if ext not in (".md", ".txt", ".csv", ".json", ".pdf"):
            raise RecordError("Unsupported file type: " + ext)
        section = "sources"
        for token, dest in (("question", "question"), ("manuscript", "manuscript"), ("conclusion", "conclusions"),
                            ("gap", "gaps"), ("lead", "leads"), ("decision", "decisions"), ("ruled", "ruled-out"), ("current", "current")):
            if token in path.stem.lower() and ext in (".md", ".txt"):
                section = dest
                break
        items.append({"path": str(path.resolve()), "sha256": digest(raw), "key": "source-" + digest(raw),
                      "section": section, "reason": "Filename suggests " + section if section != "sources" else "Preserve source bytes and provenance"})
    return {"items": items}

def apply_import(store, plan):
    prepared = []
    for item in plan["items"]:
        path = Path(item["path"])
        raw = path.read_bytes()
        ext = path.suffix.lower()
        if (digest(raw) != item["sha256"] or item["key"] != "source-" + digest(raw)
                or item["section"] not in SECTIONS or ext not in (".md", ".txt", ".csv", ".json", ".pdf")
                or not isinstance(item.get("reason"), str) or not item["reason"].strip()):
            raise RecordError("Import changed since preview or invalid placement.")
        text = None if ext == ".pdf" else raw.decode("utf-8")
        prepared.append((item, path, raw, text))
    results = []
    sources = records(store, "source")
    by_hash = {r["sha256"]: k for k, r in sources.items()}
    for item, path, raw, text in prepared:
        k = by_hash.get(item["sha256"], item["key"])
        existing = store.get(k)
        if existing:
            previous = parse_structured(existing["content"])
            if previous.get("kind") != "source" or previous.get("sha256") != item["sha256"]:
                raise RecordError("Stable source key conflict.")
            if previous.get("attachment"):
                store.attachment(k, previous["attachment"], raw)
            elif digest(previous.get("original_text", "")) != item["sha256"]:
                raise RecordError("Canonical source bytes differ.")
            if previous.get("provenance") != path.name:
                alias = "source-alias-" + digest(canonical([k, path.name]))[:24]
                if not store.get(alias):
                    store.create(alias, "Additional provenance: " + path.name, structured({
                        "kind": "source-alias", "source": k, "sha256": item["sha256"], "provenance": path.name
                    }), "sources")
            results.append({"key": k, "status": "already imported"})
            continue
        row = {"kind": "source", "sha256": item["sha256"], "provenance": path.name,
               "placement_reason": item["reason"], "section": item["section"]}
        if text is None:
            row["attachment"] = path.name
        else:
            row["original_text"] = text
        store.create(k, path.name, structured(row), item["section"])
        if row.get("attachment"):
            store.attachment(k, row["attachment"], raw)
        by_hash[item["sha256"]] = k
        results.append({"key": k, "status": "imported"})
    return results

def export_zip(store, destination):
    rows = store.list()
    manifest = {"schema": "uriel.record-export.v1", "project": parse_structured(rows["project"]["content"])["project"], "notes": []}
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for k, note in sorted(rows.items()):
            archive.writestr("notes/" + key(k) + ".md", note["content"])
            row = {"key": k, "title": note["title"], "sha256": note["sha256"], "parent": "project" if k in SECTIONS or k == "project" else "decisions"}
            if k not in SECTIONS and k != "project" and note_body(note["content"]).lstrip().startswith("```json\n"):
                data = parse_structured(note["content"])
                row["parent"] = data.get("section") or KINDS.get(data.get("kind"), "decisions")
                if data.get("attachment"):
                    raw = store.read_attachment(k, data["attachment"])
                    if digest(raw) != data["sha256"]:
                        raise RecordError("Attachment hash mismatch.")
                    archive.writestr("attachments/" + k + "/data", raw)
            if k not in SECTIONS and k != "project":
                if hasattr(store, "id"):
                    parent_keys = [pk for pk in SECTIONS if store.id(pk) in note["parents"]]
                else:
                    parent_keys = [pk for pk in SECTIONS if pk in note["parents"]]
                if len(parent_keys) == 1:
                    row["parent"] = parent_keys[0]
            row["original_placement"] = note["parents"]
            manifest["notes"].append(row)
        archive.writestr("manifest.json", canonical(manifest))
    return {"exported": len(rows), "path": str(destination)}

def import_zip(store, source):
    with zipfile.ZipFile(source) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise RecordError("Duplicate ZIP members.")
        if sum(info.file_size for info in archive.infolist()) > 512 * 1024 * 1024:
            raise RecordError("Export exceeds the 512 MiB uncompressed import limit.")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schema") != "uriel.record-export.v1":
            raise RecordError("Unknown export format.")
        if getattr(store, "project", manifest["project"]) != manifest["project"] or (store.get("project") and obj(store, "project")["project"] != manifest["project"]):
            raise RecordError("Export project identity differs.")
        rows = manifest["notes"]
        keys = [key(r["key"]) for r in rows]
        if len(keys) != len(set(keys)):
            raise RecordError("Duplicate export key.")
        prepared = []
        for row in rows:
            k = row["key"]
            content = archive.read("notes/" + k + ".md").decode("utf-8")
            if digest(content) != row["sha256"] or not content.startswith("<!-- uriel-key:" + k + " -->\n"):
                raise RecordError("Export hash or key mismatch.")
            if row.get("parent") not in ("project", *SECTIONS):
                raise RecordError("Invalid portable parent.")
            if k == "project" and parse_structured(content).get("project") != manifest["project"]:
                raise RecordError("Export project record differs from manifest.")
            attachment = None
            if k not in SECTIONS and k != "project" and note_body(content).lstrip().startswith("```json\n"):
                data = parse_structured(content)
                if data.get("attachment"):
                    attachment = archive.read("attachments/" + k + "/data")
                    if digest(attachment) != data["sha256"]:
                        raise RecordError("Export attachment hash mismatch.")
            prepared.append((row, content, attachment))
        prepared.sort(key=lambda p: 0 if p[0]["key"] == "project" else 1 if p[0]["key"] in SECTIONS else 2)
        result = []
        for row, content, attachment in prepared:
            k = row["key"]
            old = store.get(k)
            if old:
                if old["sha256"] != row["sha256"]:
                    conflict = "conflict-" + digest(canonical([k, row["sha256"]]))[:24]
                    if not store.get(conflict):
                        store.create(conflict, "Import conflict: " + k, structured({"target": k, "human": old, "proposed": content}), "decisions")
                    result.append({"key": k, "status": "conflict", "conflict": conflict})
                    continue
                result.append({"key": k, "status": "already present"})
            else:
                store.create(k, row["title"], note_body(content), row["parent"], content=content)
                result.append({"key": k, "status": "created"})
            if k not in SECTIONS and k != "project" and note_body(content).lstrip().startswith("```json\n"):
                data = parse_structured(content)
                if data.get("attachment"):
                    store.attachment(k, data["attachment"], attachment)
    return result

def checklist(store, stage, attestations=None, lead=None, prediction=None, result=None, prior=None):
    attestations = attestations or {}
    notes = store.list()
    rows = records(store, notes=notes)
    checks = []
    search = None
    preflight = None
    def add(name, passed, target):
        checks.append({"check": name, "passed": bool(passed), "fix": target, "locator": notes.get(target, {}).get("locator")})
    def has(kind):
        return any(r.get("kind") == kind for r in rows.values())
    def att(name, target):
        v = attestations.get(name, {})
        add(name, isinstance(v, dict) and v.get("confirmed") is True and v.get("evidence") and v.get("by"), target)
    def prose(k):
        return note_body(notes[k]["content"]) if k in notes else ""
    integrity = verify(store, notes=notes)
    add("record integrity", integrity["verified"], "project")
    add("conflicts reviewed", not integrity["unresolved_conflicts"], "decisions")
    if stage == "start":
        add("verbatim question", bool(prose("question").strip()), "question")
        add("declared mode", obj(store, "project")["mode"] in MODES, "project")
        sources = [r["sha256"] for r in rows.values() if r.get("kind") == "source"]
        add("sources loaded and deduplicated", bool(sources) and len(sources) == len(set(sources)), "sources")
        add("current picture", bool(prose("current").strip()), "current")
        att("prior work and closed ideas imported", "conclusions")
    elif stage in ("mid-before", "mid-after"):
        lead_row = rows.get(lead, {})
        add("lead identified", lead_row.get("kind") == "lead", "leads")
        if lead_row.get("kind") == "lead":
            search = check_before_push(store, lead_row["idea"])
        att("tree read", "current")
        att("duplicate search reviewed", "leads")
        att("reused changes and gaps stated", "leads")
        if stage == "mid-after":
            result_row = rows.get(result, {})
            prediction = result_row.get("prediction")
            add("result linked", result_row.get("kind") == "result" and result_row.get("lead") == lead and valid_result(result_row), "conclusions")
            prior_row = rows.get(prior, {})
            add("prior checklist linked", prior_row.get("stage") == "mid-before" and prior_row.get("complete") is True and prior_row.get("lead") == lead and prior_row.get("prediction") == prediction, "decisions")
            current_changed = prior_row.get("current_snapshot") != signature(notes["current"]) if "current" in notes and prior_row else False
            if current_changed:
                add("current picture rewritten", True, "current")
            else:
                att("current picture unchanged with reason", "current")
            if any(r.get("kind") == "conclusion" and r.get("result") == result and valid_result(r) for r in rows.values()):
                add("register updated", True, "conclusions")
            else:
                att("register unchanged with reason", "conclusions")
            att("contradictions listed for author", "gaps")
        pred = rows.get(prediction, {})
        add("frozen prediction", pred.get("kind") == "prediction" and pred.get("lead") == lead and valid_prediction(pred), "leads")
    elif stage == "pre-submission":
        claims = [r for r in rows.values() if r.get("kind") == "claim"]
        valid = bool(claims)
        for claim in claims:
            try:
                validate_evidence_label(claim)
                valid = valid and bool(claim.get("evidence")) and all(ref in rows and rows[ref].get("kind") in ("source", "result") for ref in claim["evidence"])
            except ValueError:
                valid = False
        add("claims labelled and evidence linked", valid, "manuscript")
        add("counter-evidence and limitations", has("gap"), "gaps")
        conclusions = [r for r in rows.values() if r.get("kind") == "conclusion"]
        valid = bool(conclusions)
        for r in conclusions:
            if r["classification"] == "Closed":
                result = rows.get(r.get("result"), {})
                pred = rows.get(result.get("prediction")) if not result.get("exploratory") else None
                valid = valid and valid_result(r) and valid_result(result) and audit_negative(pred, result)["classification"] == "Closed"
        add("negative audit", valid, "conclusions")
        add("frozen predictions linked", all(r.get("prediction") in rows for r in conclusions if r.get("classification") == "Closed"), "leads")
        preflight = analyze_text(prose("manuscript"))
        add("manuscript preflight", bool(prose("manuscript").strip()) and preflight["status"] == "NO_DETERMINISTIC_LEADS", "manuscript")
        for name in ("all material manuscript claims registered", "numbers reproduce from code", "AI assistance disclosure", "author voice pass", "venue rules checked", "human approval"):
            att(name, "manuscript")
    else:
        raise RecordError("Unknown checklist.")
    receipt = {"kind": "checklist", "stage": stage, "checks": checks, "attestations": attestations, "timestamp": now(),
               "complete": all(c["passed"] for c in checks), "boundary": "Defined checks, not scientific correctness."}
    if stage in ("mid-before", "mid-after"):
        receipt.update(lead=lead, prediction=prediction, result=result, prior=prior,
                       current_snapshot=signature(notes["current"]) if "current" in notes else None,
                       duplicate_search=search)
    if preflight is not None:
        receipt["preflight"] = preflight
    k = "checklist-" + digest(canonical(receipt))[:24]
    store.create(k, "Checklist: " + stage, structured(receipt), "decisions")
    return dict(receipt, key=k)
