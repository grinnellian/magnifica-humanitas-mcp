"""MCP server for Magnifica Humanitas — Pope Leo XIV's 2026 encyclical on AI and the human person."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache

import httpx
from bs4 import BeautifulSoup, Tag
from mcp.server.fastmcp import FastMCP

ENCYCLICAL_URL = (
    "https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/"
    "20260515-magnifica-humanitas.html"
)

CHAPTER_HEADER_RE = re.compile(r"^CHAPTER\s+(ONE|TWO|THREE|FOUR|FIVE)$", re.I)
PARA_RE = re.compile(r"^(\d+)\.\s+(.*)", re.DOTALL)
FOOTNOTE_RE = re.compile(r"^\[\d+\]")  # endnote references: [1] text...
WORD_TO_INT = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


@dataclass
class Paragraph:
    number: int
    text: str
    section: str
    chapter: str

    def __str__(self) -> str:
        return f"[§{self.number}] ({self.chapter} › {self.section})\n{self.text}"


@dataclass
class Section:
    title: str
    chapter: str
    paragraphs: list[Paragraph] = field(default_factory=list)

    def full_text(self) -> str:
        lines = [f"{self.chapter} › {self.title}", ""]
        lines.extend(f"{p.number}. {p.text}" for p in self.paragraphs)
        return "\n\n".join(lines)


@dataclass
class Chapter:
    number: int
    title: str
    sections: list[Section] = field(default_factory=list)

    def full_text(self) -> str:
        lines = [f"CHAPTER {self.number}: {self.title}", ""]
        for sec in self.sections:
            lines.append(f"--- {sec.title} ---")
            lines.extend(f"{p.number}. {p.text}" for p in sec.paragraphs)
            lines.append("")
        return "\n\n".join(lines)


@dataclass
class Document:
    chapters: list[Chapter] = field(default_factory=list)
    paragraphs: dict[int, Paragraph] = field(default_factory=dict)

    def all_sections(self) -> list[Section]:
        return [sec for ch in self.chapters for sec in ch.sections]


def _clean_p(p: Tag) -> str:
    for sup in p.find_all("sup"):
        sup.decompose()
    return re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()


def _parse(html: str) -> Document:
    soup = BeautifulSoup(html, "lxml")

    texts = [_clean_p(p) for p in soup.find_all("p")]

    # The document has a ToC block before the real content. Skip it by finding
    # the second occurrence of "INTRODUCTION" (first is in the ToC, second starts content).
    content_start = 0
    intro_seen = 0
    for i, t in enumerate(texts):
        if t == "INTRODUCTION":
            intro_seen += 1
            if intro_seen >= 2:
                content_start = i
                break

    doc = Document()

    # Intro is a virtual chapter 0 (no "CHAPTER N" marker in the document).
    intro_ch = Chapter(number=0, title="Introduction")
    doc.chapters.append(intro_ch)
    intro_sec = Section(title="Introduction", chapter="Introduction")
    intro_ch.sections.append(intro_sec)
    current_chapter: Chapter = intro_ch
    current_section: Section = intro_sec

    pending_num: int | None = None   # chapter number awaiting its title
    title_parts: list[str] = []      # title lines accumulated after CHAPTER N

    def _commit_chapter() -> None:
        nonlocal current_chapter, current_section, pending_num, title_parts
        if pending_num is not None and title_parts:
            ch = Chapter(number=pending_num, title=" ".join(title_parts))
            doc.chapters.append(ch)
            current_chapter = ch
            sec = Section(title=ch.title, chapter=ch.title)
            ch.sections.append(sec)
            current_section = sec
        pending_num = None
        title_parts = []

    for t in texts[content_start:]:
        if not t:
            continue

        # Chapter number marker — e.g. "CHAPTER THREE"
        m_ch = CHAPTER_HEADER_RE.match(t)
        if m_ch:
            _commit_chapter()
            pending_num = WORD_TO_INT[m_ch.group(1).lower()]
            continue

        # Numbered paragraph — e.g. "17. In this first chapter…"
        m_para = PARA_RE.match(t)
        if m_para:
            _commit_chapter()
            num = int(m_para.group(1))
            content = m_para.group(2).strip()
            para = Paragraph(num, content, current_section.title, current_chapter.title)
            current_section.paragraphs.append(para)
            doc.paragraphs[num] = para
            continue

        # Accumulate multi-line chapter title (e.g. Ch. 3 has two title lines)
        if pending_num is not None:
            title_parts.append(t)
            continue

        # Skip redundant INTRODUCTION heading at content_start
        if t == "INTRODUCTION" and current_chapter is intro_ch:
            continue

        # Skip footnote/endnote lines: [1] Some citation...
        if FOOTNOTE_RE.match(t):
            continue

        # Everything else at this point is a section heading
        sec = Section(title=t, chapter=current_chapter.title)
        current_chapter.sections.append(sec)
        current_section = sec

    _commit_chapter()
    return doc


@lru_cache(maxsize=1)
def _get_document() -> Document:
    response = httpx.get(ENCYCLICAL_URL, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return _parse(response.text)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _find_section(query: str, doc: Document) -> Section | None:
    sections = doc.all_sections()
    best = max(sections, key=lambda s: _similarity(query, s.title), default=None)
    if best and _similarity(query, best.title) >= 0.4:
        return best
    # Fallback: substring match
    q = query.lower()
    for sec in sections:
        if q in sec.title.lower():
            return sec
    return None


mcp = FastMCP("Magnifica Humanitas")


@mcp.tool()
def list_structure() -> str:
    """Return the full table of contents: chapters and their sections."""
    doc = _get_document()
    lines = ["# Magnifica Humanitas — Structure", ""]
    for ch in doc.chapters:
        lines.append(f"## Chapter {ch.number}: {ch.title}")
        for sec in ch.sections:
            para_range = ""
            if sec.paragraphs:
                lo, hi = sec.paragraphs[0].number, sec.paragraphs[-1].number
                para_range = f" [§{lo}–§{hi}]"
            lines.append(f"  - {sec.title}{para_range}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_chapter(number: int) -> str:
    """Get the full text of a chapter by its number (1–5)."""
    doc = _get_document()
    matches = [ch for ch in doc.chapters if ch.number == number]
    if not matches:
        available = ", ".join(str(ch.number) for ch in doc.chapters)
        return f"Chapter {number} not found. Available chapters: {available}"
    return matches[0].full_text()


@mcp.tool()
def get_section(title: str) -> str:
    """Get the full text of a section by title (fuzzy match)."""
    doc = _get_document()
    sec = _find_section(title, doc)
    if sec is None:
        titles = [s.title for s in doc.all_sections()]
        return f"No section matching '{title}'. Available sections:\n" + "\n".join(
            f"  - {t}" for t in titles
        )
    return sec.full_text()


@mcp.tool()
def get_paragraph(number: int) -> str:
    """Get a specific numbered paragraph (§1–§75+)."""
    doc = _get_document()
    para = doc.paragraphs.get(number)
    if para is None:
        nums = sorted(doc.paragraphs.keys())
        return f"Paragraph {number} not found. Range: §{nums[0]}–§{nums[-1]}."
    return str(para)


@mcp.tool()
def search(query: str, limit: int = 8) -> str:
    """Search paragraphs for a word or phrase. Returns matching paragraphs with context."""
    doc = _get_document()
    q = query.lower()
    results: list[tuple[float, Paragraph]] = []

    for para in doc.paragraphs.values():
        text_lower = para.text.lower()
        if q in text_lower:
            # Score by density of occurrences
            score = text_lower.count(q) / max(len(text_lower), 1)
            results.append((score, para))

    if not results:
        return f"No paragraphs found containing '{query}'."

    results.sort(key=lambda x: -x[0])
    lines = [f"# Search results for '{query}' ({min(len(results), limit)} of {len(results)} matches)", ""]
    for _, para in results[:limit]:
        lines.append(str(para))
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
