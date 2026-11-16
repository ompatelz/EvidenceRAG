"""Owned, in-memory preflight fixture. It is outside all benchmark splits."""

import pymupdf


def test_same_caption_and_page_can_require_different_answers() -> None:
    captions: list[str] = []
    observed_winners: list[str] = []
    for left_height, right_height in [(55, 30), (30, 55)]:
        with pymupdf.open() as pdf:  # type: ignore[no-untyped-call]
            page = pdf.new_page(width=160, height=120)
            page.insert_text((10, 16), "Wait time by mode", fontsize=10)
            page.insert_text((34, 108), "A", fontsize=10)
            page.insert_text((104, 108), "B", fontsize=10)
            for x, height in [(30, left_height), (100, right_height)]:
                page.draw_rect(
                    (x, 90 - height, x + 12, 90),
                    color=None,
                    fill=(0, 0, 0),
                )
            captions.append(page.get_text())
            pixels = page.get_pixmap(colorspace=pymupdf.csRGB, alpha=False)
            counts = [
                sum(pixels.pixel(x, y) == (0, 0, 0) for y in range(25, 90)) for x in (36, 106)
            ]
            observed_winners.append("A" if counts[0] > counts[1] else "B")

    assert captions == ["Wait time by mode\nA\nB\n"] * 2
    assert observed_winners == ["A", "B"]
