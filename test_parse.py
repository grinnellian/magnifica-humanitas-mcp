"""Smoke test: fetch and parse the encyclical, print structure summary."""

import sys
sys.path.insert(0, "src")

from magnifica_humanitas_mcp.server import _get_document, list_structure, get_paragraph, search

print("Fetching and parsing...")
doc = _get_document()

print(f"\nChapters: {len(doc.chapters)}")
for ch in doc.chapters:
    sections = len(ch.sections)
    paras = sum(len(s.paragraphs) for s in ch.sections)
    print(f"  Ch {ch.number}: {ch.title!r} — {sections} sections, {paras} paragraphs")

print(f"\nTotal paragraphs indexed: {len(doc.paragraphs)}")
print(f"Paragraph range: §{min(doc.paragraphs)} – §{max(doc.paragraphs)}")

print("\n--- list_structure() ---")
print(list_structure())

print("\n--- get_paragraph(1) ---")
print(get_paragraph(1))

print("\n--- search('artificial intelligence', limit=3) ---")
print(search("artificial intelligence", limit=3))
