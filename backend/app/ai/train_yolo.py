"""
YOLOv8 Custom Garment Detection Trainer
----------------------------------------
This script allows you to train/fine-tune a custom YOLOv8 model for garment 
feature detection (Blouse, Crop-Top, T-Shirt, Necklines, Sleeves).

Instructions:
1. Prepare your dataset in YOLO format (images + .txt label files) or export from Roboflow / DeepFashion.
2. Update dataset paths in `garment_data.yaml`.
3. Run: `python app/ai/train_yolo.py`
4. The trained weights will be saved to `backend/app/ai/models/yolov8n-garment.pt`.
"""

import os
from ultralytics import YOLO

def train_garment_model():
    # 1. Path to dataset YAML configuration
    yaml_path = os.path.join(os.path.dirname(__file__), "garment_data.yaml")
    
    # Create sample dataset config if it does not exist
    if not os.path.exists(yaml_path):
        with open(yaml_path, "w") as f:
            f.write("""path: ./dataset
train: images/train
val: images/val

names:
  0: blouse
  1: crop-top
  2: t-shirt
  3: off-the-shoulder
  4: v-neck
  5: round-neck
  6: short-sleeve
  7: sleeveless
  8: long-sleeve
""")
        print(f"Created sample dataset configuration: {yaml_path}")

    # 2. Load pre-trained YOLOv8 Nano model
    print("Loading pre-trained YOLOv8 model...")
    model = YOLO("yolov8n.pt")

    # 3. Start fine-tuning / training
    print("Starting YOLOv8 garment training...")
    try:
        results = model.train(
            data=yaml_path,
            epochs=50,
            imgsz=640,
            batch=16,
            name="yolov8_garment_model",
            project=os.path.join(os.path.dirname(__file__), "runs")
        )
        print("Training completed successfully!")
        
        # 4. Copy best trained weights to app/ai/models/yolov8n-garment.pt
        best_weights = os.path.join(os.path.dirname(__file__), "runs", "yolov8_garment_model", "weights", "best.pt")
        target_path = os.path.join(os.path.dirname(__file__), "models", "yolov8n-garment.pt")
        
        if os.path.exists(best_weights):
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            import shutil
            shutil.copy(best_weights, target_path)
            print(f"Saved best trained weights to: {target_path}")

    except Exception as e:
        print(f"Training failed: {str(e)}")
        print("Ensure 'ultralytics' is installed and dataset images are present.")

if __name__ == "__main__":
    train_garment_model()
