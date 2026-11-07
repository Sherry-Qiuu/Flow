"""T11 photo quality, camera capture and optional OCR/VLM adapters."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from capture.extract import TaskDraft, extract_from_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PhotoQuality:
    ok: bool
    brightness: float = 0.0
    sharpness: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "brightness": round(self.brightness, 3),
            "sharpness": round(self.sharpness, 3),
            "reason": self.reason,
        }


class PhotoReader(Protocol):
    name: str

    @property
    def available(self) -> bool:
        ...

    def read(self, jpeg: bytes) -> list[TaskDraft]:
        ...


class RulePhotoReader:
    """Deterministic fallback: a photo becomes one editable draft."""

    name = "rule"
    available = True

    def read(self, jpeg: bytes) -> list[TaskDraft]:
        del jpeg
        return [
            TaskDraft(
                title="拍照导入的课程任务",
                source="photo",
                quote="请核对并修改标题/截止时间",
            )
        ]


class VlmPhotoReader:
    name = "vlm"
    available = False

    def __init__(self, endpoint: str = "") -> None:
        self.endpoint = endpoint

    def read(self, jpeg: bytes) -> list[TaskDraft]:
        raise RuntimeError("VLM endpoint is not configured")


class OcrPhotoReader:
    name = "paddleocr"
    available = False

    def read(self, jpeg: bytes) -> list[TaskDraft]:
        raise RuntimeError("PaddleOCR is not installed")


def check_quality(jpeg: bytes) -> PhotoQuality:
    if len(jpeg) < 100:
        return PhotoQuality(False, reason="图片太小或为空")
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return PhotoQuality(True, reason="Pillow unavailable; accept")
    try:
        image = Image.open(io.BytesIO(jpeg)).convert("L")
    except Exception:
        return PhotoQuality(False, reason="不是有效图片")
    stat = ImageStat.Stat(image)
    brightness = float(stat.mean[0]) / 255.0
    # Simple edge proxy: standard deviation of a downscaled image.
    small = image.resize((64, 64))
    pixels = list(small.getdata())
    mean = sum(pixels) / len(pixels)
    variance = sum((value - mean) ** 2 for value in pixels) / len(pixels)
    sharpness = min(1.0, variance / 4096.0)
    if brightness < 0.12:
        return PhotoQuality(
            False,
            brightness,
            sharpness,
            "画面太暗，请补光或靠近一点",
        )
    if sharpness < 0.02:
        return PhotoQuality(
            False,
            brightness,
            sharpness,
            "画面太糊，请对焦后重拍",
        )
    return PhotoQuality(True, brightness, sharpness)


class PhotoImporter:
    def __init__(
        self,
        camera: Any,
        *,
        inbox: str | Path,
        vlm: PhotoReader | None = None,
        ocr: PhotoReader | None = None,
    ) -> None:
        self.camera = camera
        self.inbox = Path(inbox)
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.vlm = vlm or VlmPhotoReader()
        self.ocr = ocr or OcrPhotoReader()

    def capture(self, *, filename: str = "") -> dict[str, Any]:
        if self.camera is None:
            return {"ok": False, "reason": "no camera"}
        frame = self.camera.capture()
        if frame is None:
            return {"ok": False, "reason": "camera capture failed"}
        jpeg = frame.jpeg if hasattr(frame, "jpeg") else bytes(frame)
        quality = check_quality(jpeg)
        if not quality.ok:
            return {"ok": False, "quality": quality.to_dict()}
        path = self._save(jpeg, filename)
        drafts = self.extract(jpeg)
        return {
            "ok": True,
            "quality": quality.to_dict(),
            "path": str(path),
            "drafts": [draft.to_dict() for draft in drafts],
        }

    def extract(self, jpeg: bytes) -> list[TaskDraft]:
        for reader in (self.vlm, self.ocr):
            if getattr(reader, "available", False):
                try:
                    drafts = reader.read(jpeg)
                    if drafts:
                        return drafts
                except Exception:
                    logger.exception("photo reader failed: %s", reader.name)
        return RulePhotoReader().read(jpeg)

    def _save(self, jpeg: bytes, filename: str = "") -> Path:
        stamp = __import__("datetime").datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )
        suffix = Path(filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".pdf"}:
            suffix = ".jpg"
        path = self.inbox / \
            f"{stamp}-{__import__('uuid').uuid4().hex[:8]}{suffix}"
        path.write_bytes(jpeg)
        return path


def drafts_from_photo_text(text: str) -> list[TaskDraft]:
    return extract_from_text(text, source="photo")
