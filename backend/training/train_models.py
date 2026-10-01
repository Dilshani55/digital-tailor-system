"""Train the four garment models, one after the other (CPU is enough; a few hours in total).

    backend\\venv\\Scripts\\python backend\\training\\train_models.py                 # all four
    backend\\venv\\Scripts\\python backend\\training\\train_models.py neckline        # one of: garment neckline sleeve_length sleeve_design

Data: backend/training/datasets/attributes (made by prepare_datasets.py). Each model keeps the weights of the epoch
with the best VALIDATION result; the test photos are not looked at here. Results go to backend/training/runs/<task>/
and the chosen weights are copied to backend/model/ (see evaluate_models.py for the test results and thresholds).

  garment        MobileNetV3-Large, ImageNet-pretrained (torchvision), fine-tuned end to end; checkpoint = best
                 validation macro-F1
  the others     YOLOv8n-cls, ImageNet-pretrained (Ultralytics), Ultralytics classification training; checkpoint =
                 best validation top-1 accuracy on a class-capped validation folder
Settings below were fixed before the first run and are the same for every run (seed 42).
"""
import json
import os
import random
import shutil
import sys
import time

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/training")
import common as C  # noqa: E402

RUNS = f"{C.ROOT}/runs"
PRETRAINED_YOLO = f"{C.MODEL_DIR}/pretrained/yolov8n-cls.pt"
IMG = 224
SEED = 42
YOLO_SETTINGS = {
    "neckline": dict(epochs=30, patience=8, batch=32),
    "sleeve_length": dict(epochs=20, patience=6, batch=32),
    "sleeve_design": dict(epochs=60, patience=15, batch=16),
}
GARMENT = dict(epochs=14, patience=5, batch=32, lr_backbone=1e-4, lr_head=1e-3, weight_decay=1e-4)


def train_yolo(task):
    from ultralytics import YOLO
    s = YOLO_SETTINGS[task]
    model = YOLO(PRETRAINED_YOLO)
    model.train(data=os.path.abspath(f"{C.OUT}/{task}"), imgsz=IMG, epochs=s["epochs"], patience=s["patience"], batch=s["batch"],
                device="cpu", workers=4, seed=SEED, deterministic=True, project=os.path.abspath(RUNS), name=task, exist_ok=True,
                # the images are already garment crops padded to a square: keep most of the garment in view and never
                # erase part of it (the neckline or the sleeve is a small part of the picture)
                scale=0.3, erasing=0.0, fliplr=0.5, auto_augment="randaugment", plots=False, verbose=False)
    best = f"{RUNS}/{task}/weights/best.pt"
    os.makedirs(C.MODEL_DIR, exist_ok=True)
    shutil.copyfile(best, f"{C.MODEL_DIR}/{C.WEIGHTS[task]}")
    return best


def macro_f1(y, p, n):
    scores = []
    for c in range(n):
        tp = sum(1 for a, b in zip(y, p) if a == c and b == c)
        fp = sum(1 for a, b in zip(y, p) if a != c and b == c)
        fn = sum(1 for a, b in zip(y, p) if a == c and b != c)
        if tp + fn:
            scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def train_garment():
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision import datasets, transforms
    from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large

    random.seed(SEED)
    torch.manual_seed(SEED)
    g = GARMENT
    mean, std = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
    train_tf = transforms.Compose([transforms.RandomResizedCrop(IMG, scale=(0.7, 1.0)), transforms.RandomHorizontalFlip(),
                                   transforms.ColorJitter(0.2, 0.2, 0.2, 0.02), transforms.ToTensor(), transforms.Normalize(mean, std)])
    eval_tf = transforms.Compose([transforms.Resize((IMG, IMG)), transforms.ToTensor(), transforms.Normalize(mean, std)])
    root = f"{C.OUT}/garment"
    train = datasets.ImageFolder(f"{root}/train", train_tf)
    val = datasets.ImageFolder(f"{root}/val", eval_tf)
    classes = train.classes
    assert sorted(classes) == sorted(C.TASKS["garment"]) and val.classes == classes, classes
    loader = DataLoader(train, batch_size=g["batch"], shuffle=True, num_workers=4, persistent_workers=True)
    val_loader = DataLoader(val, batch_size=64, num_workers=4, persistent_workers=True)

    model = mobilenet_v3_large(weights=MobileNet_V3_Large_Weights.IMAGENET1K_V2)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(classes))
    optim = torch.optim.AdamW([{"params": model.features.parameters(), "lr": g["lr_backbone"]},
                               {"params": model.classifier.parameters(), "lr": g["lr_head"]}], weight_decay=g["weight_decay"])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=g["epochs"])
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.05)

    out = f"{RUNS}/garment"
    os.makedirs(out, exist_ok=True)
    history, best, stale = [], -1.0, 0
    for epoch in range(1, g["epochs"] + 1):
        t0 = time.time()
        model.train()
        total = 0.0
        for x, y in loader:
            optim.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            optim.step()
            total += loss.item() * len(y)
        sched.step()
        model.eval()
        ys, ps = [], []
        with torch.inference_mode():
            for x, y in val_loader:
                ps += model(x).argmax(1).tolist()
                ys += y.tolist()
        f1 = macro_f1(ys, ps, len(classes))
        acc = sum(a == b for a, b in zip(ys, ps)) / len(ys)
        history.append({"epoch": epoch, "train_loss": round(total / len(train), 4), "val_accuracy": round(acc, 4),
                        "val_macro_f1": round(f1, 4), "seconds": round(time.time() - t0)})
        print(history[-1], flush=True)
        if f1 > best:
            best, stale = f1, 0
            torch.save({"architecture": "mobilenet_v3_large", "classes": classes, "image_size": IMG, "mean": mean, "std": std,
                        "state_dict": model.state_dict(), "epoch": epoch, "val_macro_f1": round(f1, 4), "seed": SEED}, f"{out}/best.pt")
        else:
            stale += 1
            if stale >= g["patience"]:
                print(f"early stop: no validation improvement for {stale} epochs", flush=True)
                break
        json.dump({"settings": g, "classes": classes, "history": history}, open(f"{out}/history.json", "w"), indent=1)
    os.makedirs(C.MODEL_DIR, exist_ok=True)
    shutil.copyfile(f"{out}/best.pt", f"{C.MODEL_DIR}/{C.WEIGHTS['garment']}")
    return f"{out}/best.pt"


def main():
    tasks = sys.argv[1:] or ["sleeve_design", "garment", "neckline", "sleeve_length"]
    for task in tasks:
        t0 = time.time()
        print(f"\n===== {task} =====", flush=True)
        best = train_garment() if task == "garment" else train_yolo(task)
        print(f"===== {task} done in {round((time.time() - t0) / 60, 1)} min -> {best}", flush=True)


if __name__ == "__main__":
    main()
