from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version_returns_tool_versions(client):
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"service", "ocrmypdf", "tesseract", "docling"}
    for key, val in body.items():
        assert isinstance(val, str) and val, f"version key {key!r} is empty"


def test_extract_born_digital_returns_markdown(client):
    pdf = (FIXTURES / "born_digital_single.pdf").read_bytes()
    r = client.post("/extract", files={"file": ("test.pdf", pdf, "application/pdf")})
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert "UNIQUE" in r.text.replace("\\", "")
    assert r.headers.get("x-pages", "").isdigit()
    assert r.headers.get("x-processing-ms", "").isdigit()
    assert r.headers.get("x-ocr-pages", "").isdigit()


def test_extract_missing_file_returns_400(client):
    r = client.post("/extract", data={})
    assert r.status_code == 400
    body = r.json()
    assert "error" in body
    assert "detail" in body


def test_extract_non_pdf_returns_400(client):
    r = client.post("/extract", files={"file": ("doc.txt", b"hello world", "text/plain")})
    assert r.status_code == 400
    body = r.json()
    assert "error" in body


def test_extract_oversized_returns_400(client, monkeypatch):
    import pdf_extract.main as main_mod

    original = main_mod._settings
    from pdf_extract.config import Settings

    monkeypatch.setattr(main_mod, "_settings", Settings(MAX_FILE_SIZE_MB=0))
    pdf = (FIXTURES / "born_digital_single.pdf").read_bytes()
    r = client.post("/extract", files={"file": ("test.pdf", pdf, "application/pdf")})
    monkeypatch.setattr(main_mod, "_settings", original)
    assert r.status_code == 400
    assert "error" in r.json()


def test_extract_corrupt_pdf_returns_422(client):
    # Valid magic bytes but corrupt body → pipeline fails
    corrupt = b"%PDF-1.4\n" + b"X" * 100
    r = client.post("/extract", files={"file": ("bad.pdf", corrupt, "application/pdf")})
    assert r.status_code == 422
    body = r.json()
    assert "error" in body
    assert "detail" in body


def test_extract_returns_503_when_queue_full(monkeypatch):
    import asyncio

    import pdf_extract.main as main_mod
    from pdf_extract.config import Settings

    monkeypatch.setattr(
        main_mod, "_settings", Settings(MAX_CONCURRENT_JOBS=1, QUEUE_WAIT_SECONDS=0)
    )
    monkeypatch.setattr(main_mod, "_semaphore", asyncio.Semaphore(1))

    original_wait_for = asyncio.wait_for

    async def _fake_wait_for(coro, timeout=None):
        # Only intercept the semaphore acquire, not the pipeline wait_for
        if hasattr(coro, "__qualname__") and "acquire" in getattr(coro, "__qualname__", ""):
            coro.close()
            raise TimeoutError
        return await original_wait_for(coro, timeout=timeout)

    monkeypatch.setattr(asyncio, "wait_for", _fake_wait_for)

    from fastapi.testclient import TestClient

    with TestClient(main_mod.app, raise_server_exceptions=False) as c:
        pdf = (FIXTURES / "born_digital_single.pdf").read_bytes()
        r = c.post("/extract", files={"file": ("test.pdf", pdf, "application/pdf")})

    assert r.status_code == 503
    assert "error" in r.json()


def test_extract_returns_504_on_timeout(monkeypatch):
    import asyncio

    import pdf_extract.main as main_mod
    from pdf_extract.config import Settings

    monkeypatch.setattr(main_mod, "_settings", Settings(JOB_TIMEOUT_SECONDS=0))
    monkeypatch.setattr(main_mod, "_semaphore", asyncio.Semaphore(1))

    original_wait_for = asyncio.wait_for

    async def _fake_wait_for(coro, timeout=None):
        # Intercept the pipeline to_thread call (not the semaphore acquire)
        if hasattr(coro, "__qualname__") and "acquire" in getattr(coro, "__qualname__", ""):
            return await original_wait_for(coro, timeout=timeout)
        coro.close()
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", _fake_wait_for)

    from fastapi.testclient import TestClient

    with TestClient(main_mod.app, raise_server_exceptions=False) as c:
        pdf = (FIXTURES / "born_digital_single.pdf").read_bytes()
        r = c.post("/extract", files={"file": ("test.pdf", pdf, "application/pdf")})

    assert r.status_code == 504
    assert "error" in r.json()


def test_concurrent_burst_no_crashes():
    """10 simultaneous requests with MAX_CONCURRENT_JOBS=2 — all 200 or 503, no 500s."""
    import concurrent.futures

    from fastapi.testclient import TestClient

    import pdf_extract.main as main_mod
    from pdf_extract.config import Settings

    main_mod._settings = Settings(MAX_CONCURRENT_JOBS=2, QUEUE_WAIT_SECONDS=0)

    import asyncio

    main_mod._semaphore = asyncio.Semaphore(2)

    pdf = (FIXTURES / "born_digital_single.pdf").read_bytes()

    with TestClient(main_mod.app, raise_server_exceptions=False) as c:

        def _send(_):
            return c.post(
                "/extract", files={"file": ("test.pdf", pdf, "application/pdf")}
            ).status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            codes = list(pool.map(_send, range(10)))

    main_mod._settings = None
    main_mod._semaphore = None

    assert all(code in (200, 503) for code in codes), f"unexpected codes: {codes}"
    assert 500 not in codes
