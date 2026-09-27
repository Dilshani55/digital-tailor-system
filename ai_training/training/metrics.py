#!/usr/bin/env python3
"""
metrics.py

Multi-Head Multi-Task Evaluation Metrics Computation for Digital Tailor AI (Milestone M11).
Computes per-head:
- Evaluated active record count
- Accuracy
- Macro Precision, Macro Recall, Macro F1
- Per-class support, precision, recall, F1
- Confusion matrices
- Explicit "N/A" marking for classes without gold evaluation support
"""

import json
from collections import defaultdict


HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]


class MultiTaskMetricsTracker:
    def __init__(self, class_to_idx: dict, idx_to_class: dict):
        self.class_to_idx = class_to_idx
        self.idx_to_class = idx_to_class
        self.reset()

    def reset(self):
        self.preds_by_head = {h: [] for h in HEADS}
        self.targets_by_head = {h: [] for h in HEADS}

    def update(self, logits_dict: dict, targets_dict: dict, masks_dict: dict):
        """Updates predictions and targets for active masks."""
        for head in HEADS:
            logits = logits_dict[head]
            targets = targets_dict[head]
            masks = masks_dict[head]

            preds = logits.argmax(dim=-1)

            for i in range(len(masks)):
                if masks[i].item() == 1.0:
                    self.preds_by_head[head].append(preds[i].item())
                    self.targets_by_head[head].append(targets[i].item())

    def compute(self) -> dict:
        """Computes comprehensive per-head and overall metrics."""
        results = {}

        for head in HEADS:
            preds = self.preds_by_head[head]
            targets = self.targets_by_head[head]

            classes = list(self.class_to_idx[head].keys())
            num_classes = len(classes)
            evaluated_count = len(targets)

            if evaluated_count == 0:
                results[head] = {
                    "evaluated_count": 0,
                    "accuracy": 0.0,
                    "macro_precision": 0.0,
                    "macro_recall": 0.0,
                    "macro_f1": 0.0,
                    "per_class": {c: {"support": 0, "precision": "N/A", "recall": "N/A", "f1": "N/A"} for c in classes},
                    "confusion_matrix": [[0] * num_classes for _ in range(num_classes)],
                }
                continue

            # Accuracy
            correct = sum(1 for p, t in zip(preds, targets) if p == t)
            accuracy = correct / evaluated_count

            # Confusion matrix: cm[gt][pred]
            cm = [[0] * num_classes for _ in range(num_classes)]
            for p, t in zip(preds, targets):
                cm[t][p] += 1

            per_class_metrics = {}
            valid_precisions = []
            valid_recalls = []
            valid_f1s = []

            for c_idx, c_name in enumerate(classes):
                support = sum(1 for t in targets if t == c_idx)
                tp = cm[c_idx][c_idx]
                fp = sum(cm[other_gt][c_idx] for other_gt in range(num_classes) if other_gt != c_idx)
                fn = sum(cm[c_idx][other_pred] for other_pred in range(num_classes) if other_pred != c_idx)

                if support == 0:
                    per_class_metrics[c_name] = {
                        "support": 0,
                        "precision": "N/A",
                        "recall": "N/A",
                        "f1": "N/A",
                    }
                else:
                    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

                    per_class_metrics[c_name] = {
                        "support": support,
                        "precision": round(prec, 4),
                        "recall": round(rec, 4),
                        "f1": round(f1, 4),
                    }
                    valid_precisions.append(prec)
                    valid_recalls.append(rec)
                    valid_f1s.append(f1)

            macro_p = sum(valid_precisions) / len(valid_precisions) if valid_precisions else 0.0
            macro_r = sum(valid_recalls) / len(valid_recalls) if valid_recalls else 0.0
            macro_f1 = sum(valid_f1s) / len(valid_f1s) if valid_f1s else 0.0

            results[head] = {
                "evaluated_count": evaluated_count,
                "accuracy": round(accuracy, 4),
                "macro_precision": round(macro_p, 4),
                "macro_recall": round(macro_r, 4),
                "macro_f1": round(macro_f1, 4),
                "per_class": per_class_metrics,
                "confusion_matrix": cm,
            }

        return results
