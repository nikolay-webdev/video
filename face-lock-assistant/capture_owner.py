from __future__ import annotations

from pathlib import Path
from time import sleep

import cv2

import config


BASE_DIR = Path(__file__).resolve().parent
KNOWN_FACE_PATH = BASE_DIR / config.KNOWN_FACE_PATH
WINDOW_NAME = "Capture owner photo"
FRAME_READ_RETRIES = 20
FRAME_READ_RETRY_DELAY_SECONDS = 0.2


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


def save_owner_photo(frame) -> bool:
    KNOWN_FACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return cv2.imwrite(str(KNOWN_FACE_PATH), frame)


def run() -> int:
    camera = open_camera()
    if camera is None:
        return 1

    print("Owner photo capture started.")
    print("Press SPACE to save the current frame.")
    print("Press Q or ESC to exit without saving.")
    print(f"Output file: {KNOWN_FACE_PATH}")

    try:
        while True:
            frame_ok, frame = read_frame(camera)
            if not frame_ok:
                print(
                    "ERROR: Failed to read frame from camera.\n"
                    "Close Teams/Zoom/browser camera tabs and try again."
                )
                return 1

            preview = frame.copy()
            cv2.putText(
                preview,
                "SPACE: save | Q/ESC: quit",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(WINDOW_NAME, preview)

            key = cv2.waitKey(1) & 0xFF
            if key == 32:
                if save_owner_photo(frame):
                    print(f"Owner photo saved: {KNOWN_FACE_PATH}")
                    return 0

                print(f"ERROR: Failed to save owner photo: {KNOWN_FACE_PATH}")
                return 1

            if key in (27, ord("q"), ord("Q")):
                print("Capture cancelled.")
                return 0
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(run())
