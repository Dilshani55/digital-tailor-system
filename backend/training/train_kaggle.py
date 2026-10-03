"""Train the neckline and sleeve-design models again with the Kaggle photos added (data: prepare_kaggle.py).

    backend\\venv\\Scripts\\python backend\\training\\train_kaggle.py                      # both
    backend\\venv\\Scripts\\python backend\\training\\train_kaggle.py sleeve_design        # one

Same model (YOLOv8n-cls, ImageNet-pretrained), same settings and seed as train_models.py; only the training photos
differ. The weights go to runs/candidate_kaggle/ - NOT to backend/model. The app changes only if
    backend\\venv\\Scripts\\python backend\\training\\evaluate_models.py --candidate-dir=backend/training/runs/candidate_kaggle neckline sleeve_design
shows the candidate is better on the same test photos (see "Switching to a candidate" in README.md).
"""
import os
import shutil
import sys
import time

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/training")
import common as C          # noqa: E402
import train_models as T    # noqa: E402

DATA = f"{C.ROOT}/datasets/attributes_kaggle"
CANDIDATE = f"{T.RUNS}/candidate_kaggle"


def train(task):
    from ultralytics import YOLO
    s = T.YOLO_SETTINGS[task]
    model = YOLO(T.PRETRAINED_YOLO)
    model.train(data=os.path.abspath(f"{DATA}/{task}"), imgsz=T.IMG, epochs=s["epochs"], patience=s["patience"], batch=s["batch"],
                device="cpu", workers=4, seed=T.SEED, deterministic=True, project=os.path.abspath(T.RUNS),
                name=f"{task}_kaggle", exist_ok=True, scale=0.3, erasing=0.0, fliplr=0.5, auto_augment="randaugment",
                plots=False, verbose=False)
    best = f"{T.RUNS}/{task}_kaggle/weights/best.pt"
    os.makedirs(CANDIDATE, exist_ok=True)
    shutil.copyfile(best, f"{CANDIDATE}/{C.WEIGHTS[task]}")
    return best


def main():
    for task in sys.argv[1:] or ["sleeve_design", "neckline"]:
        t0 = time.time()
        print(f"\n===== {task} (with Kaggle photos) =====", flush=True)
        best = train(task)
        print(f"===== {task} done in {round((time.time() - t0) / 60, 1)} min -> {best}", flush=True)


if __name__ == "__main__":
    main()
