"""MCP server for Magnifica Humanitas — Pope Leo XIV's 2026 encyclical on AI and the human person."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from mcp.server.fastmcp import FastMCP

ENCYCLICAL_URL = (
    "https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/"
    "20260515-magnifica-humanitas.html"
)

CHAPTER_HEADER_RE = re.compile(r"^CHAPTER\s+(ONE|TWO|THREE|FOUR|FIVE)$", re.I)
PARA_RE = re.compile(r"^(\d+)\.\s+(.*)", re.DOTALL)
FTNREF_HREF_RE = re.compile(r"#_ftn(\d+)$")   # href="#_ftn1" in body paragraphs
FTNNAME_RE = re.compile(r"^_ftn(\d+)$")        # name="_ftn1" in endnote anchors
WORD_TO_INT = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Footnote:
    number: int
    text: str                            # plain text of the citation
    links: list[tuple[str, str]] = field(default_factory=list)  # (label, url)

    def __str__(self) -> str:
        parts = [f"[{self.number}] {self.text}"]
        if self.links:
            parts.append("Links:")
            parts.extend(f"  {label}: {url}" for label, url in self.links)
        return "\n".join(parts)


@dataclass
class Paragraph:
    number: int
    text: str                            # rich text: [N] refs + "label [url]" links
    section: str
    chapter: str
    footnote_refs: list[int] = field(default_factory=list)

    def __str__(self) -> str:
        s = f"[§{self.number}] ({self.chapter} › {self.section})\n{self.text}"
        if self.footnote_refs:
            s += f"\n\nFootnotes cited: {', '.join(f'[{n}]' for n in self.footnote_refs)}"
        return s


@dataclass
class Section:
    title: str
    chapter: str
    paragraphs: list[Paragraph] = field(default_factory=list)

    def full_text(self) -> str:
        lines = [f"{self.chapter} › {self.title}", ""]
        lines.extend(str(p) for p in self.paragraphs)
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
            lines.extend(str(p) for p in sec.paragraphs)
            lines.append("")
        return "\n\n".join(lines)


@dataclass
class Document:
    chapters: list[Chapter] = field(default_factory=list)
    paragraphs: dict[int, Paragraph] = field(default_factory=dict)
    footnotes: dict[int, Footnote] = field(default_factory=dict)

    def all_sections(self) -> list[Section]:
        return [sec for ch in self.chapters for sec in ch.sections]


# ---------------------------------------------------------------------------
# HTML extraction helpers
# ---------------------------------------------------------------------------

def _plain_text(elem: Tag) -> str:
    """Plain text for structure detection — strips all tags."""
    for sup in elem.find_all("sup"):
        sup.decompose()
    return re.sub(r"\s+", " ", elem.get_text(" ", strip=True)).strip()


def _rich_text(elem: Tag) -> str:
    """Text preserving footnote refs as [N] and absolute links as 'label [url]'."""
    parts: list[str] = []

    def walk(node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            parts.append(str(node))
            return
        if node.name == "sup":
            return  # skip superscripts (not footnote refs — those are <a> tags)
        if node.name == "a":
            href = node.get("href", "")
            label = node.get_text()
            if href.startswith("http"):
                parts.append(f"{label} [{href}]")
            else:
                parts.append(label)  # internal anchor ([N] footnote ref)
            return
        for child in node.children:
            walk(child)

    walk(elem)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _footnote_refs(elem: Tag) -> list[int]:
    """Extract footnote numbers from <a href="#_ftnN"> elements in a paragraph."""
    refs = []
    for a in elem.find_all("a", href=FTNREF_HREF_RE):
        m = FTNREF_HREF_RE.search(a["href"])
        if m:
            refs.append(int(m.group(1)))
    return refs


def _parse_footnote(p: Tag) -> Footnote | None:
    """Parse a MsoFootnoteText <p> into a Footnote."""
    anchor = p.find("a", attrs={"name": FTNNAME_RE})
    if not anchor:
        return None
    m = FTNNAME_RE.match(anchor.get("name", ""))
    if not m:
        return None
    number = int(m.group(1))

    links = [
        (a.get_text().strip(), a["href"])
        for a in p.find_all("a", href=True)
        if a["href"].startswith("http")
    ]

    text = _rich_text(p)
    text = re.sub(r"^\[\d+\]\s*", "", text)  # strip leading [N] from endnote text
    return Footnote(number=number, text=text, links=links)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse(html: str) -> Document:
    soup = BeautifulSoup(html, "lxml")
    all_ps = soup.find_all("p")

    doc = Document()

    # Collect footnotes from MsoFootnoteText paragraphs
    content_ps: list[Tag] = []
    for p in all_ps:
        classes = p.get("class") or []
        if "MsoFootnoteText" in classes:
            fn = _parse_footnote(p)
            if fn:
                doc.footnotes[fn.number] = fn
        else:
            content_ps.append(p)

    # Build (plain_text, original_tag) pairs for the content paragraphs
    tagged = [(_plain_text(p), p) for p in content_ps]

    # Skip the ToC block: find the second "INTRODUCTION" (first is in the ToC)
    content_start = 0
    intro_seen = 0
    for i, (t, _) in enumerate(tagged):
        if t == "INTRODUCTION":
            intro_seen += 1
            if intro_seen >= 2:
                content_start = i
                break

    # Intro is a virtual chapter 0 (no "CHAPTER N" marker in the document)
    intro_ch = Chapter(number=0, title="Introduction")
    doc.chapters.append(intro_ch)
    intro_sec = Section(title="Introduction", chapter="Introduction")
    intro_ch.sections.append(intro_sec)
    current_chapter: Chapter = intro_ch
    current_section: Section = intro_sec

    pending_num: int | None = None
    title_parts: list[str] = []

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

    for t, p in tagged[content_start:]:
        if not t:
            continue

        m_ch = CHAPTER_HEADER_RE.match(t)
        if m_ch:
            _commit_chapter()
            pending_num = WORD_TO_INT[m_ch.group(1).lower()]
            continue

        m_para = PARA_RE.match(t)
        if m_para:
            _commit_chapter()
            num = int(m_para.group(1))
            # Use rich text for content; strip the leading "N. " prefix
            content = re.sub(r"^\d+\.\s*", "", _rich_text(p))
            refs = _footnote_refs(p)
            para = Paragraph(num, content, current_section.title, current_chapter.title, refs)
            current_section.paragraphs.append(para)
            doc.paragraphs[num] = para
            continue

        if pending_num is not None:
            title_parts.append(t)
            continue

        if t == "INTRODUCTION" and current_chapter is intro_ch:
            continue

        sec = Section(title=t, chapter=current_chapter.title)
        current_chapter.sections.append(sec)
        current_section = sec

    _commit_chapter()
    return doc


# ---------------------------------------------------------------------------
# Cache + helpers
# ---------------------------------------------------------------------------

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
    q = query.lower()
    for sec in sections:
        if q in sec.title.lower():
            return sec
    return None


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

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
    """Get a specific numbered paragraph (§1–§245) with its footnote references."""
    doc = _get_document()
    para = doc.paragraphs.get(number)
    if para is None:
        nums = sorted(doc.paragraphs.keys())
        return f"Paragraph {number} not found. Range: §{nums[0]}–§{nums[-1]}."
    return str(para)


@mcp.tool()
def get_footnote(number: int) -> str:
    """Get the text and links of a specific footnote by number."""
    doc = _get_document()
    fn = doc.footnotes.get(number)
    if fn is None:
        nums = sorted(doc.footnotes.keys())
        return f"Footnote {number} not found. Range: [{nums[0]}]–[{nums[-1]}]."
    return str(fn)


@mcp.tool()
def search(query: str, limit: int = 8) -> str:
    """Search paragraphs for a word or phrase. Returns matching paragraphs with context."""
    doc = _get_document()
    q = query.lower()
    results: list[tuple[float, Paragraph]] = []

    for para in doc.paragraphs.values():
        text_lower = para.text.lower()
        if q in text_lower:
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
