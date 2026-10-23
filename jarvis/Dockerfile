FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 JARVIS_MODELS=/opt/models
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# The default voice and speech recognition are part of the image (no download on the first start).
# The last step is a real test: Piper speaks a sentence and faster-whisper has to recognise it.
RUN mkdir -p /opt/models/piper /opt/models/whisper \
    && python -m piper.download_voices de_DE-thorsten-medium --download-dir /opt/models/piper \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root='/opt/models/whisper')" \
    && python - <<'PY'
import io, wave
from piper import PiperVoice
from faster_whisper import WhisperModel
voice = PiperVoice.load("/opt/models/piper/de_DE-thorsten-medium.onnx")
with wave.open("/tmp/test.wav", "wb") as w:
    voice.synthesize_wav("Guten Abend, Sir. Alle Systeme sind bereit.", w)
model = WhisperModel("base", device="cpu", compute_type="int8", download_root="/opt/models/whisper", local_files_only=True)
text = " ".join(s.text for s in model.transcribe("/tmp/test.wav", language="de")[0]).lower()
print("Erkannt:", text)
assert "abend" in text and "system" in text, text
PY

COPY app /app
COPY run.sh /run.sh
RUN chmod a+rx /run.sh && chmod -R a+rX /app /opt/models
CMD [ "/run.sh" ]
