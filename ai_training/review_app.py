#!/usr/bin/env python3
"""
review_app.py

Standalone Flask review app for manual spot-checking of AI-assisted garment pseudo-labels (Milestone AI-6B).

Requirements:
- Work strictly inside ai_training/
- Prioritize spot-checking 15 accepted AI predictions per target class (blouse, t-shirt, crop-top)
- Interactive buttons: Blouse, T-shirt, Crop-top, Reject, Unclear
- Show current AI suggestion, confidence, top-2 class, margin
- Previous / Next navigation
- Incremental decision saving to ai_training/data/labelling/human_review.jsonl
- Require confirmation before overwriting existing review decisions
- Show live progress counters
- Preserve human_verified=true on reviewer decision
"""

import argparse
import datetime
import json
import os
import sys
from flask import Flask, jsonify, request, send_file, render_template_string

app = Flask(__name__)

# Configurable paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "labelling")
HUMAN_REVIEW_FILE = os.path.join(DATA_DIR, "human_review.jsonl")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Garment Pseudo-Label Review Tool</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #22c55e;
            --accent-yellow: #eab308;
            --accent-red: #ef4444;
            --accent-purple: #a855f7;
            --border-color: #334155;
        }

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
            max-width: 900px;
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
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
            font-size: 1.4rem;
            margin: 0;
            color: var(--accent-blue);
        }

        .progress-bar-container {
            display: flex;
            gap: 15px;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }

        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }

        .image-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: #090d16;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            padding: 16px;
            min-height: 320px;
        }

        .crop-img {
            max-width: 100%;
            max-height: 380px;
            object-fit: contain;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        }

        .details-container {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .info-card {
            background: #0f172a;
            border-radius: 8px;
            padding: 14px;
            border: 1px solid var(--border-color);
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-accepted { background: rgba(34, 197, 94, 0.2); color: var(--accent-green); border: 1px solid var(--accent-green); }
        .badge-review { background: rgba(234, 179, 8, 0.2); color: var(--accent-yellow); border: 1px solid var(--accent-yellow); }
        .badge-rejected { background: rgba(239, 68, 68, 0.2); color: var(--accent-red); border: 1px solid var(--accent-red); }

        .metric-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.95rem;
            margin-bottom: 8px;
        }

        .metric-label { color: var(--text-secondary); }
        .metric-value { font-weight: 600; }

        .button-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 10px;
        }

        .btn {
            background: #334155;
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            padding: 12px;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .btn:hover { transform: translateY(-2px); filter: brightness(1.2); }
        .btn-blouse { background: #1e3a8a; border-color: #3b82f6; }
        .btn-tshirt { background: #065f46; border-color: #10b981; }
        .btn-croptop { background: #581c87; border-color: #a855f7; }
        .btn-reject { background: #7f1d1d; border-color: #ef4444; }
        .btn-unclear { background: #713f12; border-color: #eab308; }

        .nav-controls {
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid var(--border-color);
        }

        .nav-btn {
            background: #334155;
            color: var(--text-primary);
            border: none;
            padding: 8px 18px;
            border-radius: 6px;
            cursor: pointer;
        }

        .shortcut-hint {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>AI Garment Pseudo-Label Review</h1>
            <div class="progress-bar-container">
                <span id="progress-text">Loading items...</span>
            </div>
        </header>

        <div class="main-content">
            <div class="image-container">
                <img id="crop-img" class="crop-img" src="" alt="Garment Crop">
                <div style="margin-top: 10px; font-size: 0.85rem; color: var(--text-secondary);">
                    Annotation ID: <span id="ann-id">-</span> | Split: <span id="split-id">-</span>
                </div>
            </div>

            <div class="details-container">
                <div class="info-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span style="font-weight: 600;">AI Prediction</span>
                        <span id="ai-decision-badge" class="badge">AI Suggestion</span>
                    </div>

                    <div class="metric-row">
                        <span class="metric-label">Suggested Garment:</span>
                        <span id="ai-top1-label" class="metric-value" style="color: var(--accent-blue);">-</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Top-1 Confidence:</span>
                        <span id="ai-top1-conf" class="metric-value">-</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Top-2 Class:</span>
                        <span id="ai-top2-label" class="metric-value">-</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Top-1 / Top-2 Margin:</span>
                        <span id="ai-margin" class="metric-value">-</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Prompt Agreement:</span>
                        <span id="ai-agreement" class="metric-value">-</span>
                    </div>
                    <div class="metric-row" style="margin-top: 6px;">
                        <span class="metric-label">Source Evidence:</span>
                        <span id="ai-evidence" class="metric-value" style="font-size: 0.85rem;">-</span>
                    </div>
                </div>

                <div class="info-card">
                    <div style="font-weight: 600; margin-bottom: 10px;">Human Reviewer Decision</div>
                    <div id="current-decision-status" style="font-size: 0.9rem; color: var(--accent-yellow); margin-bottom: 10px;">
                        Unreviewed
                    </div>

                    <div class="button-grid">
                        <button class="btn btn-blouse" onclick="submitDecision('blouse')">Blouse <div class="shortcut-hint">[1]</div></button>
                        <button class="btn btn-tshirt" onclick="submitDecision('t-shirt')">T-shirt <div class="shortcut-hint">[2]</div></button>
                        <button class="btn btn-croptop" onclick="submitDecision('crop-top')">Crop-top <div class="shortcut-hint">[3]</div></button>
                        <button class="btn btn-reject" onclick="submitDecision('reject')">Reject <div class="shortcut-hint">[4]</div></button>
                        <button class="btn btn-unclear" onclick="submitDecision('unclear')">Unclear <div class="shortcut-hint">[5]</div></button>
                    </div>
                </div>
            </div>
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
        let humanReviews = {};

        async function init() {
            const res = await fetch('/api/items');
            const data = await res.json();
            items = data.items;
            humanReviews = data.human_reviews || {};
            updateUI();
        }

        function updateUI() {
            if (items.length === 0) {
                document.getElementById('progress-text').innerText = "No items available for review.";
                return;
            }

            const item = items[currentIndex];
            document.getElementById('item-index').innerText = `Item ${currentIndex + 1} of ${items.length}`;

            // Image
            document.getElementById('crop-img').src = `/crop_image/${item.crop_path}`;
            document.getElementById('ann-id').innerText = item.source_annotation_id;
            document.getElementById('split-id').innerText = item.split || 'train';

            // AI details
            document.getElementById('ai-top1-label').innerText = item.top1_label || item.predicted_garment_type;
            document.getElementById('ai-top1-conf').innerText = `${(item.top1_confidence * 100).toFixed(1)}%`;
            document.getElementById('ai-top2-label').innerText = item.top2_label || '-';
            document.getElementById('ai-margin').innerText = `${(item.margin * 100).toFixed(1)}%`;
            document.getElementById('ai-agreement').innerText = item.prompt_agreement ? "Yes (>= 2 prompts)" : "No";

            const ev = item.source_evidence || {};
            document.getElementById('ai-evidence').innerText = `${ev.candidate_garment_type || '-'} (${ev.candidate_garment_reason || ''})`;

            // Badge
            const badge = document.getElementById('ai-decision-badge');
            if (item.decision === 'accepted') {
                badge.innerText = "Accepted AI";
                badge.className = "badge badge-accepted";
            } else if (item.decision === 'review_required') {
                badge.innerText = "Review Required";
                badge.className = "badge badge-review";
            } else {
                badge.innerText = "Rejected AI";
                badge.className = "badge badge-rejected";
            }

            // Existing Human Review
            const annId = item.source_annotation_id;
            const existing = humanReviews[annId];
            const statusDiv = document.getElementById('current-decision-status');

            if (existing) {
                statusDiv.innerHTML = `Current Verified Decision: <strong style="color: var(--accent-green);">${existing.reviewer_decision}</strong> (Reviewed at ${new Date(existing.timestamp).toLocaleTimeString()})`;
            } else {
                statusDiv.innerText = "Status: Not yet human-verified";
                statusDiv.style.color = "var(--text-secondary)";
            }

            // Progress text
            const reviewedCount = Object.keys(humanReviews).length;
            document.getElementById('progress-text').innerText = `Verified: ${reviewedCount} / ${items.length} items`;
        }

        async function submitDecision(decision) {
            const item = items[currentIndex];
            const annId = item.source_annotation_id;

            if (humanReviews[annId]) {
                if (!confirm(`Overwrite existing review '${humanReviews[annId].reviewer_decision}' with '${decision}'?`)) {
                    return;
                }
            }

            const payload = {
                source_annotation_id: annId,
                source_image_id: item.source_image_id,
                reviewer_decision: decision,
                timestamp: new Date().toISOString(),
                ai_prediction: item,
                human_verified: true
            };

            const res = await fetch('/api/decision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                humanReviews[annId] = payload;
                updateUI();
                setTimeout(() => nextItem(), 200);
            } else {
                alert("Failed to save review decision.");
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
            else if (e.key === '5') submitDecision('unclear');
            else if (e.key === 'ArrowLeft') prevItem();
            else if (e.key === 'ArrowRight') nextItem();
        });

        window.onload = init;
    </script>
</body>
</html>
"""


def load_human_reviews():
    reviews = {}
    if os.path.exists(HUMAN_REVIEW_FILE):
        with open(HUMAN_REVIEW_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    reviews[rec["source_annotation_id"]] = rec
    return reviews


def load_prioritized_items():
    """
    Prioritizes 15 accepted predictions per target class for spot-checking,
    followed by review_required items and rejected items.
    """
    accepted_file = os.path.join(DATA_DIR, "accepted_pseudo_labels.jsonl")
    review_file = os.path.join(DATA_DIR, "review_required.jsonl")
    rejected_file = os.path.join(DATA_DIR, "rejected.jsonl")

    accepted_by_class = {"blouse": [], "t-shirt": [], "crop-top": []}

    if os.path.exists(accepted_file):
        with open(accepted_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    cls = rec.get("predicted_garment_type")
                    if cls in accepted_by_class:
                        accepted_by_class[cls].append(rec)

    items = []

    # Take up to 15 accepted per class for spot-checking
    for cls in ["blouse", "t-shirt", "crop-top"]:
        items.extend(accepted_by_class[cls][:15])

    # Add remaining accepted items
    for cls in ["blouse", "t-shirt", "crop-top"]:
        items.extend(accepted_by_class[cls][15:])

    # Add review required items
    if os.path.exists(review_file):
        with open(review_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line.strip()))

    # Add rejected items
    if os.path.exists(rejected_file):
        with open(rejected_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line.strip()))

    return items


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/items")
def get_items():
    items = load_prioritized_items()
    reviews = load_human_reviews()
    return jsonify({"items": items, "human_reviews": reviews})


@app.route("/api/decision", methods=["POST"])
def save_decision():
    data = request.json
    if not data or "source_annotation_id" not in data or "reviewer_decision" not in data:
        return jsonify({"status": "error", "message": "Invalid decision payload"}), 400

    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Save incrementally to human_review.jsonl
    with open(HUMAN_REVIEW_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")

    return jsonify({"status": "success"})


@app.route("/crop_image/<path:crop_rel_path>")
def get_crop_image(crop_rel_path):
    abs_path = os.path.abspath(crop_rel_path)
    if os.path.exists(abs_path):
        return send_file(abs_path, mimetype="image/jpeg")
    return jsonify({"error": "Crop image not found"}), 404


def main():
    parser = argparse.ArgumentParser(description="Start manual review application")
    parser.add_argument("--port", type=int, default=5000, help="Port to run Flask server on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind Flask server")
    args = parser.parse_args()

    print(f"Starting Garment Pseudo-Label Review Server on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
