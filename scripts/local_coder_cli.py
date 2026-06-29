#!/usr/bin/env python3
"""Local Coder CLI — send tasks to the Local Coder 5090 HTTP server."""

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

BASE_URL = "http://127.0.0.1:8022"


def post_json(path: str, payload: dict) -> dict:
    req = Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=1800) as resp:
        return json.loads(resp.read())


def get_json(path: str) -> dict:
    with urlopen(f"{BASE_URL}{path}", timeout=10) as resp:
        return json.loads(resp.read())


def cmd_status(_: argparse.Namespace) -> None:
    result = get_json("/status")
    print(json.dumps(result, indent=2))


def cmd_chat(args: argparse.Namespace) -> None:
    payload = {
        "prompt": args.prompt,
        "project_path": args.project or "",
        "context_mode": args.mode,
        "max_tokens": args.max_tokens,
    }
    result = post_json("/chat", payload)
    if "response" in result:
        print(result["response"])
    else:
        print(json.dumps(result, indent=2))


def cmd_loop(args: argparse.Namespace) -> None:
    patch_text = ""
    if args.patch:
        patch_text = Path(args.patch).read_text(encoding="utf-8")
    payload = {
        "task": args.task,
        "cwd": args.cwd or str(Path.cwd()),
        "patch": patch_text,
        "apply": args.apply,
        "context_mode": args.mode,
    }
    result = post_json("/coding/loop", payload)
    print(json.dumps(result, indent=2))


def cmd_patch(args: argparse.Namespace) -> None:
    patch_text = Path(args.file).read_text(encoding="utf-8")
    payload = {
        "patch": patch_text,
        "cwd": args.cwd or str(Path.cwd()),
        "title": args.title or Path(args.file).stem,
        "apply": args.apply,
    }
    result = post_json("/patch", payload)
    print(json.dumps(result, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Coder 5090 CLI")
    parser.add_argument("--base-url", default=BASE_URL)
    sub = parser.add_subparsers(dest="cmd", required=True)

    # status
    sub.add_parser("status", help="Show server + model status")

    # chat
    p_chat = sub.add_parser("chat", help="Send a chat prompt")
    p_chat.add_argument("prompt")
    p_chat.add_argument("--project", "-p", default="")
    p_chat.add_argument("--mode", choices=["fast", "repo", "deep"], default="fast")
    p_chat.add_argument("--max-tokens", type=int, default=1024)

    # loop
    p_loop = sub.add_parser("loop", help="Run coding loop (patch → compile → test)")
    p_loop.add_argument("task")
    p_loop.add_argument("--patch", help="Path to .diff/.patch file")
    p_loop.add_argument("--cwd", default="")
    p_loop.add_argument("--apply", action="store_true")
    p_loop.add_argument("--mode", choices=["fast", "repo", "deep"], default="repo")

    # patch
    p_patch = sub.add_parser("patch", help="Check or apply a diff file")
    p_patch.add_argument("file", help="Path to unified diff file")
    p_patch.add_argument("--cwd", default="")
    p_patch.add_argument("--title", default="")
    p_patch.add_argument("--apply", action="store_true")

    args = parser.parse_args()
    global BASE_URL
    BASE_URL = args.base_url

    dispatch = {"status": cmd_status, "chat": cmd_chat, "loop": cmd_loop, "patch": cmd_patch}
    try:
        dispatch[args.cmd](args)
        return 0
    except (HTTPError, URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
