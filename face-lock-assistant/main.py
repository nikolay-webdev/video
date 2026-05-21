from __future__ import annotations

import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from time import sleep


BASE_DIR = Path(__file__).resolve().parent
PROJECT_VENV_PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"


def relaunch_with_project_venv() -> None:
    if not PROJECT_VENV_PYTHON.exists():
        return

    current_python = Path(sys.executable).resolve()
    project_python = PROJECT_VENV_PYTHON.resolve()

    if current_python == project_python:
        return

    print(f"Restarting with project Python: {project_python}", flush=True)
    completed_process = subprocess.run(
        [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        check=False,
    )
    raise SystemExit(completed_process.returncode)


relaunch_with_project_venv()

try:
    import cv2
    from deepface import DeepFace
except ModuleNotFoundError as error:
    missing_module = error.name or "unknown"
    print(
        f"ERROR: Python module '{missing_module}' is not installed.\n"
        "Run the script with the project virtual environment:\n"
        f"{PROJECT_VENV_PYTHON} main.py\n"
        "Or install dependencies into .venv with:\n"
        f"{PROJECT_VENV_PYTHON} -m pip install -r requirements.txt"
    )
    raise SystemExit(1) from error

import config


if "--check-env" in sys.argv:
    print(f"Environment OK: {sys.executable}", flush=True)
    raise SystemExit(0)


LOGS_DIR = BASE_DIR / "logs"
SNAPSHOTS_DIR = BASE_DIR / "snapshots"
KNOWN_FACE_PATH = BASE_DIR / config.KNOWN_FACE_PATH
APP_LOG_PATH = LOGS_DIR / "app.log"

DETECTOR_BACKEND = "opencv"
MODEL_NAME = "SFace"
DISTANCE_METRIC = "cosine"
MIN_FACE_CONFIDENCE = 0.5
FRAME_READ_RETRIES = 5
FRAME_READ_RETRY_DELAY_SECONDS = 0.2


def setup_directories() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    logging.basicConfig(
        filename=APP_LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )


def validate_known_face() -> bool:
    if KNOWN_FACE_PATH.exists():
        return True

    print(
        "ERROR: Owner photo was not found.\n"
        f"Put the owner photo here: {KNOWN_FACE_PATH}"
    )
    return False


def open_camera() -> cv2.VideoCapture | None:
    backends = [
        ("DirectShow", cv2.CAP_DSHOW),
        ("Default", cv2.CAP_ANY),
    ]

    for backend_name, backend in backends:
        camera = cv2.VideoCapture(config.CAMERA_INDEX, backend)
        if camera.isOpened():
            print(f"Camera opened with backend: {backend_name}")
            return camera

        camera.release()

    print(
        "ERROR: Camera is not available.\n"
        f"Check camera connection, close Teams/Zoom/browser camera tabs, "
        f"and check CAMERA_INDEX={config.CAMERA_INDEX}."
    )
    return None


def read_frame(camera: cv2.VideoCapture):
    for _ in range(FRAME_READ_RETRIES):
        frame_ok, frame = camera.read()
        if frame_ok:
            return True, frame

        sleep(FRAME_READ_RETRY_DELAY_SECONDS)

    return False, None


def lock_windows_screen() -> None:
    logging.info("Owner absent too long. Locking Windows workstation.")
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)


def extract_detected_faces(frame) -> list[dict]:
    try:
        faces = DeepFace.extract_faces(
            img_path=frame,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=False,
        )
    except Exception as error:
        logging.exception("Face extraction failed: %s", error)
        return []

    # DeepFace can return very low-confidence fallback regions when detection is weak.
    return [
        face
        for face in faces
        if float(face.get("confidence", 1.0) or 0.0) >= MIN_FACE_CONFIDENCE
    ]


def prepare_face_for_verification(face_image):
    if face_image.max() <= 1.0:
        face_image = (face_image * 255).astype("uint8")

    return cv2.cvtColor(face_image, cv2.COLOR_RGB2BGR)


def is_owner_present(faces: list[dict]) -> bool:
    for face in faces:
        face_image = face.get("face")
        if face_image is None:
            continue

        face_image = prepare_face_for_verification(face_image)

        try:
            result = DeepFace.verify(
                img1_path=face_image,
                img2_path=str(KNOWN_FACE_PATH),
                model_name=MODEL_NAME,
                detector_backend=DETECTOR_BACKEND,
                distance_metric=DISTANCE_METRIC,
                enforce_detection=False,
            )
        except Exception as error:
            logging.exception("Face verification failed: %s", error)
            continue

        if result.get("verified"):
            return True

    return False


def save_unknown_snapshot(frame) -> Path | None:
    if not config.SAVE_UNKNOWN_FACE_SNAPSHOT:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOTS_DIR / f"unknown_{timestamp}.jpg"
    if cv2.imwrite(str(snapshot_path), frame):
        return snapshot_path

    logging.error("Failed to save unknown face snapshot: %s", snapshot_path)
    return None


def can_save_unknown_snapshot(last_snapshot_at: float | None) -> bool:
    if last_snapshot_at is None:
        return True

    seconds_since_last_snapshot = time.monotonic() - last_snapshot_at
    return seconds_since_last_snapshot >= config.UNKNOWN_FACE_SNAPSHOT_COOLDOWN_SECONDS


def print_status(status: str, absent_seconds: float, snapshot_path: Path | None = None) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"[{timestamp}] {status} | absent: {absent_seconds:.1f}s"
    if snapshot_path:
        message += f" | snapshot: {snapshot_path}"
    print(message)


def run() -> int:
    setup_directories()
    setup_logging()

    if not validate_known_face():
        return 1

    camera = open_camera()
    if camera is None:
        return 1

    owner_last_seen_at = time.monotonic()
    last_unknown_snapshot_at = None
    lock_already_requested = False

    print("Face Lock Assistant started. Press Ctrl+C to stop.")

    try:
        while True:
            snapshot_path = None
            frame_ok, frame = read_frame(camera)
            if not frame_ok:
                logging.error("Failed to read frame from camera.")
                print(
                    "ERROR: Failed to read frame from camera. "
                    "Close Teams/Zoom/browser camera tabs and try again."
                )
                time.sleep(config.CHECK_INTERVAL_SECONDS)
                continue

            faces = extract_detected_faces(frame)

            if not faces:
                status = "NO_FACE"
            elif is_owner_present(faces):
                status = "OWNER_PRESENT"
                owner_last_seen_at = time.monotonic()
                lock_already_requested = False
            else:
                status = "UNKNOWN_FACE"
                if can_save_unknown_snapshot(last_unknown_snapshot_at):
                    snapshot_path = save_unknown_snapshot(frame)
                    last_unknown_snapshot_at = time.monotonic()
                    logging.warning("Unknown face detected. Snapshot: %s", snapshot_path or "disabled")
                else:
                    logging.warning("Unknown face detected. Snapshot skipped by cooldown.")

            absent_seconds = time.monotonic() - owner_last_seen_at
            print_status(status, absent_seconds, snapshot_path)

            if (
                absent_seconds >= config.ABSENCE_SECONDS_BEFORE_LOCK
                and not lock_already_requested
            ):
                print("Owner absent too long. Locking Windows screen.")
                lock_windows_screen()
                lock_already_requested = True
                print(f"Paused for {config.PAUSE_SECONDS_AFTER_LOCK}s after locking.")
                time.sleep(config.PAUSE_SECONDS_AFTER_LOCK)

            time.sleep(config.CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nFace Lock Assistant stopped by user.")
        logging.info("Application stopped by user.")
        return 0
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(run())
