# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python MCP server that fetches and parses Pope Leo XIV's 2026 encyclical *Magnifica Humanitas* from the Vatican website, exposing it as navigable tools for LLM clients. The encyclical has 245 numbered paragraphs across 5 chapters plus an introduction.

## Commands

```bash
# Build and run smoke test (always use Docker, not host pip)
docker build -t magnifica-mcp .
docker run --rm -v $(pwd)/test_parse.py:/app/test_parse.py magnifica-mcp python test_parse.py

# Run the MCP server
docker run --rm magnifica-mcp
```

## Architecture

`src/magnifica_humanitas_mcp/server.py` is the entire implementation:

- **Fetching**: `httpx.get` against the Vatican URL, cached via `@lru_cache(maxsize=1)` on `_get_document()` so the network hit happens once per process lifetime.
- **Parsing** (`_parse`): walks all `<p>` tags as plain text — the Vatican HTML has no structural CSS classes or anchor attributes. Skips the ToC block (first ~20 paragraphs) by finding the second occurrence of "INTRODUCTION". State machine tracks chapter/section/paragraph transitions; footnotes (`[N] text`) are filtered by `FOOTNOTE_RE`. Multi-line chapter titles (Chapters 3 and 4 each have two title lines) are accumulated into `title_parts` and joined.
- **Tools**: `list_structure`, `get_chapter`, `get_section` (fuzzy title match via `SequenceMatcher`), `get_paragraph`, `search`.

The document structure is: Introduction (virtual chapter 0, §1–§16) → Chapters 1–5 (§17–§245), each subdivided into named sections. Some sections are header-only (0 paragraphs) — they introduce sub-groups of sections within a chapter and are accurate to the source.
