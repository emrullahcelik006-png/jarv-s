import pytest
from unittest.mock import patch, MagicMock
from tools.process_manager import ProcessKillTool


@pytest.mark.asyncio
async def test_process_kill_reports_failure_when_taskkill_fails():
    """
    Milestone 4 regresyon testi: taskkill basarisiz donerse (returncode != 0),
    arac bunu success=False olarak raporlamali, 'basariyla kapatildi' YALANINI
    soylememeli.
    """
    fake_process = MagicMock()
    fake_process.info = {"pid": 1234, "name": "notepad.exe"}

    with patch("tools.process_manager.psutil.process_iter", return_value=[fake_process]):
        with patch("tools.process_manager.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "ERROR: Access is denied."

            tool = ProcessKillTool()
            res = await tool.execute(target="notepad")

            assert res.success is False
            assert "sonlandırılamadı" in res.error.lower() or "access is denied" in res.error.lower()


@pytest.mark.asyncio
async def test_process_kill_reports_success_when_taskkill_succeeds():
    """taskkill basarili donerse (returncode=0), success=True olmali."""
    fake_process = MagicMock()
    fake_process.info = {"pid": 1234, "name": "notepad.exe"}

    with patch("tools.process_manager.psutil.process_iter", return_value=[fake_process]):
        with patch("tools.process_manager.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "SUCCESS"
            mock_run.return_value.stderr = ""

            tool = ProcessKillTool()
            res = await tool.execute(target="notepad")

            assert res.success is True
