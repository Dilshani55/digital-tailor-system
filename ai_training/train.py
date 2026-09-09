import os
import shutil
import torch
from ultralytics import YOLO

# ── Check GPU availability ────────────────────────────────────────────────────
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Training on: {device.upper()}")
if device == "cpu":
    print("Running optimized transfer learning on CPU...")

# ── Load pretrained YOLOv8 nano model (fastest & lightweight) ─────────────────
model = YOLO("yolov8n.pt")

# ── Train with transfer learning ──────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
data_yaml_path = os.path.join(current_dir, "data.yaml")

results = model.train(
    data        = data_yaml_path,     # dataset config
    epochs      = 15,                 # 15 transfer learning epochs for optimal convergence
    imgsz       = 320,                # optimized CPU resolution
    batch       = 16,                 # batch size
    workers     = 2,                  # CPU worker threads
    name        = "garment_detector",
    project     = os.path.join(current_dir, "runs"),
    device      = device,
    pretrained  = True,
    lr0         = 0.01,
    lrf         = 0.01,
    augment     = True,
    exist_ok    = True,
    verbose     = True
)

print("\nTraining complete!")
best_model_path = os.path.join(current_dir, "runs", "garment_detector", "weights", "best.pt")
last_model_path = os.path.join(current_dir, "runs", "garment_detector", "weights", "last.pt")
source_weights = best_model_path if os.path.exists(best_model_path) else last_model_path
print(f"Model saved to: {source_weights}")

# ── Automatically deploy weights to backend models directory ──────────────────
target_model_dir = os.path.join(os.path.dirname(current_dir), "backend", "app", "ai", "models")
os.makedirs(target_model_dir, exist_ok=True)
target_model_path = os.path.join(target_model_dir, "yolov8n-garment.pt")

if os.path.exists(source_weights):
    shutil.copy(source_weights, target_model_path)
    print(f"Successfully deployed trained model to: {target_model_path}")
else:
    print("Note: Check runs directory for exported weights.")
