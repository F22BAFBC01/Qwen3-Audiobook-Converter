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
    # Chapter/part titles often end with "?" in this publisher's EPUBs — not FAQ prompts.
    if is_major_section(line.rstrip("?").rstrip(".")):
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


# ---------------------------------------------------------------------------
# General-purpose EPUB extraction (any publisher)
# ---------------------------------------------------------------------------

try:
    from bs4 import BeautifulSoup, Tag
    from bs4.element import NavigableString

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    Tag = object  # type: ignore

try:
    import ebooklib
    from ebooklib import epub as ebooklib_epub

    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False

BLOCK_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"})

SKIP_EPUB_TYPES = frozenset({
    "cover", "toc", "nav", "copyright-page", "titlepage", "dedication",
    "contributors", "index", "landmarks", "pagebreak", "halftitlepage",
    "list-of-illustrations", "list-of-tables", "lot", "loi", "abstract",
    "colophon", "imprint", "seriespage", "volume", "frontmatter",
})

BACK_MATTER_STOP = frozenset({
    "acknowledgments",
    "acknowledgements",
    "references",
    "bibliography",
    "index",
    "about the author",
    "also by",
    "colophon",
})

END_OF_BOOK_MARKERS = BACK_MATTER_STOP | {
    "self-assessment quiz",
    "commonly asked questions",
}

CONTENT_START_RE = re.compile(
    r"(?i)^(preface|introduction|prologue|foreword|"
    r"chapter\s+(?:1|one)\b|part\s+(?:1|one|i)\b|chapter\s+1[:.])"
)

CHAPTER_HEADING_RE = re.compile(r"(?i)^(?:part\s+\d+\s*:?\s*.+|chapter\s+\d+[:.]?\s*.+)$")

SKIP_CLASS_RE = re.compile(
    r"(?i)(^|[\s_-])(toc|nav|cover|copyright|cip|titlepage|title-page|"
    r"front-sales|sales-quote|pull-?quote|epigraph|advert|promo|"
    r"landmark|navpoint|page-number|pagenum|footnote|endnote|"
    r"free-style|dedf|pcon|quot(?:t)?)([\s_-]|$)"
)

MAJOR_CLASS_RE = re.compile(
    r"(?i)(chapter-title|chaptertitle|part-title|parttitle|fm-head|"
    r"chapter-head|part-head|^cn$|\bcn\b|x03-chapter-title|x02-part-title|x01-fm-head)"
)

BODY_CLASS_RE = re.compile(
    r"(?i)(body-text|bodytext|paragraph|x04-body|x03-co-body|x13-bm|"
    r"^paft$|\bpaft\b|^p$|\bp\b|text-body|prose)"
)

SECTION_CLASS_RE = re.compile(
    r"(?i)(section-head|subhead|x05-head|^ah$|^bh$|^dh$|heading|head-a)"
)


def _element_classes(element: Tag) -> str:
    classes = element.get("class") or []
    return " ".join(classes)


def _element_epub_type(element: Tag) -> str:
    for key in ("epub:type", "epub_type"):
        value = element.get(key)
        if value:
            return value.split()[0].lower()
    return ""


def _inside_skipped_container(element: Tag) -> bool:
    for parent in element.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name == "nav":
            return True
        role = (parent.get("role") or "").lower()
        if role in {"doc-toc", "doc-pagelist", "doc-noteref", "doc-bibliography"}:
            return True
        epub_type = _element_epub_type(parent)
        if epub_type in SKIP_EPUB_TYPES:
            return True
        if parent.name == "aside" and epub_type in {"toc", "footnote", "endnote"}:
            return True
    return False


def _is_nav_document(html: str, item_name: str) -> bool:
    lower_name = (item_name or "").lower()
    if any(token in lower_name for token in ("nav", "toc", "cover")):
        return True
    if re.search(r"<nav\b", html, re.I):
        if re.search(r'epub:type=["\']toc["\']', html, re.I):
            return True
    return False


def _is_content_start(text: str, kind: str) -> bool:
    if kind != "major":
        return False
    normalized = text.lower().strip().rstrip(".")
    if normalized in {"preface", "introduction", "prologue", "foreword"}:
        return True
    return bool(CONTENT_START_RE.match(text.strip()))


def _is_back_matter_stop(text: str, kind: str) -> bool:
    normalized = text.lower().strip().rstrip(".?")
    return normalized in END_OF_BOOK_MARKERS


