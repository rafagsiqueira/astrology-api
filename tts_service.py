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



import wave
import io
from google.genai import types

def generate_tts_audio(
    *,
    script: str,
    user_id: str,
    date_key: str,
    message_id: str,
    gemini_client,
) -> Tuple[str, str]:
    """Generate TTS audio via Gemini and upload it directly to Firebase Storage.

    Returns:
        Tuple[path, audio_format]
    """
    if not script or not script.strip():
        raise ValueError("TTS script must be non-empty")

    # Use .wav extension as Gemini returns raw audio which we wrap in WAV container
    blob, blob_name = create_audio_blob(
        user_id=user_id,
        date_key=date_key,
        message_id=message_id,
        extension="wav",
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
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=script,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name='Kore',
                        )
                    )
                ),
            )
        )
        
        # Audio data from Gemini
        if not response.candidates or not response.candidates[0].content.parts:
             raise RuntimeError("Gemini TTS returned no content")
             
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        
        # Prepare in-memory WAV file
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(24000) # 24kHz
            wf.writeframes(audio_data)
            
        wav_data = wav_buffer.getvalue()

        if not wav_data:
             raise RuntimeError("Generated WAV data is empty")

        blob.upload_from_string(wav_data, content_type="audio/wav")

        token = uuid.uuid4().hex
        blob.metadata = {"firebaseStorageDownloadTokens": token}
        blob.patch()

        return blob_name, "wav"
    except Exception:
        try:
            blob.delete()
        except Exception:  # pragma: no cover - defensive cleanup
            pass
        raise
