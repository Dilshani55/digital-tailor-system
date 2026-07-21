from ultralytics import YOLO
import json

MODEL_PATH = "runs/train/garment_detector/weights/best.pt"
DATA_YAML  = "data.yaml"

model = YOLO(MODEL_PATH)

# ── Run evaluation on test set ────────────────────────────────────────────────
metrics = model.val(data=DATA_YAML, split="test")

print("\n=== Evaluation Results ===")
print(f"mAP50       : {metrics.box.map50:.4f}")
print(f"mAP50-95    : {metrics.box.map:.4f}")
print(f"Precision   : {metrics.box.mp:.4f}")
print(f"Recall      : {metrics.box.mr:.4f}")

# Per-class results
print("\nPer-class Results:")
names = ["t-shirt", "blouse", "crop-top"]
for i, name in enumerate(names):
    print(f"  {name:12} → mAP50: {metrics.box.ap50[i]:.4f}")

# Save results to JSON for your dissertation
results_dict = {
    "mAP50":     float(metrics.box.map50),
    "mAP50-95":  float(metrics.box.map),
    "precision": float(metrics.box.mp),
    "recall":    float(metrics.box.mr),
    "per_class": {
        names[i]: float(metrics.box.ap50[i])
        for i in range(len(names))
    }
}

with open("evaluation_results.json", "w") as f:
    json.dump(results_dict, f, indent=2)

print("\nResults saved to evaluation_results.json")
