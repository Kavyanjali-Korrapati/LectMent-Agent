"""
Fetch captions/transcript from a YouTube URL using youtube-transcript-api.
Works with auto-generated captions — no API key required.
Compatible with youtube-transcript-api >= 1.0 (instance-based API).
"""
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    YouTubeTranscriptApiException,
)


def _extract_video_id(url: str) -> str:
    """Parse YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract a YouTube video ID from: {url!r}")


def get_youtube_transcript(url: str, preferred_languages: list[str] | None = None) -> str:
    """
    Fetch the full transcript for a YouTube video.

    Args:
        url: Any valid YouTube URL.
        preferred_languages: Language codes in priority order, e.g. ["en", "en-US"].
                             Falls back to auto-generated captions if manual not found.

    Returns:
        The full transcript as a single plain-text string.

    Raises:
        ValueError: If the URL is invalid.
        RuntimeError: If transcripts are disabled or unavailable.
    """
    video_id = _extract_video_id(url)
    langs    = preferred_languages or ["en", "en-US", "en-GB"]

    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)

        # Try manual captions first, then auto-generated
        try:
            transcript = transcript_list.find_manually_created_transcript(langs)
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(langs)
            except NoTranscriptFound:
                # Last resort: grab whatever is available in any language
                transcript = transcript_list.find_transcript(langs)

        fetched = transcript.fetch()
        # v1.x returns FetchedTranscript — each item has a .text attribute
        segments = [
            seg.text if hasattr(seg, "text") else seg.get("text", "")
            for seg in fetched
        ]
        return " ".join(segments).strip()

    except TranscriptsDisabled:
        raise RuntimeError("Transcripts are disabled for this YouTube video.")
    except VideoUnavailable:
        raise RuntimeError("This YouTube video is unavailable or private.")
    except NoTranscriptFound:
        raise RuntimeError(
            "No transcript found for this video in the requested languages. "
            "Try a different language or paste the transcript manually."
        )
    except YouTubeTranscriptApiException as exc:
        raise RuntimeError(f"Could not retrieve transcript: {exc}")
