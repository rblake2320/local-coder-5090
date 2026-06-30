"""Live integration tests for local_coder_browser.py HTTP server.

Requires the server running on :8022:
  python scripts/local_coder_browser.py --no-open
  python -m pytest tests/ops/test_local_coder_browser.py -v
"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8022"


def _get(path: str, timeout: int = 8) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def _post(path: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ── /status ───────────────────────────────────────────────────────────────────

def test_status_up():
    data = _get("/status")
    assert data["health"]["status"] == "ok"


def test_status_has_base_url():
    data = _get("/status")
    assert "base_url" in data


def test_status_has_model_field():
    data = _get("/status")
    assert "model" in data["health"] or "model" in data


# ── / (main UI) ───────────────────────────────────────────────────────────────

def test_root_serves_html():
    with urllib.request.urlopen(f"{BASE}/", timeout=8) as r:
        html = r.read().decode()
    assert '<div class="app">' in html


def test_root_has_settings_panel():
    with urllib.request.urlopen(f"{BASE}/", timeout=8) as r:
        html = r.read().decode()
    assert "settingsPanel" in html


def test_root_three_column_layout():
    with urllib.request.urlopen(f"{BASE}/", timeout=8) as r:
        html = r.read().decode()
    assert 'class="sidebar"' in html
    assert 'class="main"' in html
    assert 'class="settings-panel"' in html


# ── /kb ───────────────────────────────────────────────────────────────────────

def test_kb_list_returns_dict():
    data = _get("/kb")
    assert isinstance(data, dict)


# ── /instructions ─────────────────────────────────────────────────────────────

def test_instructions_returns_both_scopes():
    data = _get("/instructions")
    assert "global" in data
    assert "project" in data


def test_instructions_has_paths():
    data = _get("/instructions")
    assert "global_path" in data
    assert "project_path" in data


# ── /tools/run ────────────────────────────────────────────────────────────────

def test_tool_chkdsk_report():
    data = _post("/tools/run", {"command": "chkdsk_report", "args": []})
    assert data.get("returncode") is not None


def test_tool_tool_search():
    data = _post("/tools/run", {"command": "tool_search", "args": ["spark"]})
    assert data.get("returncode") == 0
    assert "matches" in data


def test_tool_unknown_rejected():
    try:
        _post("/tools/run", {"command": "rm_rf_everything", "args": []})
        assert False, "should have raised"
    except urllib.error.HTTPError as e:
        assert e.code in (400, 403, 422, 500)


# ── /control (daily_control) ──────────────────────────────────────────────────

def test_control_status():
    data = _post("/control", {"action": "status"})
    assert "returncode" in data


def test_control_impact():
    data = _post("/control", {"action": "impact"})
    assert "returncode" in data


def test_control_bad_action_rejected():
    try:
        _post("/control", {"action": "drop_all_tables"})
        assert False, "should have raised"
    except urllib.error.HTTPError as e:
        assert e.code in (400, 403, 422, 500)
