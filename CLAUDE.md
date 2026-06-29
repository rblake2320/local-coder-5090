# Local Coder 5090 — Claude Code Instructions

## What this project is
On-device coding loop for RTX 5090 / Windows 11 using Ollama as the model backend.
Ported from the DGX Spark implementation (Qwen3-Coder-Next 80B / llama.cpp).

## Key files
- `scripts/local_coder_browser.py` — HTTP server, all handlers, embedded UI (~3400 lines)
- `mcp/arcade/server.py` — MCP tool arcade (35 tools)
- `ops/daily_control_win.py` — Windows service / GPU control
- `install-service.ps1` — NSSM service installer

## Commands
```powershell
# Dev server (opens browser at :8022)
python scripts\local_coder_browser.py

# Status check
python scripts\local_coder_cli.py status

# Service install (Admin PS)
.\install-service.ps1

# GPU / service status
python ops\daily_control_win.py status
python ops\daily_control_win.py impact
```

## Architecture
```
Browser (:8022)
  └── post_model(payload, fast=False)
        ├── fast=True  → FAST_MODEL (gemma3:latest) via Ollama :11434
        └── fast=False → MODEL (deepseek-r1:32b) via Ollama :11434
```

## Critical differences from Spark original
1. **Health check**: Use `/api/tags` not `/health` — Ollama has no `/health` endpoint
2. **Model field**: Ollama requires `model` field in every request — `post_model()` always sends it
3. **Backend**: `MODEL_BASE = "http://localhost:11434"` — not `http://127.0.0.1:8012`
4. **python3 → python**: All subprocess calls use `python` not `python3`
5. **Paths**: `C:/Users/techai/local-coder/...` not `/home/rblake2320/ai-business/...`

## Context modes (scaled for 32 GB VRAM)
| Mode | Tokens | Use |
|------|--------|-----|
| fast | 32k | Quick Q&A, tool calls |
| repo | 65k | File-level context |
| deep | 131k | Full-repo analysis |

## Development notes
- The main server is stdlib only (no FastAPI). `ThreadingHTTPServer` + `BaseHTTPRequestHandler`.
- `post_model(payload, fast=True)` routes to gemma3. `fast=False` → deepseek-r1.
- Training flywheel: every chat logged to `C:/Users/techai/local-coder/flywheel/mcp_YYYYMMDD.jsonl`
- Bug #9 (specialist factory refactor) is the main remaining cleanup task.

## Bug fix status (10 from code review)
All 10 merged into mcp/arcade/server.py. See README.md table for details.
