"""Jarvis' ears and voice, both on the Home Assistant server: faster-whisper (speech → text) and Piper
(text → speech). The default models are part of the image; other voices or sizes are downloaded once."""

import io
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path

log = logging.getLogger("speech")
MODELS = Path(os.environ.get("JARVIS_MODELS", "/opt/models"))
DATA_MODELS = Path(os.environ.get("JARVIS_DATA", "/data")) / "modelle"


class SpeechError(Exception):
    pass


class Ears:
    def __init__(self, size: str):
        self.size = size or "base"
        self.model = None
        self.lock = threading.Lock()

    def load(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            root = MODELS / "whisper" if (MODELS / "whisper").exists() else DATA_MODELS / "whisper"
            log.info("Lade Spracherkennung (%s) …", self.size)
            kwargs = dict(device="cpu", compute_type="int8", download_root=str(root), cpu_threads=max(1, os.cpu_count() or 2))
            try:            # the model from the image, without asking the internet
                self.model = WhisperModel(self.size, local_files_only=True, **kwargs)
            except Exception:  # noqa: BLE001 – another size: download it once
                DATA_MODELS.mkdir(parents=True, exist_ok=True)
                self.model = WhisperModel(self.size, **{**kwargs, "download_root": str(DATA_MODELS / "whisper")})
        return self.model

    def transcribe(self, audio: bytes, suffix: str = ".webm") -> str:
        if len(audio) < 1500:
            return ""
        with self.lock, tempfile.NamedTemporaryFile(suffix=suffix) as fh:
            fh.write(audio)
            fh.flush()
            try:
                segments, _ = self.load().transcribe(fh.name, language="de", beam_size=1, vad_filter=True,
                                                     initial_prompt="Jarvis, Licht, Wohnzimmer, Drucker, Werkbank, Pino.")
                return " ".join(s.text.strip() for s in segments).strip()
            except Exception as err:  # noqa: BLE001 – a broken recording must not take Jarvis down
                raise SpeechError(f"Aufnahme nicht verständlich: {err}") from err


class Voice:
    def __init__(self, name: str, speed: float):
        self.name = name or "de_DE-thorsten-medium"
        self.speed = speed or 1.0
        self.voice = None
        self.lock = threading.Lock()

    def model_path(self) -> Path:
        for folder in (MODELS / "piper", DATA_MODELS / "piper"):
            if (folder / f"{self.name}.onnx").exists():
                return folder / f"{self.name}.onnx"
        DATA_MODELS.mkdir(parents=True, exist_ok=True)
        log.info("Lade Stimme %s herunter …", self.name)
        subprocess.run([sys.executable, "-m", "piper.download_voices", self.name, "--download-dir", str(DATA_MODELS / "piper")],
                       check=False, timeout=600)
        path = DATA_MODELS / "piper" / f"{self.name}.onnx"
        if not path.exists():
            raise SpeechError(f"Stimme {self.name} nicht verfügbar")
        return path

    def load(self):
        if self.voice is None:
            from piper import PiperVoice
            self.voice = PiperVoice.load(self.model_path())
        return self.voice

    def speak(self, text: str) -> tuple[bytes, float]:
        """WAV audio and its length in seconds."""
        from piper import SynthesisConfig
        with self.lock:
            voice = self.load()        # before wave.open: a failed load must not leave a half-written WAV
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav:
                voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=1 / max(0.5, min(2.0, self.speed))))
            data = buf.getvalue()
        with wave.open(io.BytesIO(data), "rb") as wav:
            seconds = wav.getnframes() / float(wav.getframerate() or 22050)
        return data, seconds


EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF️]")


def speakable(text: str, limit: int = 700) -> str:
    """Markdown, links and emojis out; long answers end at a sentence near the limit."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[*_#`>|]+", "", t)
    t = EMOJI.sub("", t)
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.M)
    t = t.replace("°C", " Grad").replace("°", " Grad").replace("€", " Euro").replace("%", " Prozent")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        cut = max(t.rfind(". ", 0, limit), t.rfind("! ", 0, limit), t.rfind("? ", 0, limit))
        t = t[: cut + 1] if cut > limit // 3 else t[:limit] + " …"
    return t
