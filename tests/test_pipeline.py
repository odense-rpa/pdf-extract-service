from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings():
    from pdf_extract.config import Settings

    return Settings()


def _plain(markdown: str) -> str:
    """Strip markdown backslash escapes for token matching."""
    return markdown.replace("\\", "")


def test_born_digital_single_extracts_text(settings):
    from pdf_extract.pipeline import extract_pdf

    result = extract_pdf(FIXTURES / "born_digital_single.pdf", settings=settings)
    assert "UNIQUE_TOKEN_BORN_DIGITAL_SINGLE" in _plain(result.markdown)
    assert result.pages == 1
    assert result.ocr_pages == 0


def test_born_digital_multi_extracts_all_pages(settings):
    from pdf_extract.pipeline import extract_pdf

    result = extract_pdf(FIXTURES / "born_digital_multi.pdf", settings=settings)
    plain = _plain(result.markdown)
    for i in range(1, 4):
        assert f"UNIQUE_TOKEN_PAGE_{i}" in plain
    assert result.pages == 3
    assert result.ocr_pages == 0


def test_corrupt_pdf_raises_pipeline_error(settings, tmp_path):
    from pdf_extract.pipeline import PipelineError, extract_pdf

    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"not a pdf at all")
    with pytest.raises(PipelineError):
        extract_pdf(corrupt, settings=settings)
