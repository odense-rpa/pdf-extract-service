# pdf-extract-service

Self-hosted HTTP service that accepts a PDF and returns extracted text as markdown. Uses OCRmyPDF + Tesseract for OCR normalization and Docling for text extraction.

## Quick start

```bash
docker compose up --build
```

Then:

```bash
# Extract text from a PDF
curl -sS -F file=@your-contract.pdf http://localhost:8000/extract

# Health check
curl http://localhost:8000/health

# Tool versions
curl http://localhost:8000/version
```

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/extract` | Upload PDF, receive markdown |
| GET | `/health` | Liveness probe |
| GET | `/version` | Service + tool versions |

### POST /extract

- Body: `multipart/form-data` with field `file` (PDF)
- Response: `200 text/markdown` with headers `X-Pages`, `X-Processing-Ms`, `X-OCR-Pages`
- Errors: `400` (bad input), `422` (pipeline failure), `503` (busy), `504` (timeout)

Error body: `{"error": "...", "detail": "..."}`

## Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAX_CONCURRENT_JOBS` | `2` | Max parallel pipelines |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit |
| `JOB_TIMEOUT_SECONDS` | `300` | Per-request hard timeout |
| `QUEUE_WAIT_SECONDS` | `30` | Max wait for a free slot |
| `OCR_LANGUAGES` | `eng` | Tesseract language codes |
| `OCRMYPDF_JOBS` | `<cpu_count>` | Parallel pages within OCRmyPDF |
| `LOG_LEVEL` | `INFO` | Python log level |
| `TEMP_DIR` | `/tmp` | Intermediate file directory |

## Development

```bash
uv sync
uv run pytest
uv run ruff format .
uv run ruff check --fix .
uv run uvicorn pdf_extract.main:app --reload
```
