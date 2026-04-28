import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import ocrmypdf
import pypdf
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from pdf_extract.config import Settings


class PipelineError(Exception):
    pass


@dataclass
class ExtractResult:
    markdown: str
    pages: int
    ocr_pages: int


def _count_text_pages(pdf_path: Path) -> int:
    """Count pages that already have a text layer."""
    reader = pypdf.PdfReader(str(pdf_path))
    count = 0
    for page in reader.pages:
        if page.extract_text().strip():
            count += 1
    return count


def extract_pdf(input_path: Path, *, settings: Settings) -> ExtractResult:
    try:
        reader = pypdf.PdfReader(str(input_path))
        total_pages = len(reader.pages)
    except Exception as exc:
        raise PipelineError(f"could not read PDF: {exc}") from exc
    text_pages_before = _count_text_pages(input_path)

    with tempfile.NamedTemporaryFile(suffix=".pdf", dir=settings.TEMP_DIR, delete=False) as tmp:
        intermediate = Path(tmp.name)

    try:
        exit_code = ocrmypdf.ocr(
            str(input_path),
            str(intermediate),
            skip_text=True,
            deskew=True,
            rotate_pages=True,
            rotate_pages_threshold=5,
            optimize=0,
            output_type="pdf",
            jobs=settings.OCRMYPDF_JOBS,
            language=settings.OCR_LANGUAGES,
            progress_bar=False,
        )
        # exit_code 6 = already has text, treated as success
        if exit_code != 0 and exit_code != ocrmypdf.ExitCode.already_done_ocr:
            raise PipelineError(f"ocrmypdf exited with code {exit_code}")
    except ocrmypdf.exceptions.PriorOcrFoundError:
        shutil.copy2(input_path, intermediate)
    except ocrmypdf.exceptions.InputFileError as exc:
        raise PipelineError(f"ocrmypdf input error: {exc}") from exc
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(f"ocrmypdf failed: {exc}") from exc

    ocr_pages = total_pages - text_pages_before

    try:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
        conv_result = converter.convert(str(intermediate))
        markdown = conv_result.document.export_to_markdown()
    except Exception as exc:
        raise PipelineError(f"docling failed: {exc}") from exc
    finally:
        intermediate.unlink(missing_ok=True)

    return ExtractResult(markdown=markdown, pages=total_pages, ocr_pages=ocr_pages)
