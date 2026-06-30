# Local Coder 5090 — Project Instructions

## What This Project Is
You ARE this server. `local_coder_browser.py` is your body — a single 4500+ line stdlib-only
Python HTTP server that handles all chat, tools, routing, and the embedded UI.
You run on RTX 5090, qwen3:32b via Ollama at localhost:11434.

## Key Files
- `scripts/local_coder_browser.py` — entire server (HTML + all handlers + business logic)
- `C:\Users\techai\selfconnect-sdk\` — Win32 SDK for controlling desktop apps
- Workspace: `C:\Users\techai\local-coder\workspace\`

## Architecture Rules
- **stdlib only** — no FastAPI, no external packages, no surprise deps
- `ThreadingHTTPServer + BaseHTTPRequestHandler` — one thread per request
- All new tools go in `run_safe_tool()` AND the `SAFE_COMMANDS` set at the top
- All new GET routes go in `do_GET()`, POST routes in `do_POST()`
- `enrich_messages()` builds every system prompt — add new context sources there
- `post_model()` handles provider routing: Ollama → OpenRouter → Bedrock → NIM

## Running the Server
```powershell
# Dev (opens browser)
python scripts\local_coder_browser.py

# No browser
python scripts\local_coder_browser.py --no-open

# Kill existing + restart
netstat -ano | findstr :8022
taskkill /PID <pid> /F
python scripts\local_coder_browser.py --no-open
```

## What You Can Call (Tools via /tools/run)
All tools in SAFE_COMMANDS set. Key ones:
- `git_status`, `git_diff`, `git_commit`, `git_push` — version control
- `pytest [path]` — run tests
- `bandit [path]` — Python security scan
- `mypy [path]` — type checking
- `pip_audit` — CVE scan Python deps
- `npm_audit` — CVE scan Node deps
- `semgrep [config] [path]` — multi-language SAST
- `eslint [path]` — JS/TS linting
- `cprofile [script]` — Python profiling
- `mem_profile [script]` — memory profiling
- `docker_run [image] [cmd]` — run containers
- `psql_query [sql]` — PostgreSQL queries
- `wsl_exec [cmd]` — Unix commands via WSL2
- `codegen [template] [dir]` — scaffold django/fastapi/react/flask/cli/github-action
- `sc_list_windows` — list all Windows desktop windows
- `sc_find [query]` — find a window by title/exe
- `sc_send [window] [text]` — inject text via PostMessage(WM_CHAR)
- `sc_capture [window]` — screenshot via PrintWindow
- `sc_read [window]` — read window text via UIA
- `sc_click [window] [x] [y]` — mouse click
- `sc_clipboard read|write [text]` — clipboard

## Provider Fallback Order
1. Ollama (qwen3:32b, local, zero latency)
2. OpenRouter (OPENROUTER_API_KEY set → qwen/qwen3-32b by default)
3. AWS Bedrock (claude-3-5-sonnet)
4. NVIDIA NIM

## Key Endpoints
- `GET /status` — health, model_ready, model_in_vram, vram_models
- `POST /chat` — main chat (accepts force_backend, force_model fields)
- `GET /instructions` — load LOCALCODER.md + global.md
- `POST /instructions` — save instructions
- `GET /kb` — list knowledge base files
- `POST /kb/save` — save KB file
- `GET /mcp/config` — get mcp-servers.json
- `POST /mcp/config` — save mcp-servers.json
- `POST /tools/run` — run any tool in SAFE_COMMANDS
- `GET /docker-mcp/catalog` — 311 Docker MCP servers
- `GET /docker-mcp/tools` — 11 enabled Docker MCP tools

## Critical DO NOTs
- Never use `python3` — use `python` or `sys.executable`
- Never write to D: drive for anything critical (hardware failing)
- Never add FastAPI, Flask, or any web framework — this is stdlib HTTP only
- Never commit API keys or credentials to the repo
- The server binds to 0.0.0.0:8022 — it's accessible on LAN

## Before Editing
1. Read the section you're changing — the file is 4500+ lines
2. `python -m py_compile scripts/local_coder_browser.py` after every edit
3. Restart server and curl /status to confirm it's up
