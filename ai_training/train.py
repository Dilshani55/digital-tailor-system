from ultralytics import YOLO
import torch

# ── Check GPU availability ────────────────────────────────────────────────────
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Training on: {device.upper()}")
if device == "cpu":
    print("WARNING: No GPU detected. Training will be slow.")
    print("Tip: Use Google Colab (free GPU) for faster training.")

# ── Load pretrained YOLOv8 model ──────────────────────────────────────────────
# yolov8n = nano  (fastest, less accurate) — good for testing
# yolov8s = small (balanced)               — recommended for your project
# yolov8m = medium (slower, more accurate)
model = YOLO("yolov8s.pt")   # downloads pretrained weights automatically

# ── Train with transfer learning ──────────────────────────────────────────────
results = model.train(
    data      = "data.yaml",      # dataset config
    epochs    = 50,               # number of training rounds
    imgsz     = 640,              # image size (YOLOv8 standard)
    batch     = 16,               # images per batch (reduce to 8 if out of memory)
    name      = "garment_detector",
    project   = "runs/train",
    patience  = 10,               # stop early if no improvement for 10 epochs
    device    = device,
    pretrained = True,            # use ImageNet pretrained weights
    optimizer = "Adam",
    lr0       = 0.001,            # initial learning rate
    augment   = True,             # data augmentation (flip, rotate, colour jitter)
    verbose   = True
)

print("\nTraining complete!")
print(f"Best model saved to: runs/train/garment_detector/weights/best.pt")
print(f"mAP50: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
