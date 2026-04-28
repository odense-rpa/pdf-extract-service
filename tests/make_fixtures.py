"""Script to generate synthetic test fixtures. Run once: uv run python tests/make_fixtures.py"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_born_digital_single(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawString(72, 750, "CONTRACT FIXTURE SINGLE PAGE")
    c.drawString(72, 720, "This agreement is between Alpha Corp and Beta Ltd.")
    c.drawString(72, 700, "UNIQUE_TOKEN_BORN_DIGITAL_SINGLE")
    c.save()


def make_born_digital_multi(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for i in range(1, 4):
        c.drawString(72, 750, f"CONTRACT PAGE {i}")
        c.drawString(72, 720, f"UNIQUE_TOKEN_PAGE_{i}")
        c.showPage()
    c.save()


def make_corrupt(path: Path) -> None:
    # Valid magic bytes but corrupt body
    path.write_bytes(b"%PDF-1.4\n%%garbage data that is not a valid pdf")


if __name__ == "__main__":
    fixtures = Path(__file__).parent / "fixtures"
    fixtures.mkdir(exist_ok=True)
    make_born_digital_single(fixtures / "born_digital_single.pdf")
    make_born_digital_multi(fixtures / "born_digital_multi.pdf")
    make_corrupt(fixtures / "corrupt.pdf")
    print("Fixtures written to", fixtures)
