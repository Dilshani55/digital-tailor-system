"""
multitask_dataset_v2.py - MultiTaskDataset that also trains on WHOLE photos.

Users upload whole photos, not tight garment crops. With probability `full_image_prob` (training only) a record
is shown as its full photo (`full_image_path`, or the source image of a Fashionpedia record) instead of the
garment crop; validation/test always use the crop unless `eval_mode="full"`. Every image is EXIF-corrected.
"""

import os
import random

from PIL import Image, ImageOps

from ai_training.datasets.multitask_dataset import MultiTaskDataset


class MultiTaskDatasetV2(MultiTaskDataset):
    def __init__(self, *args, full_image_prob: float = 0.0, eval_mode: str = "crop", **kwargs):
        super().__init__(*args, **kwargs)
        self.full_image_prob = float(full_image_prob)
        self.eval_mode = eval_mode                       # "crop" | "full" (evaluation only)

    @staticmethod
    def _open(path):
        with Image.open(path) as im:
            return ImageOps.exif_transpose(im).convert("RGB")

    def _full_path(self, record):
        p = record.get("full_image_path") or record.get("source_image_path")
        return p.replace("\\", "/") if p and os.path.exists(p.replace("\\", "/")) else None

    def load_and_crop_image(self, record):
        want_full = (self.is_train and random.random() < self.full_image_prob) or (not self.is_train and self.eval_mode == "full")
        if want_full:
            p = self._full_path(record)
            if p:
                return self._open(p)
        crop_p = record.get("crop_path")
        if crop_p and os.path.exists(crop_p):
            return self._open(crop_p)
        source_p = record.get("source_image_path")
        if not source_p or not os.path.exists(source_p.replace("\\", "/")):
            raise FileNotFoundError(f"image missing for record {record.get('record_uid')}: {source_p}")
        img = self._open(source_p.replace("\\", "/"))
        bbox = record.get("bbox")
        if bbox and len(bbox) == 4:
            try:
                bx, by, bw, bh = [float(v) for v in bbox]
                w, h = img.size
                l, t, r, b = max(0, int(round(bx))), max(0, int(round(by))), min(w, int(round(bx + bw))), min(h, int(round(by + bh)))
                if r - l >= 8 and b - t >= 8:
                    img = img.crop((l, t, r, b))
            except Exception:                            # noqa: BLE001
                pass
        return img
