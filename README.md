# Local Coder 5090

On-device coding assistant for RTX 5090 / Windows 11 — ported from the DGX Spark (Qwen3-Coder-Next 80B / llama.cpp) to Ollama.

## What it is

A zero-cloud, zero-API-key coding loop running entirely on local hardware:

```
Browser UI → local_coder_browser.py :8022 → Ollama :11434 → deepseek-r1:32b
```

Same architecture as the Spark version:
- `python stdlib http.server` — no FastAPI, no extra deps
- `POST /chat` for inference
- `POST /coding/loop` — patch → `git apply --check` → `py_compile` → `pytest`
- `POST /tools/run` — allowlisted shell tools
- `POST /patch` — check or apply unified diffs
- Training flywheel — every interaction logged to daily JSONL for future fine-tuning
- Per-project JSON memory
- MCP arcade server (35 tools) in `mcp/arcade/server.py`

## Hardware

| Component | Spec |
|-----------|------|
| GPU       | RTX 5090 32 GB VRAM |
| RAM       | 128 GB |
| OS        | Windows 11 |
| Python    | 3.12 |
| Backend   | Ollama (OpenAI-compat endpoint) |

## Models

| Role | Model | VRAM | Speed |
|------|-------|------|-------|
| Primary (coding + reasoning) | `deepseek-r1:32b` | ~20 GB | ~30 s/response |
| Fast tier (quick completions) | `gemma3:latest` | ~7 GB | <1 s |
| Heavy (long-context analysis) | `llama3.1:70b` | ~28 GB | ~60 s |

Pull models:
```
ollama pull deepseek-r1:32b
ollama pull gemma3
```

## Quick start

```powershell
# 1. Clone
git clone https://github.com/rblake2320/local-coder-5090.git
cd local-coder-5090

# 2. Create workspace dir
mkdir C:\Users\techai\local-coder\workspace

# 3. Run (dev mode, opens browser)
python scripts\local_coder_browser.py

# 4. Or install as Windows service (Admin PowerShell)
.\install-service.ps1
```

Open `http://127.0.0.1:8022/` in your browser.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LOCAL_CODER_MODEL_BASE` | `http://localhost:11434` | Ollama base URL |
| `LOCAL_CODER_MODEL` | `deepseek-r1:32b` | Primary model |
| `LOCAL_CODER_FAST_MODEL` | `gemma3:latest` | Fast tier model |
| `LOCAL_CODER_HOME` | `C:\Users\techai\local-coder` | Root workspace |
| `LOCAL_CODER_WORKSPACE` | `$HOME\workspace` | Project workspace |
| `LOCAL_MODEL_URL` | `http://localhost:11434/v1/chat/completions` | Direct model URL |
| `LOCAL_MODEL_URL_2` | *(none)* | Second Ollama instance |

## CLI

```powershell
# Status
python scripts\local_coder_cli.py status

# Chat
python scripts\local_coder_cli.py chat "explain this function"

# Coding loop
python scripts\local_coder_cli.py loop "fix the failing test" --patch fix.diff --apply

# Apply a patch
python scripts\local_coder_cli.py patch my_change.diff --cwd C:\my-project --apply
```

## Service management

```powershell
# Install
.\install-service.ps1

# Uninstall
.\install-service.ps1 -Uninstall

# Control
D:\tools\nssm\nssm.exe start LocalCoder
D:\tools\nssm\nssm.exe stop  LocalCoder

# Status / GPU
python ops\daily_control_win.py status
python ops\daily_control_win.py impact

# Unload all models (free VRAM)
python ops\daily_control_win.py model-mode off

# Pre-load primary model
python ops\daily_control_win.py model-mode on
```

## Differences from Spark version

| | Spark (DGX GB10) | 5090 (Windows) |
|--|---|---|
| Model | Qwen3-Coder-Next 80B | deepseek-r1:32b |
| Backend | llama.cpp :8012 | Ollama :11434 |
| Fast tier | llama3.1:70b | gemma3:latest |
| Health check | `/health` | `/api/tags` |
| Service mgmt | systemd | NSSM |
| Python cmd | `python3` | `python` |
| Workspace | `/home/rblake2320/...` | `C:/Users/techai/...` |
| Deep context | 262k tokens | 131k tokens (32 GB VRAM) |

## Bug fixes vs original (from code review)

| # | Location | Fix |
|---|----------|-----|
| 1 | `_try_nvidia` | Returns `None` on HTTP error (was truthy error string; callers check `if result:`) |
| 2 | `ocr_extract_text` | Actually sends base64 image data in the model prompt |
| 3 | `has_corrections` | Changed `OR` to `AND`; old logic was almost always True |
| 4 | `call_bedrock_sync` | Wrapped in `run_in_executor` so it doesn't block the event loop |
| 5 | `try_local_inference` | Guards against missing `choices[]`; logs structural errors instead of silently swallowing |
| 6 | `FlywheelCollector.collect` | Single `datetime.now()` call so timestamp and filename can't be different days |
| 7 | `local_coder_tool_chat` | `isinstance(item, dict)` guard prevents double-wrapping tools |
| 8 | `list_specialists` | Guards against prompts with no second line after `Expertise:` header |
| 9 | Specialist functions | *(refactor pending — 8 copy-paste specialists → factory loop)* |
| 10 | `LOCAL_MODEL_URL_2` | Removed hardcoded `spark2` hostname; requires explicit `$env:LOCAL_MODEL_URL_2` |

## Project structure

```
local-coder-5090/
├── scripts/
│   ├── local_coder_browser.py   # Main HTTP server (3400+ lines)
│   └── local_coder_cli.py       # CLI wrapper
├── mcp/arcade/server.py         # 35 MCP tools
├── ops/
│   ├── daily_control_win.py     # Windows service control
│   └── daily_services_win.json  # Ollama model registry
├── local_coder/__init__.py      # Package constants
├── config/
│   ├── local_coder_provider.json
│   └── hermes_local_coder_fragment.yaml
├── install-service.ps1          # NSSM service installer
└── CLAUDE.md
```
