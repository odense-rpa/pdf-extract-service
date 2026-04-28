# pdf-extract-service

Self-hosted HTTP service that converts PDFs to markdown. Handles born-digital and scanned PDFs via the same endpoint. Intended for backend RPA pipelines where downstream consumers (regex, LLMs) do further processing.

**Pipeline:** OCRmyPDF (Tesseract) → Docling → markdown

## Quick start

```bash
docker compose up --build
```

## Usage

### curl

```bash
curl -F file=@contract.pdf http://localhost:9431/extract
```

### httpx (Python)

```python
import httpx

with open("contract.pdf", "rb") as f:
    r = httpx.post(
        "http://localhost:9431/extract",
        files={"file": ("contract.pdf", f, "application/pdf")},
    )

r.raise_for_status()
markdown = r.text
pages = int(r.headers["x-pages"])
ocr_pages = int(r.headers["x-ocr-pages"])
processing_ms = int(r.headers["x-processing-ms"])
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/extract` | Upload PDF, receive markdown |
| `GET` | `/health` | Liveness probe — `{"status": "ok"}` |
| `GET` | `/version` | Service and tool versions |

### POST /extract

- **Request:** `multipart/form-data`, field `file` (PDF)
- **Response:** `200 text/markdown; charset=utf-8`
- **Headers:** `X-Pages`, `X-OCR-Pages`, `X-Processing-Ms`
- **Errors:** `400` bad input · `422` pipeline failure · `503` busy · `504` timeout

Error body: `{"error": "...", "detail": "..."}`

## Configuration

All via environment variables. Defaults are conservative for a 4 vCPU / 8 GB container.

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONCURRENT_JOBS` | `2` | Max parallel pipelines |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit |
| `JOB_TIMEOUT_SECONDS` | `300` | Per-request hard timeout |
| `QUEUE_WAIT_SECONDS` | `30` | Max wait for a free slot before 503 |
| `OCR_LANGUAGES` | `eng` | Tesseract language codes (e.g. `eng+dan`) |
| `OCRMYPDF_JOBS` | `<cpu_count>` | Page-level parallelism within OCRmyPDF |
| `LOG_LEVEL` | `INFO` | Python log level |
| `TEMP_DIR` | `/tmp` | Intermediate file directory |

## Development

```bash
uv sync
uv run pytest
uv run ruff format . && uv run ruff check --fix .
uv run uvicorn pdf_extract.main:app --reload
```

## License

MIT
