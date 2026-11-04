"""Generate deterministic, repository-owned PDF evaluation fixtures."""

import argparse
import tempfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

FIXTURE_NAMES = ("atlas-narrative.pdf", "retrieval-table.pdf", "queue-chart.pdf")


def _canvas(path: Path, title: str) -> Canvas:
    canvas = Canvas(
        str(path),
        pagesize=letter,
        pageCompression=0,
        invariant=1,
    )
    canvas.setTitle(title)
    canvas.setAuthor("EvidenceRAG contributors")
    canvas.setCreator("EvidenceRAG deterministic fixture generator")
    return canvas


def generate_atlas(path: Path) -> None:
    """Create a narrative fact plus a simple original process diagram."""
    canvas = _canvas(path, "Atlas Sensor Note")
    width, height = letter
    canvas.setFillColor(colors.HexColor("#17324D"))
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(54, height - 68, "Atlas Sensor Note")
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica", 11)
    canvas.drawString(54, height - 104, "The Atlas sensor samples at 20 hertz during calibration.")
    canvas.drawString(54, height - 122, "Each sample passes through a filter before archival.")

    labels = ((70, "Sensor"), (250, "Filter"), (430, "Archive"))
    y = height - 250
    for x, label in labels:
        canvas.setFillColor(colors.HexColor("#EAF2F8"))
        canvas.roundRect(x, y, 110, 48, 6, fill=1, stroke=1)
        canvas.setFillColor(colors.HexColor("#17324D"))
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawCentredString(x + 55, y + 18, label)
    canvas.setStrokeColor(colors.HexColor("#557A95"))
    canvas.setLineWidth(2)
    for x0, x1 in ((180, 250), (360, 430)):
        canvas.line(x0, y + 24, x1 - 8, y + 24)
        canvas.line(x1 - 16, y + 30, x1 - 8, y + 24)
        canvas.line(x1 - 16, y + 18, x1 - 8, y + 24)
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Oblique", 10)
    canvas.drawString(70, y - 24, "Figure 1. Calibration data flow: Sensor -> Filter -> Archive.")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 54, 36, "Repository-owned evaluation fixture | Page 1")
    canvas.save()


def generate_table(path: Path) -> None:
    """Create an original, human-verifiable retrieval-results table."""
    canvas = _canvas(path, "Retrieval Baseline Fixture")
    width, height = letter
    canvas.setFillColor(colors.HexColor("#17324D"))
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(54, height - 68, "Retrieval Baseline Fixture")
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica", 11)
    canvas.drawString(
        54,
        height - 104,
        "Table 1 contains synthetic values created only for schema testing.",
    )

    x0, y_top = 72, height - 160
    widths = (160, 100, 100, 100)
    row_height = 34
    rows = (
        ("Method", "Precision", "Recall", "F1"),
        ("Lexical", "0.78", "0.72", "0.75"),
        ("Dense", "0.82", "0.80", "0.81"),
        ("Hybrid", "0.88", "0.84", "0.86"),
    )
    for row_index, row in enumerate(rows):
        y = y_top - (row_index + 1) * row_height
        canvas.setFillColor(colors.HexColor("#DCEAF4") if row_index == 0 else colors.white)
        canvas.rect(x0, y, sum(widths), row_height, fill=1, stroke=1)
        x = x0
        for column_index, (value, cell_width) in enumerate(zip(row, widths, strict=True)):
            if column_index:
                canvas.line(x, y, x, y + row_height)
            canvas.setFillColor(colors.HexColor("#17324D") if row_index == 0 else colors.black)
            canvas.setFont("Helvetica-Bold" if row_index == 0 else "Helvetica", 10)
            canvas.drawCentredString(x + cell_width / 2, y + 12, value)
            x += cell_width
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Oblique", 10)
    canvas.drawString(
        72,
        y_top - len(rows) * row_height - 24,
        "Table 1. Synthetic retrieval metrics.",
    )
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 54, 36, "Repository-owned evaluation fixture | Page 1")
    canvas.save()


def generate_chart(path: Path) -> None:
    """Create a technical chart whose bar heights are absent from extracted text."""
    canvas = _canvas(path, "Queue Scheduling Note")
    width, height = letter
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(54, height - 68, "Queue Scheduling Note")
    canvas.setFont("Helvetica", 11)
    canvas.drawString(54, height - 104, "Experiment QS-17 compares three scheduler modes.")
    canvas.drawString(
        54, height - 122, "Each run processed 500 synthetic requests at concurrency 8."
    )
    canvas.drawString(54, height - 140, "The timeout budget was 250 ms per request.")
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(72, height - 190, "Median queue wait (ms)")
    x0, y0 = 110, 310
    canvas.line(x0, y0, x0, y0 + 240)
    canvas.line(x0, y0, x0 + 400, y0)
    for tick, value in enumerate((0, 20, 40, 60, 80)):
        y = y0 + tick * 55
        canvas.line(x0 - 4, y, x0, y)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(x0 - 10, y - 3, str(value))
    for x, label, units, color in (
        (155, "FIFO", 66, "#426990"),
        (275, "Priority", 37, "#6C8E5D"),
        (395, "Fair", 49, "#B07A43"),
    ):
        canvas.setFillColor(colors.HexColor(color))
        canvas.rect(x, y0, 60, units * 2.75, fill=1, stroke=0)
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica", 10)
        canvas.drawCentredString(x + 30, y0 - 18, label)
    canvas.setFont("Helvetica-Oblique", 10)
    canvas.drawString(72, y0 - 50, "Figure 1. Median queue wait by scheduler mode.")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 54, 36, "Repository-owned evaluation fixture | Page 1")
    canvas.save()


def generate_all(output_dir: Path) -> None:
    """Generate every fixture into an existing or new directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generate_atlas(output_dir / FIXTURE_NAMES[0])
    generate_table(output_dir / FIXTURE_NAMES[1])
    generate_chart(output_dir / FIXTURE_NAMES[2])


def check_committed(output_dir: Path) -> bool:
    """Return whether regenerated bytes equal every committed fixture."""
    with tempfile.TemporaryDirectory(prefix="evidencerag-fixtures-") as directory:
        generated = Path(directory)
        generate_all(generated)
        return all(
            (generated / name).read_bytes() == (output_dir / name).read_bytes()
            for name in FIXTURE_NAMES
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets/fixtures"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        if not check_committed(args.output_dir):
            parser.error("committed fixtures differ from deterministic regeneration")
        print("committed fixtures are deterministic")
    else:
        generate_all(args.output_dir)
        print(f"generated {len(FIXTURE_NAMES)} fixtures in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
