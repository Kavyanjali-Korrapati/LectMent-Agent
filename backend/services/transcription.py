"""
Audio-to-text transcription service.
Primary  : IBM Watson Speech-to-Text (REST, free lite plan — 500 min/month)
Fallback : openai-whisper (local, CPU) — OPTIONAL, only used if installed.
           If neither is available, raises a clear error asking the user
           to paste the transcript manually instead of uploading audio.
"""
import os
import io
import tempfile
from pathlib import Path


# ─── IBM Watson Speech-to-Text ────────────────────────────────────────────────

def _ibm_stt(audio_bytes: bytes, content_type: str = "audio/mp3") -> str:
    """Transcribe via IBM Watson STT REST API."""
    from ibm_watson import SpeechToTextV1
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

    api_key = os.environ["IBM_STT_API_KEY"]
    stt_url = os.environ["IBM_STT_URL"]

    authenticator = IAMAuthenticator(api_key)
    stt = SpeechToTextV1(authenticator=authenticator)
    stt.set_service_url(stt_url)

    result = stt.recognize(
        audio            = io.BytesIO(audio_bytes),
        content_type     = content_type,
        model            = "en-US_BroadbandModel",
        smart_formatting = True,
    ).get_result()

    transcripts = [
        alt["transcript"]
        for res in result.get("results", [])
        for alt in res.get("alternatives", [])
    ]
    return " ".join(transcripts).strip()


# ─── Whisper (optional local fallback) ───────────────────────────────────────

def _whisper_available() -> bool:
    """Return True only if openai-whisper is actually installed."""
    try:
        import importlib
        return importlib.util.find_spec("whisper") is not None
    except Exception:
        return False


def _whisper_stt(audio_bytes: bytes, filename: str = "audio.mp3") -> str:
    """Transcribe using openai-whisper (CPU, base model)."""
    import whisper  # only called after _whisper_available() confirmed True

    suffix = Path(filename).suffix or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        model  = whisper.load_model("base")
        result = model.transcribe(tmp_path, fp16=False)
        return result["text"].strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─── Public entry point ───────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.mp3") -> str:
    """
    Transcription priority:
      1. IBM Watson STT  — when IBM_STT_API_KEY env var is set.
      2. openai-whisper  — when installed locally (pip install openai-whisper).
      3. Clear error     — tells the user to paste transcript manually.

    Returns the transcript as a plain string.
    """
    # ── Path 1: IBM Watson STT ────────────────────────────────────────────────
    if os.environ.get("IBM_STT_API_KEY") and os.environ.get("IBM_STT_URL"):
        ext = Path(filename).suffix.lower()
        content_map = {
            ".mp3" : "audio/mp3",
            ".wav" : "audio/wav",
            ".flac": "audio/flac",
            ".ogg" : "audio/ogg",
            ".m4a" : "audio/mp4",
        }
        content_type = content_map.get(ext, "audio/mp3")
        return _ibm_stt(audio_bytes, content_type)

    # ── Path 2: Local Whisper ─────────────────────────────────────────────────
    if _whisper_available():
        return _whisper_stt(audio_bytes, filename)

    # ── Path 3: No transcription backend available ────────────────────────────
    raise RuntimeError(
        "No audio transcription backend is configured. "
        "To enable audio uploads, do ONE of the following:\n"
        "  • Set IBM_STT_API_KEY + IBM_STT_URL in your .env file (free IBM Watson STT), OR\n"
        "  • Install Whisper locally: pip install openai-whisper\n"
        "Alternatively, paste your transcript as text directly."
    )
