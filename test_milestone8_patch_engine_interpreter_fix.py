import inspect
from tools.patch_engine import AutonomousPatchTool


def test_patch_engine_uses_sys_executable_not_py_launcher():
    """
    Milestone 8 regresyon testi: AutonomousPatchTool, test calistirmak icin
    'py' launcher yerine sys.executable kullanmali. 'py' launcher, aktif
    venv disinda farkli bir Python'a gidebilir ve bagimliliklari eksik
    bir ortamda calisirsa gecerli bir yamayi bile yanlislikla geri alabilir.

    NOT: Bu test, yorumlari degil GERCEK subprocess cagri pattern'ini kontrol
    eder (ilk duzenlemede naif bir substring kontrolu yorumla cakisip
    false positive uretmisti - bu versiyon o hatayi duzeltir).
    """
    source = inspect.getsource(AutonomousPatchTool.execute)

    # Gercek subprocess.run cagrisinin komut listesini kontrol et:
    # Eski (bug'li) hali: ["py", "-m", "pytest", "-v"]
    # Yeni (duzeltilmis) hali: [sys.executable, "-m", "pytest", "-v"]
    assert '["py", "-m", "pytest"' not in source, \
        "Gercek subprocess cagrisi hala 'py' launcher kullaniyor"
    assert "[sys.executable, \"-m\", \"pytest\"" in source, \
        "Gercek subprocess cagrisi sys.executable kullanmiyor"
