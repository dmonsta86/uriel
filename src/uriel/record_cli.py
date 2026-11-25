"""CLI integration for the research-record workflow."""
from __future__ import annotations
import json
import os
from pathlib import Path
from .core import Refusal
from .record_store import Folder, Trilium, RecordError, signature
from . import research_record as rr
from . import record_transfer as transfer

def location(p, remote=False):
    if not remote:
        p.add_argument("--folder", default=None, help="Markdown record directory (default: ./research-record)")
    p.add_argument("--url", default=None, help="ETAPI server URL; or URIEL_TRILIUM_URL")
    p.add_argument("--project", default=None, help="Stable project key")
    p.add_argument("--parent", default="root", help="Trilium parent note ID")
    p.set_defaults(remote=remote)

def register(commands):
    for name, remote in (("record", False), ("trilium", True)):
        top = commands.add_parser(name, help="Research record" if not remote else "Trilium research record")
        actions = top.add_subparsers(dest="record_action", required=True)
        def action(name, help):
            p = actions.add_parser(name, help=help)
            location(p, remote)
            return p
        if remote:
            action("connect", "Test ETAPI connection using URIEL_ETAPI_TOKEN")
        p = action("init", "Initialize the project tree")
        p.add_argument("--question-file", required=True)
        p.add_argument("--mode", choices=rr.MODES, required=True)
        p = action("read", "Read a note with its revision expectation")
        p.add_argument("key")
        action("list", "List current notes and snapshots")
        p = action("rewrite", "Rewrite section prose, preserving history and conflicts")
        p.add_argument("key")
        p.add_argument("--file", required=True)
        p.add_argument("--expected", required=True, help="JSON from record read")
        p.add_argument("--exclusive-write", action="store_true", help="For ETAPI only: confirm no other human or assistant is editing; otherwise save a proposal")
        for verb in ("add", "freeze", "result", "conclude", "assign"):
            p = action(verb, "Record " + verb)
            p.add_argument("key", help="Lead key for assign; otherwise new record key")
            p.add_argument("--file", required=True, help="JSON record")
        p = action("import", "Preview placement or apply a confirmed preview")
        p.add_argument("files", nargs="*")
        p.add_argument("--plan", help="Save or load preview JSON")
        p.add_argument("--confirm", action="store_true")
        p = action("verify", "Verify stable keys, content and optional baseline")
        p.add_argument("--baseline")
        p.add_argument("--save-baseline")
        p = action("export", "Export a portable ZIP")
        p.add_argument("file")
        p = action("import-zip", "Import a portable ZIP without duplicating keys")
        p.add_argument("file")
        p.add_argument("--confirm", action="store_true", required=True)
        p = action("import-verbatim", "Import consented existing Research Verbatim Ledger entries verbatim")
        p.add_argument("--root", required=True)
        p.add_argument("--user", required=True)
        p.add_argument("--confirm", action="store_true", required=True)
    p = commands.add_parser("check-before-push", help="Search existing leads and conclusions before starting")
    location(p)
    p.add_argument("idea")
    p = commands.add_parser("summary", help="Generate a successor summary")
    location(p)
    p.add_argument("--for-successors", required=True, action="store_true")
    p = commands.add_parser("checklist", help="Record research checklist state")
    location(p)
    p.add_argument("stage", choices=("start", "mid-before", "mid-after", "pre-submission"))
    p.add_argument("--attestations", help="JSON named human/assistant confirmations with evidence")
    p.add_argument("--lead", help="Lead key for mid-research checklist")
    p.add_argument("--prediction", help="Frozen prediction key for mid-before")
    p.add_argument("--result", help="Result key for mid-after")
    p.add_argument("--prior", help="Mid-before receipt key for mid-after")

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)

def backend(args):
    folder = getattr(args, "folder", None)
    url = args.url or (os.environ.get("URIEL_TRILIUM_URL") if not folder else None)
    if url and folder:
        raise RecordError("Choose one authoritative backend.")
    if args.remote or url:
        if not url:
            raise RecordError("Provide --url or URIEL_TRILIUM_URL.")
        if not args.project and getattr(args, "record_action", None) != "connect":
            raise RecordError("Provide --project for ETAPI operations.")
        return Trilium(url, args.project or "connection-test", args.parent, exclusive_write=getattr(args, "exclusive_write", False))
    return Folder(folder or "research-record")

def run(args):
    try:
        store = backend(args)
        if args.command == "summary":
            return rr.summary(store)
        if args.command == "check-before-push":
            return rr.check_before_push(store, args.idea)
        if args.command == "checklist":
            return transfer.checklist(store, args.stage, load(args.attestations) if args.attestations else None, lead=args.lead, prediction=args.prediction, result=args.result, prior=args.prior)
        a = args.record_action
        if a == "connect":
            return store.connect()
        if a == "init":
            if not args.project:
                raise RecordError("Provide --project.")
            return rr.initialize(store, args.project, Path(args.question_file).read_bytes().decode("utf-8"), args.mode)
        if a == "read":
            note = store.get(args.key)
            if note is None:
                raise RecordError("Note not found.")
            return dict(note, expected=signature(note))
        if a == "list":
            return store.list()
        if a == "rewrite":
            expected = load(args.expected)
            if "result" in expected:
                expected = expected["result"]
            return rr.rewrite(store, args.key, Path(args.file).read_bytes().decode("utf-8"), expected.get("expected", expected))
        if a in ("add", "freeze", "result", "conclude", "assign"):
            op = {"add": rr.add_record, "freeze": rr.freeze, "result": rr.add_result,
                  "conclude": rr.conclude, "assign": rr.start_task}[a]
            return op(store, args.key, load(args.file))
        if a == "verify":
            baseline = load(args.baseline) if args.baseline else None
            if baseline and "baseline" in baseline:
                baseline = baseline["baseline"]
            report = transfer.verify(store, baseline)
            if args.save_baseline:
                save(args.save_baseline, report["baseline"])
            return report
        if a == "import":
            if args.confirm:
                if not args.plan or args.files:
                    raise RecordError("Confirm an existing plan, not new filenames.")
                return transfer.apply_import(store, load(args.plan))
            if not args.files:
                raise RecordError("Provide files to preview.")
            plan = transfer.import_plan(args.files)
            if args.plan:
                save(args.plan, plan)
            return plan
        if a == "export":
            return transfer.export_zip(store, args.file)
        if a == "import-zip":
            return transfer.import_zip(store, args.file)
        if a == "import-verbatim":
            from .research_verbatim import review_entries, verify_ledger
            checked = verify_ledger(args.root, args.user)
            if not checked["verified"]:
                raise RecordError("Verbatim ledger integrity check failed.")
            rows = review_entries(args.root, args.user)["entries"]
            imported = []
            from .record_store import digest, structured
            for row in rows:
                identity = "verbatim-" + digest(json.dumps(row, sort_keys=True, ensure_ascii=False))[:48]
                if not store.get(identity):
                    store.create(identity, "Verbatim ledger entry", structured({"kind": "verbatim", "exact_text": row["exact_text"], "ledger_entry": row}), "question")
                imported.append(identity)
            return {"imported_keys": imported}
    except (RecordError, OSError, ValueError, KeyError, TypeError) as exc:
        raise Refusal(str(exc), code="RESEARCH_RECORD_REFUSED") from exc
    raise Refusal("Unknown record command", code="UNKNOWN_COMMAND")
