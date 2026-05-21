from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import ctypes
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_VENV_PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"
CHECK_ENV_FLAG = "--check-env"
SELF_TEST_FLAG = "--self-test"
DIAGNOSE_DETECTORS_FLAG = "--diagnose-detectors"


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

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

if CHECK_ENV_FLAG in sys.argv:
    print(f"Environment OK: {sys.executable}", flush=True)
    raise SystemExit(0)

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


LOGS_DIR = BASE_DIR / "logs"
SNAPSHOTS_DIR = BASE_DIR / "snapshots"
KNOWN_FACES_DIR = BASE_DIR / config.KNOWN_FACES_DIR
APP_LOG_PATH = LOGS_DIR / "app.log"

MODEL_NAME = "SFace"
DISTANCE_METRIC = "cosine"
MIN_FACE_CONFIDENCE = 0.5
FRAME_READ_RETRIES = 5
FRAME_READ_RETRY_DELAY_SECONDS = 0.2
DIAGNOSTIC_DETECTOR_BACKENDS = ["opencv", "ssd", "mtcnn", "retinaface"]
DESKTOP_SWITCHDESKTOP = 0x0100


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
    if get_known_face_paths():
        return True

    print(
        "ERROR: Owner photos were not found.\n"
        f"Put owner photos here: {KNOWN_FACES_DIR}"
    )
    return False


def get_known_face_paths() -> list[Path]:
    image_extensions = ("*.jpg", "*.jpeg", "*.png")
    paths: list[Path] = []

    for extension in image_extensions:
        paths.extend(KNOWN_FACES_DIR.glob(extension))

    return sorted(paths)


def open_camera() -> cv2.VideoCapture | None:
    camera_index = config.get_camera_index()
    backends = [
        ("DirectShow", cv2.CAP_DSHOW),
        ("Default", cv2.CAP_ANY),
    ]

    for backend_name, backend in backends:
        camera = cv2.VideoCapture(camera_index, backend)
        if camera.isOpened():
            print(f"Camera opened with backend: {backend_name}, index: {camera_index}")
            return camera

        camera.release()

    print(
        "ERROR: Camera is not available.\n"
        f"Check camera connection, close Teams/Zoom/browser camera tabs, "
        f"and check camera index={camera_index}."
    )
    return None


def read_frame(camera: cv2.VideoCapture):
    for _ in range(FRAME_READ_RETRIES):
        frame_ok, frame = camera.read()
        if frame_ok:
            return True, frame

        time.sleep(FRAME_READ_RETRY_DELAY_SECONDS)

    return False, None


def lock_windows_screen() -> None:
    logging.info("Owner absent too long. Locking Windows workstation.")
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)


def is_workstation_unlocked() -> bool:
    user32 = ctypes.windll.user32
    input_desktop = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not input_desktop:
        return False

    try:
        return bool(user32.SwitchDesktop(input_desktop))
    finally:
        user32.CloseDesktop(input_desktop)


def wait_after_lock_until_unlock() -> bool:
    print(
        "Waiting until Windows is unlocked "
        f"(max {config.PAUSE_SECONDS_AFTER_LOCK}s)."
    )

    wait_started_at = time.monotonic()
    last_status_print_at = None
    time.sleep(config.LOCK_MIN_WAIT_BEFORE_UNLOCK_CHECK_SECONDS)

    while True:
        elapsed_seconds = time.monotonic() - wait_started_at
        if elapsed_seconds >= config.PAUSE_SECONDS_AFTER_LOCK:
            print("Lock wait timeout reached. Monitoring will resume.")
            return False

        if is_workstation_unlocked():
            print("Windows is unlocked. Monitoring resumed.")
            return True

        if should_print_locked_wait(last_status_print_at):
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] LOCKED_WAIT | lock_wait: {elapsed_seconds:.0f}s")
            last_status_print_at = time.monotonic()

        time.sleep(config.LOCK_STATE_CHECK_INTERVAL_SECONDS)


def extract_detected_faces(frame) -> list[dict]:
    return extract_detected_faces_with_backend(frame, config.DETECTOR_BACKEND)


