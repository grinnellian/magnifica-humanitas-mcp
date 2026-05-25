# Contributing

## Development

All builds and tests run in Docker — no host-level Python or Node required.

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

A local publish script is also available as a fallback:

```bash
NPM_TOKEN=xxx PYPI_TOKEN=xxx ./scripts/publish-local.sh
```
