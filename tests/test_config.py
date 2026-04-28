import os


def test_settings_defaults():
    from pdf_extract.config import Settings

    s = Settings()
    assert s.MAX_CONCURRENT_JOBS == 2
    assert s.MAX_FILE_SIZE_MB == 50
    assert s.JOB_TIMEOUT_SECONDS == 300
    assert s.QUEUE_WAIT_SECONDS == 30
    assert s.OCR_LANGUAGES == "eng"
    assert s.LOG_LEVEL == "INFO"
    assert s.TEMP_DIR == "/tmp"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("MAX_CONCURRENT_JOBS", "5")
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "100")
    monkeypatch.setenv("JOB_TIMEOUT_SECONDS", "600")

    # Re-import to pick up env changes
    import importlib

    import pdf_extract.config as cfg_module

    importlib.reload(cfg_module)
    s = cfg_module.Settings()
    assert s.MAX_CONCURRENT_JOBS == 5
    assert s.MAX_FILE_SIZE_MB == 100
    assert s.JOB_TIMEOUT_SECONDS == 600


def test_ocrmypdf_jobs_defaults_to_cpu_count():

    from pdf_extract.config import Settings

    s = Settings()
    assert os.cpu_count() == s.OCRMYPDF_JOBS
