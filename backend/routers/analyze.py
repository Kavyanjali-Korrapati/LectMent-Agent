"""
/api/analyze router — LectMent processing pipeline.

Input endpoints:
  POST /api/analyze/text    — raw transcript + mode + language + difficulty + num_cards
  POST /api/analyze/youtube — YouTube URL + mode + language + difficulty + num_cards
  POST /api/analyze/audio   — audio file upload + mode + language + difficulty
  POST /api/analyze/video   — video file upload + mode + language + difficulty
  POST /api/analyze/ask     — follow-up question against a previous transcript

Modes: study | research | sheet | quiz | summarize
"""
import logging
import hashlib
import re
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from cachetools import TTLCache
from slowapi import Limiter
from slowapi.util import get_remote_address

try:
    from langdetect import detect as _langdetect, LangDetectException
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False

from backend.services.prompts import get_prompt, ask_prompt
from backend.services.watsonx_client import generate
from backend.services.youtube_transcript import get_youtube_transcript
from backend.services.transcription import transcribe_audio

log     = logging.getLogger("lectment.analyze")
limiter = Limiter(key_func=get_remote_address)
router  = APIRouter(prefix="/analyze", tags=["analyze"])

CHUNK_SIZE           = 12_000   # chars per chunk for map-reduce
MAX_MEDIA_BYTES      = 200 * 1024 * 1024

DEFAULT_MODE       = "study"
DEFAULT_LANGUAGE   = "English"
DEFAULT_DIFFICULTY = "medium"
DEFAULT_NUM_CARDS  = 8

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/flac", "audio/ogg", "audio/mp4", "audio/m4a",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4", "video/mpeg", "video/webm", "video/quicktime",
    "video/x-msvideo", "video/x-matroska",
}

# ── In-memory TTL cache (max 200 entries, expires after 1 hour) ──────────────
_cache: TTLCache = TTLCache(maxsize=200, ttl=3600)


def _cache_key(transcript: str, mode: str, language: str, difficulty: str, num_cards: int) -> str:
    raw = f"{mode}|{language}|{difficulty}|{num_cards}|{transcript}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Auto language detection ────────────────────────────────────────────────────

def _detect_language(text: str, requested: str) -> str:
    """
    If the user asked for English (default) and langdetect is available,
    check if the transcript is actually in another language and return the
    detected language name so the prompt preamble adds the right instruction.
    """
    if not _LANGDETECT_AVAILABLE:
        return requested
    if not requested.lower().startswith("en"):
        # User explicitly set a non-English language — honour it
        return requested
    try:
        code = _langdetect(text[:2000])   # sample first 2 000 chars
        # Map common ISO codes to readable names the prompt preamble can use
        _CODE_MAP = {
            "es": "Spanish", "fr": "French", "de": "German", "zh-cn": "Chinese",
            "zh-tw": "Chinese (Traditional)", "ja": "Japanese", "ko": "Korean",
            "pt": "Portuguese", "it": "Italian", "ru": "Russian", "ar": "Arabic",
            "hi": "Hindi", "tr": "Turkish", "nl": "Dutch", "pl": "Polish",
        }
        if code.startswith("en"):
            return requested
        return _CODE_MAP.get(code, requested)
    except Exception:
        return requested


# ── Smart map-reduce chunking ──────────────────────────────────────────────────

def _chunk_and_reduce(text: str, mode: str, language: str, difficulty: str) -> str:
    """
    For transcripts larger than CHUNK_SIZE:
      1. Split into overlapping chunks of CHUNK_SIZE chars.
      2. Summarize each chunk with a short 'summarize' prompt.
      3. Concatenate summaries → treat as the final transcript.
    For transcripts within limit, return as-is.
    """
    if len(text) <= CHUNK_SIZE:
        return text

    # Build chunks with a 200-char overlap so sentences aren't cut mid-idea
    OVERLAP = 200
    chunks  = []
    start   = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - OVERLAP

    log.info("Map-reduce chunking: %d chunks from %d chars", len(chunks), len(text))

    summaries = []
    for i, chunk in enumerate(chunks):
        chunk_prompt = (
            f"Summarize the following lecture segment in 3–5 concise bullet points. "
            f"Keep all key terms and facts. Do NOT add outside information.\n\n"
            f"Segment {i+1}/{len(chunks)}:\n{chunk}\n\nSummary:"
        )
        try:
            summary = generate(chunk_prompt, "summarize")
            summaries.append(f"[Segment {i+1}]\n{summary}")
        except Exception as exc:
            log.warning("Chunk %d summarization failed: %s", i + 1, exc)
            # Fall back to raw truncated chunk so we don't lose content
            summaries.append(f"[Segment {i+1}]\n{chunk[:1000]}")

    combined = "\n\n".join(summaries)
    log.info("Map-reduce complete: combined length=%d chars", len(combined))
    return combined


# ── Section parser ────────────────────────────────────────────────────────────

