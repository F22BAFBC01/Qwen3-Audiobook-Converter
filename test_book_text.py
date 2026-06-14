#!/usr/bin/env python3
"""Smoke tests for pause-aware audiobook text chunking."""

from pathlib import Path

from book_text import (
    PAUSE_MAJOR_MS,
    PAUSE_PARAGRAPH_MS,
    PAUSE_SECTION_MS,
    parse_text_blocks,
    prepare_section_text_for_tts,
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
    """Structured EPUB output should match pre-formatted audiobook section split."""
    epub_candidates = list(Path(__file__).resolve().parent.glob("book_to_convert/*.epub"))
    epub_candidates += list(Path(__file__).resolve().parent.parent.glob("*Tawwab*.epub"))
    if not epub_candidates:
        print("SKIP: no Tawwab EPUB found for structured extract test")
        return

    from book_format import format_epub_if_supported

    epub_path = epub_candidates[0]
    formatted = format_epub_if_supported(epub_path)
    assert formatted, "structured EPUB formatting failed"

    sections = split_into_audiobook_sections(formatted)
    assert sections[0].title == "Preface", sections[0].title
    assert all(s.title != "Opening" for s in sections)
    assert all(s.title != "Commonly Asked Questions" for s in sections)
    print(f"Structured EPUB: {len(formatted.split()):,} words, {len(sections)} sections")


def test_short_title_merged_for_tts():
    sample = Path(__file__).resolve().parent.parent / (
        "Set Boundaries, Find Peace - Nedra Glover Tawwab (audiobook).txt"
    )
    if not sample.exists():
        print("SKIP: audiobook sample not found")
        return

    text = sample.read_text(encoding="utf-8")
    sections = split_into_audiobook_sections(text)
    preface = sections[0]
    prepared = prepare_section_text_for_tts(preface.text)
    chunks = split_into_tts_chunks(prepared, max_words=300, for_section=False)

    assert chunks, "expected chunks"
    first = chunks[0].text
    assert first != "Preface.", f"short title should be merged, got: {first!r}"
    assert first.startswith("Preface."), first
    assert "My life before" in first or len(first.split()) > 5, first
    print(f"Preface opener chunk: {first[:100]}...")


if __name__ == "__main__":
    test_blank_line_pauses()
    test_formatted_audiobook_sample()
    test_audiobook_sections()
    test_structured_epub_matches_audiobook_sample()
    test_short_title_merged_for_tts()
    print("OK")
