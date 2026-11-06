import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from services.audio_service import AudioService


@pytest.mark.asyncio
async def test_audio_tts_generation():
    output_file = "storage/test_audio.mp3"
    target_path = Path(output_file).resolve()
    
    # Fast Hermetic Mock for Edge TTS save to ensure zero-network latency in unit tests
    async def mock_save(path_str):
        p = Path(path_str)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"ID3_HERMETIC_MOCK_AUDIO_DATA_321")

    with patch("edge_tts.Communicate.save", side_effect=mock_save):
        output = await AudioService.text_to_speech(
            text="JARVIS ses testi basarili.",
            output_file=output_file
        )
        assert Path(output).exists()
        assert Path(output).stat().st_size > 0