# Markers mapped to section keys — order matters for the regex split
_SECTION_PATTERNS = [
    (re.compile(r"###\s*SECTION\s*1\s*[—\-–]?\s*SUMMARY",       re.IGNORECASE), "summary"),
    (re.compile(r"###\s*SECTION\s*2\s*[—\-–]?\s*KEY\s*TAKEAWAY", re.IGNORECASE), "takeaways"),
    (re.compile(r"###\s*SECTION\s*3\s*[—\-–]?\s*QUIZ",          re.IGNORECASE), "quiz"),
    (re.compile(r"###\s*SECTION\s*4\s*[—\-–]?\s*FLASH",         re.IGNORECASE), "flashcards"),
    (re.compile(r"###\s*SECTION\s*4\s*[—\-–]?\s*CHEAT",         re.IGNORECASE), "cheatsheet"),
    (re.compile(r"###\s*SECTION\s*4\s*[—\-–]?\s*RESEARCH",      re.IGNORECASE), "research"),
    (re.compile(r"###\s*SECTION\s*5\s*[—\-–]?\s*DIFF",          re.IGNORECASE), "prerequisites"),
]

def _parse_sections(raw: str) -> dict:
    sections: dict[str, str] = {
        "summary"      : "",
        "takeaways"    : "",
        "quiz"         : "",
        "flashcards"   : "",
        "cheatsheet"   : "",
        "research"     : "",
        "prerequisites": "",
    }

    # Split on any known section header
    all_patterns = "|".join(p.pattern for p, _ in _SECTION_PATTERNS)
    splitter     = re.compile(all_patterns, re.IGNORECASE)
    parts        = splitter.split(raw)
    headers      = splitter.findall(raw)

    if not headers:
        # No section headers found — store the whole output as summary fallback
        sections["summary"] = raw.strip()
        return sections

    # Skip the text before the first header (preamble/echo of prompt)
    for header_text, section_body in zip(headers, parts[1:]):
        key = None
        for pattern, section_key in _SECTION_PATTERNS:
            if pattern.search(header_text):
                key = section_key
                break
        if key:
            sections[key] = section_body.strip()

    # Secondary fallback: if summary is still empty, store full raw
    if not sections["summary"]:
        sections["summary"] = raw.strip()

    return sections


# ── Output validator ──────────────────────────────────────────────────────────

_REQUIRED_KEYWORDS = {
    "study"    : ["SECTION 1", "SECTION 2", "SECTION 3"],
    "research" : ["SECTION 1", "SECTION 2", "SECTION 3", "SECTION 4"],
    "sheet"    : ["SECTION 1", "SECTION 2", "SECTION 3", "SECTION 4"],
    "quiz"     : ["SECTION 1", "SECTION 2", "SECTION 3", "SECTION 4"],
    "summarize": ["SECTION 1", "SECTION 2", "SECTION 3"],
}

def _is_valid_output(raw: str, mode: str) -> bool:
    if len(raw) < 200:
        return False
    required = _REQUIRED_KEYWORDS.get(mode, ["SECTION 1"])
    return all(kw.lower() in raw.lower() for kw in required)


# ── Core analysis runner ───────────────────────────────────────────────────────

def _run_analysis(
    transcript: str,
    mode      : str,
    language  : str,
    difficulty: str = DEFAULT_DIFFICULTY,
    num_cards : int = DEFAULT_NUM_CARDS,
) -> dict:
    cleaned = transcript.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Transcript is empty.")

    # Auto-detect language if user left default "English"
    detected_language = _detect_language(cleaned, language)
    if detected_language != language:
        log.info("Language auto-detected: %s (requested: %s)", detected_language, language)
        language = detected_language

    # Smart chunking — map-reduce for long transcripts
    processed = _chunk_and_reduce(cleaned, mode, language, difficulty)

    key = _cache_key(processed, mode, language, difficulty, num_cards)
    if key in _cache:
        log.info("Cache HIT — mode=%s lang=%s diff=%s chars=%d", mode, language, difficulty, len(processed))
        return _cache[key]

    log.info("Cache MISS — calling Granite. mode=%s lang=%s diff=%s cards=%d chars=%d",
             mode, language, difficulty, num_cards, len(processed))

    prompt = get_prompt(mode, processed, language, difficulty, num_cards)

    try:
        raw_output = generate(prompt, mode)
    except EnvironmentError as exc:
        # Missing credentials — tell the user clearly
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        log.error("Granite generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")

    # Output validation — retry once if output looks malformed
    if not _is_valid_output(raw_output, mode):
        log.warning("Output validation failed (len=%d). Retrying once.", len(raw_output))
        try:
            raw_output = generate(prompt, mode)
        except Exception:
            pass   # use whatever we got from the first attempt
        if not _is_valid_output(raw_output, mode):
            log.warning("Retry also produced short/malformed output. Using as-is.")

    sections = _parse_sections(raw_output)

    # Word count + reading time metadata
    word_count          = len(cleaned.split())
    est_reading_time    = max(1, round(word_count / 200))   # avg 200 wpm reading speed

    result = {
        "mode"               : mode,
        "language"           : language,
        "difficulty"         : difficulty,
        "word_count"         : word_count,
        "est_reading_time_min": est_reading_time,
        "transcript_preview" : cleaned[:500] + ("…" if len(cleaned) > 500 else ""),
        **sections,
    }

    # Guard: only cache if at least one section has content
    if any(v for v in sections.values()):
        _cache[key] = result

    return result


