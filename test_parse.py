"""Smoke test: fetch and parse the encyclical, print structure summary."""

import sys
sys.path.insert(0, "src")

from magnifica_humanitas_mcp.server import _get_document, list_structure, get_paragraph, get_footnote, search

print("Fetching and parsing...")
doc = _get_document()

print(f"\nChapters: {len(doc.chapters)}")
for ch in doc.chapters:
    sections = len(ch.sections)
    paras = sum(len(s.paragraphs) for s in ch.sections)
    print(f"  Ch {ch.number}: {ch.title!r} — {sections} sections, {paras} paragraphs")

print(f"\nTotal paragraphs indexed: {len(doc.paragraphs)}")
print(f"Paragraph range: §{min(doc.paragraphs)} – §{max(doc.paragraphs)}")
print(f"Footnotes indexed: {len(doc.footnotes)} (range [{min(doc.footnotes)}]–[{max(doc.footnotes)}])")

# Check footnote refs on a paragraph
para_with_refs = [(n, p) for n, p in doc.paragraphs.items() if p.footnote_refs]
print(f"Paragraphs with footnote refs: {len(para_with_refs)}")

print("\n--- get_paragraph(1) ---")
print(get_paragraph(1))

print("\n--- get_footnote(1) ---")
print(get_footnote(1))

print("\n--- get_paragraph with inline links (para 30, has Vatican links) ---")
print(get_paragraph(30))

print("\n--- get_footnote with links ---")
# Find a footnote that has links
fn_with_links = next((fn for fn in sorted(doc.footnotes.values(), key=lambda f: f.number) if fn.links), None)
if fn_with_links:
    print(get_footnote(fn_with_links.number))

print("\n--- search('artificial intelligence', limit=2) ---")
print(search("artificial intelligence", limit=2))
