import asyncio
import importlib.metadata
import subprocess
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse, Response

from pdf_extract import __version__
from pdf_extract.config import Settings, get_settings
from pdf_extract.logging import configure_logging, log_extract
from pdf_extract.pipeline import PipelineError, extract_pdf


def _tesseract_version() -> str:
    try:
        out = subprocess.check_output(
            ["tesseract", "--version"], stderr=subprocess.STDOUT, text=True
        )
        return out.splitlines()[0].replace("tesseract", "").strip()
    except Exception:
        return "unknown"


_TESSERACT_VERSION = _tesseract_version()

_semaphore: asyncio.Semaphore | None = None
_settings: Settings | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _semaphore, _settings
    _settings = get_settings()
    configure_logging(_settings.LOG_LEVEL)
    _semaphore = asyncio.Semaphore(_settings.MAX_CONCURRENT_JOBS)
    yield


app = FastAPI(title="pdf-extract-service", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"error": str(exc.status_code), "detail": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/extract":
        return JSONResponse(
            status_code=400,
            content={"error": "Bad Request", "detail": str(exc)},
        )
    return JSONResponse(status_code=422, content={"error": "Validation error", "detail": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {
        "service": __version__,
        "ocrmypdf": importlib.metadata.version("ocrmypdf"),
        "tesseract": _TESSERACT_VERSION,
        "docling": importlib.metadata.version("docling"),
    }


@app.post("/extract")
async def extract(file: UploadFile):
    settings = _settings or get_settings()
    semaphore = _semaphore

    # --- validation ---
    if not file.filename:
        raise HTTPException(400, detail={"error": "Bad Request", "detail": "No file provided"})

    raw = await file.read()
    input_size = len(raw)

    if input_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            400,
            detail={
                "error": "Bad Request",
                "detail": f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit",
            },
        )

    if not raw[:5] == b"%PDF-":
        raise HTTPException(400, detail={"error": "Bad Request", "detail": "File is not a PDF"})

    # --- write to temp ---
    with tempfile.NamedTemporaryFile(suffix=".pdf", dir=settings.TEMP_DIR, delete=False) as tmp:
        tmp.write(raw)
        input_path = Path(tmp.name)

    start_ms = int(time.monotonic() * 1000)

    try:
        # --- acquire semaphore ---
        if semaphore is not None:
            try:
                await asyncio.wait_for(semaphore.acquire(), timeout=settings.QUEUE_WAIT_SECONDS)
            except TimeoutError:
                raise HTTPException(
                    503,
                    detail={"error": "Service Unavailable", "detail": "Concurrency limit reached"},
                ) from None

        try:
            # --- run pipeline ---
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(extract_pdf, input_path, settings=settings),
                    timeout=settings.JOB_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                raise HTTPException(
                    504,
                    detail={"error": "Gateway Timeout", "detail": "Processing exceeded timeout"},
                ) from None
            except PipelineError as exc:
                raise HTTPException(
                    422, detail={"error": "Unprocessable Entity", "detail": str(exc)}
                ) from exc
        finally:
            if semaphore is not None:
                semaphore.release()
    finally:
        input_path.unlink(missing_ok=True)

    duration_ms = int(time.monotonic() * 1000) - start_ms
    log_extract(
        duration_ms=duration_ms,
        pages=result.pages,
        ocr_pages=result.ocr_pages,
        status=200,
        input_size_bytes=input_size,
    )

    return Response(
        content=result.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "X-Pages": str(result.pages),
            "X-Processing-Ms": str(duration_ms),
            "X-OCR-Pages": str(result.ocr_pages),
        },
    )
