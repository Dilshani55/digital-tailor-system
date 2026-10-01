#!/usr/bin/env python3
"""
orphan_report.py - READ-ONLY report of saved records whose references no longer match.

It only reads the database and the uploads / outputs folders. It never changes, deletes or creates anything.
The "repair plan" it prints is a dry run: a list of what a person could decide to do, not something it does.

Checks
  pdf_exports      -> pattern missing, PDF file missing on disk
  pattern_results  -> session missing
  sessions         -> user / customer profile / design photo missing; "complete" but no pattern
  design_images    -> user missing, photo file missing on disk
  measurements     -> user missing
  files            -> PDF or photo files on disk that no record refers to

Usage (from backend/):
  venv\\Scripts\\python tools\\orphan_report.py                      (database from backend/.env)
  venv\\Scripts\\python tools\\orphan_report.py --out ..\\evidence\\db_integrity
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pymongo import MongoClient                                                # noqa: E402
from config import Config                                                      # noqa: E402

MANUAL_IMAGE = "manual_selection.png"


def _ids(db, collection):
    return {d["_id"] for d in db[collection].find({}, {"_id": 1})}


def _ref(value):
    """A stored reference is an ObjectId or a DBRef."""
    return getattr(value, "id", value)


def collect(db, upload_dir, output_dir):
    users, profiles, images = _ids(db, "users"), _ids(db, "measurements"), _ids(db, "design_images")
    sessions, patterns = _ids(db, "sessions"), _ids(db, "pattern_results")
    findings = []

    def add(kind, collection, doc_id, detail, plan):
        findings.append({"kind": kind, "collection": collection, "id": str(doc_id), "detail": detail,
                         "dry_run_plan": plan})

    used_pdfs = set()
    for e in db.pdf_exports.find({}, {"pattern_id": 1, "file_path": 1}):
        name = os.path.basename(e.get("file_path") or "")
        used_pdfs.add(name)
        if _ref(e.get("pattern_id")) not in patterns:
            add("pdf_without_pattern", "pdf_exports", e["_id"], f"pattern {_ref(e.get('pattern_id'))} does not exist",
                "Review, then remove this PDF record (the app already ignores it: it is not listed or counted).")
        elif not name or not os.path.isfile(os.path.join(output_dir, name)):
            add("pdf_file_missing", "pdf_exports", e["_id"], f"file '{name}' is not in the outputs folder",
                "Create the PDF again from the saved pattern, or remove this PDF record.")

    session_of_pattern = Counter()
    for p in db.pattern_results.find({}, {"session_id": 1}):
        sid = _ref(p.get("session_id"))
        session_of_pattern[sid] += 1
        if sid not in sessions:
            add("pattern_without_session", "pattern_results", p["_id"], f"session {sid} does not exist",
                "Nobody can open this pattern (no owner). Review, then remove it together with its PDFs.")

    for s in db.sessions.find({}, {"user_id": 1, "image_id": 1, "measurement_id": 1, "status": 1}):
        uid, iid, mid = _ref(s.get("user_id")), _ref(s.get("image_id")), _ref(s.get("measurement_id"))
        if uid not in users:
            add("session_without_user", "sessions", s["_id"], f"user {uid} does not exist",
                "Belongs to a deleted account. Review, then remove with its pattern and PDFs.")
        if mid is not None and mid not in profiles:
            add("session_customer_deleted", "sessions", s["_id"], f"customer profile {mid} does not exist",
                "No action needed: the pattern keeps its own copy of the measurements; the customer shows as unknown.")
        if iid is not None and iid not in images:
            add("session_photo_deleted", "sessions", s["_id"], f"design photo record {iid} does not exist",
                "No action needed: the pattern keeps its confirmed design; the PDF is made without the photo.")
        if s.get("status") == "complete" and session_of_pattern[s["_id"]] == 0:
            add("complete_session_without_pattern", "sessions", s["_id"], "status is 'complete' but no pattern refers to it",
                "Cause not known from the data. Review; the app does not list or count sessions, only patterns.")

    used_photos = set()
    for i in db.design_images.find({}, {"user_id": 1, "file_path": 1}):
        name = os.path.basename(i.get("file_path") or "")
        used_photos.add(name)
        if _ref(i.get("user_id")) not in users:
            add("photo_without_user", "design_images", i["_id"], f"user {_ref(i.get('user_id'))} does not exist",
                "Belongs to a deleted account. Review, then remove the record and its file.")
        if name and name != MANUAL_IMAGE and not os.path.isfile(os.path.join(upload_dir, name)):
            add("photo_file_missing", "design_images", i["_id"], f"file '{name}' is not in the uploads folder",
                "The photo cannot be shown or analysed again. Review; upload the photo again if it is needed.")

    for m in db.measurements.find({}, {"user_id": 1}):
        if _ref(m.get("user_id")) not in users:
            add("customer_without_user", "measurements", m["_id"], f"user {_ref(m.get('user_id'))} does not exist",
                "Belongs to a deleted account. Review, then remove.")

    for folder, used, kind in ((output_dir, used_pdfs, "pdf_file_without_record"),
                               (upload_dir, used_photos, "photo_file_without_record")):
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.startswith(".") or not os.path.isfile(os.path.join(folder, name)) or name in used:
                    continue
                add(kind, "files", name, f"'{name}' in {os.path.basename(folder)}/ is not referred to by any record",
                    "Review, then remove the file to free disk space.")

    totals = {c: db[c].count_documents({}) for c in
              ("users", "measurements", "design_images", "sessions", "pattern_results", "pdf_exports")}
    return totals, findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mongo-uri", default=Config.MONGO_URI)
    ap.add_argument("--uploads", default=Config.UPLOAD_FOLDER)
    ap.add_argument("--outputs", default=Config.OUTPUT_FOLDER)
    ap.add_argument("--out", help="folder for orphan_report.json and orphan_report.md (optional)")
    a = ap.parse_args()

    client = MongoClient(a.mongo_uri, serverSelectionTimeoutMS=5000)
    db = client.get_default_database()
    totals, findings = collect(db, a.uploads, a.outputs)
    client.close()

    by_kind = Counter(f["kind"] for f in findings)
    report = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "database": db.name,
              "read_only": True, "records": totals, "findings_by_kind": dict(sorted(by_kind.items())),
              "findings": findings}

    print(f"Database: {db.name}   (read only - nothing was changed)")
    print("Records:  " + ", ".join(f"{k} {v}" for k, v in totals.items()))
    if not findings:
        print("No inconsistent references found.")
    for kind, n in sorted(by_kind.items()):
        plan = next(f["dry_run_plan"] for f in findings if f["kind"] == kind)
        print(f"  {n:4d}  {kind}\n        dry-run plan: {plan}")

    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "orphan_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        lines = [f"# Database reference report ({db.name})", "",
                 f"Generated {report['generated_at']}. Read only: nothing was changed, deleted or created.", "",
                 "| Collection | Records |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in totals.items()]
        lines += ["", "| Finding | Count | Dry-run plan (not carried out) |", "|---|---|---|"]
        for kind, n in sorted(by_kind.items()):
            lines.append(f"| {kind} | {n} | {next(f['dry_run_plan'] for f in findings if f['kind'] == kind)} |")
        if not findings:
            lines.append("| none | 0 | - |")
        with open(os.path.join(a.out, "orphan_report.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Written: {os.path.join(a.out, 'orphan_report.json')} and orphan_report.md")


if __name__ == "__main__":
    main()