def extract_detected_faces_with_backend(frame, detector_backend: str) -> list[dict]:
    try:
        faces = DeepFace.extract_faces(
            img_path=frame,
            detector_backend=detector_backend,
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
    known_face_paths = get_known_face_paths()

    for face in faces:
        face_image = face.get("face")
        if face_image is None:
            continue

        face_image = prepare_face_for_verification(face_image)

        for known_face_path in known_face_paths:
            try:
                result = DeepFace.verify(
                    img1_path=face_image,
                    img2_path=str(known_face_path),
                    model_name=MODEL_NAME,
                    detector_backend=config.DETECTOR_BACKEND,
                    distance_metric=DISTANCE_METRIC,
                    enforce_detection=False,
                )
            except Exception as error:
                logging.exception("Face verification failed for %s: %s", known_face_path, error)
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


def should_print_locked_wait(last_print_at: float | None) -> bool:
    if last_print_at is None:
        return True

    seconds_since_last_print = time.monotonic() - last_print_at
    return seconds_since_last_print >= config.LOCKED_STATUS_PRINT_INTERVAL_SECONDS


def print_unlock_grace(grace_until: float) -> None:
    remaining_seconds = max(0.0, grace_until - time.monotonic())
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] UNLOCK_GRACE | remaining: {remaining_seconds:.0f}s")


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
    last_locked_wait_print_at = None
    lock_already_requested = False
    unlock_grace_until = 0.0
    last_unlock_grace_print_at = None

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
            now = time.monotonic()

            if not faces:
                status = "NO_FACE"
            elif is_owner_present(faces):
                status = "OWNER_PRESENT"
                owner_last_seen_at = now
                last_locked_wait_print_at = None
                last_unlock_grace_print_at = None
                lock_already_requested = False
            else:
                status = "UNKNOWN_FACE"
                if can_save_unknown_snapshot(last_unknown_snapshot_at):
                    snapshot_path = save_unknown_snapshot(frame)
                    last_unknown_snapshot_at = now
                    logging.warning("Unknown face detected. Snapshot: %s", snapshot_path or "disabled")
                else:
                    logging.debug("Unknown face detected. Snapshot skipped by cooldown.")

            absent_seconds = now - owner_last_seen_at
            unlock_grace_active = now < unlock_grace_until

            if unlock_grace_active and status != "OWNER_PRESENT":
                if should_print_locked_wait(last_unlock_grace_print_at):
                    print_unlock_grace(unlock_grace_until)
                    last_unlock_grace_print_at = now
            elif lock_already_requested and status != "OWNER_PRESENT":
                if should_print_locked_wait(last_locked_wait_print_at):
                    print_status("LOCKED_WAIT", absent_seconds, snapshot_path)
                    last_locked_wait_print_at = now
            else:
                print_status(status, absent_seconds, snapshot_path)

            if (
                absent_seconds >= config.ABSENCE_SECONDS_BEFORE_LOCK
                and not lock_already_requested
                and not unlock_grace_active
            ):
                print("Owner absent too long. Locking Windows screen.")
                lock_windows_screen()
                lock_already_requested = True
                last_locked_wait_print_at = now
                unlocked = wait_after_lock_until_unlock()
                if unlocked:
                    unlocked_at = time.monotonic()
                    owner_last_seen_at = unlocked_at
                    unlock_grace_until = unlocked_at + config.UNLOCK_GRACE_SECONDS
                    last_locked_wait_print_at = None
                    last_unlock_grace_print_at = None
                    lock_already_requested = False

            time.sleep(config.CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nFace Lock Assistant stopped by user.")
        logging.info("Application stopped by user.")
        return 0
    finally:
        camera.release()
        cv2.destroyAllWindows()


def run_self_test() -> int:
    print(f"Environment OK: {sys.executable}")
    print(f"Known faces dir: {KNOWN_FACES_DIR}")
    print(f"Known face photos: {len(get_known_face_paths())}")
    print(f"Camera index: {config.get_camera_index()}")
    print(f"Detector backend: {config.DETECTOR_BACKEND}")
    print("Self-test does not lock Windows and does not save snapshots.")

    setup_directories()
    setup_logging()

    if not validate_known_face():
        return 1

    camera = open_camera()
    if camera is None:
        return 1

    try:
        deadline = time.monotonic() + config.SELF_TEST_SECONDS
        frame_count = 0
        max_faces_detected = 0
        last_frame_shape = None
        final_status = "NO_FACE"

        while time.monotonic() < deadline:
            frame_ok, frame = read_frame(camera)
            if not frame_ok:
                print("ERROR: Failed to read a test frame from camera.")
                return 1

            frame_count += 1
            height, width = frame.shape[:2]
            last_frame_shape = (width, height)

            faces = extract_detected_faces(frame)
            max_faces_detected = max(max_faces_detected, len(faces))

            if faces and is_owner_present(faces):
                final_status = "OWNER_PRESENT"
                break

            if faces:
                final_status = "UNKNOWN_FACE"

            time.sleep(config.CHECK_INTERVAL_SECONDS)

        if last_frame_shape is None:
            print("ERROR: No test frames were read.")
            return 1

        width, height = last_frame_shape
        print(f"Camera frame OK: {width}x{height}")
        print(f"Frames checked: {frame_count}")
        print(f"Max detected faces: {max_faces_detected}")
        print(f"Recognition status: {final_status}")

        print("Self-test finished.")
        return 0
    finally:
        camera.release()
        cv2.destroyAllWindows()


def run_detector_diagnostics() -> int:
    print("Detector diagnostics started.")
    print("This mode does not lock Windows and does not save snapshots.")

    setup_directories()
    setup_logging()

    camera = open_camera()
    if camera is None:
        return 1

    try:
        frame_ok, frame = read_frame(camera)
        if not frame_ok:
            print("ERROR: Failed to read a diagnostic frame from camera.")
            return 1

        height, width = frame.shape[:2]
        print(f"Camera frame OK: {width}x{height}")

        for backend in DIAGNOSTIC_DETECTOR_BACKENDS:
            started_at = time.monotonic()
            faces = extract_detected_faces_with_backend(frame, backend)
            elapsed = time.monotonic() - started_at
            print(f"{backend}: faces={len(faces)} time={elapsed:.2f}s")

        print("Detector diagnostics finished.")
        return 0
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    if SELF_TEST_FLAG in sys.argv:
        raise SystemExit(run_self_test())

    if DIAGNOSE_DETECTORS_FLAG in sys.argv:
        raise SystemExit(run_detector_diagnostics())

    raise SystemExit(run())
