import httpx
from typing import Dict, Any
from core.config import get_settings
from core.logger import setup_logger

logger = setup_logger("WeatherService")
settings = get_settings()


class WeatherService:
    @staticmethod
    async def get_current_weather(city: str = None) -> Dict[str, Any]:
        target_city = city or settings.JARVIS_CITY or "Istanbul"
        try:
            # Open-Meteo ucretsiz ve hizli canlı hava durumu servisi (Istanbul lat: 41.0082, lon: 28.9784)
            url = "https://api.open-meteo.com/v1/forecast?latitude=41.0082&longitude=28.9784&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json().get("current", {})
                    return {
                        "city": target_city.upper(),
                        "temp_c": round(data.get("temperature_2m", 21.0)),
                        "humidity": data.get("relative_humidity_2m", 60),
                        "wind_kmh": round(data.get("wind_speed_10m", 12.0)),
                        "status": "ONLINE"
                    }
        except Exception as e:
            logger.warning(f"Hava durumu baglanti hatasi ({e}), varsayilan veriler yuklendi.")

        return {
            "city": target_city.upper(),
            "temp_c": 21,
            "humidity": 65,
            "wind_kmh": 15,
            "status": "OFFLINE_FALLBACK"
        }
