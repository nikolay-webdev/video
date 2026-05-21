from __future__ import annotations

from pathlib import Path
from time import sleep

import cv2

import config


BASE_DIR = Path(__file__).resolve().parent
KNOWN_FACES_DIR = BASE_DIR / config.KNOWN_FACES_DIR
WINDOW_NAME = "Owner face scan"
FRAME_READ_RETRIES = 20
FRAME_READ_RETRY_DELAY_SECONDS = 0.2

SCAN_STEPS = [
    ("front", "Look straight at the camera"),
    ("monitor", "Look at the monitor naturally"),
    ("keyboard", "Look down at the keyboard"),
    ("left", "Turn your head slightly left"),
    ("right", "Turn your head slightly right"),
    ("up", "Tilt your head slightly up"),
    ("glasses_or_normal", "Use your normal working posture"),
]


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


def draw_face_template(frame, instruction: str, step_index: int, total_steps: int):
    preview = frame.copy()
    height, width = preview.shape[:2]
    center = (width // 2, height // 2)
    axes = (max(90, width // 6), max(130, height // 3))

    cv2.ellipse(preview, center, axes, 0, 0, 360, (0, 255, 0), 2, cv2.LINE_AA)
    cv2.line(
        preview,
        (center[0] - axes[0], center[1]),
        (center[0] + axes[0], center[1]),
        (0, 180, 0),
        1,
        cv2.LINE_AA,
    )
    cv2.line(
        preview,
        (center[0], center[1] - axes[1]),
        (center[0], center[1] + axes[1]),
        (0, 180, 0),
        1,
        cv2.LINE_AA,
    )

    cv2.rectangle(preview, (0, 0), (width, 92), (0, 0, 0), -1)
    cv2.putText(
        preview,
        f"Step {step_index + 1}/{total_steps}: {instruction}",
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        preview,
        "Align face with oval. SPACE: save | S: skip | Q/ESC: quit",
        (20, 68),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return preview


def save_scan_photo(frame, step_name: str) -> Path | None:
    KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = KNOWN_FACES_DIR / f"nikolay_{step_name}.jpg"

    if cv2.imwrite(str(output_path), frame):
        return output_path

    return None


def run() -> int:
    camera = open_camera()
    if camera is None:
        return 1

    print("Owner face scan started.")
    print("SPACE: save current step | S: skip step | Q/ESC: quit")
    print(f"Output folder: {KNOWN_FACES_DIR}")

    saved_paths: list[Path] = []
    step_index = 0

    try:
        while step_index < len(SCAN_STEPS):
            step_name, instruction = SCAN_STEPS[step_index]
            frame_ok, frame = read_frame(camera)
            if not frame_ok:
                print(
                    "ERROR: Failed to read frame from camera.\n"
                    "Close Teams/Zoom/browser camera tabs and try again."
                )
                return 1

            preview = draw_face_template(frame, instruction, step_index, len(SCAN_STEPS))
            cv2.imshow(WINDOW_NAME, preview)

            key = cv2.waitKey(1) & 0xFF
            if key == 32:
                saved_path = save_scan_photo(frame, step_name)
                if saved_path is None:
                    print(f"ERROR: Failed to save step: {step_name}")
                    return 1

                saved_paths.append(saved_path)
                print(f"Saved: {saved_path}")
                step_index += 1
                sleep(0.5)
                continue

            if key in (ord("s"), ord("S")):
                print(f"Skipped: {step_name}")
                step_index += 1
                sleep(0.3)
                continue

            if key in (27, ord("q"), ord("Q")):
                print("Scan cancelled.")
                return 0

        print("Owner face scan finished.")
        print(f"Saved photos: {len(saved_paths)}")
        for saved_path in saved_paths:
            print(f"- {saved_path}")
        return 0
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(run())
