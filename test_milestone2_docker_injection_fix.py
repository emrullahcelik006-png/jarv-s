import pytest
from unittest.mock import patch
from tools.docker_control import DockerControlTool


@pytest.mark.asyncio
async def test_docker_control_rejects_injection_attempt():
    """
    Milestone 2 guvenlik regresyon testi:
    container_name icine shell metakarakteri (&, ;, |) enjekte edilmeye
    calisilirsa, arac bunu calistirmadan REDDETMELI.

    shutil.which('docker') mock'lanir cunku bu testin amaci guvenlik
    validasyon katmanini test etmektir, makinede gercek Docker kurulu
    olup olmamasindan bagimsiz olmalidir.
    """
    with patch("tools.docker_control.shutil.which", return_value="C:\\fake\\docker.exe"):
        tool = DockerControlTool()
        malicious_name = "x & echo INJECTED > injected.txt"
        res = await tool.execute(action="logs", container_name=malicious_name)

        assert res.success is False
        assert "Geçersiz container adı" in res.error


@pytest.mark.asyncio
async def test_docker_control_accepts_valid_container_name():
    """Gecerli bir container adi, guvenlik kontrolunden hatasiz gecmeli."""
    with patch("tools.docker_control.shutil.which", return_value="C:\\fake\\docker.exe"):
        with patch("tools.docker_control.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "fake log output"
            mock_run.return_value.stderr = ""

            tool = DockerControlTool()
            res = await tool.execute(action="logs", container_name="jarvis_app_1")

            assert res.success is True
            # Komutun liste formatinda (shell=False) cagrildigini dogrula
            called_args, called_kwargs = mock_run.call_args
            assert called_kwargs.get("shell") is False
            assert isinstance(called_args[0], list)
            assert "jarvis_app_1" in called_args[0]


@pytest.mark.asyncio
async def test_docker_control_no_docker_installed_returns_gracefully():
    """Docker kurulu degilse, hata firlatmadan bilgilendirici mesaj donmeli."""
    with patch("tools.docker_control.shutil.which", return_value=None):
        tool = DockerControlTool()
        res = await tool.execute(action="ps")
        assert res.success is True
        assert "Docker" in res.output
