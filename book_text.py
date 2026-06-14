"""Pause-aware text parsing and chunking for audiobook TTS."""

from __future__ import annotations

import re
from dataclasses import dataclass

SOFT_HYPHEN = "\u00ad"

# Blank-line markers in formatted audiobook text -> silence before the next block.
PAUSE_PARAGRAPH_MS = 600
PAUSE_SECTION_MS = 1500
PAUSE_MAJOR_MS = 2500


@dataclass(frozen=True)
class TextChunk:
    text: str
    pause_before_ms: int = 0


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


def split_into_tts_chunks(text: str, max_words: int) -> list[TextChunk]:
    """Split structured audiobook text into TTS chunks with pause metadata."""
    blocks = parse_text_blocks(text)
    if not blocks and text.strip():
        blocks = [(text.strip(), 0)]

    chunks: list[TextChunk] = []
    for block_text, pause_ms in blocks:
        sub_chunks = split_block_into_chunks(block_text, max_words)
        for index, sub_chunk in enumerate(sub_chunks):
            chunks.append(
                TextChunk(
                    text=sub_chunk,
                    pause_before_ms=pause_ms if index == 0 else 0,
                )
            )

    return chunks
