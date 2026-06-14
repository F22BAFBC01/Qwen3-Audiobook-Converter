#!/usr/bin/env python3
"""Smoke tests for pause-aware audiobook text chunking."""

from pathlib import Path

from book_text import (
    PAUSE_MAJOR_MS,
    PAUSE_PARAGRAPH_MS,
    PAUSE_SECTION_MS,
    blocks_to_text,
    merge_continuation_blocks,
    parse_text_blocks,
    split_block_into_chunks,
    split_into_audiobook_sections,
    split_into_tts_chunks,
)


def test_blank_line_pauses():
    text = "First paragraph.\n\nSecond paragraph.\n\n\nSection heading.\n\n\n\nChapter title.\n\nBody."
    blocks = parse_text_blocks(text)
    assert blocks[0] == ("First paragraph.", 0)
    assert blocks[1][1] == PAUSE_PARAGRAPH_MS
    assert blocks[2][1] == PAUSE_SECTION_MS
    assert blocks[3][1] == PAUSE_MAJOR_MS


def test_formatted_audiobook_sample():
    sample = Path(__file__).resolve().parent.parent / (
        "Set Boundaries, Find Peace - Nedra Glover Tawwab (audiobook).txt"
    )
    if not sample.exists():
        print(f"SKIP: sample not found at {sample}")
        return

    text = sample.read_text(encoding="utf-8")
    chunks = split_into_tts_chunks(text, max_words=300)

    assert chunks, "expected chunks from audiobook sample"
    assert any(c.pause_before_ms == PAUSE_MAJOR_MS for c in chunks), "expected major pauses"
    assert any(c.pause_before_ms == PAUSE_SECTION_MS for c in chunks), "expected section pauses"
    assert all(len(c.text.split()) <= 300 for c in chunks), "chunks exceed word limit"

    major = [c for c in chunks if c.pause_before_ms == PAUSE_MAJOR_MS][:5]
    print(f"Total chunks: {len(chunks)}")
    print(f"Major pauses: {sum(1 for c in chunks if c.pause_before_ms == PAUSE_MAJOR_MS)}")
    print(f"Section pauses: {sum(1 for c in chunks if c.pause_before_ms == PAUSE_SECTION_MS)}")
    print(f"Paragraph pauses: {sum(1 for c in chunks if c.pause_before_ms == PAUSE_PARAGRAPH_MS)}")
    print("Sample major-pause chunks:")
    for chunk in major:
        preview = chunk.text[:80].replace("\n", " ")
        print(f"  [{chunk.pause_before_ms}ms] {preview}...")


def test_audiobook_sections():
    sample = Path(__file__).resolve().parent / "book_to_convert" / (
        "Set Boundaries, Find Peace - Nedra Glover Tawwab (audiobook).txt"
    )
    if not sample.exists():
        sample = Path(__file__).resolve().parent.parent / (
            "Set Boundaries, Find Peace - Nedra Glover Tawwab (audiobook).txt"
        )
    if not sample.exists():
        print("SKIP: audiobook sample not found")
        return

    text = sample.read_text(encoding="utf-8")
    sections = split_into_audiobook_sections(text)
    assert len(sections) >= 10, f"expected many sections, got {len(sections)}"
    assert sections[0].title == "Preface"
    assert sections[0].filename.startswith("01_")
    assert sections[1].title == "Introduction"
    assert any(s.title.startswith("Chapter 2") for s in sections)
    assert all(s.title != "Opening" for s in sections)
    assert all(s.title != "Commonly Asked Questions" for s in sections)

    print(f"Sections: {len(sections)}")
    for section in sections:
        print(f"  {section.track_number:02d} {section.filename} ({len(section.text.split())} words)")


