#!/usr/bin/env python3
"""Structured EPUB extraction and formatting for audiobook conversion."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from html import unescape
from pathlib import Path

SOFT_HYPHEN = "\u00ad"
MAJOR_PAUSE = ["", "", ""]  # three blank lines = long pause for TTS
SECTION_PAUSE = ["", ""]  # two blank lines before subsection headings


@dataclass
class SourceLine:
    text: str
    tab_count: int
    is_callout: bool


def clean_text(text: str) -> str:
    text = text.replace(SOFT_HYPHEN, "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", "—").replace("\u2013", "-")
    return text.strip()


def parse_source_lines(raw_lines: list[str]) -> list[SourceLine]:
    parsed: list[SourceLine] = []
    for raw in raw_lines:
        if not raw.strip():
            parsed.append(SourceLine(text="", tab_count=0, is_callout=False))
            continue
        ws = re.match(r"^(\s*)", raw).group(1)
        tab_count = ws.count("\t")
        text = clean_text(raw)
        is_callout = is_callout_aside(text, tab_count)
        parsed.append(SourceLine(text=text, tab_count=tab_count, is_callout=is_callout))
    return parsed


def is_callout_aside(text: str, tab_count: int) -> bool:
    """Deep-indented short lines are decorative pull-quote asides in the Tawwab export."""
    if not text or not text.endswith("."):
        return False
    if tab_count < 7:
        return False
    words = text.split()
    if len(words) > 15:
        return False
    if text.count(". ") >= 1:
        return False
    return True


def is_dialogue_line(line: str) -> bool:
    return line.startswith(('"', "“", "‘", "'"))


def ensure_heading_period(title: str) -> str:
    title = title.strip()
    if not title:
        return title
    if title.endswith(("?", "!", ".", ":", "—")):
        return title
    lower = title.lower()
    for suffix in (" like", " such as", " including", " for example"):
        if lower.endswith(suffix):
            return title
    return title + "."


def is_likely_body_paragraph(line: str) -> bool:
    if not line:
        return False
    if is_dialogue_line(line):
        return True
    if line.endswith(".") and len(line.split()) >= 4:
        return True
    if len(line) > 100:
        return True
    if line.count(". ") >= 1 and len(line) > 60:
        return True
    if line.endswith(".") and len(line.split()) > 8:
        return True
    return False


def is_likely_heading(line: str) -> bool:
    if not line or is_dialogue_line(line):
        return False
    if line.endswith("."):
        return False
    if is_likely_body_paragraph(line):
        return False
    if line.startswith(("http://", "https://", "—", "- ", "* ")):
        return False
    if re.fullmatch(r"\d{1,2}", line):
        return False
    if re.fullmatch(r"(?i)(part|chapter)\s+\d+", line):
        return False
    if re.fullmatch(r"(?i)chapter\s+\d+:", line):
        return False
    if re.fullmatch(r"(?i)part\s+\d+", line):
        return False
    if len(line.split()) > 14:
        return False
    return True


def is_major_section(title: str) -> bool:
    lower = title.lower().rstrip(".")
    if lower in {
        "preface",
        "introduction",
        "epilogue",
        "self-assessment quiz",
        "commonly asked questions",
    }:
        return True
    if re.fullmatch(r"(?i)part \d+:.*", title):
        return True
    if re.fullmatch(r"(?i)chapter \d+\..*", title):
        return True
    return False


CHECKLIST_PREFIXES = (
    "My parent",
    "When I was",
    "When it came",
    "When ",
    "I didn't",
    "I never",
    "Conversations ",
    "Even polite",
    "Facts and",
    "It was ",
    "If I ",
    "You feel ",
    "You avoid ",
    "You make ",
    "You frequently ",
    "You have ",
    "You don't ",
    "You apologize ",
    "You allow ",
    "You speak ",
    "You assume ",
    "Consider ",
    "Do you ",
    "Have you ",
    "Is your ",
    "Limit ",
    "Respond ",
    "Saying yes",
    "Loaning money",
    "Never sharing",
    "Building walls",
    "Being clear",
    "Listening to",
    "Sharing with",
    "Having a healthy",
    "Being comfortable",
    "Oversharing",
    "Codependency",
    "Enmeshment",
    "Inability to",
    "People-pleasing",
    "Dependency on",
    "Paralyzing fear",
    "Accepting mistreatment",
    "People with boundaries",
)


def is_list_item_text(text: str, tab_count: int) -> bool:
    if not text or is_dialogue_line(text):
        return False
    if text.endswith(":"):
        return False
    words = text.split()
    if len(words) > 22 or len(text) > 160:
        return False
    if text.count(". ") >= 1 and len(words) > 14:
        return False
    if tab_count >= 4:
        return True
    return text.startswith(CHECKLIST_PREFIXES)


def is_checklist_item(line: str) -> bool:
    if not line or is_dialogue_line(line):
        return False
    if re.fullmatch(r"[A-Z][A-Za-z]+\.", line):
        return False
    return line.startswith(CHECKLIST_PREFIXES)


def is_decorative_line(line: str) -> bool:
    if line in {"—", "* * *", "• • •"}:
        return True
    return bool(re.fullmatch(r"[\*\-–—•\s]+", line))


def _skip_blank_runs(lines: list[str], idx: int) -> int:
    while idx < len(lines) and not lines[idx]:
        idx += 1
    return idx


def is_epigraph(source: list[SourceLine], i: int, after_heading: bool) -> bool:
    if not after_heading:
        return False
    line = source[i].text
    if not line or is_dialogue_line(line):
        return False
    if source[i].tab_count >= 4:
        return False
    words = line.split()
    if len(words) > 12 or not line.endswith("."):
        return False
    if line.count(". ") >= 1:
        return False
    texts = [entry.text for entry in source]
    nxt = _skip_blank_runs(texts, i + 1)
    if nxt >= len(source):
        return False
    nxt_line = source[nxt].text
    if is_list_item_text(nxt_line, source[nxt].tab_count) or is_likely_heading(nxt_line):
        return False
    return len(nxt_line.split()) >= 12 or len(nxt_line) > 80


def is_duplicate_lead_in(line: str, lines: list[str], i: int) -> bool:
    """Standalone sentence repeated at the start of the next paragraph."""
    nxt = _skip_blank_runs(lines, i + 1)
    if nxt >= len(lines):
        return False
    nxt_line = lines[nxt]
    lead = line.rstrip(".")
    if nxt_line.startswith(lead + ".") or nxt_line.startswith(lead + " "):
        return True
    return False


def append_pause(output: list[str], pause: list[str]) -> None:
    while output and output[-1] == "":
        output.pop()
    output.extend(pause)


def emit_heading(output: list[str], title: str) -> None:
    title = ensure_heading_period(title)
    if is_major_section(title):
        append_pause(output, MAJOR_PAUSE)
        output.append(title)
        append_pause(output, MAJOR_PAUSE)
    else:
        append_pause(output, SECTION_PAUSE)
        output.append(title)
        output.append("")


def merge_part_or_chapter(lines: list[str], i: int) -> tuple[str | None, int]:
    line = lines[i]
    part_match = re.fullmatch(r"(?i)(part)\s+(\d+)", line)
    chapter_colon = re.fullmatch(r"(?i)chapter\s+(\d+):", line)
    chapter_only = re.fullmatch(r"(?i)chapter\s+(\d+)", line)
    number_only = re.fullmatch(r"(\d{1,2})", line)

    def next_content(idx: int) -> tuple[str | None, int]:
        j = _skip_blank_runs(lines, idx + 1)
        if j < len(lines):
            return lines[j], j
        return None, j

    if part_match:
        title, j = next_content(i)
        if title and is_likely_heading(title) and not is_dialogue_line(title):
            merged = f"Part {part_match.group(2)}: {title.rstrip('.')}"
            return merged, j
        return f"Part {part_match.group(2)}", i

    if chapter_colon:
        title, j = next_content(i)
        if title:
            return f"Chapter {chapter_colon.group(1)}. {title.rstrip('.')}", j
        return f"Chapter {chapter_colon.group(1)}", i

    if chapter_only:
        title, j = next_content(i)
        if title and is_likely_heading(title):
            return f"Chapter {chapter_only.group(1)}. {title.rstrip('.')}", j

    if number_only:
        num = int(number_only.group(1))
        if 1 <= num <= 20:
            title, j = next_content(i)
            if title and is_likely_heading(title) and not title.lower().startswith("chapter"):
                return f"Chapter {num}. {title.rstrip('.')}", j

    return None, i


def format_list_block(source: list[SourceLine], start: int) -> tuple[str, int]:
    header = source[start].text
    items: list[str] = []
    i = start + 1
    texts = [entry.text for entry in source]
    while i < len(source):
        line = source[i].text
        if not line:
            nxt = _skip_blank_runs(texts, i + 1)
            if nxt < len(source) and is_list_item_text(source[nxt].text, source[nxt].tab_count):
                i = nxt
                continue
            if items:
                break
            i += 1
            continue
        if is_likely_heading(line) and not is_list_item_text(line, source[i].tab_count):
            break
        if is_likely_body_paragraph(line) and not is_list_item_text(line, source[i].tab_count):
            break
        if is_list_item_text(line, source[i].tab_count):
            items.append(line.rstrip(".").strip())
            i += 1
            continue
        break

    if len(items) < 2:
        return header, start

    intro = ensure_heading_period(header.rstrip(":"))
    joined = ". ".join(items)
    if not joined.endswith((".", "?", "!")):
        joined += "."
    return f"{intro}\n\n{joined}", i - 1


def format_checklist_block(lines: list[str], start: int) -> tuple[str, int]:
    items: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line:
            nxt = _skip_blank_runs(lines, i + 1)
            if nxt < len(lines) and is_checklist_item(lines[nxt]):
                i = nxt
                continue
            if items:
                break
            i += 1
            continue
        if is_checklist_item(line):
            items.append(line)
            i += 1
            continue
        if items:
            break
        return lines[start], start
    if len(items) < 2:
        return lines[start], start
    return " ".join(items), i - 1


def looks_like_faq_question(line: str) -> bool:
    if not line.endswith("?"):
        return False
    if is_dialogue_line(line):
        return False
    return len(line.split()) >= 4


def process_lines(source_lines: list[SourceLine]) -> list[str]:
    lines = [entry.text for entry in source_lines]
    skip_indices: set[int] = set()

    for idx, entry in enumerate(source_lines):
        if entry.is_callout:
            skip_indices.add(idx)

    for idx in range(len(lines)):
        if idx in skip_indices or not lines[idx]:
            continue
        if is_duplicate_lead_in(lines[idx], lines, idx):
            skip_indices.add(idx)

    output: list[str] = []
    i = 0
    after_heading = False

    while i < len(source_lines):
        if i in skip_indices:
            i += 1
            continue

        entry = source_lines[i]
        line = entry.text
        if not line:
            i += 1
            continue

        if is_decorative_line(line):
            i += 1
            continue

        if is_epigraph(source_lines, i, after_heading):
            i += 1
            after_heading = False
            continue

        merged, jump = merge_part_or_chapter(lines, i)
        if merged and jump > i:
            emit_heading(output, merged)
            after_heading = True
            i = jump + 1
            continue

        after_heading = False

        if is_checklist_item(line):
            peek = _skip_blank_runs(lines, i + 1)
            if peek < len(lines) and is_checklist_item(lines[peek]):
                block, end = format_checklist_block(lines, i)
                output.append(block)
                output.append("")
                i = end + 1
                continue

        if is_likely_heading(line):
            peek = _skip_blank_runs(lines, i + 1)
            if peek < len(lines) and is_list_item_text(
                source_lines[peek].text, source_lines[peek].tab_count
            ):
                block, end = format_list_block(source_lines, i)
                if end > i:
                    append_pause(output, SECTION_PAUSE)
                    output.append(block)
                    output.append("")
                    i = end + 1
                    continue

        if looks_like_faq_question(line):
            append_pause(output, SECTION_PAUSE)
            output.append(f"Question: {line}")
            output.append("")
            i += 1
            continue

        if is_likely_heading(line):
            emit_heading(output, line)
            after_heading = is_major_section(ensure_heading_period(line))
            i += 1
            continue

        if output and output[-1] != "":
            output.append("")
        output.append(line)
        i += 1

    return output


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\n{6,}", "\n\n\n\n\n", text)
    return text.strip() + "\n"


def find_marker(lines: list[str], marker: str, occurrence: int = 1) -> int:
    target = marker.lower()
    seen = 0
    for idx, line in enumerate(lines):
        if line.lower() == target:
            seen += 1
            if seen == occurrence:
                return idx
    raise ValueError(f"Marker '{marker}' occurrence {occurrence} not found")


def slice_content(
    lines: list[str],
    start_marker: str,
    end_markers: list[str],
    *,
    start_occurrence: int = 1,
    min_end_distance: int = 500,
) -> list[str]:
    start_idx = find_marker(lines, start_marker, occurrence=start_occurrence)
    end_idx = len(lines)
    end_targets = {marker.lower() for marker in end_markers}
    for idx in range(start_idx + min_end_distance, len(lines)):
        if lines[idx].lower() in end_targets:
            end_idx = idx
            break
    return lines[start_idx:end_idx]


def html_to_text(html_fragment: str) -> str:
    text = re.sub(r"<(br|/?p)\s*/?>", " ", html_fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return clean_text(re.sub(r"\s+", " ", text))


TAWWAB_SKIP_CLASSES = {
    "x14-free-style-1-l",
    "x14-free-style-1-r",
    "x03-chapter-epigraph",
    "x01-fm-front-sales-quote",
}


def classify_tawwab_element(tag: str, cls: str, text: str) -> str:
    primary = cls.split()[0] if cls else ""
    if tag == "blockquote" or primary in TAWWAB_SKIP_CLASSES:
        return "skip"
    if primary == "x01-fm-copyright-logo":
        if len(text.split()) <= 12 and not text.endswith(":"):
            return "skip"
        return "body"
    if primary.startswith("x07-list"):
        return "list"
    if primary in {"x01-fm-head", "x03-chapter-title", "x02-part-title"}:
        return "major"
    if primary == "x03-chapter-number":
        return "chapter_number"
    if primary.startswith("x05-head"):
        return "section"
    if primary in {"x04-body-text", "x03-co-body-text", "x13-bm-text"}:
        return "body"
    return "skip"


def extract_tawwab_epub(epub_path: Path) -> list[SourceLine]:
    source: list[SourceLine] = []
    pending_chapter_num: str | None = None

    with zipfile.ZipFile(epub_path) as zf:
        html_files = sorted(
            n
            for n in zf.namelist()
            if n.endswith(".html")
            and (m := re.search(r"part(\d+)", n))
            and int(m.group(1)) >= 5
        )
        for name in html_files:
            data = zf.read(name).decode("utf-8", errors="replace")
            for m in re.finditer(
                r"<(h1|h2|h3|p|blockquote|li)[^>]*class=\"([^\"]*)\"[^>]*>(.*?)</\1>",
                data,
                re.S | re.I,
            ):
                tag, cls, inner = m.group(1).lower(), m.group(2), m.group(3)
                text = html_to_text(inner)
                if not text:
                    continue
                if text == "Acknowledgments" and "x01-fm-head" in cls:
                    return source
                kind = classify_tawwab_element(tag, cls, text)
                if kind == "skip":
                    continue
                if kind == "chapter_number":
                    pending_chapter_num = text
                    continue
                if kind == "major":
                    if pending_chapter_num and "chapter" in cls:
                        text = f"Chapter {pending_chapter_num}. {text.rstrip('.')}"
                        pending_chapter_num = None
                    source.append(SourceLine(text=text, tab_count=0, is_callout=False))
                    continue
                if kind == "section":
                    source.append(SourceLine(text=text, tab_count=0, is_callout=False))
                    continue
                if kind == "list":
                    source.append(SourceLine(text=text, tab_count=5, is_callout=False))
                    continue
                source.append(SourceLine(text=text, tab_count=3, is_callout=False))

    return source


GIBSON_SKIP_CLASSES = {"quot", "quott", "cip", "cipf", "dedf", "pcon", "toc", "cover"}


def classify_gibson_element(cls: str, text: str) -> str:
    primary = cls.split()[0] if cls else ""
    if primary in GIBSON_SKIP_CLASSES:
        return "skip"
    if primary == "cn":
        return "major"
    if primary in {"ah", "bh", "dh", "exh", "stf"}:
        return "section"
    if primary.startswith(("bl", "ul", "nl", "exul")):
        return "list"
    if primary in {"paft", "p", "st", "stl", "exf", "exl", "ex", "ans"}:
        return "body"
    return "skip"


def extract_gibson_epub(epub_path: Path) -> list[SourceLine]:
    source: list[SourceLine] = []
    with zipfile.ZipFile(epub_path) as zf:
        data = zf.read("OEBPS/EPUB_Adult_Children_of_Emotionally_Immature_Parents_EPUB.xhtml").decode(
            "utf-8", errors="replace"
        )
        started = False
        for m in re.finditer(r"<p[^>]*class=\"([^\"]*)\"[^>]*>(.*?)</p>", data, re.S | re.I):
            cls, inner = m.group(1), m.group(2)
            primary = cls.split()[0]
            text = html_to_text(inner)
            if not text:
                continue
            if not started:
                if primary == "cn" and text == "Introduction" and "_idTextAnchor001" in m.group(0):
                    started = True
                else:
                    continue
            if primary == "cn" and text == "References":
                break
            kind = classify_gibson_element(cls, text)
            if kind == "skip":
                continue
            tab_count = 5 if kind == "list" else 3
            source.append(SourceLine(text=text, tab_count=tab_count, is_callout=False))
    return source


def find_epub(base: Path, stem: str) -> Path | None:
    exact = base / f"{stem}.epub"
    if exact.exists():
        return exact
    words = stem.split()[:4]
    for path in base.glob("*.epub"):
        if all(w in path.name for w in words[:3]):
            return path
    return None


def format_book_from_epub(epub_path: Path, book: str) -> str:
    if book == "tawwab":
        source = extract_tawwab_epub(epub_path)
    else:
        source = extract_gibson_epub(epub_path)
    processed = process_lines(source)
    return normalize_whitespace("\n".join(processed))


def detect_epub_profile(epub_path: Path) -> str | None:
    """Return 'tawwab', 'gibson', or None if this EPUB has no structured profile."""
    try:
        with zipfile.ZipFile(epub_path) as zf:
            names = zf.namelist()
            if any("EPUB_Adult_Children_of_Emotionally" in n for n in names):
                return "gibson"
            for name in names:
                if not name.lower().endswith((".html", ".xhtml", ".htm")):
                    continue
                head = zf.read(name).decode("utf-8", errors="replace")[:100000]
                if any(
                    marker in head
                    for marker in ("x04-body-text", "x03-chapter-title", "x02-part-title")
                ):
                    return "tawwab"
    except Exception:
        return None
    return None


def format_epub_if_supported(epub_path: Path) -> str | None:
    """
    Extract and format EPUB text when a known book profile is detected.

    Skips front-matter blurbs, pull quotes, and back matter that raw HTML
    extraction would incorrectly treat as chapters.
    """
    profile = detect_epub_profile(epub_path)
    if profile == "tawwab":
        source = extract_tawwab_epub(epub_path)
    elif profile == "gibson":
        source = extract_gibson_epub(epub_path)
    else:
        return None

    if not source:
        return None

    processed = process_lines(source)
    return normalize_whitespace("\n".join(processed))
