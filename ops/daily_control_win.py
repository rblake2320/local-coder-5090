#!/usr/bin/env python3
"""Windows service / process control for Local Coder 5090.

Replaces the Spark/systemd daily_control.py with Windows equivalents:
  - Service management via NSSM / sc.exe
  - Process management via psutil
  - Ollama model management via HTTP API
  - nvidia-smi for GPU stats (works on Windows too)

Usage:
  python ops/daily_control_win.py status
  python ops/daily_control_win.py impact
  python ops/daily_control_win.py start LocalCoder
  python ops/daily_control_win.py stop  LocalCoder
  python ops/daily_control_win.py model-mode status
  python ops/daily_control_win.py model-mode on
  python ops/daily_control_win.py model-mode off
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

NSSM = Path(r"D:\tools\nssm\nssm.exe")
OLLAMA_BASE = "http://localhost:11434"
LOCAL_CODER_SERVICE = "LocalCoder"
SERVICE_NAMES = [LOCAL_CODER_SERVICE, "OllamaService"]


# ── helpers ───────────────────────────────────────────────────────────────────

def run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, **kw)


def nssm_status(service: str) -> str:
    if not NSSM.exists():
        return "nssm_not_found"
    r = run([str(NSSM), "status", service])
    return r.stdout.strip() or r.stderr.strip() or "unknown"


def sc_status(service: str) -> str:
    r = run(["sc", "query", service])
    for line in r.stdout.splitlines():
        if "STATE" in line:
            return line.split(":", 1)[-1].strip()
    return "not_found"


def ollama_get(path: str) -> dict[str, Any] | None:
    try:
        req = Request(f"{OLLAMA_BASE}{path}")
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def gpu_stats() -> dict[str, Any]:
    r = run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu",
        "--format=csv,noheader,nounits",
    ])
    if r.returncode != 0:
        return {"error": "nvidia-smi not available"}
    fields = [f.strip() for f in r.stdout.strip().split(",")]
    keys = ["name", "mem_total_mb", "mem_used_mb", "mem_free_mb", "temp_c", "util_pct"]
    return dict(zip(keys, fields, strict=False))


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_status() -> dict[str, Any]:
    tags = ollama_get("/api/tags")
    models_loaded = [m["name"] for m in (tags.get("models") or [])] if tags else []

    services = {}
    for svc in SERVICE_NAMES:
        services[svc] = nssm_status(svc) if NSSM.exists() else sc_status(svc)

    return {
        "ollama": "ok" if tags else "unreachable",
        "models_loaded": models_loaded,
        "services": services,
        "gpu": gpu_stats(),
    }


def cmd_impact() -> dict[str, Any]:
    status = cmd_status()
    gpu = status.get("gpu", {})
    mem_used = int(gpu.get("mem_used_mb") or 0)
    mem_total = int(gpu.get("mem_total_mb") or 1)
    return {
        **status,
        "vram_pct": round(100 * mem_used / mem_total, 1) if mem_total else None,
        "recommendation": (
            "ok: VRAM under 80%"
            if mem_used / max(mem_total, 1) < 0.8
            else "warning: VRAM over 80%, consider unloading idle models"
        ),
    }


def cmd_start(service: str) -> dict[str, Any]:
    if NSSM.exists():
        r = run([str(NSSM), "start", service])
    else:
        r = run(["sc", "start", service])
    return {"service": service, "action": "start", "output": r.stdout.strip() or r.stderr.strip()}


def cmd_stop(service: str, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"service": service, "action": "stop_dry_run", "status": nssm_status(service)}
    if NSSM.exists():
        r = run([str(NSSM), "stop", service])
    else:
        r = run(["sc", "stop", service])
    return {"service": service, "action": "stop", "output": r.stdout.strip() or r.stderr.strip()}


def cmd_model_mode(mode: str) -> dict[str, Any]:
    tags = ollama_get("/api/tags")
    loaded = [m["name"] for m in (tags.get("models") or [])] if tags else []

    if mode == "status":
        return {"model_mode": "on" if loaded else "off", "models": loaded}

    if mode == "off":
        # Unload all models by requesting with keep_alive=0
        results = []
        for model in loaded:
            try:
                payload = json.dumps({"model": model, "keep_alive": 0}).encode()
                req = Request(
                    f"{OLLAMA_BASE}/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=15):
                    pass
                results.append({"model": model, "unloaded": True})
            except Exception as exc:
                results.append({"model": model, "error": str(exc)})
        return {"model_mode": "off", "results": results}

    if mode == "on":
        # Pre-load the primary model by sending an empty generate.
        # Keep in sync with local_coder_browser.py MODEL default.
        model = os.environ.get("LOCAL_CODER_MODEL", "qwen3:32b")
        try:
            payload = json.dumps({"model": model, "prompt": "", "stream": False}).encode()
            req = Request(
                f"{OLLAMA_BASE}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=120):
                pass
            return {"model_mode": "on", "model": model, "loaded": True}
        except Exception as exc:
            return {"model_mode": "on", "model": model, "error": str(exc)}

    return {"error": f"unknown mode: {mode}"}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Local Coder 5090 — Windows service control")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status")
    sub.add_parser("impact")

    p_start = sub.add_parser("start")
    p_start.add_argument("service", nargs="?", default=LOCAL_CODER_SERVICE)

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("service", nargs="?", default=LOCAL_CODER_SERVICE)
    p_stop.add_argument("--apply", action="store_true")

    p_mm = sub.add_parser("model-mode")
    p_mm.add_argument("mode", choices=["status", "on", "off"])

    args = parser.parse_args()

    if args.cmd == "status":
        result = cmd_status()
    elif args.cmd == "impact":
        result = cmd_impact()
    elif args.cmd == "start":
        result = cmd_start(args.service)
    elif args.cmd == "stop":
        result = cmd_stop(args.service, dry_run=not args.apply)
    elif args.cmd == "model-mode":
        result = cmd_model_mode(args.mode)
    else:
        parser.print_help()
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
