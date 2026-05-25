# magnifica-humanitas-mcp

An MCP server for navigating *[Magnifica Humanitas](https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/20260515-magnifica-humanitas.html)* — Pope Leo XIV's 2026 encyclical on safeguarding the human person in the time of artificial intelligence.

Fetches the document live from the Vatican website and exposes it as structured MCP tools, so any LLM client can navigate the text without loading all ~80 paragraphs into context at once.

## Tools

| Tool | Description |
|------|-------------|
| `list_structure()` | Full table of contents with paragraph ranges |
| `get_chapter(number)` | Full text of a chapter (1–5) |
| `get_section(title)` | Full text of a section by title (fuzzy match) |
| `get_paragraph(number)` | A single numbered paragraph |
| `search(query, limit)` | Find paragraphs containing a word or phrase |

## Usage

### With `uvx` (no install needed)

```bash
uvx magnifica-humanitas-mcp
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "magnifica-humanitas": {
      "command": "uvx",
      "args": ["magnifica-humanitas-mcp"]
    }
  }
}
```

### Claude Code (this project)

```bash
claude mcp add magnifica-humanitas -- uvx magnifica-humanitas-mcp
```

### Docker

```bash
docker build -t magnifica-humanitas-mcp .
docker run --rm magnifica-humanitas-mcp
```

## License

The MCP server code is MIT licensed. The encyclical text is © Copyright Dicastery for Communication – Libreria Editrice Vaticana. This tool fetches that content from the Vatican's website at runtime and does not redistribute it.

## Development

```bash
pip install -e .
python test_parse.py        # smoke test against live Vatican URL
magnifica-humanitas-mcp     # run the MCP server
```
