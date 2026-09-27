#!/usr/bin/env python3
"""
masked_loss.py

Masked Multi-Task Cross-Entropy Loss with Provenance Sample Weighting and Capped Class Weights (Milestone M11).
- Masked heads (mask == 0) do not contribute to loss or gradient.
- Applies per-head provenance sample weights (human_verified: 1.0, fashionpedia_direct: 1.0, rule_derived: 0.8, pseudo_label: 0.5).
- Applies train-split capped class-balancing weights to handle class imbalance safely without exploding gradients.
- Normalizes total loss safely by total active weighted masks.
- Returns zero scalar loss safely if a batch contains zero active labels.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]


def compute_capped_class_weights(
    train_manifest_records: list,
    class_to_idx: dict,
    cap: float = 5.0,
) -> dict:
    """
    Computes capped class-balancing weights from train-split class frequencies.
    Weight formula: W_c = min(cap, max(1.0, N_max / N_c)) normalized so mean weight == 1.0.
    """
    class_weights_dict = {}

    for head in HEADS:
        num_classes = len(class_to_idx[head])
        counts = [0] * num_classes

        for r in train_manifest_records:
            mask = r.get("masks", {}).get(head, 0)
            lbl = r.get("labels", {}).get(head)
            if mask == 1 and lbl in class_to_idx[head]:
                c_idx = class_to_idx[head][lbl]
                counts[c_idx] += 1

        max_count = max(counts) if max(counts) > 0 else 1
        raw_weights = []
        for c in range(num_classes):
            cnt = counts[c]
            if cnt == 0:
                w = cap
            else:
                w = min(cap, max(1.0, max_count / cnt))
            raw_weights.append(w)

        # Normalize so average class weight is 1.0
        mean_w = sum(raw_weights) / len(raw_weights)
        norm_weights = [w / mean_w for w in raw_weights]

        class_weights_dict[head] = torch.tensor(norm_weights, dtype=torch.float32)

    return class_weights_dict


class MaskedMultiTaskLoss(nn.Module):
    def __init__(self, class_weights: dict = None):
        super().__init__()
        self.class_weights = class_weights or {}

    def forward(
        self,
        logits_dict: dict,
        targets_dict: dict,
        masks_dict: dict,
        sample_weights_dict: dict,
    ) -> tuple:
        """
        Computes masked weighted multi-task cross-entropy loss.
        Returns (total_loss, head_losses_dict).
        """
        total_weighted_loss = 0.0
        total_active_weight = 0.0
        head_losses = {}

        device = next(iter(logits_dict.values())).device

        for head in HEADS:
            logits = logits_dict[head]  # [B, C_h]
            targets = targets_dict[head].to(device)  # [B]
            masks = masks_dict[head].to(device)  # [B]
            weights = sample_weights_dict[head].to(device)  # [B]

            if head in self.class_weights and self.class_weights[head] is not None:
                c_w = self.class_weights[head].to(device)
            else:
                c_w = None

            # Unweighted per-sample CrossEntropy
            ce = F.cross_entropy(logits, targets, weight=c_w, reduction="none")  # [B]

            # Masked weighted loss
            active_weights = masks * weights
            weighted_ce = ce * active_weights

            active_sum = active_weights.sum()
            head_loss_sum = weighted_ce.sum()

            if active_sum > 0:
                head_mean_loss = head_loss_sum / active_sum
            else:
                head_mean_loss = torch.tensor(0.0, device=device)

            head_losses[head] = head_mean_loss.detach().item()

            total_weighted_loss = total_weighted_loss + head_loss_sum
            total_active_weight = total_active_weight + active_sum

        if total_active_weight > 0:
            final_loss = total_weighted_loss / total_active_weight
        else:
            final_loss = torch.tensor(0.0, device=device, requires_grad=True)

        return final_loss, head_losses
