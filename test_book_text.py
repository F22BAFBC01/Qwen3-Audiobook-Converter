#!/usr/bin/env python3
"""Smoke tests for pause-aware audiobook text chunking."""

from pathlib import Path

from book_text import (
    PAUSE_MAJOR_MS,
    PAUSE_PARAGRAPH_MS,
    PAUSE_SECTION_MS,
    SYNTHESIS_MAX_WORDS,
    blocks_to_text,
    extract_section_title,
    format_heading_for_tts,
    group_blocks_for_synthesis,
    is_section_title,
    merge_continuation_blocks,
    merge_heading_blocks,
    parse_text_blocks,
    prepare_section_text_for_tts,
    split_block_into_chunks,
    split_into_audiobook_sections,
    split_into_tts_chunks,
    split_text_for_voice_clone,
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
    chunks = split_into_tts_chunks(text)

    assert chunks, "expected chunks from audiobook sample"
    assert any(c.pause_before_ms == PAUSE_MAJOR_MS for c in chunks), "expected major pauses"
    assert any(c.pause_before_ms == PAUSE_SECTION_MS for c in chunks), "expected section pauses"
    assert all(len(c.text.split()) <= SYNTHESIS_MAX_WORDS for c in chunks), "chunks exceed word limit"

    major = [c for c in chunks if c.pause_before_ms == PAUSE_MAJOR_MS][:5]
    print(f"Total synthesis units: {len(chunks)}")
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


def test_chapter_titles_with_question_mark_are_sections():
    from book_format import looks_like_faq_question

    title = "Chapter 1. What the Heck Are Boundaries?"
    assert not looks_like_faq_question(title)
    assert is_section_title(title)
    assert extract_section_title(title) == "Chapter 1. What the Heck Are Boundaries"

    faq = "Question: Chapter 1. What the Heck Are Boundaries?"
    assert is_section_title(faq)
    assert extract_section_title(faq) == "Chapter 1. What the Heck Are Boundaries"


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
    titles = [s.title for s in sections]
    assert any(t.startswith("Chapter 1.") for t in titles), titles
    assert any(t.startswith("Chapter 3.") for t in titles), titles
    assert any(t.startswith("Chapter 9.") for t in titles), titles
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


def test_split_text_for_voice_clone():
    """Fallback splitter for text that exceeds API char limit (punctuation boundaries)."""
    paragraph = (
        "My life before I had healthy boundaries was overwhelming and chaotic. "
        "I, too, have struggled with codependency, peace in life and at work, "
        "and unfulfilling relationships. But setting expectations and limits "
        "helped me find balance."
    )
    segments = split_text_for_voice_clone(paragraph, max_chars=500)
    assert segments
    assert all(len(segment) <= 500 for segment in segments)
    assert " ".join(segments) == paragraph


def test_heading_merged_into_body():
    blocks = [
        ("Introduction.", 0),
        ("I've been a therapist for fourteen years.", PAUSE_PARAGRAPH_MS),
        ("Signs That You Need Boundaries.", PAUSE_SECTION_MS),
        ("You feel overwhelmed.", PAUSE_PARAGRAPH_MS),
    ]
    merged = merge_heading_blocks(blocks)
    assert merged[0][0].startswith('"Introduction\u2014"\n\nI\'ve been')
    assert merged[1][0].startswith('"Signs That You Need Boundaries\u2014"\n\nYou feel')


def test_synthesis_splits_at_section_pause():
    blocks = [
        ('"Introduction\u2014"\n\nFirst subsection paragraph.', 0),
        ("Second paragraph in same subsection.", PAUSE_PARAGRAPH_MS),
        ('"Signs That You Need Boundaries\u2014"\n\nSubsection body.', PAUSE_SECTION_MS),
        ("Another paragraph.", PAUSE_PARAGRAPH_MS),
    ]
    units = group_blocks_for_synthesis(blocks)
    assert len(units) == 2
    assert units[0][0].count("\n\n") >= 2
    assert "Second paragraph" in units[0][0]
    assert units[1][0].startswith('"Signs That You Need Boundaries')


def test_synthesis_units_group_by_structure():
    epub_candidates = list(Path(__file__).resolve().parent.parent.glob("*Tawwab*.epub"))
    if not epub_candidates:
        print("SKIP: no EPUB for synthesis unit test")
        return

    from book_format import format_epub

    try:
        text = format_epub(epub_candidates[0])
    except RuntimeError as exc:
        print(f"SKIP: EPUB deps not installed ({exc})")
        return

    sections = split_into_audiobook_sections(text)
    preface = next(s for s in sections if s.title == "Preface")
    intro = next(s for s in sections if s.title == "Introduction")

    preface_units = split_into_tts_chunks(preface.text, for_section=True)
    intro_units = split_into_tts_chunks(intro.text, for_section=True)

    assert len(preface_units) == 1, f"Preface should be one synthesis unit, got {len(preface_units)}"
    assert '"Preface\u2014"\n\n' in preface_units[0].text
    assert len(intro_units) > 1, "Introduction has subsections — expect multiple synthesis units"
    assert '"Introduction\u2014"\n\n' in intro_units[0].text
    print(
        f"Preface: {len(preface_units)} unit(s); "
        f"Introduction: {len(intro_units)} units; "
        f"first intro unit: {intro_units[0].text[:70]}..."
    )


def test_word_limit_splits_have_no_mid_paragraph_pause():
    """Oversized single blocks split for word limit only — no pauses between parts."""
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


def test_format_heading_for_tts():
    assert format_heading_for_tts("Preface.") == '"Preface\u2014"'
    assert format_heading_for_tts("Chapter 2. The Cost") == '"Chapter 2. The Cost\u2014"'


if __name__ == "__main__":
    test_blank_line_pauses()
    test_blocks_to_text_roundtrip()
    test_format_heading_for_tts()
    test_merge_continuation_blocks()
    test_heading_merged_into_body()
    test_chapter_titles_with_question_mark_are_sections()
    test_split_text_for_voice_clone()
    test_word_limit_splits_have_no_mid_paragraph_pause()
    test_formatted_audiobook_sample()
    test_audiobook_sections()
    test_structured_epub_matches_audiobook_sample()
    test_synthesis_splits_at_section_pause()
    test_synthesis_units_group_by_structure()
    print("OK")
