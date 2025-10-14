"""Opt-in integration test for generating TTS audio and uploading to Firebase Storage."""

import os
import uuid

import pytest
from firebase_admin import storage

from auth import initialize_firebase
from config import get_openai_client
from tts_service import generate_tts_audio
from config import GCS_AUDIO_BUCKET

RUN_TTS_INTEGRATION_TEST = os.getenv("RUN_TTS_INTEGRATION_TEST") == "1"

@pytest.mark.skipif(
    not RUN_TTS_INTEGRATION_TEST,
    reason="Set RUN_TTS_INTEGRATION_TEST=1 to run tts integration tests (requires network access).",
)
def test_generate_tts_audio_upload():
    initialize_firebase()

    try:
        bucket = storage.bucket(GCS_AUDIO_BUCKET)
        if hasattr(bucket, "exists") and not bucket.exists():
            pytest.skip("Firebase Storage bucket does not exist or access is denied.")
    except Exception as exc:  # pragma: no cover - environment-specific
        pytest.skip(f"Unable to verify Firebase Storage bucket: {exc}")

    openai_client = get_openai_client()
    if not openai_client:
        pytest.skip("OpenAI client is not configured.")

    script = os.getenv("TTS_TEST_SCRIPT", "Hello from the Avra TTS integration test.")
    user_id = os.getenv("TTS_TEST_USER_ID", "integration-test-user")
    date_key = os.getenv("TTS_TEST_DATE_KEY", "1970-01-01")
    message_id = os.getenv("TTS_TEST_MESSAGE_ID", f"integration-{uuid.uuid4().hex}")

    path, audio_format = generate_tts_audio(
        script=script,
        user_id=user_id,
        date_key=date_key,
        message_id=message_id,
        openai_client=openai_client,
    )

    assert path, "Expected storage path for generated TTS audio"
    assert audio_format == "mp3"

    if os.getenv("TTS_TEST_KEEP_BLOB") != "1":
        bucket = storage.bucket(GCS_AUDIO_BUCKET)
        blob = bucket.blob(path)
        try:
            if blob.exists():
                blob.delete()
        except Exception:  # pragma: no cover - best effort cleanup
            pass
