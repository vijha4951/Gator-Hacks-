# gator-hacks

A hackathon project built with **FastAPI**, the **Model Context Protocol (MCP)**, and **OpenAI**.

## Quick start

```bash
# Create and activate the virtual environment
uv venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# Sync dependencies (including dev tools)
uv sync --dev

# Run the CLI
gator-hacks

# Run the FastAPI server
uvicorn gator_hacks.server:app --reload
```

## Project layout

```
src/gator_hacks/
  __init__.py   # package entry point
  cli.py        # CLI entry point (`gator-hacks` command)
  server.py     # FastAPI application
```

## License

Private project — all rights reserved.