# ── 1. Plain text ─────────────────────────────────────────────────────────────

class TextRequest(BaseModel):
    transcript : str
    mode       : str = DEFAULT_MODE
    language   : str = DEFAULT_LANGUAGE
    difficulty : str = DEFAULT_DIFFICULTY
    num_cards  : int = DEFAULT_NUM_CARDS

@router.post("/text")
@limiter.limit("15/minute")
async def analyze_text(request: Request, body: TextRequest):
    return JSONResponse(_run_analysis(
        body.transcript, body.mode, body.language, body.difficulty, body.num_cards
    ))


# ── 2. YouTube URL ────────────────────────────────────────────────────────────

class YouTubeRequest(BaseModel):
    url        : str
    mode       : str = DEFAULT_MODE
    language   : str = DEFAULT_LANGUAGE
    difficulty : str = DEFAULT_DIFFICULTY
    num_cards  : int = DEFAULT_NUM_CARDS

@router.post("/youtube")
@limiter.limit("15/minute")
async def analyze_youtube(request: Request, body: YouTubeRequest):
    try:
        transcript = get_youtube_transcript(body.url)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(_run_analysis(
        transcript, body.mode, body.language, body.difficulty, body.num_cards
    ))


# ── 3. Audio file upload ──────────────────────────────────────────────────────

@router.post("/audio")
@limiter.limit("10/minute")
async def analyze_audio(
    request   : Request,
    file      : UploadFile = File(...),
    mode      : str        = Form(DEFAULT_MODE),
    language  : str        = Form(DEFAULT_LANGUAGE),
    difficulty: str        = Form(DEFAULT_DIFFICULTY),
):
    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type '{file.content_type}'. Use MP3, WAV, FLAC, OGG or M4A.",
        )
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 200 MB limit.")
    log.info("Audio upload: file=%s size=%d mode=%s lang=%s diff=%s",
             file.filename, len(audio_bytes), mode, language, difficulty)
    try:
        transcript = transcribe_audio(audio_bytes, file.filename or "audio.mp3")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
    return JSONResponse(_run_analysis(transcript, mode, language, difficulty))


# ── 4. Video file upload ──────────────────────────────────────────────────────

@router.post("/video")
@limiter.limit("5/minute")
async def analyze_video(
    request   : Request,
    file      : UploadFile = File(...),
    mode      : str        = Form(DEFAULT_MODE),
    language  : str        = Form(DEFAULT_LANGUAGE),
    difficulty: str        = Form(DEFAULT_DIFFICULTY),
):
    if file.content_type not in ALLOWED_VIDEO_TYPES | ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type '{file.content_type}'. Upload MP4, WebM, MOV, MKV, AVI.",
        )
    video_bytes = await file.read()
    if len(video_bytes) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="Video file exceeds 200 MB limit.")

    log.info("Video upload: file=%s size=%d mode=%s lang=%s diff=%s",
             file.filename, len(video_bytes), mode, language, difficulty)
    audio_bytes = _extract_audio(video_bytes, file.filename or "video.mp4")
    try:
        transcript = transcribe_audio(audio_bytes, "extracted_audio.wav")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
    return JSONResponse(_run_analysis(transcript, mode, language, difficulty))


# ── 5. Follow-up Q&A ─────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    transcript: str
    question  : str
    language  : str = DEFAULT_LANGUAGE
    mode      : str = DEFAULT_MODE

@router.post("/ask")
@limiter.limit("20/minute")
async def analyze_ask(request: Request, body: AskRequest):
    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty.")
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question is empty.")
    prompt = ask_prompt(
        body.transcript[:CHUNK_SIZE],   # cap at chunk size for Q&A
        body.question,
        body.language,
        body.mode,
    )
    try:
        answer = generate(prompt, body.mode)
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        log.error("Ask generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")
    return JSONResponse({"answer": answer.strip(), "question": body.question})


# ── Video audio extractor ─────────────────────────────────────────────────────

def _extract_audio(video_bytes: bytes, filename: str) -> bytes:
    import subprocess, tempfile, os
    from pathlib import Path

    suffix = Path(filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as vin:
        vin.write(video_bytes)
        vin_path = vin.name

    vout_path = vin_path + "_audio.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", vin_path, "-vn",
             "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", vout_path],
            check=True, capture_output=True,
        )
        with open(vout_path, "rb") as f:
            return f.read()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return video_bytes
    finally:
        for p in (vin_path, vout_path):
            try: os.unlink(p)
            except OSError: pass
