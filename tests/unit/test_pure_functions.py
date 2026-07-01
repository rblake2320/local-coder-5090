"""Offline unit tests for local_coder_browser.py pure functions.

Unlike tests/ops/test_local_coder_browser.py (which needs a live server + Ollama),
these import the module directly and exercise pure logic. They run anywhere:

    python -m pytest tests/unit/ -v

Environment paths are redirected to a temp dir BEFORE import so the module never
touches Windows-only or user-home locations during collection.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import pytest

# --- Redirect all filesystem roots to a throwaway temp dir before import -------
_TMP = Path(tempfile.mkdtemp(prefix="localcoder_test_"))
os.environ.setdefault("LOCAL_CODER_HOME", str(_TMP / "home"))
os.environ.setdefault("LOCAL_CODER_WORKSPACE", str(_TMP / "workspace"))
os.environ.setdefault("LOCAL_CODER_SKILL_GEN", str(_TMP / "skills"))

# --- Import the server module by path (scripts/ is not a package) -------------
_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "local_coder_browser", _ROOT / "scripts" / "local_coder_browser.py"
)
assert _SPEC and _SPEC.loader
lcb = importlib.util.module_from_spec(_SPEC)
sys.modules["local_coder_browser"] = lcb
_SPEC.loader.exec_module(lcb)


# ── safe_slug ─────────────────────────────────────────────────────────────────

def test_safe_slug_strips_unsafe_chars():
    assert lcb.safe_slug("hello world!@#") == "hello-world"


def test_safe_slug_empty_falls_back():
    assert lcb.safe_slug("") == "local-coder-output"
    assert lcb.safe_slug("///") == "local-coder-output"


def test_safe_slug_truncates_to_72():
    assert len(lcb.safe_slug("a" * 200)) == 72


def test_safe_slug_preserves_dots_and_dashes():
    assert lcb.safe_slug("v1.2.3-beta") == "v1.2.3-beta"


# ── safe_relative_path (path traversal guard) ─────────────────────────────────

@pytest.mark.parametrize("bad", ["../etc/passwd", "..", ".", "", "a/../../b"])
def test_safe_relative_path_rejects_traversal(bad):
    with pytest.raises(ValueError):
        lcb.safe_relative_path(bad)


def test_safe_relative_path_strips_leading_slash():
    # A leading slash is normalized away (lstrip), yielding a safe relative path
    # confined under the upload root — this is intended, not an escape.
    result = str(lcb.safe_relative_path("/abs/path")).replace("\\", "/")
    assert result == "abs/path"


def test_safe_relative_path_accepts_nested():
    assert str(lcb.safe_relative_path("src/app/main.py")).replace("\\", "/") == "src/app/main.py"


def test_safe_relative_path_normalizes_backslashes():
    # Windows-style separators should be accepted and normalized
    result = str(lcb.safe_relative_path("src\\app\\main.py")).replace("\\", "/")
    assert result == "src/app/main.py"


# ── upload_root (id validation + escape guard) ────────────────────────────────

@pytest.mark.parametrize("bad_id", ["short", "has space", "../escape", "a" * 200, "bad/slash"])
def test_upload_root_rejects_bad_ids(bad_id):
    with pytest.raises(ValueError):
        lcb.upload_root(bad_id)


def test_upload_root_accepts_valid_id():
    root = lcb.upload_root("2026-06-30_abc123XY")
    assert str(root).startswith(str(lcb.UPLOAD_DIR.resolve()))


# ── _assert_allowed_cwd (sandbox enforcement) ─────────────────────────────────

def test_assert_allowed_cwd_blocks_outside():
    with pytest.raises(ValueError):
        lcb._assert_allowed_cwd("/etc")


def test_assert_allowed_cwd_allows_workspace():
    lcb.WORKSPACE.mkdir(parents=True, exist_ok=True)
    resolved = lcb._assert_allowed_cwd(str(lcb.WORKSPACE))
    assert resolved == str(lcb.WORKSPACE.resolve())


def test_assert_allowed_cwd_defaults_to_ai_business():
    # None -> AI_BUSINESS root, which is always allowed
    resolved = lcb._assert_allowed_cwd(None)
    assert resolved == str(lcb.AI_BUSINESS)


# ── run_safe_tool (allowlist enforcement) ─────────────────────────────────────

def test_run_safe_tool_rejects_unknown_command():
    with pytest.raises(ValueError, match="tool not allowed"):
        lcb.run_safe_tool("rm_rf_everything")


def test_run_safe_tool_pwd_returns_workdir():
    lcb.WORKSPACE.mkdir(parents=True, exist_ok=True)
    result = lcb.run_safe_tool("pwd", cwd=str(lcb.WORKSPACE))
    assert result["returncode"] == 0
    assert result["stdout"].strip() == str(lcb.WORKSPACE.resolve())


def test_spark_exec_requires_node_and_command():
    result = lcb.run_safe_tool("spark_exec", args=["spark1"])
    assert result["returncode"] == 1
    assert "requires" in result["stderr"]


def test_spark_exec_unconfigured_node_errors_cleanly(monkeypatch):
    # No LOCAL_CODER_SSH_* set -> clear, non-crashing error (no hardcoded host)
    monkeypatch.delenv("LOCAL_CODER_SSH_SPARK1", raising=False)
    result = lcb.run_safe_tool("spark_exec", args=["spark1", "echo hi"])
    assert result["returncode"] == 1
    assert "LOCAL_CODER_SSH_SPARK1" in result["stderr"]


def test_spark_exec_missing_ssh_binary_errors_cleanly(monkeypatch, tmp_path):
    # Real subprocess failure, no mocks: point PATH at an empty dir so the OS
    # genuinely cannot find ssh (mirrors a Windows box without OpenSSH Client).
    # Must return clean JSON with guidance, not raise -> HTTP 500.
    monkeypatch.setenv("LOCAL_CODER_SSH_TESTNODE", "nobody@192.0.2.1")
    monkeypatch.setenv("PATH", str(tmp_path))
    result = lcb.run_safe_tool("spark_exec", args=["testnode", "echo hi"])
    assert result["returncode"] == 127
    assert "ssh client not found" in result["stderr"]


# ── parse_skill_frontmatter ───────────────────────────────────────────────────

def test_parse_frontmatter_extracts_fields():
    text = '---\nname: my-skill\ndescription: "does things"\n---\n\n# body'
    meta = lcb.parse_skill_frontmatter(text)
    assert meta["name"] == "my-skill"
    assert meta["description"] == "does things"


def test_parse_frontmatter_no_frontmatter_returns_empty():
    assert lcb.parse_skill_frontmatter("# just markdown") == {}


def test_parse_frontmatter_unterminated_returns_empty():
    assert lcb.parse_skill_frontmatter("---\nname: x\nno close") == {}


# ── _is_thinking_model ────────────────────────────────────────────────────────

@pytest.mark.parametrize("model", ["qwen3:32b", "deepseek-r1:32b", "qwq:latest", "qwen3.6:27b"])
def test_is_thinking_model_true(model):
    assert lcb._is_thinking_model(model) is True


@pytest.mark.parametrize("model", ["gemma4:latest", "llama3.1:70b", "mistral:7b", ""])
def test_is_thinking_model_false(model):
    assert lcb._is_thinking_model(model) is False


# ── chat_payload_from_incoming (thinking-token reservation) ───────────────────

def test_chat_payload_reserves_thinking_overhead():
    payload = lcb.chat_payload_from_incoming({"prompt": "hi", "model": "qwen3:32b", "max_tokens": 100})
    assert payload["max_tokens"] == 100 + lcb._THINKING_OVERHEAD


def test_chat_payload_no_overhead_for_plain_model():
    payload = lcb.chat_payload_from_incoming({"prompt": "hi", "model": "gemma4:latest", "max_tokens": 100})
    assert payload["max_tokens"] == 100


def test_chat_payload_builds_messages_from_prompt():
    payload = lcb.chat_payload_from_incoming({"prompt": "hello", "model": "gemma4:latest"})
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


# ── chat_response (thinking-only fallback) ────────────────────────────────────

def test_chat_response_extracts_content():
    raw = {"choices": [{"message": {"content": "answer"}}], "usage": {"total_tokens": 5}}
    result = lcb.chat_response(raw)
    assert result["content"] == "answer"
    assert result["usage"] == {"total_tokens": 5}


def test_chat_response_falls_back_to_reasoning():
    raw = {"choices": [{"message": {"content": "", "reasoning": "first\n\nlast thought"}}]}
    result = lcb.chat_response(raw)
    assert "last thought" in result["content"]
    assert "thinking only" in result["content"]


def test_chat_response_empty_choices():
    assert lcb.chat_response({"choices": []})["content"] == ""


# ── route_decision (risk labelling + mode escalation) ─────────────────────────

def test_route_decision_flags_risky_terms():
    decision = lcb.route_decision({"prompt": "please apply patch to production"})
    assert decision["risk_label"] == "review"


def test_route_decision_normal_for_benign():
    decision = lcb.route_decision({"prompt": "explain this function"})
    assert decision["risk_label"] == "normal"


def test_route_decision_escalates_large_prompt():
    decision = lcb.route_decision({"prompt": "x" * 30000, "context_mode": "fast"})
    assert decision["context_mode"] == "repo"


# ── _CircuitBreaker state machine ─────────────────────────────────────────────

def test_circuit_breaker_opens_after_threshold():
    cb = lcb._CircuitBreaker()
    for _ in range(cb.THRESHOLD):
        cb.record_failure()
    assert cb.is_open() is True


def test_circuit_breaker_closes_on_success():
    cb = lcb._CircuitBreaker()
    for _ in range(cb.THRESHOLD):
        cb.record_failure()
    cb.record_success()
    assert cb.is_open() is False


# ── _TokenBucket rate limiter ─────────────────────────────────────────────────

def test_token_bucket_allows_burst():
    bucket = lcb._TokenBucket()
    # First BURST requests from a fresh IP should all pass
    assert all(bucket.consume("1.2.3.4") for _ in range(int(bucket.BURST)))


def test_token_bucket_blocks_when_exhausted():
    bucket = lcb._TokenBucket()
    ip = "9.9.9.9"
    for _ in range(int(bucket.BURST) + 5):
        bucket.consume(ip)
    # After draining burst, the very next call should be blocked
    assert bucket.consume(ip) is False


# ── SSRF host blocking ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "172.16.0.1"],
)
def test_ssrf_blocks_private_hosts(host):
    assert lcb._SSRF_BLOCKED_HOSTS.match(host) is not None


@pytest.mark.parametrize("host", ["example.com", "8.8.8.8", "api.github.com", "172.15.0.1"])
def test_ssrf_allows_public_hosts(host):
    assert lcb._SSRF_BLOCKED_HOSTS.match(host) is None


def test_web_fetch_rejects_private_url():
    with pytest.raises(ValueError, match="private/loopback"):
        lcb.web_fetch({"url": "http://169.254.169.254/latest/meta-data/"})


def test_web_fetch_rejects_non_http_scheme():
    with pytest.raises(ValueError):
        lcb.web_fetch({"url": "file:///etc/passwd"})


# ── skill_package_slug ────────────────────────────────────────────────────────

def test_skill_package_slug_valid():
    assert lcb.skill_package_slug("My Cool Skill") == "my-cool-skill"


def test_skill_package_slug_too_short_raises():
    with pytest.raises(ValueError):
        lcb.skill_package_slug("ab")


# ── now_stamp format ──────────────────────────────────────────────────────────

def test_now_stamp_is_utc_iso_compact():
    stamp = lcb.now_stamp()
    assert stamp.endswith("Z")
    assert "T" in stamp
