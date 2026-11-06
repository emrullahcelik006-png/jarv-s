import pytest
from pathlib import Path
from services.audio_service import AudioService
from tools.system import NetworkPortHealthTool
from tools.mouse_control import MouseControlTool
from core.policy import SecurityPolicyEngine
from tasks.models import RiskLevel


@pytest.mark.asyncio
async def test_offline_tts_fallback_handling():
    """Internet olmasa dahi ses sentezlemenin dosya uretebildigini test eder."""
    output_p = "storage/test_offline_audio.mp3"
    result_path = await AudioService.text_to_speech(text="Yerel ses motoru testi.", output_file=output_p)
    assert Path(result_path).exists()
    assert Path(result_path).stat().st_size > 0


@pytest.mark.asyncio
async def test_network_port_health_offline_detection():
    """Soket seviyesinde yerel port durumlarini zaman asamimsiz test eder."""
    tool = NetworkPortHealthTool()
    res = await tool.execute(port=11434)
    assert res.success is True
    assert "Port 11434" in res.output


@pytest.mark.asyncio
async def test_mouse_control_2d_directional_scroll():
    """Fare aracinin sag/sol/yukari/asagi 2D kaydirma mantigini test eder."""
    tool = MouseControlTool()
    res_right = await tool.execute(action="scroll", direction="right", amount=200)
    assert res_right.success is True
    assert "SAYFA KAYDIRILDI" in res_right.output

    res_up = await tool.execute(action="scroll", direction="up", amount=200)
    assert res_up.success is True
    assert "SAYFA KAYDIRILDI" in res_up.output


def test_security_policy_canonical_alias_enforcement():
    """Takma adlarin (alias) güvenlik politikasinda kanonik isme donusturulup engellendigini test eder."""
    risk_alias, app_alias = SecurityPolicyEngine.evaluate_risk("write_file", {"file_path": "test.txt"})
    risk_canon, app_canon = SecurityPolicyEngine.evaluate_risk("file_write", {"file_path": "test.txt"})
    assert risk_alias == risk_canon == RiskLevel.HIGH
    assert app_alias == app_canon is True
