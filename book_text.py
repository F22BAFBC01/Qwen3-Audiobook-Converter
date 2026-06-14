"""Pause-aware text parsing and chunking for audiobook TTS."""

from __future__ import annotations

import re
from dataclasses import dataclass

SOFT_HYPHEN = "\u00ad"

# Blank-line markers in formatted audiobook text -> silence before the next block.
PAUSE_PARAGRAPH_MS = 600
PAUSE_SECTION_MS = 1500
PAUSE_MAJOR_MS = 2500

FRONT_MATTER_TITLES = {
    "preface",
    "introduction",
    "prologue",
    "foreword",
    "opening credits",
    "opening",
    "dedication",
    "copyright",
    "title page",
    "epilogue",
    "afterword",
    "conclusion",
    "appendix",
    "acknowledgments",
    "acknowledgements",
    "commonly asked questions",
    "self-assessment quiz",
    "references",
    "closing credits",
    "closing",
}

CHAPTER_TITLE_RE = re.compile(
    r"(?i)^(?:part\s+\d+\s*:?\s*.+|chapter\s+\d+[:.]?\s*.+)$"
)


@dataclass(frozen=True)
class TextChunk:
    text: str
    pause_before_ms: int = 0
    speech_role: str = "body"  # "body" or "section_title"


@dataclass(frozen=True)
class AudiobookSection:
    """One exported MP3 track (ACX-style section/chapter)."""

    track_number: int
    title: str
    text: str
    filename: str


def clean_text_preserve_structure(text: str) -> str:
    """Normalize text without destroying paragraph/section blank-line markers."""
    if not text:
        return ""

    text = text.replace(SOFT_HYPHEN, "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')

    normalized_lines: list[str] = []
    blank_run = 0

    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            blank_run += 1
            if blank_run <= 3:
                normalized_lines.append("")
            continue
        blank_run = 0
        normalized_lines.append(line)

    return "\n".join(normalized_lines).strip()


def pause_ms_for_blank_run(blank_count: int) -> int:
    if blank_count >= 3:
        return PAUSE_MAJOR_MS
    if blank_count == 2:
        return PAUSE_SECTION_MS
    if blank_count == 1:
        return PAUSE_PARAGRAPH_MS
    return 0


def parse_text_blocks(text: str) -> list[tuple[str, int]]:
    """Split structured text into blocks with silence duration before each block."""
    lines = text.splitlines()
    blocks: list[tuple[str, int]] = []
    current: list[str] = []
    pause_before_next = 0

    i = 0
    while i < len(lines):
        if not lines[i].strip():
            blank_count = 0
            while i < len(lines) and not lines[i].strip():
                blank_count += 1
                i += 1
            if current:
                blocks.append(("\n".join(current).strip(), pause_before_next))
                current = []
                pause_before_next = 0
            pause_before_next = pause_ms_for_blank_run(blank_count)
            continue

        current.append(lines[i].strip())
        i += 1

    if current:
        blocks.append(("\n".join(current).strip(), pause_before_next))

    return blocks


def _split_long_sentence(sentence: str, max_words: int) -> list[str]:
    parts = re.split(r"[,;:]", sentence)
    chunks: list[str] = []
    current = ""
    current_words = 0

    for part in parts:
        part = part.strip()
        if not part:
            continue
        part_words = len(part.split())
        if part_words > max_words:
            if current:
                chunks.append(current.strip())
                current = ""
                current_words = 0
            words = part.split()
            for start in range(0, len(words), max_words):
                chunks.append(" ".join(words[start : start + max_words]))
            continue

        if current_words + part_words <= max_words:
            current = f"{current}{part}, " if current else f"{part}, "
            current_words += part_words
        else:
            if current:
                chunks.append(current.rstrip(", ").strip())
            current = f"{part}, "
            current_words = part_words

    if current.strip():
        chunks.append(current.rstrip(", ").strip())
    return chunks


def split_block_into_chunks(block_text: str, max_words: int) -> list[str]:
    """Split one text block into TTS-sized chunks on sentence boundaries."""
    normalized = re.sub(r"\s+", " ", block_text).strip()
    if not normalized:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    chunks: list[str] = []
    current = ""
    current_words = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_words = len(sentence.split())
        if sentence_words > max_words:
            if current:
                chunks.append(current.strip())
                current = ""
                current_words = 0
            chunks.extend(_split_long_sentence(sentence, max_words))
            continue

        if current_words + sentence_words <= max_words:
            current = f"{current} {sentence}".strip()
            current_words += sentence_words
        else:
            if current:
                chunks.append(current.strip())
            current = sentence
            current_words = sentence_words

    if current.strip():
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk.strip()]


