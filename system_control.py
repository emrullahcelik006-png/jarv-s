import asyncio
import pyautogui
from typing import Optional, Union
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("SystemControlTools")


def _set_vol_sync(target_percent: int) -> bool:
    try:
        import comtypes
        from pycaw.pycaw import AudioUtilities
        comtypes.CoInitialize()
        try:
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            scalar_val = max(0.0, min(1.0, target_percent / 100.0))
            volume.SetMasterVolumeLevelScalar(scalar_val, None)
            return True
        finally:
            comtypes.CoUninitialize()
    except Exception as e:
        logger.error(f"pycaw set volume error: {e}")
        return False


def _get_vol_sync() -> Optional[int]:
    try:
        import comtypes
        from pycaw.pycaw import AudioUtilities
        comtypes.CoInitialize()
        try:
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            return int(round(volume.GetMasterVolumeLevelScalar() * 100))
        finally:
            comtypes.CoUninitialize()
    except Exception as e:
        logger.error(f"pycaw get volume error: {e}")
        return None


class SystemHardwareControlTool(BaseTool):
    name = "system_hardware_control"
    description = "Bilgisayarin sesini (%0-%100 mutlak seviye), ekran parlakligini (DDC/CI) ve medyasini yonetir."
    risk_level = RiskLevel.LOW

    async def execute(self, action: str = "volume_up", value: Union[int, str] = 10, **kwargs) -> ToolResult:
        try:
            act = str(action).lower().strip()
            
            # Safe integer conversion for value
            try:
                val = int(value)
            except (ValueError, TypeError):
                val = 10

            # 1. SES KONTROLLERI
            if act in ("volume_up", "ses_yukselt", "sesi_ac", "ses_arttir"):
                current_vol = await asyncio.to_thread(_get_vol_sync)
                if current_vol is not None:
                    new_vol = min(100, current_vol + val)
                    await asyncio.to_thread(_set_vol_sync, new_vol)
                    return ToolResult(success=True, output=f"🔊 **[DONANIM SENSÖRÜ]**: Ses seviyesi %{current_vol} konumundan %{new_vol} seviyesine yükseltildi.")
                else:
                    steps = max(1, min(50, val // 2))
                    for _ in range(steps):
                        pyautogui.press("volumeup")
                    return ToolResult(success=True, output=f"🔊 **[DONANIM SENSÖRÜ]**: Ses seviyesi {val} birim yükseltildi (Tuş simülasyonu).")

            elif act in ("volume_down", "ses_kis", "sesi_azalt"):
                current_vol = await asyncio.to_thread(_get_vol_sync)
                if current_vol is not None:
                    new_vol = max(0, current_vol - val)
                    await asyncio.to_thread(_set_vol_sync, new_vol)
                    return ToolResult(success=True, output=f"🔉 **[DONANIM SENSÖRÜ]**: Ses seviyesi %{current_vol} konumundan %{new_vol} seviyesine düşürüldü.")
                else:
                    steps = max(1, min(50, val // 2))
                    for _ in range(steps):
                        pyautogui.press("volumedown")
                    return ToolResult(success=True, output=f"🔉 **[DONANIM SENSÖRÜ]**: Ses seviyesi {val} birim düşürüldü (Tuş simülasyonu).")

            elif act in ("volume_set", "ses_ayarla", "sesi_sabitle"):
                target_v = max(0, min(100, val))
                ok = await asyncio.to_thread(_set_vol_sync, target_v)
                if ok:
                    return ToolResult(success=True, output=f"🔊 **[DONANIM SENSÖRÜ]**: Ses seviyesi %{target_v} olarak sabitlendi.")
                return ToolResult(success=False, output=None, error="Ses seviyesi pycaw ile ayarlanamadi.")

            elif act in ("volume_mute", "sesi_kapat", "sessiz", "komple_kapat", "0_yap"):
                ok = await asyncio.to_thread(_set_vol_sync, 0)
                if ok:
                    return ToolResult(success=True, output="🔇 **[DONANIM SENSÖRÜ]**: Ses seviyesi %0 (Sessiz) yapıldı.")
                pyautogui.press("volumemute")
                return ToolResult(success=True, output="🔇 **[DONANIM SENSÖRÜ]**: Ses Mute/Unmute yapıldı.")

            elif act in ("brightness_set", "parlaklik_ayarla", "parlaklik_arttir", "parlaklik_azalt"):
                target_b = max(0, min(100, val))
                try:
                    import screen_brightness_control as sbc
                    sbc.set_brightness(target_b)
                    return ToolResult(success=True, output=f"☀️ **[DONANIM SENSÖRÜ]**: Ekran parlaklığı %{target_b} seviyesine ayarlandı.")
                except Exception as ex:
                    logger.warning(f"sbc parlaklik hatasi: {ex}")
                return ToolResult(success=False, output=None, error="Ekran parlaklığı değiştirilemedi.")

            elif act in ("media_play_pause", "durdur", "oynat"):
                pyautogui.press("playpause")
                return ToolResult(success=True, output="⏯️ **[MEDYA SENSÖRÜ]**: Medya Oynat/Durdur tetiklendi.")

            return ToolResult(success=False, output=None, error=f"Bilinmeyen donanim eylemi: {action}")

        except Exception as e:
            logger.error(f"Hardware control hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
