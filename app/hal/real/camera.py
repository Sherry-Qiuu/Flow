"""Camera implementations for Pi Camera and USB webcams."""

from __future__ import annotations

import io
import logging
from typing import Any

from hal.contracts import Camera, DeviceStatus

logger = logging.getLogger(__name__)


class RealCamera(Camera):
    """Prefer picamera2 (CSI) and fall back to OpenCV (USB)."""

    name = "camera"

    def __init__(self) -> None:
        super().__init__()
        self._picam: Any = None
        self._cv2: Any = None
        self._backend = ""

    @property
    def is_open(self) -> bool:
        return self._opened

    def probe(self) -> DeviceStatus:
        try:
            import picamera2  # noqa: F401

            return DeviceStatus.ok("picamera2 available")
        except ImportError:
            pass
        try:
            import cv2  # noqa: F401

            return DeviceStatus.ok("opencv available")
        except ImportError:
            return DeviceStatus.missing(
                "neither picamera2 nor opencv is installed"
            )

    def open(self) -> DeviceStatus:
        status = self.probe()
        if not status.available:
            return status
        try:
            from picamera2 import Picamera2

            camera = Picamera2()
            config = camera.create_still_configuration(
                main={"size": (1280, 720)}
            )
            camera.configure(config)
            camera.start()
            self._picam = camera
            self._backend = "picamera2"
            self._opened = True
            return DeviceStatus.ok("picamera2 opened")
        except Exception as exc:
            logger.debug("picamera2 open failed: %s", exc)
            self._picam = None
        try:
            import cv2

            camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                camera.release()
                return DeviceStatus.missing("no USB camera at index 0")
            self._cv2 = camera
            self._backend = "opencv"
            self._opened = True
            return DeviceStatus.ok("USB camera opened")
        except Exception as exc:
            return DeviceStatus.error(f"camera open failed: {exc}")

    def close(self) -> None:
        if self._picam is not None:
            try:
                self._picam.stop()
                self._picam.close()
            except Exception:  # pragma: no cover - hardware boundary
                logger.exception("failed to close picamera2")
            self._picam = None
        if self._cv2 is not None:
            try:
                self._cv2.release()
            except Exception:  # pragma: no cover - hardware boundary
                logger.exception("failed to release USB camera")
            self._cv2 = None
        self._opened = False

    def health(self) -> DeviceStatus:
        if not self._opened:
            return self.probe()
        if self._backend == "picamera2" and self._picam is None:
            return DeviceStatus.error("picamera2 handle is gone")
        if self._backend == "opencv" and self._cv2 is None:
            return DeviceStatus.error("USB camera handle is gone")
        return DeviceStatus.ok(f"{self._backend} open")

    def capture(self) -> bytes | None:
        if not self._opened:
            status = self.open()
            if not status.available:
                return None
        try:
            if self._backend == "picamera2":
                return self._capture_picamera2()
            if self._backend == "opencv":
                return self._capture_opencv()
        except Exception as exc:
            logger.warning("camera capture failed, degrading: %s", exc)
            self.close()
        return None

    def _capture_picamera2(self) -> bytes | None:
        request = self._picam.capture_request()
        try:
            array = request.make_array("main")
        finally:
            request.release()
        from PIL import Image

        image = Image.fromarray(array)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()

    def _capture_opencv(self) -> bytes | None:
        ok, frame = self._cv2.read()
        if not ok or frame is None:
            return None
        import cv2

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        return encoded.tobytes()
