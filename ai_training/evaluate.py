from ultralytics import YOLO

def evaluate():
    model = YOLO('runs/detect/garment_feature_detector/weights/best.pt')
    metrics = model.val()
    print("Validation mAP50-95:", metrics.box.map)

if __name__ == '__main__':
    evaluate()
