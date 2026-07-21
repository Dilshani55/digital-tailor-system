import shutil
import os

SOURCE = "runs/train/garment_detector/weights/best.pt"
DEST   = "../backend/app/ai/models/garment_detector.pt"

os.makedirs(os.path.dirname(DEST), exist_ok=True)
shutil.copy(SOURCE, DEST)
print(f"Model exported to: {DEST}")