def split_text_for_voice_clone(text: str, max_chars: int) -> list[str]:
    """Split text at sentence boundaries to fit voice-clone API character limits."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            words = sentence.split()
            part = ""
            for word in words:
                candidate = f"{part} {word}".strip()
                if len(candidate) <= max_chars:
                    part = candidate
                else:
                    if part:
                        chunks.append(part)
                    part = word
            if part:
                current = part
            continue

        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = sentence

    if current.strip():
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk.strip()]


def merge_continuation_blocks(blocks: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Join blocks split mid-thought (lead-in lines before quotes or list examples)."""
    if not blocks:
        return blocks

    merged: list[tuple[str, int]] = []
    i = 0
    while i < len(blocks):
        text, pause = blocks[i]
        while i + 1 < len(blocks):
            stripped = text.rstrip()
            if stripped.endswith((".", "!", "?", '"', "'")):
                break
            nxt_text, _ = blocks[i + 1]
            nxt_stripped = nxt_text.lstrip()
            if nxt_stripped.startswith(('"', "'", "\u201c", "\u2018")):
                text = f"{stripped} {nxt_stripped}"
                i += 1
                continue
            if stripped.endswith(":") and len(stripped.split()) <= 12:
                text = f"{stripped} {nxt_stripped}"
                i += 1
                continue
            break
        merged.append((text, pause))
        i += 1
    return merged


def format_heading_for_tts(text: str) -> str:
    """Prefix for headings merged into the following body (TTS pauses after quoted title)."""
    line = _first_line(text).strip().rstrip(".")
    return f'"{line}\u2014"'


def is_attachable_heading(text: str, pause_before_ms: int = 0) -> bool:
    """True when a short heading/subheading should be read with the next paragraph."""
    if is_section_title(text):
        return True
    line = _first_line(text)
    if "\n" in text or is_toc_artifact(text):
        return False
    words = line.split()
    if not line.endswith(".") or len(words) > 14 or len(line) > 100:
        return False
    if pause_before_ms >= PAUSE_SECTION_MS:
        return True
    return False


