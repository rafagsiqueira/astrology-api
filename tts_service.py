"""Utility functions for generating TTS audio and uploading to Firebase Storage."""

from __future__ import annotations

import uuid
from typing import Optional, Tuple

from firebase_admin import storage as firebase_storage
from google.cloud import exceptions as gcs_exceptions

from config import GCS_AUDIO_BUCKET, get_logger

AUDIO_STREAM_CHUNK_SIZE = 262144  # OpenAI Responses API requires multiples of 262144 bytes.

logger = get_logger(__name__)


def get_storage_bucket():
    """Return the configured Firebase Storage bucket, or None if unavailable."""
    try:
        if GCS_AUDIO_BUCKET:
            return firebase_storage.bucket(GCS_AUDIO_BUCKET)
        return firebase_storage.bucket()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to obtain storage bucket: %s", exc)
        return None


def create_audio_blob(
    *,
    user_id: str,
    date_key: str,
    message_id: str,
    extension: str = "mp3",
):
    """Create (but do not upload) a Firebase Storage blob for an audio asset."""
    bucket = get_storage_bucket()
    if bucket is None:
        return None, None

    blob_name = f"daily_transits/{user_id}/{date_key}/{message_id}.{extension}"
    return bucket.blob(blob_name), blob_name


def generate_tts_audio(
    *,
    script: str,
    user_id: str,
    date_key: str,
    message_id: str,
    openai_client,
) -> Tuple[str, str]:
    """Generate TTS audio via OpenAI and upload it directly to Firebase Storage.

    Returns:
        Tuple[path, audio_format]
    """
    if not script or not script.strip():
        raise ValueError("TTS script must be non-empty")

    blob, blob_name = create_audio_blob(
        user_id=user_id,
        date_key=date_key,
        message_id=message_id,
        extension="mp3",
    )
    if blob is None or blob_name is None:
        raise RuntimeError("Unable to access Firebase Storage bucket")

    try:
        if hasattr(blob, "bucket") and hasattr(blob.bucket, "exists"):
            if not blob.bucket.exists():
                raise RuntimeError("Firebase Storage bucket does not exist or access is denied")
    except gcs_exceptions.GoogleCloudError as exc:  # pragma: no cover - network dependent
        raise RuntimeError("Failed to verify Firebase Storage bucket") from exc

    try:
        bytes_written = 0
        with openai_client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="sage",
            response_format="mp3",
            input=script,
            instructions = """Voice Affect: Calm, composed, and reassuring; project quiet authority and confidence.\n\nTone: Sincere, empathetic, and gently authoritative—express genuine apology while conveying competence.\n\nPacing: Steady and moderate; unhurried enough to communicate care, yet efficient enough to demonstrate professionalism.\n\nEmotion: Genuine empathy and understanding; speak with warmth, especially during apologies (\"I'm very sorry for any disruption...\").\n\nPronunciation: Clear and precise, emphasizing key reassurances (\"smoothly,\" \"quickly,\" \"promptly\") to reinforce confidence.\n\nPauses: Brief pauses after offering assistance or requesting details, highlighting willingness to listen and support."""
        ) as speech_response:
            with blob.open(mode="wb", chunk_size=AUDIO_STREAM_CHUNK_SIZE) as writer:
                for chunk in speech_response.iter_bytes(AUDIO_STREAM_CHUNK_SIZE):
                    if not chunk:
                        continue
                    if isinstance(chunk, str):
                        chunk = chunk.encode()
                    writer.write(chunk)
                    bytes_written += len(chunk)

        if bytes_written == 0:
            try:
                blob.delete()
            except Exception:  # pragma: no cover - defensive cleanup
                pass
            raise RuntimeError("OpenAI TTS returned no audio content")

        token = uuid.uuid4().hex
        blob.metadata = {"firebaseStorageDownloadTokens": token}
        blob.patch()

        return blob_name, "mp3"
    except Exception:
        try:
            blob.delete()
        except Exception:  # pragma: no cover - defensive cleanup
            pass
        raise
