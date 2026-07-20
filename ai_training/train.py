from ultralytics import YOLO

def train():
    # Load YOLOv8 pre-trained model
    model = YOLO('yolov8n.pt')

    # Train model on DeepFashion2 tailored dataset
    model.train(data='data.yaml', epochs=50, imgsz=640, batch=16, name='garment_feature_detector')

if __name__ == '__main__':
    train()
