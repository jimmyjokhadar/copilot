import os
import requests
import tempfile
from faster_whisper import WhisperModel

class STTService:
    def __init__(self):
        self.model = WhisperModel("small", device="cpu", compute_type="int8")
        self.audio_types = {"mp3", "wav", "m4a", "ogg", "webm", "mp4"}

    def is_audio_file(self, file_obj):
        mime = (file_obj.get("mimetype") or "").lower()
        ext = (file_obj.get("filetype") or "").lower()
        return mime.startswith("audio/") or ext in self.audio_types

    def transcribe_remote_file(self, file_obj):
        url = file_obj["url_private_download"]
        token = os.getenv("SLACK_BOT_TOKEN")

        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()

        ext = file_obj.get("filetype") or "wav"
        fd, path = tempfile.mkstemp(suffix=f".{ext}")

        with os.fdopen(fd, "wb") as f:
            f.write(resp.content)

        segments, _ = self.model.transcribe(path)
        os.remove(path)

        return " ".join([s.text for s in segments]).strip()
