"""T07 prioritized speech output with emotion and quiet hours."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bus import topics
from hal.contracts import AudioOut
from voice.tts import AudioCache, SilentTts, TtsProvider

logger = logging.getLogger(__name__)

PRIORITIES = {
    "decoration": 0,
    "chat": 1,
    "normal": 2,
    "dialogue": 2,
    "reminder": 3,
}
_PREEMPT_AT = 3


@dataclass(frozen=True)
class SaySettings:
    voice: str = "zh"
    dedupe_s: float = 5.0
    quiet_start: int = 22
    quiet_end: int = 7
    emotion_hold_s: float = 0.8
    cache_dir: str = "data/audio/cache"
    max_cache_files: int = 200


class SayService:
    def __init__(
        self,
        *,
        tts: TtsProvider | None = None,
        audio_out: AudioOut | None = None,
        publisher: Any = None,
        settings: SaySettings | None = None,
        clock=time.monotonic,
    ) -> None:
        self.settings = settings or SaySettings()
        self.tts = tts or SilentTts()
        self.audio_out = audio_out
        self.publisher = publisher
        self.cache = AudioCache(
            self.settings.cache_dir,
            max_files=self.settings.max_cache_files,
        )
        self.clock = clock
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seq = 0
        self._generation = 0
        self._last_spoken: dict[str, float] = {}
        self._lock = threading.RLock()
        self._last_text = ""
        self._last_emotion = "neutral"
        self._spoken = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="flow-say",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put((999, 0, None, "neutral", self._generation))
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def say(
        self,
        text: str,
        emotion: str = "neutral",
        priority: str = "normal",
        *,
        now: datetime | None = None,
    ) -> bool:
        text = str(text or "").strip()
        if not text:
            return False
        timestamp = self.clock()
        with self._lock:
            last = self._last_spoken.get(text)
            if last is not None and timestamp - last < self.settings.dedupe_s:
                return False
            self._last_spoken[text] = timestamp
            self._seq += 1
            seq = self._seq
            level = PRIORITIES.get(priority, PRIORITIES["normal"])
            quiet = is_quiet(now or datetime.now(), self.settings)
            self._last_text = text
            self._last_emotion = emotion
            if level >= _PREEMPT_AT:
                self._preempt_locked()
            if not quiet:
                self._queue.put(
                    (10 - level, seq, text, emotion, self._generation)
                )
        self._publish(
            topics.ASSISTANT_SAY,
            {
                "text": text,
                "emotion": emotion,
                "priority": priority,
                "quiet": quiet,
            },
        )
        self._publish(topics.EMOTION_FACE, {"emotion": emotion})
        return True

    def interrupt(self) -> None:
        with self._lock:
            self._generation += 1
            self._drain()
            if self.audio_out is not None:
                try:
                    self.audio_out.stop()
                except Exception:
                    logger.exception("audio stop failed")
        self._publish(topics.SPEECH_BARGE_IN, {"reason": "tts_interrupt"})

    def health(self) -> dict[str, object]:
        return {
            "state": "ok" if self.running else "error",
            "tts": self.tts.name,
            "tts_available": self.tts.available,
            "queue": self._queue.qsize(),
            "spoken": self._spoken,
            "last_text": self._last_text,
        }

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                _, _, text, emotion, generation = self._queue.get(
                    timeout=0.5
                )
            except queue.Empty:
                continue
            if text is None:
                return
            if generation != self._generation:
                continue
            self._speak(text, emotion)
            self._queue.task_done()

    def _speak(self, text: str, emotion: str) -> None:
        path = self.cache.get(text, self.settings.voice)
        if path is None and self.tts.available:
            generated = self.tts.synthesize(text, self.settings.voice)
            if generated is not None:
                path = self.cache.put(
                    text,
                    generated,
                    self.settings.voice,
                )
                generated.unlink(missing_ok=True)
        if path is not None and self.audio_out is not None:
            try:
                self.audio_out.play(path)
            except Exception:
                logger.exception("TTS playback failed")
        with self._lock:
            self._spoken += 1
        if self.settings.emotion_hold_s > 0:
            time.sleep(self.settings.emotion_hold_s)
            self._publish(topics.EMOTION_FACE, {"emotion": "neutral"})

    def _preempt_locked(self) -> None:
        self._generation += 1
        self._drain()
        if self.audio_out is not None:
            try:
                self.audio_out.stop()
            except Exception:
                logger.exception("audio preempt failed")

    def _drain(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            if item[2] is not None:
                self._queue.task_done()

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("say publish failed: %s", topic)


def is_quiet(now: datetime, settings: SaySettings) -> bool:
    hour = now.hour
    start = settings.quiet_start % 24
    end = settings.quiet_end % 24
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


__all__ = ["SayService", "SaySettings", "is_quiet"]