def test_structured_epub_matches_audiobook_sample():
    """General EPUB extraction should produce a sensible section split for Tawwab."""
    epub_candidates = list(Path(__file__).resolve().parent.glob("book_to_convert/*.epub"))
    epub_candidates += list(Path(__file__).resolve().parent.parent.glob("*Tawwab*.epub"))
    if not epub_candidates:
        print("SKIP: no Tawwab EPUB found for structured extract test")
        return

    from book_format import format_epub

    epub_path = epub_candidates[0]
    try:
        formatted = format_epub(epub_path)
    except RuntimeError as exc:
        print(f"SKIP: EPUB deps not installed ({exc})")
        return
    assert formatted, "structured EPUB formatting failed"

    sections = split_into_audiobook_sections(formatted)
    assert sections[0].title == "Preface", sections[0].title
    assert all(s.title != "Opening" for s in sections)
    assert all(
        s.title not in {"Commonly Asked Questions", "Self-Assessment Quiz"} for s in sections
    )
    print(f"Structured EPUB: {len(formatted.split()):,} words, {len(sections)} sections")


def test_blocks_to_text_roundtrip():
    blocks = [
        ("Title.", 0),
        ("First paragraph.", PAUSE_PARAGRAPH_MS),
        ("Second paragraph.", PAUSE_PARAGRAPH_MS),
    ]
    roundtrip = parse_text_blocks(blocks_to_text(blocks))
    assert len(roundtrip) == len(blocks)
    assert roundtrip[0][0] == "Title."
    assert roundtrip[1][1] == PAUSE_PARAGRAPH_MS


def test_word_limit_splits_have_no_mid_paragraph_pause():
    """Word-limit sub-chunks within one block must not receive structural pauses."""
    paragraph = " ".join(["This is sentence number %d." % i for i in range(1, 80)])
    sub_chunks = split_block_into_chunks(paragraph, max_words=40)
    assert len(sub_chunks) > 1, "expected word-limit split"

    chunks = split_into_tts_chunks(paragraph, max_words=40, for_section=False)
    assert len(chunks) > 1
    assert chunks[0].pause_before_ms == 0
    assert all(chunk.pause_before_ms == 0 for chunk in chunks[1:])


def test_merge_continuation_blocks():
    blocks = [
        ("I receive questions like", 600),
        ('"My friends get drunk every week."', 600),
        ("Complete sentence here.", 600),
        ("Examples:", 600),
        ('"Thank you for letting me know."', 600),
    ]
    merged = merge_continuation_blocks(blocks)
    assert len(merged) == 3
    assert merged[0][0].startswith("I receive questions like")
    assert merged[0][0].endswith('"')
    assert merged[1][0] == "Complete sentence here."
    assert merged[2][0].startswith("Examples:")


def test_short_section_title_delivery():
    """Short section titles are announced separately with a major pause before body."""
    epub_candidates = list(Path(__file__).resolve().parent.glob("book_to_convert/*.epub"))
    epub_candidates += list(Path(__file__).resolve().parent.parent.glob("*Tawwab*.epub"))
    if not epub_candidates:
        print("SKIP: no EPUB found for section title delivery test")
        return

    from book_format import format_epub

    try:
        text = format_epub(epub_candidates[0])
    except RuntimeError as exc:
        print(f"SKIP: EPUB deps not installed ({exc})")
        return

    sections = split_into_audiobook_sections(text)
    for title in ("Preface", "Introduction"):
        section = next(s for s in sections if s.title == title)
        chunks = split_into_tts_chunks(section.text, max_words=300, for_section=True)
        assert chunks[0].text.rstrip(".") == title, chunks[0].text
        assert chunks[0].speech_role == "section_title", chunks[0].speech_role
        assert chunks[1].speech_role == "body", chunks[1].speech_role
        assert chunks[1].pause_before_ms >= PAUSE_MAJOR_MS, chunks[1].pause_before_ms
        assert title not in chunks[1].text[:20], chunks[1].text[:80]
        print(f"{title}: title chunk + {chunks[1].pause_before_ms}ms pause before body")


if __name__ == "__main__":
    test_blank_line_pauses()
    test_blocks_to_text_roundtrip()
    test_merge_continuation_blocks()
    test_word_limit_splits_have_no_mid_paragraph_pause()
    test_formatted_audiobook_sample()
    test_audiobook_sections()
    test_structured_epub_matches_audiobook_sample()
    test_short_section_title_delivery()
    print("OK")
