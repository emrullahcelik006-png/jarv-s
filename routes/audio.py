from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from services.audio_service import AudioService

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])


class TTSRequest(BaseModel):
    text: str
    voice: str = "tr-TR-AhmetNeural"


@router.post("/tts")
async def generate_speech(request: TTSRequest):
    try:
        audio_file = await AudioService.text_to_speech(text=request.text, voice=request.voice)
        return FileResponse(audio_file, media_type="audio/mpeg", filename="jarvis_response.mp3")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