def _looks_like_toc_document(soup: BeautifulSoup) -> bool:
    """Detect TOC/nav HTML files mislabeled as body content in the spine."""
    chapter_like = 0
    short_headings = 0
    for element in soup.find_all(BLOCK_TAGS):
        if not isinstance(element, Tag):
            continue
        text = clean_text(element.get_text(" ", strip=True))
        if not text:
            continue
        if CHAPTER_HEADING_RE.match(text) or re.match(r"(?i)^chapter\s+\d+\s*:", text):
            chapter_like += 1
            if len(text.split()) <= 14:
                short_headings += 1
    return chapter_like >= 4 and short_headings >= max(3, chapter_like - 1)


def _is_major_heading_text(text: str) -> bool:
    normalized = text.lower().strip().rstrip(".")
    if normalized in {"preface", "introduction", "prologue", "foreword", "epilogue"}:
        return True
    return bool(CHAPTER_HEADING_RE.match(text.strip()))


def _classify_epub_element(element: Tag, text: str) -> str:
    if not text or _inside_skipped_container(element):
        return "skip"

    tag = element.name.lower()
    cls = _element_classes(element)
    epub_type = _element_epub_type(element)

    if epub_type in SKIP_EPUB_TYPES:
        return "skip"

    # Publisher-specific body classes (check before broad skip patterns).
    if "copyright-logo" in cls.lower():
        if len(text.split()) <= 12 and not text.endswith(":"):
            return "skip"
        return "body"
    if BODY_CLASS_RE.search(cls):
        return "list" if tag == "li" else "body"

    if SKIP_CLASS_RE.search(cls):
        return "skip"
    if tag == "blockquote":
        return "skip"

    if MAJOR_CLASS_RE.search(cls) or (tag in {"h1", "h2"} and _is_major_heading_text(text)):
        return "major"
    if SECTION_CLASS_RE.search(cls) or tag in {"h3", "h4", "h5", "h6"}:
        if len(text.split()) <= 18:
            return "section"
    if tag in {"p", "li"}:
        return "list" if tag == "li" else "body"
    return "skip"


def _iter_block_elements(soup: BeautifulSoup):
    for element in soup.find_all(BLOCK_TAGS):
        if not isinstance(element, Tag):
            continue
        if element.name == "p" and element.find_parent("li"):
            continue
        if element.name == "p" and element.find_parent("blockquote"):
            continue
        yield element


def extract_epub(epub_path: Path) -> list[SourceLine]:
    """
    Extract audiobook-ready lines from any EPUB using spine order and semantic HTML.

    Skips covers, TOCs, pull quotes, and nav landmarks; starts at preface/introduction/
    chapter 1; stops at acknowledgments/references/index.
    """
    if not EBOOKLIB_AVAILABLE or not BS4_AVAILABLE:
        raise RuntimeError("ebooklib and beautifulsoup4 are required for EPUB extraction")

    book = ebooklib_epub.read_epub(str(epub_path))
    source: list[SourceLine] = []
    started = False
    pending_chapter_num: str | None = None
    seen_major_titles: set[str] = set()

    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        raw = item.get_content()
        html = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        if _is_nav_document(html, item.get_name()):
            continue

        soup = BeautifulSoup(html, "html.parser")
        if _looks_like_toc_document(soup):
            continue

        for element in _iter_block_elements(soup):
            text = clean_text(element.get_text(" ", strip=True))
            if not text:
                continue

            cls = _element_classes(element)
            if re.fullmatch(r"\d{1,2}", text) and "chapter-number" in cls.lower():
                pending_chapter_num = text
                continue

            kind = _classify_epub_element(element, text)
            if kind == "skip":
                continue

            if not started:
                if not _is_content_start(text, kind):
                    continue
                started = True

            if _is_back_matter_stop(text, kind):
                return source

            if kind == "major":
                if pending_chapter_num:
                    text = f"Chapter {pending_chapter_num}. {text.rstrip('.')}"
                    pending_chapter_num = None
                title_key = text.lower().strip()
                if title_key in seen_major_titles:
                    continue
                seen_major_titles.add(title_key)
                source.append(SourceLine(text=text, tab_count=0, is_callout=False))
                continue

            if kind == "section":
                source.append(SourceLine(text=text, tab_count=0, is_callout=False))
                continue

            tab_count = 5 if kind == "list" else 3
            source.append(SourceLine(text=text, tab_count=tab_count, is_callout=False))

    return source


def format_epub(epub_path: Path) -> str | None:
    """Extract and format any EPUB for audiobook TTS."""
    source = extract_epub(epub_path)
    if not source:
        return None
    processed = process_lines(source)
    return normalize_whitespace("\n".join(processed))


def format_epub_if_supported(epub_path: Path) -> str | None:
    """Extract and format an EPUB. Returns None only when no readable content is found."""
    try:
        return format_epub(epub_path)
    except RuntimeError:
        return None