def merge_heading_blocks(blocks: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Attach headings and subheadings to the following body using quoted prefixes."""
    if not blocks:
        return blocks

    merged: list[tuple[str, int]] = []
    i = 0
    while i < len(blocks):
        text, pause = blocks[i]
        if is_attachable_heading(text, pause) and i + 1 < len(blocks):
            nxt_text, _ = blocks[i + 1]
            merged.append((f"{format_heading_for_tts(text)} {nxt_text.lstrip()}", pause))
            i += 2
        else:
            merged.append((text, pause))
            i += 1
    return merged


def group_blocks_for_export(
    blocks: list[tuple[str, int]], max_words: int
) -> list[tuple[list[str], int]]:
    """
    Group paragraph blocks into large export chunks (~pre-fork 1500-word batches).

    Pauses are only between export chunks (and paragraph pauses are applied during
    voice-clone synthesis), not between sentences.
    """
    groups: list[tuple[list[str], int]] = []
    current: list[str] = []
    current_words = 0
    group_pause = 0

    for block_text, pause_ms in blocks:
        block_words = len(block_text.split())
        if current and current_words + block_words > max_words:
            groups.append((current, group_pause))
            current = []
            current_words = 0
            group_pause = pause_ms
        if not current:
            group_pause = pause_ms
        current.append(block_text)
        current_words += block_words

    if current:
        groups.append((current, group_pause))
    return groups


def split_into_tts_chunks(text: str, max_words: int, *, for_section: bool = False) -> list[TextChunk]:
    """Split text into large export chunks with pause metadata (paragraph/s section only)."""
    if for_section:
        text = prepare_section_text_for_tts(text)

    blocks = parse_text_blocks(text)
    if not blocks and text.strip():
        blocks = [(text.strip(), 0)]

    chunks: list[TextChunk] = []
    for group_blocks, pause_ms in group_blocks_for_export(blocks, max_words):
        if len(group_blocks) == 1 and len(group_blocks[0].split()) > max_words:
            for sub_index, sub_text in enumerate(split_block_into_chunks(group_blocks[0], max_words)):
                chunks.append(
                    TextChunk(
                        text=sub_text,
                        pause_before_ms=pause_ms if sub_index == 0 else 0,
                        speech_role="body",
                    )
                )
            continue

        chunk_text = "\n\n".join(group_blocks)
        chunks.append(
            TextChunk(
                text=chunk_text,
                pause_before_ms=pause_ms,
                speech_role="body",
            )
        )

    return chunks


def _first_line(text: str) -> str:
    return text.split("\n", 1)[0].strip()


def is_toc_artifact(text: str) -> bool:
    """Long duplicated TOC/nav entries from raw EPUB HTML extraction."""
    line = _first_line(text)
    words = line.split()
    if len(words) > 14:
        return True
    if line.count(",") >= 2 and len(line) > 55:
        return True
    return False


def is_section_title(text: str) -> bool:
    """True when a text block begins a new audiobook track (chapter or equivalent)."""
    line = _first_line(text)
    if not line or line.lower().startswith("question:"):
        return False
    if is_toc_artifact(text):
        return False
    if CHAPTER_TITLE_RE.match(line):
        return True
    normalized = line.lower().rstrip(".")
    if normalized in FRONT_MATTER_TITLES:
        return True
    if "\n" in text:
        return False
    if len(line.split()) > 12:
        return False
    if not line.endswith("."):
        return False
    if normalized.startswith(("part ", "chapter ")):
        return True
    return False


def extract_section_title(text: str) -> str:
    line = _first_line(text).rstrip(".")
    return line or "Section"


def is_short_section_title(text: str, max_words: int = 6) -> bool:
    """True for brief standalone titles such as 'Preface.' or 'Introduction.'"""
    if not is_section_title(text):
        return False
    return len(_first_line(text).split()) <= max_words


def _separator_newlines_for_pause(pause_ms: int) -> int:
    """Newline count between blocks so parse_text_blocks roundtrips pauses correctly."""
    if pause_ms >= PAUSE_MAJOR_MS:
        return 4
    if pause_ms >= PAUSE_SECTION_MS:
        return 3
    return 2


def blocks_to_text(blocks: list[tuple[str, int]]) -> str:
    """Rebuild structured text from parsed blocks (blank line between blocks)."""
    parts: list[str] = []
    for block_text, pause_ms in blocks:
        if parts:
            parts.append("\n" * _separator_newlines_for_pause(pause_ms))
        parts.append(block_text)
    return "".join(parts)


def prepare_section_text_for_tts(section_text: str) -> str:
    """Normalize section block boundaries before TTS chunking."""
    blocks = parse_text_blocks(section_text)
    if not blocks:
        return section_text
    blocks = merge_continuation_blocks(blocks)
    blocks = merge_heading_blocks(blocks)
    return blocks_to_text(blocks)


def sanitize_section_filename(title: str) -> str:
    """ACX-style safe filename fragment: alphanumeric, dashes, underscores."""
    cleaned = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    cleaned = re.sub(r"[\s-]+", "_", cleaned.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:80] or "Section"


def section_filename(track_number: int, total_tracks: int, title: str) -> str:
    """Build `{NN}_{Section_Title}.mp3` with zero-padding for correct sort order."""
    width = max(2, len(str(total_tracks)))
    safe_title = sanitize_section_filename(title)
    return f"{track_number:0{width}d}_{safe_title}.mp3"


def split_into_audiobook_sections(text: str) -> list[AudiobookSection]:
    """
    Split formatted audiobook text into export sections.

    Follows retail/ACX conventions: one file per TOC entry — preface, introduction,
    and each chapter heading that appears as its own titled block in the source text.
    """
    blocks = parse_text_blocks(text)
    if not blocks and text.strip():
        blocks = [(text.strip(), 0)]

    grouped: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_blocks: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_blocks
        if not current_blocks:
            return
        title = current_title or extract_section_title(current_blocks[0])
        grouped.append((title, list(current_blocks)))
        current_title = None
        current_blocks = []

    for block_text, _pause_ms in blocks:
        if is_section_title(block_text):
            flush()
            current_title = extract_section_title(block_text)
            current_blocks = [block_text]
        else:
            if not current_blocks:
                current_title = "Opening"
            current_blocks.append(block_text)

    flush()

    if not grouped and text.strip():
        grouped = [("Opening", [text.strip()])]

    total = len(grouped)
    sections: list[AudiobookSection] = []
    for index, (title, block_texts) in enumerate(grouped, start=1):
        section_text = "\n\n".join(block_texts)
        sections.append(
            AudiobookSection(
                track_number=index,
                title=title,
                text=section_text,
                filename=section_filename(index, total, title),
            )
        )
    return sections
