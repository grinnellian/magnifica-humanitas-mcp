FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY README.md .

RUN pip install -e .

EXPOSE 8000

CMD ["magnifica-humanitas-mcp"]
