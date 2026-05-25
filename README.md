# magnifica-humanitas-mcp

<!-- mcp-name: io.github.grinnellian/magnifica-humanitas-mcp -->

An MCP server for navigating *[Magnifica Humanitas](https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/20260515-magnifica-humanitas.html)* — Pope Leo XIV's 2026 encyclical on safeguarding the human person in the time of artificial intelligence.

Fetches the document live from the Vatican website and exposes it as structured MCP tools, so any LLM client can navigate the text without loading all 245 paragraphs into context at once.

## Tools

| Tool | Description |
|------|-------------|
| `list_structure()` | Full table of contents with paragraph ranges |
| `get_chapter(number)` | Full text of a chapter (1–5) |
| `get_section(title)` | Full text of a section by title (fuzzy match) |
| `get_paragraph(number)` | A single numbered paragraph |
| `search(query, limit)` | Find paragraphs containing a word or phrase |

## Usage

### With `npx` (no install needed)

```bash
npx magnifica-humanitas-mcp
```

### With `uvx` (requires [uv](https://docs.astral.sh/uv/getting-started/installation/))

```bash
uvx magnifica-humanitas-mcp
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "magnifica-humanitas": {
      "command": "npx",
      "args": ["-y", "magnifica-humanitas-mcp"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add magnifica-humanitas -- npx -y magnifica-humanitas-mcp
```

### Docker

```bash
docker run --rm grimalkinllc/magnifica-humanitas-mcp
```

## License

The MCP server code is MIT licensed. The encyclical text is © Copyright Dicastery for Communication – Libreria Editrice Vaticana. This tool fetches that content from the Vatican's website at runtime and does not redistribute it.

## Development

```bash
docker build -t magnifica-mcp .
docker run --rm -v $(pwd)/test_parse.py:/app/test_parse.py magnifica-mcp python test_parse.py
docker run --rm magnifica-mcp
```

## Releasing

Bump the version in `pyproject.toml`, `package.json`, and `server.json`, then:

```bash
git commit -am "Bump to X.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

This triggers a single GitHub Actions workflow that publishes to npm, PyPI, Docker Hub (amd64 + arm64), and the MCP Registry.
