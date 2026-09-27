#!/usr/bin/env python3
"""
review_app.py

Standalone Flask review application for Targeted Human Verification Queue and Gold-Label Review (Milestone M9A).

Requirements:
- CLI arguments: --queue, --decisions, --policy, --port, --host, --reviewer-id
- Serves review queue records from review_queue.jsonl
- Displays crop image, optional full official source image, Fashionpedia proposed evidence, CLIP predictions, split, review purpose, selection reason
- Interactive buttons: Blouse, T-shirt, Crop-top, Reject, Uncertain, Skip
- Keyboard shortcuts: [1] Blouse, [2] T-shirt, [3] Crop-top, [4] Reject, [5] Uncertain, [S] Skip, [Left] Prev, [Right] Next
- Saved decision schema with human_verified=true, reviewer_id, UTC timestamp, previous_pseudo_label, fashionpedia_evidence
- Atomic file writes for human_decisions.jsonl
- Path traversal prevention & strict queue path validation
- Confirmation before overwriting an existing decision
"""

import argparse
import datetime
import json
import os
import sys
import tempfile
from flask import Flask, jsonify, request, send_file, render_template_string

app = Flask(__name__)

# Global state configured at startup
CONFIG_STATE = {
    "queue_path": "ai_training/data/human_review/review_queue.jsonl",
    "decisions_path": "ai_training/data/human_review/human_decisions.jsonl",
    "policy_path": "ai_training/config/human_review_policy.json",
    "reviewer_id": "human_reviewer_01",
    "allowed_labels": ["blouse", "t-shirt", "crop-top", "reject", "uncertain"],
    "label_definitions": {},
    "queue_records": [],
    "queue_map": {},
    "project_root": os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Digital Tailor — Gold Label Review Tool</title>
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: #151d30;
            --card-inner: #0d1424;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #22c55e;
            --accent-yellow: #eab308;
            --accent-red: #ef4444;
            --accent-purple: #a855f7;
            --border-color: #26334d;
        }

        * { box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }

        .container {
            max-width: 1000px;
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 24px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 20px;
        }

        h1 {
            font-size: 1.35rem;
            margin: 0;
            color: var(--accent-blue);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .badge-reviewer {
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 12px;
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent-blue);
            border: 1px solid var(--accent-blue);
        }

        .progress-container {
            display: flex;
            gap: 20px;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }

        .progress-stat {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .progress-stat strong { color: var(--text-primary); }

        .main-content {
            display: grid;
            grid-template-columns: 1.1fr 1fr;
            gap: 24px;
        }

        .image-card {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: var(--card-inner);
            border-radius: 10px;
            border: 1px solid var(--border-color);
            padding: 16px;
            min-height: 380px;
            position: relative;
        }

        .crop-img {
            max-width: 100%;
            max-height: 360px;
            object-fit: contain;
            border-radius: 6px;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.5);
        }

        .img-meta {
            margin-top: 14px;
            font-size: 0.85rem;
            color: var(--text-secondary);
            display: flex;
            gap: 16px;
        }

        .details-container {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .info-card {
            background: var(--card-inner);
            border-radius: 10px;
            padding: 16px;
            border: 1px solid var(--border-color);
        }

        .info-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            font-weight: 600;
            font-size: 0.95rem;
        }

        .badge-purpose {
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 12px;
            background: rgba(168, 85, 247, 0.2);
            color: var(--accent-purple);
            border: 1px solid var(--accent-purple);
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }

        .metric-label { color: var(--text-secondary); }
        .metric-value { font-weight: 600; }

        .button-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 12px;
        }

        .btn {
            background: #1e293b;
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            padding: 12px;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }

        .btn:hover { transform: translateY(-2px); filter: brightness(1.2); }
        .btn-blouse { background: #1e3a8a; border-color: #3b82f6; }
        .btn-tshirt { background: #065f46; border-color: #10b981; }
        .btn-croptop { background: #581c87; border-color: #a855f7; }
        .btn-reject { background: #7f1d1d; border-color: #ef4444; }
        .btn-uncertain { background: #713f12; border-color: #eab308; }
        .btn-skip { background: #334155; border-color: #64748b; }

        .shortcut-hint {
            font-size: 0.72rem;
            color: var(--text-secondary);
            font-weight: normal;
        }

        .nav-controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid var(--border-color);
        }

        .nav-btn {
            background: #1e293b;
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            padding: 8px 18px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
        }

        .nav-btn:hover { background: #334155; }

        .label-policy-panel {
            margin-top: 16px;
            background: var(--card-inner);
            border-radius: 10px;
            padding: 14px;
            border: 1px solid var(--border-color);
            font-size: 0.82rem;
            color: var(--text-secondary);
        }

        .policy-title { font-weight: 600; color: var(--accent-blue); margin-bottom: 6px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>
                Gold Label Review
                <span class="badge-reviewer" id="reviewer-badge">Reviewer: -</span>
            </h1>
            <div class="progress-container">
                <div class="progress-stat">Verified: <strong id="stat-verified" style="color: var(--accent-green)">0</strong></div>
                <div class="progress-stat">Remaining: <strong id="stat-remaining" style="color: var(--accent-yellow)">0</strong></div>
                <div class="progress-stat">Total: <strong id="stat-total">0</strong></div>
            </div>
        </header>

        <div class="main-content">
            <div class="image-card">
                <img id="crop-img" class="crop-img" src="" alt="Garment Crop">
                <div class="img-meta">
                    <span>Ann ID: <strong id="ann-id">-</strong></span>
                    <span>Image ID: <strong id="img-id">-</strong></span>
                    <span>Split: <strong id="split-id" style="color: var(--accent-blue);">-</strong></span>
                </div>
            </div>

            <div class="details-container">
                <div class="info-card">
                    <div class="info-card-header">
                        <span>Review Priority & Purpose</span>
                        <span id="purpose-badge" class="badge-purpose">val_gold_set</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Selection Reason:</span>
                        <span id="selection-reason" class="metric-value" style="font-size: 0.85rem; color: var(--accent-purple);">-</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Proposed Class:</span>
                        <span id="proposed-class" class="metric-value" style="color: var(--accent-blue);">-</span>
                    </div>
                </div>

                <div class="info-card">
                    <div class="info-card-header">
                        <span>AI & Fashionpedia Evidence</span>
                        <span id="ai-decision-badge" class="metric-value" style="font-size: 0.8rem; color: var(--text-secondary);">-</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">CLIP Top-1 Label:</span>
                        <span id="ai-top1" class="metric-value">-</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Confidence / Margin:</span>
                        <span id="ai-conf-margin" class="metric-value">-</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Fashionpedia Candidate:</span>
                        <span id="ev-candidate" class="metric-value" style="font-size: 0.85rem;">-</span>
                    </div>
                </div>

                <div class="info-card">
                    <div style="font-weight: 600; margin-bottom: 8px;">Human Reviewer Decision</div>
                    <div id="current-status" style="font-size: 0.88rem; color: var(--accent-yellow); margin-bottom: 12px;">
                        Status: Not yet human-verified
                    </div>

                    <div class="button-grid">
                        <button class="btn btn-blouse" onclick="submitDecision('blouse')">Blouse <div class="shortcut-hint">[1]</div></button>
                        <button class="btn btn-tshirt" onclick="submitDecision('t-shirt')">T-shirt <div class="shortcut-hint">[2]</div></button>
                        <button class="btn btn-croptop" onclick="submitDecision('crop-top')">Crop-top <div class="shortcut-hint">[3]</div></button>
                        <button class="btn btn-reject" onclick="submitDecision('reject')">Reject <div class="shortcut-hint">[4]</div></button>
                        <button class="btn btn-uncertain" onclick="submitDecision('uncertain')">Uncertain <div class="shortcut-hint">[5]</div></button>
                        <button class="btn btn-skip" onclick="nextItem()">Skip <div class="shortcut-hint">[S]</div></button>
                    </div>
                </div>
            </div>
        </div>

        <div class="label-policy-panel">
            <div class="policy-title">Label Rules & Protocol:</div>
            <div><strong>Crop-top:</strong> Hem ends above natural waist / exposes midriff. Takes precedence over blouse/t-shirt.</div>
            <div><strong>T-shirt:</strong> Casual knitted tee with T-shirt construction. Exclude sweatshirts, hoodies, jackets, dresses.</div>
            <div><strong>Blouse:</strong> Women's blouse or non-T-shirt woven top. Exclude men's shirts, jackets, dresses, crop-tops.</div>
            <div><strong>Reject:</strong> Men's shirt, sweatshirt, hoodie, jacket, dress, non-garment, severe occlusion, bad crop.</div>
        </div>

        <div class="nav-controls">
            <button class="nav-btn" onclick="prevItem()">&larr; Previous [Left Arrow]</button>
            <span id="item-index" style="color: var(--text-secondary); font-size: 0.9rem;">Item 0 of 0</span>
            <button class="nav-btn" onclick="nextItem()">Next [Right Arrow] &rarr;</button>
        </div>
    </div>

    <script>
        let items = [];
        let currentIndex = 0;
        let humanDecisions = {};
        let reviewerId = "human_reviewer_01";

        async function init() {
            const res = await fetch('/api/items');
            const data = await res.json();
            items = data.items || [];
            humanDecisions = data.human_decisions || {};
            reviewerId = data.reviewer_id || "human_reviewer_01";
            document.getElementById('reviewer-badge').innerText = `Reviewer: ${reviewerId}`;
            updateUI();
        }

        function updateUI() {
            if (items.length === 0) {
                document.getElementById('item-index').innerText = "No items in queue";
                return;
            }

            const item = items[currentIndex];
            document.getElementById('item-index').innerText = `Item ${currentIndex + 1} of ${items.length}`;

            // Crop image
            document.getElementById('crop-img').src = `/crop_image/${item.crop_path}`;
            document.getElementById('ann-id').innerText = item.source_annotation_id;
            document.getElementById('img-id').innerText = item.source_image_id;
            document.getElementById('split-id').innerText = item.split || 'train';

            // Purpose
            document.getElementById('purpose-badge').innerText = item.review_purpose || '-';
            document.getElementById('selection-reason').innerText = item.selection_reason || '-';
            document.getElementById('proposed-class').innerText = item.proposed_class || '-';

            // AI details
            document.getElementById('ai-decision-badge').innerText = `Decision: ${item.decision || '-'}`;
            document.getElementById('ai-top1').innerText = item.previous_pseudo_label || '-';
            const conf = item.top1_confidence ? `${(item.top1_confidence * 100).toFixed(1)}%` : '-';
            const margin = item.margin ? `${(item.margin * 100).toFixed(1)}%` : '-';
            document.getElementById('ai-conf-margin').innerText = `${conf} (Margin: ${margin})`;

            const ev = item.fashionpedia_evidence || {};
            document.getElementById('ev-candidate').innerText = `${ev.candidate_garment_type || '-'} (${ev.candidate_garment_reason || ''})`;

            // Decision status
            const annId = item.source_annotation_id;
            const existing = humanDecisions[annId];
            const statusDiv = document.getElementById('current-status');

            if (existing) {
                statusDiv.innerHTML = `Current Verified Label: <strong style="color: var(--accent-green);">${existing.human_label}</strong> (By ${existing.reviewer_id} at ${new Date(existing.reviewed_at).toLocaleTimeString()})`;
            } else {
                statusDiv.innerText = "Status: Not yet human-verified";
                statusDiv.style.color = "var(--accent-yellow)";
            }

            // Stats
            const verifiedCount = Object.keys(humanDecisions).length;
            document.getElementById('stat-verified').innerText = verifiedCount;
            document.getElementById('stat-remaining').innerText = items.length - verifiedCount;
            document.getElementById('stat-total').innerText = items.length;
        }

        async function submitDecision(label) {
            const item = items[currentIndex];
            const annId = item.source_annotation_id;

            if (humanDecisions[annId]) {
                if (!confirm(`Overwrite existing decision '${humanDecisions[annId].human_label}' with '${label}'?`)) {
                    return;
                }
            }

            const payload = {
                source_annotation_id: annId,
                source_image_id: item.source_image_id,
                split: item.split,
                crop_path: item.crop_path,
                human_label: label,
                human_verified: true,
                reviewer_id: reviewerId,
                reviewed_at: new Date().toISOString(),
                previous_pseudo_label: item.previous_pseudo_label,
                fashionpedia_evidence: item.fashionpedia_evidence,
                decision_version: "1.0.0"
            };

            const res = await fetch('/api/decision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                humanDecisions[annId] = payload;
                updateUI();
                setTimeout(() => nextItem(), 150);
            } else {
                const errData = await res.json();
                alert(`Failed to save decision: ${errData.message || 'Unknown error'}`);
            }
        }

        function nextItem() {
            if (currentIndex < items.length - 1) {
                currentIndex++;
                updateUI();
            }
        }

        function prevItem() {
            if (currentIndex > 0) {
                currentIndex--;
                updateUI();
            }
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === '1') submitDecision('blouse');
            else if (e.key === '2') submitDecision('t-shirt');
            else if (e.key === '3') submitDecision('crop-top');
            else if (e.key === '4') submitDecision('reject');
            else if (e.key === '5') submitDecision('uncertain');
            else if (e.key.toLowerCase() === 's') nextItem();
            else if (e.key === 'ArrowLeft') prevItem();
            else if (e.key === 'ArrowRight') nextItem();
        });

        window.onload = init;
    </script>
</body>
</html>
"""


def load_queue_records(queue_path):
    records = []
    queue_map = {}
    if os.path.exists(queue_path):
        with open(queue_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    records.append(rec)
                    queue_map[rec["source_annotation_id"]] = rec
    return records, queue_map


def load_human_decisions(decisions_path):
    decisions = {}
    if os.path.exists(decisions_path):
        with open(decisions_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    decisions[rec["source_annotation_id"]] = rec
    return decisions


def atomic_write_decisions(decisions_path, decisions_dict):
    """
    Atomically writes decisions dictionary to decisions_path using temp file and rename.
    """
    dir_name = os.path.dirname(os.path.abspath(decisions_path))
    os.makedirs(dir_name, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", dir=dir_name, delete=False, encoding="utf-8") as tf:
        temp_name = tf.name
        for rec in decisions_dict.values():
            tf.write(json.dumps(rec) + "\n")
        tf.flush()
        os.fsync(tf.fileno())

    os.replace(temp_name, decisions_path)


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/items")
def get_items():
    records, _ = load_queue_records(CONFIG_STATE["queue_path"])
    decisions = load_human_decisions(CONFIG_STATE["decisions_path"])
    return jsonify({
        "items": records,
        "human_decisions": decisions,
        "reviewer_id": CONFIG_STATE["reviewer_id"],
    })


@app.route("/api/decision", methods=["POST"])
def save_decision():
    data = request.json
    if not data or "source_annotation_id" not in data or "human_label" not in data:
        return jsonify({"status": "error", "message": "Invalid decision payload"}), 400

    ann_id = data.get("source_annotation_id")
    label = data.get("human_label")

    # 1. Unknown queue ID rejection
    _, queue_map = load_queue_records(CONFIG_STATE["queue_path"])
    if ann_id not in queue_map:
        return jsonify({"status": "error", "message": f"Unknown source_annotation_id={ann_id} not in review queue"}), 400

    # 2. Invalid label rejection
    allowed = set(CONFIG_STATE["allowed_labels"])
    if label not in allowed:
        return jsonify({"status": "error", "message": f"Invalid human_label '{label}'. Must be one of {allowed}"}), 400

    q_rec = queue_map[ann_id]

    # Build standardized decision record
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    decision_record = {
        "source_annotation_id": ann_id,
        "source_image_id": q_rec.get("source_image_id"),
        "split": q_rec.get("split"),
        "crop_path": q_rec.get("crop_path"),
        "human_label": label,
        "human_verified": True,
        "reviewer_id": data.get("reviewer_id") or CONFIG_STATE["reviewer_id"],
        "reviewed_at": data.get("reviewed_at") or now_utc,
        "previous_pseudo_label": q_rec.get("previous_pseudo_label"),
        "fashionpedia_evidence": q_rec.get("fashionpedia_evidence", {}),
        "decision_version": "1.0.0",
    }

    # Atomically save to human_decisions.jsonl
    decisions_dict = load_human_decisions(CONFIG_STATE["decisions_path"])
    decisions_dict[ann_id] = decision_record
    atomic_write_decisions(CONFIG_STATE["decisions_path"], decisions_dict)

    return jsonify({"status": "success", "decision": decision_record})


@app.route("/crop_image/<path:crop_rel_path>")
def get_crop_image(crop_rel_path):
    # Path traversal prevention & strict queue verification
    abs_path = os.path.abspath(crop_rel_path)
    proj_root = CONFIG_STATE["project_root"]

    if not abs_path.startswith(proj_root):
        return jsonify({"error": "Path traversal prohibited"}), 403

    # Check that image path exists in review queue
    _, queue_map = load_queue_records(CONFIG_STATE["queue_path"])
    valid_paths = {os.path.abspath(r["crop_path"]) for r in queue_map.values() if r.get("crop_path")}

    if abs_path not in valid_paths:
        return jsonify({"error": "Requested image not present in review queue"}), 403

    if os.path.exists(abs_path):
        return send_file(abs_path, mimetype="image/jpeg")
    return jsonify({"error": "Crop image file not found"}), 404


def main():
    parser = argparse.ArgumentParser(description="Start Gold Label Review UI")
    parser.add_argument("--queue", default="ai_training/data/human_review/review_queue.jsonl", help="Path to review_queue.jsonl")
    parser.add_argument("--decisions", default="ai_training/data/human_review/human_decisions.jsonl", help="Path to human_decisions.jsonl")
    parser.add_argument("--policy", default="ai_training/config/human_review_policy.json", help="Path to config/human_review_policy.json")
    parser.add_argument("--port", type=int, default=5050, help="Port to run Flask server on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind Flask server")
    parser.add_argument("--reviewer-id", default="human_reviewer_01", help="Reviewer ID")
    args = parser.parse_args()

    CONFIG_STATE["queue_path"] = args.queue
    CONFIG_STATE["decisions_path"] = args.decisions
    CONFIG_STATE["policy_path"] = args.policy
    CONFIG_STATE["reviewer_id"] = args.reviewer_id

    if os.path.exists(args.policy):
        with open(args.policy, "r", encoding="utf-8") as f:
            pol = json.load(f)
            CONFIG_STATE["allowed_labels"] = pol.get("allowed_human_labels", CONFIG_STATE["allowed_labels"])
            CONFIG_STATE["label_definitions"] = pol.get("label_definitions", {})

    records, _ = load_queue_records(args.queue)
    print(f"Starting Gold-Label Review Server on http://{args.host}:{args.port}")
    print(f"Reviewer ID: {args.reviewer_id}")
    print(f"Loaded {len(records)} review queue items from {args.queue}")
    print("Press Ctrl+C to stop.")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
