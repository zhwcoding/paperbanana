"""PaperBanana REST API Server.

Async task-based HTTP API for generating academic illustrations.
Supports methodology diagrams and statistical plots via a poll-based
workflow: submit a task, poll for status, retrieve the result.

API Key authentication with per-key quota management. Admin endpoints
for key lifecycle management. SQLite-backed persistence.

Usage:
    python api_server.py                          # default config
    PAPERBANANA_CONFIG=configs/openrouter.yaml python api_server.py

Environment variables:
    PAPERBANANA_CONFIG      Path to config YAML (default: configs/openrouter.yaml)
    PAPERBANANA_DB          Path to SQLite DB (default: data/api_keys.db)
    PAPERBANANA_ADMIN_KEY   Admin key for /api/admin/* endpoints (required)
    PORT                    Server port (default: 8000)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from paperbanana.core.config import Settings
from paperbanana.core.pipeline import PaperBananaPipeline
from paperbanana.core.types import DiagramType, GenerationInput
from paperbanana.core.utils import image_to_base64, load_image

# ---------------------------------------------------------------------------
# Task store
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskRecord(BaseModel):
    task_id: str
    status: TaskStatus
    diagram_type: str
    api_key: Optional[str] = None
    image_path: Optional[str] = None
    image_base64: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_include_image: bool = False


_tasks: dict[str, TaskRecord] = {}

# Shared settings, initialised during lifespan
_settings: Settings | None = None

# SQLite connection, initialised during lifespan
_db: sqlite3.Connection | None = None

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    source_context: str = Field(description="Methodology text or paper excerpt")
    caption: str = Field(description="Figure caption")
    iterations: int = Field(default=3, ge=1, le=10)
    webhook_url: Optional[str] = Field(default=None, description="URL to POST result to when task completes")
    webhook_include_image: bool = Field(default=False, description="Include image_base64 in webhook payload")


class PlotRequest(BaseModel):
    data_json: str = Field(description="JSON string with data to plot")
    intent: str = Field(description="Description of the desired plot")
    iterations: int = Field(default=3, ge=1, le=10)
    webhook_url: Optional[str] = Field(default=None, description="URL to POST result to when task completes")
    webhook_include_image: bool = Field(default=False, description="Include image_base64 in webhook payload")


class TaskSubmitted(BaseModel):
    task_id: str
    status: TaskStatus


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    diagram_type: str
    image_base64: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.2"


# --- Admin schemas ---

class CreateKeyRequest(BaseModel):
    name: str = Field(description="Name / label for the API key")
    quota: int = Field(ge=1, description="Initial quota to assign")
    webhook_url: Optional[str] = Field(default=None, description="Default webhook URL for this key")
    webhook_secret: Optional[str] = Field(default=None, description="Secret for HMAC signature on webhooks")


class UpdateKeyRequest(BaseModel):
    quota_remaining: Optional[int] = Field(default=None, ge=0)
    quota_total: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class ApiKeyInfo(BaseModel):
    key: str
    name: str
    quota_remaining: int
    quota_total: int
    total_used: int
    active: bool
    created_at: str
    webhook_url: Optional[str] = None


class ApiKeyDetail(ApiKeyInfo):
    usage_log: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_db() -> sqlite3.Connection:
    assert _db is not None, "Database not initialised"
    return _db


def _init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key          TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            quota_remaining INTEGER NOT NULL,
            quota_total     INTEGER NOT NULL,
            total_used      INTEGER NOT NULL DEFAULT 0,
            active       INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT NOT NULL,
            webhook_url  TEXT,
            webhook_secret TEXT
        )
    """)
    # Migrate: add webhook columns if missing
    _cols = {r[1] for r in conn.execute("PRAGMA table_info(api_keys)").fetchall()}
    if "webhook_url" not in _cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN webhook_url TEXT")
    if "webhook_secret" not in _cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN webhook_secret TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            key        TEXT NOT NULL REFERENCES api_keys(key),
            task_id    TEXT NOT NULL,
            endpoint   TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_history (
            task_id      TEXT PRIMARY KEY,
            api_key      TEXT NOT NULL,
            key_name     TEXT NOT NULL DEFAULT '',
            endpoint     TEXT NOT NULL,
            diagram_type TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'pending',
            input_params TEXT NOT NULL DEFAULT '{}',
            description  TEXT,
            image_path   TEXT,
            error        TEXT,
            created_at   TEXT NOT NULL,
            completed_at TEXT,
            webhook_url  TEXT,
            webhook_include_image INTEGER NOT NULL DEFAULT 0,
            webhook_status TEXT,
            webhook_attempts INTEGER NOT NULL DEFAULT 0,
            webhook_last_error TEXT
        )
    """)
    # Migrate: add webhook columns if missing
    _thcols = {r[1] for r in conn.execute("PRAGMA table_info(task_history)").fetchall()}
    for _c, _t, _d in [
        ("webhook_url", "TEXT", None), ("webhook_include_image", "INTEGER NOT NULL", "0"),
        ("webhook_status", "TEXT", None), ("webhook_attempts", "INTEGER NOT NULL", "0"),
        ("webhook_last_error", "TEXT", None),
    ]:
        if _c not in _thcols:
            default = f" DEFAULT {_d}" if _d is not None else ""
            conn.execute(f"ALTER TABLE task_history ADD COLUMN {_c} {_t}{default}")
    conn.commit()
    return conn


def _generate_api_key() -> str:
    return "pb_" + secrets.token_hex(16)


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization[len("Bearer "):]


async def verify_api_key(authorization: str | None = Header(default=None)) -> str:
    """Validate the Bearer token against the api_keys table.

    Returns the API key string on success.
    """
    token = _extract_bearer(authorization)
    db = _get_db()
    row = db.execute("SELECT key, active, quota_remaining FROM api_keys WHERE key = ?", (token,)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not row["active"]:
        raise HTTPException(status_code=403, detail="API key is disabled")
    if row["quota_remaining"] <= 0:
        raise HTTPException(status_code=403, detail="Quota exhausted")
    return token


async def verify_admin(authorization: str | None = Header(default=None)) -> str:
    """Validate the Bearer token matches PAPERBANANA_ADMIN_KEY."""
    token = _extract_bearer(authorization)
    admin_key = os.environ.get("PAPERBANANA_ADMIN_KEY")
    if not admin_key:
        raise HTTPException(status_code=500, detail="PAPERBANANA_ADMIN_KEY not configured")
    if not secrets.compare_digest(token, admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return token


# ---------------------------------------------------------------------------
# Quota helpers
# ---------------------------------------------------------------------------


def _save_task_history(
    task_id: str, api_key: str, endpoint: str, diagram_type: str, input_params: dict,
    webhook_url: str | None = None, webhook_include_image: bool = False,
) -> None:
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    key_name = ""
    row = db.execute("SELECT name FROM api_keys WHERE key = ?", (api_key,)).fetchone()
    if row:
        key_name = row["name"]
    db.execute(
        "INSERT OR IGNORE INTO task_history "
        "(task_id, api_key, key_name, endpoint, diagram_type, status, input_params, "
        "webhook_url, webhook_include_image, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
        (task_id, api_key, key_name, endpoint, diagram_type,
         json.dumps(input_params), webhook_url, int(webhook_include_image), now),
    )
    db.commit()


def _update_task_history(
    task_id: str, status: str, description: str | None = None,
    image_path: str | None = None, error: str | None = None,
) -> None:
    db = _get_db()
    completed_at = datetime.now(timezone.utc).isoformat() if status in ("completed", "failed") else None
    db.execute(
        "UPDATE task_history SET status=?, description=?, image_path=?, error=?, completed_at=? "
        "WHERE task_id=?",
        (status, description, image_path, error, completed_at, task_id),
    )
    db.commit()


def _deduct_quota(api_key: str, task_id: str, endpoint: str) -> None:
    db = _get_db()
    db.execute(
        "UPDATE api_keys SET quota_remaining = quota_remaining - 1, total_used = total_used + 1 WHERE key = ?",
        (api_key,),
    )
    db.execute(
        "INSERT INTO usage_log (key, task_id, endpoint, created_at) VALUES (?, ?, ?, ?)",
        (api_key, task_id, endpoint, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


def _resolve_webhook(api_key: str, req_url: str | None, req_include: bool) -> tuple[str | None, bool, str | None]:
    """Return (webhook_url, include_image, webhook_secret). Per-request overrides per-key."""
    db = _get_db()
    row = db.execute("SELECT webhook_url, webhook_secret FROM api_keys WHERE key = ?", (api_key,)).fetchone()
    key_url = row["webhook_url"] if row else None
    key_secret = row["webhook_secret"] if row else None
    url = req_url or key_url
    return url, req_include, key_secret


async def _send_webhook(task_id: str) -> None:
    """POST the task result to the configured webhook URL with retries."""
    import httpx

    db = _get_db()
    row = db.execute("SELECT * FROM task_history WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        return
    wh_url = row["webhook_url"]
    if not wh_url:
        return

    include_image = bool(row["webhook_include_image"])

    # Look up webhook_secret from the API key
    key_row = db.execute("SELECT webhook_secret FROM api_keys WHERE key = ?", (row["api_key"],)).fetchone()
    wh_secret = key_row["webhook_secret"] if key_row else None

    # Build payload
    payload: dict[str, Any] = {
        "event": "task.completed" if row["status"] == "completed" else "task.failed",
        "task_id": row["task_id"],
        "status": row["status"],
        "diagram_type": row["diagram_type"],
        "description": row["description"],
        "image_url": f"https://pb.gptayn.com/api/tasks/{row['task_id']}/image",
        "image_base64": None,
        "error": row["error"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }
    if include_image and row.get("image_path") and Path(row["image_path"]).exists():
        try:
            img = load_image(row["image_path"])
            payload["image_base64"] = image_to_base64(img)
        except Exception:
            pass

    body_bytes = json.dumps(payload).encode()

    # Compute HMAC signature
    hdrs: dict[str, str] = {
        "Content-Type": "application/json",
        "X-PaperBanana-Event": payload["event"],
        "User-Agent": "PaperBanana-Webhook/0.1.2",
    }
    if wh_secret:
        sig = hmac.new(wh_secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        hdrs["X-PaperBanana-Signature"] = f"sha256={sig}"

    # Retry up to 3 times: 5s, 15s, 60s
    delays = [5, 15, 60]
    last_error = None
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(3):
            try:
                resp = await client.post(wh_url, content=body_bytes, headers=hdrs)
                if resp.status_code < 400:
                    db.execute(
                        "UPDATE task_history SET webhook_status='delivered', webhook_attempts=? WHERE task_id=?",
                        (attempt + 1, task_id),
                    )
                    db.commit()
                    return
                last_error = f"HTTP {resp.status_code}"
            except Exception as exc:
                last_error = str(exc)

            db.execute(
                "UPDATE task_history SET webhook_status='retrying', webhook_attempts=?, webhook_last_error=? "
                "WHERE task_id=?",
                (attempt + 1, last_error, task_id),
            )
            db.commit()

            if attempt < 2:
                await asyncio.sleep(delays[attempt])

    # All retries exhausted
    db.execute(
        "UPDATE task_history SET webhook_status='failed', webhook_attempts=3, webhook_last_error=? "
        "WHERE task_id=?",
        (last_error, task_id),
    )
    db.commit()


async def _run_generation(
    task_id: str,
    gen_input: GenerationInput,
    settings: Settings,
) -> None:
    """Execute the pipeline in the background and update the task record."""
    record = _tasks[task_id]
    record.status = TaskStatus.RUNNING
    _update_task_history(task_id, "running")
    try:
        pipeline = PaperBananaPipeline(settings=settings)
        result = await pipeline.generate(gen_input)

        img = load_image(result.image_path)
        b64 = image_to_base64(img)

        record.image_path = result.image_path
        record.image_base64 = b64
        record.description = result.description
        record.status = TaskStatus.COMPLETED
        _update_task_history(task_id, "completed", result.description, result.image_path)
    except Exception as exc:
        record.error = str(exc)
        record.status = TaskStatus.FAILED
        _update_task_history(task_id, "failed", error=str(exc))

    # Fire webhook if configured
    if record.webhook_url:
        asyncio.create_task(_send_webhook(task_id))

# ---------------------------------------------------------------------------
# Lifespan — load settings + init DB at startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _settings, _db
    config_path = os.environ.get("PAPERBANANA_CONFIG", "configs/openrouter.yaml")
    if Path(config_path).exists():
        _settings = Settings.from_yaml(config_path)
    else:
        _settings = Settings()

    db_path = os.environ.get("PAPERBANANA_DB", "data/api_keys.db")
    _db = _init_db(db_path)

    yield

    if _db is not None:
        _db.close()
        _db = None


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PaperBanana API",
    version="0.1.2",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


# ---------------------------------------------------------------------------
# Admin UI
# ---------------------------------------------------------------------------

ADMIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PaperBanana Admin</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0d1117;--surface:#161b22;--border:#30363d;--text:#e6edf3;
  --text-muted:#8b949e;--accent:#58a6ff;--accent-hover:#79c0ff;
  --green:#3fb950;--red:#f85149;--yellow:#d29922;--purple:#bc8cff;
  --radius:8px;--shadow:0 2px 8px rgba(0,0,0,.3);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.5;min-height:100vh}
a{color:var(--accent);text-decoration:none}
button{cursor:pointer;font-family:inherit;font-size:.875rem;border:1px solid var(--border);
  background:var(--surface);color:var(--text);padding:6px 16px;border-radius:var(--radius);
  transition:background .15s}
button:hover{background:var(--border)}
button.primary{background:var(--accent);color:#000;border-color:var(--accent);font-weight:600}
button.primary:hover{background:var(--accent-hover)}
button.danger{border-color:var(--red);color:var(--red)}
button.danger:hover{background:var(--red);color:#fff}
input,select,textarea{font-family:inherit;font-size:.875rem;background:var(--bg);
  color:var(--text);border:1px solid var(--border);border-radius:var(--radius);
  padding:8px 12px;width:100%;outline:none}
input:focus,select:focus,textarea:focus{border-color:var(--accent)}
textarea{resize:vertical;min-height:80px}
.container{max-width:1100px;margin:0 auto;padding:24px 16px}
/* Login */
#login-page{display:flex;align-items:center;justify-content:center;min-height:100vh}
.login-box{background:var(--surface);padding:40px;border-radius:12px;border:1px solid var(--border);
  width:100%;max-width:400px;box-shadow:var(--shadow)}
.login-box h1{font-size:1.5rem;margin-bottom:8px;text-align:center}
.login-box p{color:var(--text-muted);text-align:center;margin-bottom:24px;font-size:.875rem}
.login-box .logo{text-align:center;font-size:2.5rem;margin-bottom:16px}
.login-box input{margin-bottom:16px}
.login-box button{width:100%}
.login-error{color:var(--red);font-size:.8rem;margin-bottom:12px;display:none}
/* Header */
header{display:flex;align-items:center;justify-content:space-between;padding:16px 0;
  border-bottom:1px solid var(--border);margin-bottom:24px}
header h1{font-size:1.25rem;display:flex;align-items:center;gap:8px}
header .logout{font-size:.8rem}
/* Cards */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:32px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:20px;box-shadow:var(--shadow)}
.card .label{font-size:.75rem;text-transform:uppercase;color:var(--text-muted);letter-spacing:.5px}
.card .value{font-size:1.75rem;font-weight:700;margin-top:4px}
.card .value.green{color:var(--green)}.card .value.blue{color:var(--accent)}
.card .value.yellow{color:var(--yellow)}.card .value.purple{color:var(--purple)}
/* Toolbar */
.toolbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px}
.toolbar h2{font-size:1.1rem}
/* Table */
.table-wrap{overflow-x:auto;margin-bottom:32px}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border)}
th{background:var(--surface);color:var(--text-muted);font-weight:600;font-size:.75rem;
  text-transform:uppercase;letter-spacing:.5px;position:sticky;top:0}
tr:hover td{background:rgba(88,166,255,.04)}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:600}
.badge.active{background:rgba(63,185,80,.15);color:var(--green)}
.badge.inactive{background:rgba(248,81,73,.15);color:var(--red)}
.key-masked{font-family:monospace;font-size:.8rem;color:var(--text-muted)}
.actions button{margin-right:4px;padding:4px 10px;font-size:.75rem}
/* Modal */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;
  justify-content:center;z-index:100}
.modal-overlay.show{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:28px;width:100%;max-width:480px;box-shadow:var(--shadow)}
.modal h3{margin-bottom:16px;font-size:1.1rem}
.modal .field{margin-bottom:14px}
.modal .field label{display:block;font-size:.8rem;color:var(--text-muted);margin-bottom:4px}
.modal .btn-row{display:flex;gap:8px;justify-content:flex-end;margin-top:20px}
/* Detail panel */
.detail-panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:20px;margin-bottom:32px;display:none}
.detail-panel h3{margin-bottom:12px;font-size:1rem}
.detail-panel .log-table{max-height:300px;overflow-y:auto}
.detail-panel .log-table table{font-size:.8rem}
/* API Tester */
.tester{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:20px;margin-bottom:32px}
.tester h2{font-size:1.1rem;margin-bottom:16px}
.tester .row{display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap}
.tester .row>*{flex:1;min-width:200px}
.tester .response-box{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);
  padding:12px;font-family:monospace;font-size:.8rem;white-space:pre-wrap;max-height:400px;
  overflow-y:auto;margin-top:12px;color:var(--green)}
.tester .status-line{font-size:.8rem;color:var(--text-muted);margin-top:8px}
/* Tester form fields */
.t-field{margin-bottom:14px}
.t-field label{display:block;font-size:.8rem;color:var(--text-muted);margin-bottom:4px}
.t-field .hint{font-size:.7rem;color:var(--text-muted);margin-top:2px}
.preset-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.preset-chip{font-size:.75rem;padding:4px 10px;border-radius:16px;border:1px solid var(--border);
  background:var(--bg);color:var(--text-muted);cursor:pointer;transition:all .15s}
.preset-chip:hover,.preset-chip.active{border-color:var(--accent);color:var(--accent);background:rgba(88,166,255,.08)}
.iter-slider{display:flex;align-items:center;gap:10px}
.iter-slider input[type=range]{flex:1;accent-color:var(--accent)}
.iter-slider .iter-val{font-weight:700;min-width:20px;text-align:center;color:var(--accent)}
/* Result area */
.result-area{margin-top:16px}
.result-image{margin-top:12px;text-align:center}
.result-image img{max-width:100%;max-height:500px;border-radius:var(--radius);border:1px solid var(--border)}
.result-desc{margin-top:10px;padding:12px;background:var(--bg);border:1px solid var(--border);
  border-radius:var(--radius);font-size:.85rem;line-height:1.6}
.poll-status{display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:var(--radius);
  font-size:.85rem;margin-top:12px}
.poll-status.pending{background:rgba(210,153,34,.1);color:var(--yellow)}
.poll-status.running{background:rgba(88,166,255,.1);color:var(--accent)}
.poll-status.completed{background:rgba(63,185,80,.1);color:var(--green)}
.poll-status.failed{background:rgba(248,81,73,.1);color:var(--red)}
.ep-section{display:none}
.ep-section.visible{display:block}
.tabs{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:16px}
.tab{padding:8px 18px;font-size:.85rem;cursor:pointer;color:var(--text-muted);border-bottom:2px solid transparent;
  margin-bottom:-2px;transition:all .15s}
.tab:hover{color:var(--text)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
/* Spinner */
.spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite;
  vertical-align:middle;margin-left:6px}
@keyframes spin{to{transform:rotate(360deg)}}
/* Responsive */
@media(max-width:600px){
  .cards{grid-template-columns:1fr 1fr}
  .tester .row{flex-direction:column}
}
</style>
</head>
<body>

<!-- LOGIN PAGE -->
<div id="login-page">
  <div class="login-box">
    <div class="logo">&#127820;</div>
    <h1>PaperBanana</h1>
    <p>Admin Console</p>
    <div class="login-error" id="login-error"></div>
    <input type="password" id="admin-key-input" placeholder="Enter Admin Key" autofocus>
    <button class="primary" onclick="doLogin()">Sign In</button>
  </div>
</div>

<!-- DASHBOARD -->
<div id="dashboard" style="display:none">
<div class="container">
  <header>
    <h1>&#127820; PaperBanana Admin</h1>
    <div style="display:flex;align-items:center;gap:10px">
      <a href="/history" target="_blank" style="font-size:.8rem;padding:5px 12px;border:1px solid var(--border);border-radius:var(--radius)">History</a>
      <a href="/doc" target="_blank" style="font-size:.8rem;padding:5px 12px;border:1px solid var(--border);border-radius:var(--radius)">API Docs</a>
      <button class="logout" onclick="doLogout()">Logout</button>
    </div>
  </header>

  <!-- Stats cards -->
  <div class="cards">
    <div class="card"><div class="label">Total Keys</div><div class="value blue" id="stat-total">-</div></div>
    <div class="card"><div class="label">Active Keys</div><div class="value green" id="stat-active">-</div></div>
    <div class="card"><div class="label">Total Used</div><div class="value yellow" id="stat-used">-</div></div>
    <div class="card"><div class="label">Remaining Quota</div><div class="value purple" id="stat-remaining">-</div></div>
  </div>

  <!-- Key Management -->
  <div class="toolbar">
    <h2>API Keys</h2>
    <button class="primary" onclick="showCreateModal()">+ Create Key</button>
  </div>

  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Name</th><th>Key</th><th>Quota</th><th>Used</th><th>Status</th><th>Actions</th>
      </tr></thead>
      <tbody id="keys-tbody"></tbody>
    </table>
  </div>

  <!-- Detail panel -->
  <div class="detail-panel" id="detail-panel">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <h3 id="detail-title">Key Details</h3>
      <button onclick="hideDetail()">Close</button>
    </div>
    <div class="log-table" id="detail-log"></div>
  </div>

  <!-- API Tester -->
  <div class="tester">
    <h2>API Tester</h2>

    <!-- Tabs -->
    <div class="tabs">
      <div class="tab active" onclick="switchTab('generate')">Generate Diagram</div>
      <div class="tab" onclick="switchTab('plot')">Generate Plot</div>
      <div class="tab" onclick="switchTab('task')">Task Lookup</div>
      <div class="tab" onclick="switchTab('raw')">Raw Request</div>
    </div>

    <!-- Auth key selector (shared) -->
    <div class="t-field" style="margin-bottom:18px">
      <label>API Key</label>
      <select id="test-auth-key">
        <option value="__admin__">Use Admin Key</option>
      </select>
      <div class="hint">Select an API key from your key list, or use the admin key for admin-only endpoints</div>
    </div>

    <!-- === GENERATE TAB === -->
    <div class="ep-section visible" id="tab-generate">
      <div class="t-field">
        <label>Example Presets</label>
        <div class="preset-chips">
          <div class="preset-chip" onclick="loadPreset('gen',0)">CNN Architecture</div>
          <div class="preset-chip" onclick="loadPreset('gen',1)">Transformer Pipeline</div>
          <div class="preset-chip" onclick="loadPreset('gen',2)">GAN Training</div>
          <div class="preset-chip" onclick="loadPreset('gen',3)">Federated Learning</div>
        </div>
      </div>
      <div class="t-field">
        <label>Source Context <span style="color:var(--red)">*</span></label>
        <textarea id="gen-context" rows="5" placeholder="Paste the methodology section or paper excerpt here..."></textarea>
        <div class="hint">The methodology text or paper excerpt that describes the process to illustrate</div>
      </div>
      <div class="t-field">
        <label>Figure Caption <span style="color:var(--red)">*</span></label>
        <input id="gen-caption" placeholder="e.g. Figure 1: Overview of the proposed CNN architecture">
        <div class="hint">The caption that will appear below the generated diagram</div>
      </div>
      <div class="t-field">
        <label>Refinement Iterations</label>
        <div class="iter-slider">
          <input type="range" id="gen-iter" min="1" max="10" value="3" oninput="document.getElementById('gen-iter-val').textContent=this.value">
          <span class="iter-val" id="gen-iter-val">3</span>
        </div>
        <div class="hint">More iterations = higher quality but slower (1-10)</div>
      </div>
      <button class="primary" onclick="submitGenerate()">Generate Diagram</button>
      <div id="gen-result" class="result-area"></div>
    </div>

    <!-- === PLOT TAB === -->
    <div class="ep-section" id="tab-plot">
      <div class="t-field">
        <label>Example Presets</label>
        <div class="preset-chips">
          <div class="preset-chip" onclick="loadPreset('plot',0)">Accuracy Comparison</div>
          <div class="preset-chip" onclick="loadPreset('plot',1)">Training Loss Curve</div>
          <div class="preset-chip" onclick="loadPreset('plot',2)">Ablation Study</div>
          <div class="preset-chip" onclick="loadPreset('plot',3)">Distribution Histogram</div>
        </div>
      </div>
      <div class="t-field">
        <label>Data (JSON) <span style="color:var(--red)">*</span></label>
        <textarea id="plot-data" rows="6" placeholder='{"labels":["A","B","C"],"values":[85.2,91.7,88.4]}'></textarea>
        <div class="hint">JSON data to plot. Can be any structure — arrays, objects, nested data</div>
      </div>
      <div class="t-field">
        <label>Plot Intent <span style="color:var(--red)">*</span></label>
        <input id="plot-intent" placeholder="e.g. Bar chart comparing model accuracy across datasets">
        <div class="hint">Describe what kind of plot you want and what it should show</div>
      </div>
      <div class="t-field">
        <label>Refinement Iterations</label>
        <div class="iter-slider">
          <input type="range" id="plot-iter" min="1" max="10" value="3" oninput="document.getElementById('plot-iter-val').textContent=this.value">
          <span class="iter-val" id="plot-iter-val">3</span>
        </div>
      </div>
      <button class="primary" onclick="submitPlot()">Generate Plot</button>
      <div id="plot-result" class="result-area"></div>
    </div>

    <!-- === TASK LOOKUP TAB === -->
    <div class="ep-section" id="tab-task">
      <div class="t-field">
        <label>Task ID</label>
        <input id="task-id-input" placeholder="e.g. a1b2c3d4e5f6...">
        <div class="hint">Enter a task ID to check its status and retrieve the result</div>
      </div>
      <div style="display:flex;gap:8px">
        <button class="primary" onclick="lookupTask()">Check Status</button>
        <button onclick="downloadTaskImage()">Download Image</button>
      </div>
      <div id="task-result" class="result-area"></div>
    </div>

    <!-- === RAW REQUEST TAB === -->
    <div class="ep-section" id="tab-raw">
      <div class="t-field">
        <label>Endpoint</label>
        <select id="raw-endpoint">
          <option value="GET /api/health">GET /api/health</option>
          <option value="GET /api/admin/keys">GET /api/admin/keys</option>
          <option value="POST /api/admin/keys">POST /api/admin/keys</option>
          <option value="POST /api/generate">POST /api/generate</option>
          <option value="POST /api/plot">POST /api/plot</option>
          <option value="GET /api/tasks/{task_id}">GET /api/tasks/{task_id}</option>
        </select>
      </div>
      <div class="t-field">
        <label>Request Body (JSON)</label>
        <textarea id="raw-body" rows="5" placeholder='{"key":"value"}'></textarea>
      </div>
      <button class="primary" onclick="runRaw()">Send Request</button>
      <div class="status-line" id="raw-status"></div>
      <div class="response-box" id="raw-response" style="display:none"></div>
    </div>

  </div>

</div>
</div>

<!-- Create Key Modal -->
<div class="modal-overlay" id="create-modal">
  <div class="modal">
    <h3>Create API Key</h3>
    <div class="field"><label>Name</label><input id="create-name" placeholder="e.g. my-app"></div>
    <div class="field"><label>Quota</label><input id="create-quota" type="number" min="1" value="100"></div>
    <div class="field"><label>Webhook URL <span style="color:var(--text-muted);font-weight:400">(optional)</span></label><input id="create-webhook-url" placeholder="https://your-server.com/callback"></div>
    <div class="field"><label>Webhook Secret <span style="color:var(--text-muted);font-weight:400">(optional, for HMAC signature)</span></label><input id="create-webhook-secret" placeholder="your-secret-string"></div>
    <div class="btn-row">
      <button onclick="hideCreateModal()">Cancel</button>
      <button class="primary" onclick="createKey()">Create</button>
    </div>
  </div>
</div>

<!-- Edit Key Modal -->
<div class="modal-overlay" id="edit-modal">
  <div class="modal">
    <h3>Edit Key</h3>
    <input type="hidden" id="edit-key-id">
    <div class="field"><label>Remaining Quota</label><input id="edit-remaining" type="number" min="0"></div>
    <div class="field"><label>Total Quota</label><input id="edit-total" type="number" min="0"></div>
    <div class="field"><label>Active</label>
      <select id="edit-active"><option value="true">Active</option><option value="false">Inactive</option></select>
    </div>
    <div class="field"><label>Webhook URL</label><input id="edit-webhook-url" placeholder="https://your-server.com/callback"></div>
    <div class="field"><label>Webhook Secret</label><input id="edit-webhook-secret" placeholder="Leave empty to keep current"></div>
    <div class="btn-row">
      <button onclick="hideEditModal()">Cancel</button>
      <button class="primary" onclick="saveEdit()">Save</button>
    </div>
  </div>
</div>

<script>
const API = '';
let adminKey = localStorage.getItem('pb_admin_key') || '';

function headers(keyOverride) {
  return {'Authorization': 'Bearer ' + (keyOverride || adminKey), 'Content-Type': 'application/json'};
}

function maskKey(k) {
  return k.substring(0, 6) + '...' + k.substring(k.length - 4);
}

// --- Auth ---
async function doLogin() {
  const key = document.getElementById('admin-key-input').value.trim();
  if (!key) return;
  try {
    const r = await fetch(API + '/api/admin/keys', {headers: {'Authorization': 'Bearer ' + key}});
    if (!r.ok) throw new Error('Invalid key');
    adminKey = key;
    localStorage.setItem('pb_admin_key', key);
    showDashboard();
  } catch(e) {
    const el = document.getElementById('login-error');
    el.textContent = 'Authentication failed. Check your admin key.';
    el.style.display = 'block';
  }
}

function doLogout() {
  adminKey = '';
  localStorage.removeItem('pb_admin_key');
  document.getElementById('dashboard').style.display = 'none';
  document.getElementById('login-page').style.display = 'flex';
  document.getElementById('admin-key-input').value = '';
}

document.getElementById('admin-key-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') doLogin();
});

// --- Dashboard ---
async function showDashboard() {
  document.getElementById('login-page').style.display = 'none';
  document.getElementById('dashboard').style.display = 'block';
  await loadKeys();
}

async function loadKeys() {
  try {
    const r = await fetch(API + '/api/admin/keys', {headers: headers()});
    if (r.status === 401) { doLogout(); return; }
    const keys = await r.json();
    renderStats(keys);
    renderTable(keys);
    updateKeySelector(keys);
  } catch(e) {
    console.error('Failed to load keys:', e);
  }
}

function renderStats(keys) {
  document.getElementById('stat-total').textContent = keys.length;
  document.getElementById('stat-active').textContent = keys.filter(k => k.active).length;
  document.getElementById('stat-used').textContent = keys.reduce((s,k) => s + k.total_used, 0);
  document.getElementById('stat-remaining').textContent = keys.reduce((s,k) => s + k.quota_remaining, 0);
}

function renderTable(keys) {
  const tbody = document.getElementById('keys-tbody');
  tbody.innerHTML = '';
  keys.forEach(k => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${esc(k.name)}</strong></td>
      <td><span class="key-masked">${maskKey(k.key)}</span></td>
      <td>${k.quota_remaining} / ${k.quota_total}</td>
      <td>${k.total_used}</td>
      <td><span class="badge ${k.active?'active':'inactive'}">${k.active?'Active':'Inactive'}</span></td>
      <td class="actions">
        <button onclick="showDetail('${k.key}')">Detail</button>
        <button onclick="copyKey('${k.key}')">Copy</button>
        <button onclick="showEditModal('${k.key}',${k.quota_remaining},${k.quota_total},${k.active},'${esc(k.webhook_url||'')}')">Edit</button>
        <button class="danger" onclick="deleteKey('${k.key}')">Delete</button>
      </td>`;
    tbody.appendChild(tr);
  });
}

function esc(s) {
  const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
}

function copyKey(key) {
  navigator.clipboard.writeText(key).catch(() => {});
}

// --- Detail ---
async function showDetail(key) {
  try {
    const r = await fetch(API + '/api/admin/keys/' + key, {headers: headers()});
    const data = await r.json();
    document.getElementById('detail-title').textContent = 'Key: ' + data.name + ' (' + maskKey(data.key) + ')';
    let html = '<table><thead><tr><th>ID</th><th>Task ID</th><th>Endpoint</th><th>Time</th></tr></thead><tbody>';
    if (data.usage_log.length === 0) {
      html += '<tr><td colspan="4" style="color:var(--text-muted)">No usage yet</td></tr>';
    } else {
      data.usage_log.forEach(l => {
        html += `<tr><td>${l.id}</td><td style="font-family:monospace;font-size:.75rem">${l.task_id}</td><td>${l.endpoint}</td><td>${l.created_at}</td></tr>`;
      });
    }
    html += '</tbody></table>';
    document.getElementById('detail-log').innerHTML = html;
    document.getElementById('detail-panel').style.display = 'block';
    document.getElementById('detail-panel').scrollIntoView({behavior:'smooth'});
  } catch(e) { console.error(e); }
}

function hideDetail() {
  document.getElementById('detail-panel').style.display = 'none';
}

// --- Create ---
function showCreateModal() { document.getElementById('create-modal').classList.add('show'); }
function hideCreateModal() { document.getElementById('create-modal').classList.remove('show'); }

async function createKey() {
  const name = document.getElementById('create-name').value.trim();
  const quota = parseInt(document.getElementById('create-quota').value);
  if (!name || !quota) return;
  const body = {name, quota};
  const whUrl = document.getElementById('create-webhook-url').value.trim();
  const whSecret = document.getElementById('create-webhook-secret').value.trim();
  if (whUrl) body.webhook_url = whUrl;
  if (whSecret) body.webhook_secret = whSecret;
  try {
    const r = await fetch(API + '/api/admin/keys', {
      method: 'POST', headers: headers(),
      body: JSON.stringify(body)
    });
    if (r.ok) {
      const data = await r.json();
      alert('Key created!\\n\\n' + data.key + '\\n\\nCopy it now, it won\\'t be shown in full again.');
      hideCreateModal();
      document.getElementById('create-name').value = '';
      document.getElementById('create-quota').value = '100';
      document.getElementById('create-webhook-url').value = '';
      document.getElementById('create-webhook-secret').value = '';
      await loadKeys();
    }
  } catch(e) { console.error(e); }
}

// --- Edit ---
function showEditModal(key, remaining, total, active, webhookUrl) {
  document.getElementById('edit-key-id').value = key;
  document.getElementById('edit-remaining').value = remaining;
  document.getElementById('edit-total').value = total;
  document.getElementById('edit-active').value = active ? 'true' : 'false';
  document.getElementById('edit-webhook-url').value = webhookUrl || '';
  document.getElementById('edit-webhook-secret').value = '';
  document.getElementById('edit-modal').classList.add('show');
}
function hideEditModal() { document.getElementById('edit-modal').classList.remove('show'); }

async function saveEdit() {
  const key = document.getElementById('edit-key-id').value;
  const body = {
    quota_remaining: parseInt(document.getElementById('edit-remaining').value),
    quota_total: parseInt(document.getElementById('edit-total').value),
    active: document.getElementById('edit-active').value === 'true'
  };
  const whUrl = document.getElementById('edit-webhook-url').value.trim();
  body.webhook_url = whUrl || '';
  const whSecret = document.getElementById('edit-webhook-secret').value.trim();
  if (whSecret) body.webhook_secret = whSecret;
  try {
    await fetch(API + '/api/admin/keys/' + key, {
      method: 'PATCH', headers: headers(),
      body: JSON.stringify(body)
    });
    hideEditModal();
    await loadKeys();
  } catch(e) { console.error(e); }
}

// --- Delete ---
async function deleteKey(key) {
  if (!confirm('Delete this API key? This cannot be undone.')) return;
  try {
    await fetch(API + '/api/admin/keys/' + key, {method: 'DELETE', headers: headers()});
    hideDetail();
    await loadKeys();
  } catch(e) { console.error(e); }
}

// --- Tester: Key selector ---
let _allKeys = [];
function updateKeySelector(keys) {
  _allKeys = keys;
  const sel = document.getElementById('test-auth-key');
  const prev = sel.value;
  sel.innerHTML = '<option value="__admin__">Use Admin Key</option>';
  keys.filter(k => k.active).forEach(k => {
    const o = document.createElement('option');
    o.value = k.key;
    o.textContent = k.name + ' (' + maskKey(k.key) + ')  [' + k.quota_remaining + ' left]';
    sel.appendChild(o);
  });
  if (prev) sel.value = prev;
}

function getTestKey() {
  const v = document.getElementById('test-auth-key').value;
  return v === '__admin__' ? adminKey : v;
}

// --- Tester: Tabs ---
function switchTab(name) {
  document.querySelectorAll('.ep-section').forEach(el => el.classList.remove('visible'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('visible');
  event.target.classList.add('active');
}

// --- Tester: Presets ---
const PRESETS = {
  gen: [
    {
      context: "Our methodology employs a Convolutional Neural Network (CNN) with three convolutional blocks. Each block consists of a 3x3 convolution layer, batch normalization, ReLU activation, and 2x2 max pooling. The feature maps are 64, 128, and 256 channels respectively. The output is flattened and passed through two fully connected layers (512 units, 10 units) with dropout (p=0.5) for classification.",
      caption: "Figure 1: Architecture of the proposed CNN model for image classification"
    },
    {
      context: "The pipeline consists of four stages: (1) Data preprocessing with tokenization and embedding using a learned positional encoding, (2) A 6-layer Transformer encoder with multi-head self-attention (8 heads, d_model=512), (3) A task-specific decoder head with cross-attention, and (4) A post-processing module that converts logits to structured output. Skip connections and layer normalization are applied throughout.",
      caption: "Figure 2: End-to-end Transformer-based NLP pipeline"
    },
    {
      context: "We train a Generative Adversarial Network (GAN) with the following setup: The Generator takes a 100-dimensional noise vector z, applies transposed convolutions to upsample through 512, 256, 128, and 64 feature maps, producing a 64x64 RGB image. The Discriminator mirrors this with strided convolutions and LeakyReLU. We use spectral normalization in the discriminator and a hinge loss objective. Training alternates between D and G steps with a 1:1 ratio.",
      caption: "Figure 3: GAN architecture for image synthesis with spectral normalization"
    },
    {
      context: "We propose a Federated Learning framework with N=100 clients. Each round, 10% of clients are randomly selected. Selected clients perform 5 local SGD epochs on their private data, then upload model updates (gradients) to the central server. The server applies Federated Averaging (FedAvg) to aggregate updates, optionally with differential privacy (epsilon=8, delta=1e-5). The global model is redistributed and the process repeats for 200 communication rounds.",
      caption: "Figure 4: Federated Learning workflow with differential privacy guarantees"
    }
  ],
  plot: [
    {
      data: JSON.stringify({"models":["ResNet-50","ViT-B/16","EfficientNet-B4","DeiT-Small","ConvNeXt-T"],"ImageNet Top-1":[76.1,81.8,82.9,79.8,82.1],"CIFAR-100":[86.3,92.1,91.5,89.7,91.8],"Flowers-102":[94.2,97.6,96.8,95.1,97.2]}, null, 2),
      intent: "Grouped bar chart comparing model accuracy across three datasets, with distinct colors per dataset and value labels on each bar"
    },
    {
      data: JSON.stringify({"epoch":[1,2,3,4,5,10,15,20,25,30,40,50,60,80,100],"train_loss":[2.45,1.82,1.41,1.15,0.98,0.52,0.34,0.25,0.19,0.15,0.09,0.06,0.04,0.025,0.018],"val_loss":[2.48,1.90,1.55,1.35,1.22,0.78,0.62,0.55,0.51,0.49,0.47,0.46,0.46,0.47,0.48]}, null, 2),
      intent: "Line plot showing training loss and validation loss over epochs, with log scale on y-axis, highlighting the overfitting gap"
    },
    {
      data: JSON.stringify({"variant":["Full Model","w/o Attention","w/o Skip Conn","w/o BN","w/o Augmentation","w/o Pretrain"],"Accuracy":[94.2,91.8,90.5,89.3,92.1,87.6],"F1 Score":[93.8,91.2,89.9,88.7,91.5,86.9]}, null, 2),
      intent: "Horizontal bar chart for ablation study showing accuracy and F1 for each variant, sorted by accuracy descending, with the full model highlighted"
    },
    {
      data: JSON.stringify({"attention_scores":[0.02,0.05,0.03,0.12,0.08,0.15,0.22,0.31,0.45,0.52,0.48,0.41,0.35,0.28,0.18,0.11,0.07,0.04,0.02,0.01,0.55,0.62,0.71,0.58,0.43,0.38,0.25,0.19,0.33,0.29],"bin_count":30}, null, 2),
      intent: "Histogram of attention score distribution with 30 bins, KDE overlay, showing the frequency distribution across attention heads"
    }
  ]
};

function loadPreset(type, idx) {
  const p = PRESETS[type][idx];
  if (type === 'gen') {
    document.getElementById('gen-context').value = p.context;
    document.getElementById('gen-caption').value = p.caption;
  } else {
    document.getElementById('plot-data').value = p.data;
    document.getElementById('plot-intent').value = p.intent;
  }
  // highlight active chip
  const container = document.getElementById('tab-' + (type === 'gen' ? 'generate' : 'plot'));
  container.querySelectorAll('.preset-chip').forEach((c,i) => {
    c.classList.toggle('active', i === idx);
  });
}

// --- Tester: Render result ---
function renderPollStatus(el, status, taskId) {
  let icon = '';
  if (status === 'pending') icon = '&#9711;';
  else if (status === 'running') icon = '<span class="spinner"></span>';
  else if (status === 'completed') icon = '&#10003;';
  else icon = '&#10007;';
  el.innerHTML = `<div class="poll-status ${status}">${icon} Task <code>${taskId}</code> — <strong>${status}</strong></div>`;
}

function renderTaskResult(el, data) {
  let html = '';
  renderPollStatus({innerHTML:''}, data.status, data.task_id);
  html += `<div class="poll-status ${data.status}">`;
  if (data.status === 'running') html += '<span class="spinner"></span> ';
  else if (data.status === 'completed') html += '&#10003; ';
  else if (data.status === 'failed') html += '&#10007; ';
  else html += '&#9711; ';
  html += `Task <code style="margin:0 4px">${data.task_id}</code> — <strong>${data.status}</strong> (${data.diagram_type})</div>`;

  if (data.error) {
    html += `<div style="margin-top:10px;padding:12px;background:rgba(248,81,73,.1);border:1px solid var(--red);border-radius:var(--radius);color:var(--red);font-size:.85rem">${esc(data.error)}</div>`;
  }
  if (data.description) {
    html += `<div class="result-desc"><strong>Description:</strong><br>${esc(data.description)}</div>`;
  }
  if (data.image_base64) {
    html += `<div class="result-image"><img src="data:image/png;base64,${data.image_base64}" alt="Generated image"><br>
      <button style="margin-top:8px" onclick="downloadBase64('${data.task_id}','${data.image_base64.substring(0,20)}')">Download PNG</button></div>`;
  }
  el.innerHTML = html;
}

function downloadBase64(name, _unused) {
  // find the img tag and extract the full src
  const img = document.querySelector('.result-image img');
  if (!img) return;
  const a = document.createElement('a');
  a.href = img.src;
  a.download = name + '.png';
  a.click();
}

// --- Tester: Poll task ---
let _pollTimers = {};
async function pollTask(taskId, resultEl, authKey) {
  const key = authKey || getTestKey();
  try {
    const r = await fetch(API + '/api/tasks/' + taskId, {headers: {'Authorization': 'Bearer ' + key}});
    if (!r.ok) {
      resultEl.innerHTML = `<div class="poll-status failed">&#10007; Error fetching task: HTTP ${r.status}</div>`;
      return;
    }
    const data = await r.json();
    renderTaskResult(resultEl, data);
    if (data.status === 'pending' || data.status === 'running') {
      _pollTimers[taskId] = setTimeout(() => pollTask(taskId, resultEl, key), 3000);
    } else {
      await loadKeys(); // refresh stats after completion
    }
  } catch(e) {
    resultEl.innerHTML = `<div class="poll-status failed">&#10007; ${esc(e.message)}</div>`;
  }
}

// --- Tester: Submit generate ---
async function submitGenerate() {
  const context = document.getElementById('gen-context').value.trim();
  const caption = document.getElementById('gen-caption').value.trim();
  const iterations = parseInt(document.getElementById('gen-iter').value);
  const resultEl = document.getElementById('gen-result');

  if (!context) { alert('Please enter source context'); return; }
  if (!caption) { alert('Please enter a figure caption'); return; }

  resultEl.innerHTML = '<div class="poll-status running"><span class="spinner"></span> Submitting...</div>';

  try {
    const r = await fetch(API + '/api/generate', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + getTestKey(), 'Content-Type': 'application/json'},
      body: JSON.stringify({source_context: context, caption: caption, iterations: iterations})
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: 'HTTP ' + r.status}));
      resultEl.innerHTML = `<div class="poll-status failed">&#10007; ${esc(err.detail || JSON.stringify(err))}</div>`;
      return;
    }
    const data = await r.json();
    renderPollStatus(resultEl, data.status, data.task_id);
    pollTask(data.task_id, resultEl);
  } catch(e) {
    resultEl.innerHTML = `<div class="poll-status failed">&#10007; ${esc(e.message)}</div>`;
  }
}

// --- Tester: Submit plot ---
async function submitPlot() {
  const dataStr = document.getElementById('plot-data').value.trim();
  const intent = document.getElementById('plot-intent').value.trim();
  const iterations = parseInt(document.getElementById('plot-iter').value);
  const resultEl = document.getElementById('plot-result');

  if (!dataStr) { alert('Please enter JSON data'); return; }
  if (!intent) { alert('Please describe the desired plot'); return; }
  try { JSON.parse(dataStr); } catch(e) { alert('Invalid JSON: ' + e.message); return; }

  resultEl.innerHTML = '<div class="poll-status running"><span class="spinner"></span> Submitting...</div>';

  try {
    const r = await fetch(API + '/api/plot', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + getTestKey(), 'Content-Type': 'application/json'},
      body: JSON.stringify({data_json: dataStr, intent: intent, iterations: iterations})
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: 'HTTP ' + r.status}));
      resultEl.innerHTML = `<div class="poll-status failed">&#10007; ${esc(err.detail || JSON.stringify(err))}</div>`;
      return;
    }
    const data = await r.json();
    renderPollStatus(resultEl, data.status, data.task_id);
    pollTask(data.task_id, resultEl);
  } catch(e) {
    resultEl.innerHTML = `<div class="poll-status failed">&#10007; ${esc(e.message)}</div>`;
  }
}

// --- Tester: Task lookup ---
async function lookupTask() {
  const taskId = document.getElementById('task-id-input').value.trim();
  const resultEl = document.getElementById('task-result');
  if (!taskId) { alert('Please enter a task ID'); return; }

  resultEl.innerHTML = '<div class="poll-status running"><span class="spinner"></span> Looking up...</div>';
  try {
    const r = await fetch(API + '/api/tasks/' + taskId, {
      headers: {'Authorization': 'Bearer ' + getTestKey()}
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail: 'HTTP ' + r.status}));
      resultEl.innerHTML = `<div class="poll-status failed">&#10007; ${esc(err.detail || JSON.stringify(err))}</div>`;
      return;
    }
    const data = await r.json();
    renderTaskResult(resultEl, data);
    if (data.status === 'pending' || data.status === 'running') {
      pollTask(taskId, resultEl);
    }
  } catch(e) {
    resultEl.innerHTML = `<div class="poll-status failed">&#10007; ${esc(e.message)}</div>`;
  }
}

async function downloadTaskImage() {
  const taskId = document.getElementById('task-id-input').value.trim();
  if (!taskId) { alert('Please enter a task ID'); return; }
  window.open(API + '/api/tasks/' + taskId + '/image?authorization=Bearer ' + encodeURIComponent(getTestKey()), '_blank');
}

// --- Tester: Raw request ---
async function runRaw() {
  const ep = document.getElementById('raw-endpoint').value;
  let [method, path] = ep.split(' ');
  if (path.includes('{task_id}')) {
    const tid = prompt('Enter task ID:');
    if (!tid) return;
    path = path.replace('{task_id}', tid);
  }
  const bodyStr = document.getElementById('raw-body').value.trim();
  const statusEl = document.getElementById('raw-status');
  const respEl = document.getElementById('raw-response');

  statusEl.textContent = 'Sending...';
  statusEl.style.color = 'var(--text-muted)';
  respEl.style.display = 'none';

  const opts = {method, headers: {'Authorization': 'Bearer ' + getTestKey(), 'Content-Type': 'application/json'}};
  if (method === 'POST' && bodyStr) opts.body = bodyStr;

  const t0 = performance.now();
  try {
    const r = await fetch(API + path, opts);
    const ms = Math.round(performance.now() - t0);
    let text;
    const ct = r.headers.get('content-type') || '';
    if (ct.includes('json')) {
      text = JSON.stringify(await r.json(), null, 2);
    } else {
      text = await r.text();
    }
    statusEl.textContent = r.status + ' ' + r.statusText + ' — ' + ms + 'ms';
    statusEl.style.color = r.ok ? 'var(--green)' : 'var(--red)';
    respEl.textContent = text;
    respEl.style.display = 'block';
  } catch(e) {
    statusEl.textContent = 'Error: ' + e.message;
    statusEl.style.color = 'var(--red)';
  }
}

// --- Init ---
if (adminKey) {
  fetch(API + '/api/admin/keys', {headers: headers()})
    .then(r => { if (r.ok) showDashboard(); else doLogout(); })
    .catch(() => doLogout());
} else {
  document.getElementById('login-page').style.display = 'flex';
}
</script>
</body>
</html>
"""


@app.get("/adm", response_class=HTMLResponse)
async def admin_page():
    return ADMIN_HTML


# ---------------------------------------------------------------------------
# API Documentation page
# ---------------------------------------------------------------------------

DOC_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PaperBanana API Documentation</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#1c2129;--border:#30363d;
  --text:#e6edf3;--text-muted:#8b949e;--text-dim:#484f58;
  --accent:#58a6ff;--accent-hover:#79c0ff;
  --green:#3fb950;--red:#f85149;--yellow:#d29922;--purple:#bc8cff;--orange:#f0883e;
  --radius:8px;--shadow:0 2px 8px rgba(0,0,0,.3);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.7;min-height:100vh}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{font-family:'SF Mono',SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace;
  font-size:.85em;background:var(--surface2);padding:2px 6px;border-radius:4px;color:var(--orange)}
pre{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:16px;overflow-x:auto;font-family:'SF Mono',SFMono-Regular,Consolas,monospace;
  font-size:.82rem;line-height:1.6;margin:12px 0;color:var(--text)}
pre code{background:none;padding:0;color:inherit}

/* Layout */
.page{display:flex;min-height:100vh}
.sidebar{width:260px;background:var(--surface);border-right:1px solid var(--border);
  position:fixed;top:0;left:0;bottom:0;overflow-y:auto;padding:20px 0;z-index:50}
.sidebar-header{padding:0 20px 16px;border-bottom:1px solid var(--border);margin-bottom:12px}
.sidebar-header h1{font-size:1.1rem;display:flex;align-items:center;gap:8px}
.sidebar-header .ver{font-size:.7rem;color:var(--text-muted);font-weight:400}
.sidebar nav a{display:block;padding:6px 20px;font-size:.85rem;color:var(--text-muted);
  transition:all .15s;border-left:3px solid transparent}
.sidebar nav a:hover{color:var(--text);background:rgba(88,166,255,.04);text-decoration:none}
.sidebar nav a.active{color:var(--accent);border-left-color:var(--accent);background:rgba(88,166,255,.06)}
.sidebar nav .group{font-size:.7rem;text-transform:uppercase;letter-spacing:.8px;
  color:var(--text-dim);padding:14px 20px 6px;font-weight:600}
.main{margin-left:260px;flex:1;max-width:900px;padding:32px 40px 80px}

/* Headings */
h2{font-size:1.4rem;margin:48px 0 16px;padding-bottom:8px;border-bottom:1px solid var(--border)}
h2:first-of-type{margin-top:0}
h3{font-size:1.1rem;margin:32px 0 12px;color:var(--accent)}
h4{font-size:.95rem;margin:20px 0 8px}

/* Method badges */
.method{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;
  font-weight:700;font-family:monospace;margin-right:6px;letter-spacing:.5px}
.method.get{background:rgba(63,185,80,.15);color:var(--green)}
.method.post{background:rgba(88,166,255,.15);color:var(--accent)}
.method.patch{background:rgba(210,153,34,.15);color:var(--yellow)}
.method.delete{background:rgba(248,81,73,.15);color:var(--red)}
.endpoint-path{font-family:monospace;font-size:.95rem;font-weight:600}

/* Tables */
table{width:100%;border-collapse:collapse;font-size:.85rem;margin:12px 0}
th,td{text-align:left;padding:8px 12px;border:1px solid var(--border)}
th{background:var(--surface);color:var(--text-muted);font-weight:600;font-size:.8rem}
td code{font-size:.8rem}

/* Tabs for code examples */
.code-tabs{margin:12px 0 16px}
.code-tab-btns{display:flex;gap:0;border-bottom:2px solid var(--border)}
.code-tab-btn{padding:6px 16px;font-size:.8rem;cursor:pointer;color:var(--text-muted);
  border-bottom:2px solid transparent;margin-bottom:-2px;background:none;border-top:none;
  border-left:none;border-right:none;font-family:inherit}
.code-tab-btn:hover{color:var(--text)}
.code-tab-btn.active{color:var(--accent);border-bottom-color:var(--accent)}
.code-tab-content{display:none}
.code-tab-content.active{display:block}

/* Info boxes */
.info-box{padding:12px 16px;border-radius:var(--radius);margin:12px 0;font-size:.85rem;
  border-left:4px solid}
.info-box.note{background:rgba(88,166,255,.06);border-color:var(--accent);color:var(--accent)}
.info-box.warn{background:rgba(210,153,34,.06);border-color:var(--yellow);color:var(--yellow)}
.info-box.tip{background:rgba(63,185,80,.06);border-color:var(--green);color:var(--green)}
.info-box strong{display:block;margin-bottom:2px}

/* Responsive */
@media(max-width:768px){
  .sidebar{display:none}
  .main{margin-left:0;padding:20px 16px 60px}
}
/* Copy button */
.pre-wrap{position:relative}
.pre-wrap .copy-btn{position:absolute;top:8px;right:8px;font-size:.7rem;padding:3px 8px;
  background:var(--surface2);border:1px solid var(--border);border-radius:4px;
  color:var(--text-muted);cursor:pointer;opacity:0;transition:opacity .2s}
.pre-wrap:hover .copy-btn{opacity:1}
.pre-wrap .copy-btn:hover{color:var(--accent);border-color:var(--accent)}
</style>
</head>
<body>
<div class="page">

<!-- Sidebar -->
<aside class="sidebar">
  <div class="sidebar-header">
    <h1>&#127820; PaperBanana <span class="ver">v0.1.2</span></h1>
  </div>
  <nav>
    <div class="group">Getting Started</div>
    <a href="#overview">Overview</a>
    <a href="#base-url">Base URL</a>
    <a href="#authentication">Authentication</a>
    <a href="#workflow">Workflow</a>
    <a href="#errors">Error Handling</a>

    <div class="group">Public</div>
    <a href="#health">Health Check</a>

    <div class="group">Generation</div>
    <a href="#generate">Generate Diagram</a>
    <a href="#plot">Generate Plot</a>
    <a href="#webhooks">Webhooks</a>
    <a href="#get-task">Get Task Status</a>
    <a href="#get-image">Download Image</a>

    <div class="group">Admin</div>
    <a href="#create-key">Create Key</a>
    <a href="#list-keys">List Keys</a>
    <a href="#get-key">Get Key Detail</a>
    <a href="#update-key">Update Key</a>
    <a href="#delete-key">Delete Key</a>

    <div class="group">Links</div>
    <a href="/adm">Admin Panel</a>
  </nav>
</aside>

<!-- Main Content -->
<main class="main">

<!-- ============================================================ -->
<h2 id="overview">Overview</h2>
<p>
  PaperBanana is an agentic API for generating publication-quality academic illustrations.
  It supports two modes:
</p>
<ul style="margin:12px 0 12px 24px">
  <li><strong>Methodology Diagrams</strong> &mdash; Generate architecture / pipeline / workflow diagrams from paper text</li>
  <li><strong>Statistical Plots</strong> &mdash; Generate bar charts, line plots, histograms, etc. from raw data</li>
</ul>
<p>
  The API uses an <strong>asynchronous task-based workflow</strong>: you submit a generation request,
  receive a <code>task_id</code>, then poll for the result. Generation typically takes 30&ndash;120 seconds
  depending on complexity and iterations.
</p>

<!-- ============================================================ -->
<h2 id="base-url">Base URL</h2>
<pre><code>https://pb.gptayn.com</code></pre>
<p>All endpoints are relative to this base URL.</p>

<!-- ============================================================ -->
<h2 id="authentication">Authentication</h2>
<p>
  All generation and admin endpoints require a <strong>Bearer token</strong> in the
  <code>Authorization</code> header:
</p>
<pre><code>Authorization: Bearer pb_xxxxxxxxxxxxxxxxxxxxxxxxxxxx</code></pre>

<table>
  <tr><th>Token Type</th><th>Access</th><th>How to Get</th></tr>
  <tr>
    <td><code>API Key</code></td>
    <td>Generation endpoints (<code>/api/generate</code>, <code>/api/plot</code>, <code>/api/tasks/*</code>)</td>
    <td>Created by admin via <code>POST /api/admin/keys</code> or admin panel</td>
  </tr>
  <tr>
    <td><code>Admin Key</code></td>
    <td>Admin endpoints (<code>/api/admin/*</code>)</td>
    <td>Set via <code>PAPERBANANA_ADMIN_KEY</code> environment variable</td>
  </tr>
</table>

<div class="info-box note">
  <strong>Note</strong>
  Each API key has a quota. Every generation request (generate or plot) consumes 1 quota unit.
  When quota is exhausted, the API returns <code>403 Quota exhausted</code>.
</div>

<!-- ============================================================ -->
<h2 id="workflow">Typical Workflow</h2>
<p>The standard workflow has 3 steps:</p>
<pre><code>1. POST /api/generate  (or /api/plot)   &rarr;  { task_id, status: "pending" }
2. GET  /api/tasks/{task_id}             &rarr;  { status: "running" }   (poll every 3-5s)
3. GET  /api/tasks/{task_id}             &rarr;  { status: "completed", image_base64: "...", description: "..." }
   or
   GET  /api/tasks/{task_id}/image       &rarr;  PNG file download</code></pre>

<div class="info-box tip">
  <strong>Tip</strong>
  For a complete end-to-end example, see the Python and JavaScript examples under each endpoint below.
</div>

<!-- ============================================================ -->
<h2 id="errors">Error Handling</h2>
<table>
  <tr><th>HTTP Code</th><th>Meaning</th><th>Common Cause</th></tr>
  <tr><td><code>401</code></td><td>Unauthorized</td><td>Missing or invalid API key / admin key</td></tr>
  <tr><td><code>403</code></td><td>Forbidden</td><td>API key disabled or quota exhausted</td></tr>
  <tr><td><code>404</code></td><td>Not Found</td><td>Task ID not found, or task belongs to another key</td></tr>
  <tr><td><code>422</code></td><td>Validation Error</td><td>Missing required fields, invalid JSON, parameter out of range</td></tr>
  <tr><td><code>500</code></td><td>Server Error</td><td>Internal error (admin key not configured, etc.)</td></tr>
</table>
<p>Error responses return JSON:</p>
<pre><code>{
  "detail": "Human-readable error message"
}</code></pre>

<!-- ============================================================ -->
<!-- PUBLIC -->
<!-- ============================================================ -->
<h2 id="health">Health Check</h2>
<p><span class="method get">GET</span><span class="endpoint-path">/api/health</span></p>
<p>Check if the API is running. No authentication required.</p>

<h4>Response <code>200</code></h4>
<pre><code>{
  "status": "ok",
  "version": "0.1.2"
}</code></pre>

<div class="code-tabs" data-group="health">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'health','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'health','js')">JavaScript</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'health','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="health-curl">
    <pre><code>curl https://pb.gptayn.com/api/health</code></pre>
  </div>
  <div class="code-tab-content" data-tab="health-js">
    <pre><code>const res = await fetch("https://pb.gptayn.com/api/health");
const data = await res.json();
console.log(data);  // { status: "ok", version: "0.1.2" }</code></pre>
  </div>
  <div class="code-tab-content" data-tab="health-py">
    <pre><code>import requests

r = requests.get("https://pb.gptayn.com/api/health")
print(r.json())  # {'status': 'ok', 'version': '0.1.2'}</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<!-- GENERATION -->
<!-- ============================================================ -->
<h2 id="generate">Generate Methodology Diagram</h2>
<p><span class="method post">POST</span><span class="endpoint-path">/api/generate</span></p>
<p>
  Submit a methodology text excerpt to generate an academic-style architecture or workflow diagram.
  Returns a task ID for polling.
</p>

<h4>Request Body</h4>
<table>
  <tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
  <tr><td><code>source_context</code></td><td>string</td><td>Yes</td><td>The methodology text or paper excerpt to illustrate</td></tr>
  <tr><td><code>caption</code></td><td>string</td><td>Yes</td><td>The figure caption (e.g. "Figure 1: Overview of...")</td></tr>
  <tr><td><code>iterations</code></td><td>integer</td><td>No</td><td>Refinement iterations, 1&ndash;10 (default: <code>3</code>). More = better quality, slower</td></tr>
</table>

<h4>Response <code>202 Accepted</code></h4>
<pre><code>{
  "task_id": "a1b2c3d4e5f6...",
  "status": "pending"
}</code></pre>

<div class="info-box warn">
  <strong>Quota</strong>
  This endpoint deducts 1 quota from your API key immediately upon submission.
</div>

<div class="code-tabs" data-group="generate">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'generate','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'generate','js')">JavaScript</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'generate','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="generate-curl">
    <pre><code>curl -X POST https://pb.gptayn.com/api/generate \\
  -H "Authorization: Bearer pb_your_api_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "source_context": "Our model uses a 6-layer Transformer encoder with multi-head self-attention (8 heads, d_model=512). Input tokens are embedded and combined with positional encodings before entering the encoder stack. The output is passed through a linear classification head.",
    "caption": "Figure 1: Transformer encoder architecture",
    "iterations": 3
  }'</code></pre>
  </div>
  <div class="code-tab-content" data-tab="generate-js">
    <pre><code>const API_KEY = "pb_your_api_key_here";
const BASE = "https://pb.gptayn.com";

// Step 1: Submit generation request
const submitRes = await fetch(`${BASE}/api/generate`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${API_KEY}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    source_context: "Our model uses a 6-layer Transformer encoder...",
    caption: "Figure 1: Transformer encoder architecture",
    iterations: 3
  })
});
const { task_id } = await submitRes.json();
console.log("Task submitted:", task_id);

// Step 2: Poll for result
async function pollResult(taskId) {
  while (true) {
    const res = await fetch(`${BASE}/api/tasks/${taskId}`, {
      headers: { "Authorization": `Bearer ${API_KEY}` }
    });
    const task = await res.json();
    console.log("Status:", task.status);

    if (task.status === "completed") {
      console.log("Description:", task.description);
      // task.image_base64 contains the PNG as base64
      // To display in browser:
      // document.getElementById("img").src = "data:image/png;base64," + task.image_base64;
      return task;
    }
    if (task.status === "failed") {
      throw new Error(task.error);
    }
    await new Promise(r => setTimeout(r, 5000));  // wait 5s
  }
}

const result = await pollResult(task_id);</code></pre>
  </div>
  <div class="code-tab-content" data-tab="generate-py">
    <pre><code>import time
import base64
import requests

API_KEY = "pb_your_api_key_here"
BASE = "https://pb.gptayn.com"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Step 1: Submit
r = requests.post(f"{BASE}/api/generate", headers=HEADERS, json={
    "source_context": "Our model uses a 6-layer Transformer encoder...",
    "caption": "Figure 1: Transformer encoder architecture",
    "iterations": 3,
})
r.raise_for_status()
task_id = r.json()["task_id"]
print(f"Task submitted: {task_id}")

# Step 2: Poll until done
while True:
    r = requests.get(f"{BASE}/api/tasks/{task_id}", headers=HEADERS)
    task = r.json()
    print(f"Status: {task['status']}")

    if task["status"] == "completed":
        # Save the image
        img_data = base64.b64decode(task["image_base64"])
        with open("output.png", "wb") as f:
            f.write(img_data)
        print(f"Image saved! Description: {task['description']}")
        break
    elif task["status"] == "failed":
        print(f"Error: {task['error']}")
        break

    time.sleep(5)  # poll every 5 seconds</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<h2 id="plot">Generate Statistical Plot</h2>
<p><span class="method post">POST</span><span class="endpoint-path">/api/plot</span></p>
<p>
  Submit structured data and a description to generate an academic-quality plot
  (bar charts, line plots, histograms, scatter plots, etc.).
</p>

<h4>Request Body</h4>
<table>
  <tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
  <tr><td><code>data_json</code></td><td>string</td><td>Yes</td><td>JSON string containing the data to plot (any structure: arrays, objects, nested)</td></tr>
  <tr><td><code>intent</code></td><td>string</td><td>Yes</td><td>Description of the desired plot (chart type, axes, style, etc.)</td></tr>
  <tr><td><code>iterations</code></td><td>integer</td><td>No</td><td>Refinement iterations, 1&ndash;10 (default: <code>3</code>)</td></tr>
</table>

<h4>Response <code>202 Accepted</code></h4>
<pre><code>{
  "task_id": "f7e8d9c0b1a2...",
  "status": "pending"
}</code></pre>

<div class="code-tabs" data-group="plot">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'plot','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'plot','js')">JavaScript</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'plot','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="plot-curl">
    <pre><code>curl -X POST https://pb.gptayn.com/api/plot \\
  -H "Authorization: Bearer pb_your_api_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "data_json": "{\\\"models\\\":[\\\"ResNet-50\\\",\\\"ViT-B/16\\\",\\\"EfficientNet\\\"],\\\"accuracy\\\":[76.1,81.8,82.9]}",
    "intent": "Bar chart comparing model accuracy with value labels on each bar",
    "iterations": 3
  }'</code></pre>
  </div>
  <div class="code-tab-content" data-tab="plot-js">
    <pre><code>const data = {
  models: ["ResNet-50", "ViT-B/16", "EfficientNet-B4"],
  accuracy: [76.1, 81.8, 82.9]
};

const res = await fetch("https://pb.gptayn.com/api/plot", {
  method: "POST",
  headers: {
    "Authorization": "Bearer pb_your_api_key_here",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    data_json: JSON.stringify(data),  // Note: data_json is a JSON string
    intent: "Bar chart comparing model accuracy with value labels",
    iterations: 3
  })
});

const { task_id } = await res.json();
// Then poll with GET /api/tasks/{task_id} as shown above</code></pre>
  </div>
  <div class="code-tab-content" data-tab="plot-py">
    <pre><code>import json
import requests

data = {
    "models": ["ResNet-50", "ViT-B/16", "EfficientNet-B4"],
    "accuracy": [76.1, 81.8, 82.9],
}

r = requests.post("https://pb.gptayn.com/api/plot", headers=HEADERS, json={
    "data_json": json.dumps(data),   # Must be a JSON string
    "intent": "Bar chart comparing model accuracy with value labels",
    "iterations": 3,
})
task_id = r.json()["task_id"]
# Then poll with GET /api/tasks/{task_id} as shown above</code></pre>
  </div>
</div>

<div class="info-box note">
  <strong>Note on <code>data_json</code></strong>
  The <code>data_json</code> field must be a <strong>JSON string</strong> (i.e. double-serialized).
  In Python: <code>json.dumps(your_data)</code>. In JavaScript: <code>JSON.stringify(yourData)</code>.
  The API will parse it internally.
</div>

<!-- ============================================================ -->
<!-- WEBHOOKS -->
<!-- ============================================================ -->
<h2 id="webhooks">Webhooks</h2>
<p>
  Instead of polling for task completion, you can provide a <code>webhook_url</code> to receive
  an HTTP POST callback when the task finishes (or fails).
</p>

<h3>Configuration</h3>
<p>Webhooks can be configured at two levels:</p>
<table>
  <tr><th>Level</th><th>How</th><th>Precedence</th></tr>
  <tr>
    <td><strong>Per-key</strong> (default)</td>
    <td>Set <code>webhook_url</code> and <code>webhook_secret</code> when creating or updating an API key via the admin API</td>
    <td>Used when no per-request URL is provided</td>
  </tr>
  <tr>
    <td><strong>Per-request</strong> (override)</td>
    <td>Pass <code>webhook_url</code> in the <code>/api/generate</code> or <code>/api/plot</code> request body</td>
    <td>Overrides the per-key default</td>
  </tr>
</table>

<h4>Request fields (on generate / plot)</h4>
<table>
  <tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
  <tr><td><code>webhook_url</code></td><td>string</td><td>No</td><td>URL to POST the result to when task completes/fails</td></tr>
  <tr><td><code>webhook_include_image</code></td><td>boolean</td><td>No</td><td>If <code>true</code>, include <code>image_base64</code> in the payload (default: <code>false</code>)</td></tr>
</table>

<h3>Webhook Payload</h3>
<p>When a task completes or fails, PaperBanana sends an HTTP POST to the webhook URL:</p>
<pre><code>POST https://your-server.com/callback
Content-Type: application/json
X-PaperBanana-Event: task.completed
X-PaperBanana-Signature: sha256=a1b2c3d4...
User-Agent: PaperBanana-Webhook/0.1.2

{
  "event": "task.completed",
  "task_id": "a1b2c3d4e5f6...",
  "status": "completed",
  "diagram_type": "methodology",
  "description": "The diagram shows...",
  "image_url": "https://pb.gptayn.com/api/tasks/a1b2c3d4e5f6/image",
  "image_base64": null,
  "error": null,
  "created_at": "2026-02-15T10:30:00+00:00",
  "completed_at": "2026-02-15T10:31:25+00:00"
}</code></pre>

<div class="info-box note">
  <strong>Note</strong>
  <code>image_base64</code> is only populated when <code>webhook_include_image</code> is <code>true</code>.
  Otherwise, use <code>image_url</code> to fetch the image separately (requires Bearer token).
</div>

<h3>Signature Verification</h3>
<p>
  If a <code>webhook_secret</code> is configured on the API key, the request includes an
  <code>X-PaperBanana-Signature</code> header containing an HMAC-SHA256 signature of the
  request body, using the secret as the key.
</p>

<div class="code-tabs" data-group="webhook-verify">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'webhook-verify','py')">Python</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'webhook-verify','js')">JavaScript</button>
  </div>
  <div class="code-tab-content active" data-tab="webhook-verify-py">
    <pre><code>import hmac, hashlib

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# In your Flask/FastAPI handler:
# sig = request.headers.get("X-PaperBanana-Signature", "")
# is_valid = verify_signature(request.body, sig, "your-webhook-secret")</code></pre>
  </div>
  <div class="code-tab-content" data-tab="webhook-verify-js">
    <pre><code>const crypto = require("crypto");

function verifySignature(body, signature, secret) {
  const expected = "sha256=" + crypto
    .createHmac("sha256", secret)
    .update(body)
    .digest("hex");
  return crypto.timingSafeEqual(
    Buffer.from(expected), Buffer.from(signature)
  );
}

// In your Express handler:
// const sig = req.headers["x-paperbanana-signature"];
// const valid = verifySignature(JSON.stringify(req.body), sig, "your-secret");</code></pre>
  </div>
</div>

<h3>Retry Policy</h3>
<p>If the webhook delivery fails (network error or HTTP &ge; 400), PaperBanana retries up to <strong>3 times</strong>:</p>
<table>
  <tr><th>Attempt</th><th>Delay</th></tr>
  <tr><td>1st retry</td><td>5 seconds</td></tr>
  <tr><td>2nd retry</td><td>15 seconds</td></tr>
  <tr><td>3rd retry</td><td>60 seconds</td></tr>
</table>
<p>Webhook delivery status is visible in the <a href="/history">History</a> page for each task.</p>

<h3>Example: Generate with Webhook</h3>
<div class="code-tabs" data-group="webhook-ex">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'webhook-ex','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'webhook-ex','py')">Python</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'webhook-ex','js')">JavaScript</button>
  </div>
  <div class="code-tab-content active" data-tab="webhook-ex-curl">
    <pre><code>curl -X POST https://pb.gptayn.com/api/generate \\
  -H "Authorization: Bearer pb_your_api_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "source_context": "Our model uses a 6-layer Transformer encoder...",
    "caption": "Figure 1: Transformer architecture",
    "iterations": 3,
    "webhook_url": "https://your-server.com/pb-callback",
    "webhook_include_image": false
  }'

# Response: {"task_id": "abc123...", "status": "pending"}
# When done, PaperBanana POSTs the result to your webhook URL.</code></pre>
  </div>
  <div class="code-tab-content" data-tab="webhook-ex-py">
    <pre><code>import requests

r = requests.post("https://pb.gptayn.com/api/generate", headers=HEADERS, json={
    "source_context": "Our model uses a 6-layer Transformer encoder...",
    "caption": "Figure 1: Transformer architecture",
    "iterations": 3,
    "webhook_url": "https://your-server.com/pb-callback",
    "webhook_include_image": False,
})
print(r.json())  # {"task_id": "...", "status": "pending"}
# No polling needed! Your webhook endpoint will receive the result.</code></pre>
  </div>
  <div class="code-tab-content" data-tab="webhook-ex-js">
    <pre><code>const res = await fetch("https://pb.gptayn.com/api/generate", {
  method: "POST",
  headers: {
    "Authorization": "Bearer pb_your_api_key_here",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    source_context: "Our model uses a 6-layer Transformer encoder...",
    caption: "Figure 1: Transformer architecture",
    iterations: 3,
    webhook_url: "https://your-server.com/pb-callback",
    webhook_include_image: false
  })
});
// No polling needed — result will arrive at your webhook.</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<h2 id="get-task">Get Task Status &amp; Result</h2>
<p><span class="method get">GET</span><span class="endpoint-path">/api/tasks/{task_id}</span></p>
<p>
  Retrieve the current status of a generation task. Once completed,
  includes the generated image (base64) and description.
</p>

<h4>Path Parameters</h4>
<table>
  <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
  <tr><td><code>task_id</code></td><td>string</td><td>The task ID returned from generate/plot</td></tr>
</table>

<h4>Response <code>200</code></h4>
<pre><code>{
  "task_id": "a1b2c3d4e5f6...",
  "status": "completed",        // "pending" | "running" | "completed" | "failed"
  "diagram_type": "methodology", // or "statistical_plot"
  "image_base64": "iVBORw0KGgo...",  // PNG as base64 (only when completed)
  "description": "The diagram shows...", // (only when completed)
  "error": null                  // error message (only when failed)
}</code></pre>

<h4>Status Lifecycle</h4>
<table>
  <tr><th>Status</th><th>Meaning</th><th>Next Step</th></tr>
  <tr><td><code>pending</code></td><td>Task queued, not yet started</td><td>Keep polling (3&ndash;5s interval)</td></tr>
  <tr><td><code>running</code></td><td>Generation in progress</td><td>Keep polling</td></tr>
  <tr><td><code>completed</code></td><td>Done! Image available</td><td>Read <code>image_base64</code> or use <code>/image</code> endpoint</td></tr>
  <tr><td><code>failed</code></td><td>Generation failed</td><td>Check <code>error</code> field</td></tr>
</table>

<div class="code-tabs" data-group="task">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'task','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'task','js')">JavaScript</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'task','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="task-curl">
    <pre><code># Check task status
curl https://pb.gptayn.com/api/tasks/a1b2c3d4e5f6 \\
  -H "Authorization: Bearer pb_your_api_key_here"

# Poll in a loop (bash)
TASK_ID="a1b2c3d4e5f6"
while true; do
  STATUS=$(curl -s https://pb.gptayn.com/api/tasks/$TASK_ID \\
    -H "Authorization: Bearer pb_your_api_key_here" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 5
done</code></pre>
  </div>
  <div class="code-tab-content" data-tab="task-js">
    <pre><code>const res = await fetch("https://pb.gptayn.com/api/tasks/a1b2c3d4e5f6", {
  headers: { "Authorization": "Bearer pb_your_api_key_here" }
});
const task = await res.json();

if (task.status === "completed") {
  // Display image
  const img = document.createElement("img");
  img.src = "data:image/png;base64," + task.image_base64;
  document.body.appendChild(img);

  // Or download as file
  const link = document.createElement("a");
  link.href = img.src;
  link.download = task.task_id + ".png";
  link.click();
}</code></pre>
  </div>
  <div class="code-tab-content" data-tab="task-py">
    <pre><code>r = requests.get(
    "https://pb.gptayn.com/api/tasks/a1b2c3d4e5f6",
    headers=HEADERS
)
task = r.json()

if task["status"] == "completed":
    import base64
    img_bytes = base64.b64decode(task["image_base64"])
    with open("diagram.png", "wb") as f:
        f.write(img_bytes)
    print("Description:", task["description"])</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<h2 id="get-image">Download Task Image</h2>
<p><span class="method get">GET</span><span class="endpoint-path">/api/tasks/{task_id}/image</span></p>
<p>
  Download the generated image directly as a PNG file. Only available after the task is completed.
  This is an alternative to extracting <code>image_base64</code> from the task response.
</p>

<h4>Response <code>200</code></h4>
<p>Binary PNG file with <code>Content-Type: image/png</code></p>

<h4>Response <code>404</code></h4>
<p>Task not found, or image not yet available (task still running)</p>

<div class="code-tabs" data-group="image">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'image','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'image','js')">JavaScript</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'image','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="image-curl">
    <pre><code># Download image directly to file
curl -o diagram.png https://pb.gptayn.com/api/tasks/a1b2c3d4e5f6/image \\
  -H "Authorization: Bearer pb_your_api_key_here"</code></pre>
  </div>
  <div class="code-tab-content" data-tab="image-js">
    <pre><code>const res = await fetch("https://pb.gptayn.com/api/tasks/a1b2c3d4e5f6/image", {
  headers: { "Authorization": "Bearer pb_your_api_key_here" }
});
const blob = await res.blob();
const url = URL.createObjectURL(blob);

// Display
const img = document.createElement("img");
img.src = url;
document.body.appendChild(img);

// Or trigger download
const a = document.createElement("a");
a.href = url;
a.download = "diagram.png";
a.click();</code></pre>
  </div>
  <div class="code-tab-content" data-tab="image-py">
    <pre><code>r = requests.get(
    "https://pb.gptayn.com/api/tasks/a1b2c3d4e5f6/image",
    headers=HEADERS
)
r.raise_for_status()
with open("diagram.png", "wb") as f:
    f.write(r.content)
print(f"Downloaded {len(r.content)} bytes")</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<!-- ADMIN -->
<!-- ============================================================ -->
<h2 id="create-key">Create API Key</h2>
<p><span class="method post">POST</span><span class="endpoint-path">/api/admin/keys</span></p>
<p>Create a new API key with a specified name and quota. <strong>Requires admin key.</strong></p>

<h4>Request Body</h4>
<table>
  <tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
  <tr><td><code>name</code></td><td>string</td><td>Yes</td><td>A label for the key (e.g. "my-app", "research-team")</td></tr>
  <tr><td><code>quota</code></td><td>integer</td><td>Yes</td><td>Initial quota to assign (min: 1)</td></tr>
  <tr><td><code>webhook_url</code></td><td>string</td><td>No</td><td>Default webhook URL for all tasks using this key</td></tr>
  <tr><td><code>webhook_secret</code></td><td>string</td><td>No</td><td>Secret for HMAC-SHA256 signature on webhook payloads</td></tr>
</table>

<h4>Response <code>201 Created</code></h4>
<pre><code>{
  "key": "pb_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "name": "my-app",
  "quota_remaining": 100,
  "quota_total": 100,
  "total_used": 0,
  "active": true,
  "created_at": "2026-02-15T10:30:00+00:00",
  "webhook_url": "https://your-server.com/callback"
}</code></pre>

<div class="info-box warn">
  <strong>Important</strong>
  The full API key is only shown once in this response. Store it securely.
</div>

<div class="code-tabs" data-group="create-key">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'create-key','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'create-key','js')">JavaScript</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'create-key','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="create-key-curl">
    <pre><code>curl -X POST https://pb.gptayn.com/api/admin/keys \\
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "my-app", "quota": 100}'</code></pre>
  </div>
  <div class="code-tab-content" data-tab="create-key-js">
    <pre><code>const res = await fetch("https://pb.gptayn.com/api/admin/keys", {
  method: "POST",
  headers: {
    "Authorization": "Bearer YOUR_ADMIN_KEY",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({ name: "my-app", quota: 100 })
});
const newKey = await res.json();
console.log("New API Key:", newKey.key);  // Save this!</code></pre>
  </div>
  <div class="code-tab-content" data-tab="create-key-py">
    <pre><code>ADMIN_HEADERS = {"Authorization": "Bearer YOUR_ADMIN_KEY"}

r = requests.post("https://pb.gptayn.com/api/admin/keys",
    headers=ADMIN_HEADERS,
    json={"name": "my-app", "quota": 100}
)
new_key = r.json()
print(f"New API Key: {new_key['key']}")  # Save this!</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<h2 id="list-keys">List All Keys</h2>
<p><span class="method get">GET</span><span class="endpoint-path">/api/admin/keys</span></p>
<p>List all API keys with their usage stats. <strong>Requires admin key.</strong></p>

<h4>Response <code>200</code></h4>
<pre><code>[
  {
    "key": "pb_a1b2c3...",
    "name": "my-app",
    "quota_remaining": 87,
    "quota_total": 100,
    "total_used": 13,
    "active": true,
    "created_at": "2026-02-15T10:30:00+00:00"
  },
  ...
]</code></pre>

<div class="code-tabs" data-group="list-keys">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'list-keys','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'list-keys','js')">JavaScript</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'list-keys','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="list-keys-curl">
    <pre><code>curl https://pb.gptayn.com/api/admin/keys \\
  -H "Authorization: Bearer YOUR_ADMIN_KEY"</code></pre>
  </div>
  <div class="code-tab-content" data-tab="list-keys-js">
    <pre><code>const res = await fetch("https://pb.gptayn.com/api/admin/keys", {
  headers: { "Authorization": "Bearer YOUR_ADMIN_KEY" }
});
const keys = await res.json();
keys.forEach(k => {
  console.log(`${k.name}: ${k.quota_remaining}/${k.quota_total} remaining`);
});</code></pre>
  </div>
  <div class="code-tab-content" data-tab="list-keys-py">
    <pre><code>r = requests.get("https://pb.gptayn.com/api/admin/keys", headers=ADMIN_HEADERS)
for key in r.json():
    print(f"{key['name']}: {key['quota_remaining']}/{key['quota_total']} remaining")</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<h2 id="get-key">Get Key Detail</h2>
<p><span class="method get">GET</span><span class="endpoint-path">/api/admin/keys/{key}</span></p>
<p>Get full details of an API key including its usage log. <strong>Requires admin key.</strong></p>

<h4>Path Parameters</h4>
<table>
  <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
  <tr><td><code>key</code></td><td>string</td><td>The full API key string</td></tr>
</table>

<h4>Response <code>200</code></h4>
<pre><code>{
  "key": "pb_a1b2c3...",
  "name": "my-app",
  "quota_remaining": 87,
  "quota_total": 100,
  "total_used": 13,
  "active": true,
  "created_at": "2026-02-15T10:30:00+00:00",
  "usage_log": [
    {
      "id": 1,
      "task_id": "abc123...",
      "endpoint": "generate",
      "created_at": "2026-02-15T11:00:00+00:00"
    },
    ...
  ]
}</code></pre>

<div class="code-tabs" data-group="get-key">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'get-key','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'get-key','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="get-key-curl">
    <pre><code>curl https://pb.gptayn.com/api/admin/keys/pb_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6 \\
  -H "Authorization: Bearer YOUR_ADMIN_KEY"</code></pre>
  </div>
  <div class="code-tab-content" data-tab="get-key-py">
    <pre><code>api_key = "pb_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
r = requests.get(f"https://pb.gptayn.com/api/admin/keys/{api_key}", headers=ADMIN_HEADERS)
detail = r.json()
print(f"Usage log: {len(detail['usage_log'])} entries")</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<h2 id="update-key">Update API Key</h2>
<p><span class="method patch">PATCH</span><span class="endpoint-path">/api/admin/keys/{key}</span></p>
<p>Update quota or status of an API key. All fields are optional. <strong>Requires admin key.</strong></p>

<h4>Request Body</h4>
<table>
  <tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
  <tr><td><code>quota_remaining</code></td><td>integer</td><td>No</td><td>Set remaining quota (min: 0)</td></tr>
  <tr><td><code>quota_total</code></td><td>integer</td><td>No</td><td>Set total quota (min: 0)</td></tr>
  <tr><td><code>active</code></td><td>boolean</td><td>No</td><td>Enable or disable the key</td></tr>
  <tr><td><code>webhook_url</code></td><td>string</td><td>No</td><td>Update default webhook URL (empty string to remove)</td></tr>
  <tr><td><code>webhook_secret</code></td><td>string</td><td>No</td><td>Update webhook secret (empty string to remove)</td></tr>
</table>

<h4>Response <code>200</code></h4>
<p>Returns the updated key info (same schema as Create Key response).</p>

<div class="code-tabs" data-group="update-key">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'update-key','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'update-key','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="update-key-curl">
    <pre><code># Add 50 more quota and ensure key is active
curl -X PATCH https://pb.gptayn.com/api/admin/keys/pb_a1b2c3... \\
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"quota_remaining": 150, "quota_total": 200, "active": true}'

# Disable a key
curl -X PATCH https://pb.gptayn.com/api/admin/keys/pb_a1b2c3... \\
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"active": false}'</code></pre>
  </div>
  <div class="code-tab-content" data-tab="update-key-py">
    <pre><code># Recharge quota
r = requests.patch(
    f"https://pb.gptayn.com/api/admin/keys/{api_key}",
    headers=ADMIN_HEADERS,
    json={"quota_remaining": 150, "quota_total": 200}
)
print(r.json())

# Disable a key
requests.patch(
    f"https://pb.gptayn.com/api/admin/keys/{api_key}",
    headers=ADMIN_HEADERS,
    json={"active": False}
)</code></pre>
  </div>
</div>

<!-- ============================================================ -->
<h2 id="delete-key">Delete API Key</h2>
<p><span class="method delete">DELETE</span><span class="endpoint-path">/api/admin/keys/{key}</span></p>
<p>Permanently delete an API key and all its usage logs. <strong>This cannot be undone. Requires admin key.</strong></p>

<h4>Response <code>204 No Content</code></h4>
<p>Empty response body on success.</p>

<div class="code-tabs" data-group="delete-key">
  <div class="code-tab-btns">
    <button class="code-tab-btn active" onclick="showCodeTab(this,'delete-key','curl')">cURL</button>
    <button class="code-tab-btn" onclick="showCodeTab(this,'delete-key','py')">Python</button>
  </div>
  <div class="code-tab-content active" data-tab="delete-key-curl">
    <pre><code>curl -X DELETE https://pb.gptayn.com/api/admin/keys/pb_a1b2c3... \\
  -H "Authorization: Bearer YOUR_ADMIN_KEY"</code></pre>
  </div>
  <div class="code-tab-content" data-tab="delete-key-py">
    <pre><code>r = requests.delete(
    f"https://pb.gptayn.com/api/admin/keys/{api_key}",
    headers=ADMIN_HEADERS
)
assert r.status_code == 204</code></pre>
  </div>
</div>

</main>
</div>

<script>
function showCodeTab(btn, group, lang) {
  const tabs = btn.closest('.code-tabs');
  tabs.querySelectorAll('.code-tab-btn').forEach(b => b.classList.remove('active'));
  tabs.querySelectorAll('.code-tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  tabs.querySelector('[data-tab="' + group + '-' + lang + '"]').classList.add('active');
}

// Sidebar active state on scroll
const sections = document.querySelectorAll('h2[id], h3[id]');
const navLinks = document.querySelectorAll('.sidebar nav a[href^="#"]');
window.addEventListener('scroll', () => {
  let current = '';
  sections.forEach(s => {
    if (window.scrollY >= s.offsetTop - 80) current = s.id;
  });
  navLinks.forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === '#' + current);
  });
});
</script>
</body>
</html>
"""


@app.get("/doc", response_class=HTMLResponse)
async def doc_page():
    return DOC_HTML


# ---------------------------------------------------------------------------
# History page
# ---------------------------------------------------------------------------

HISTORY_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PaperBanana - History</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#1c2129;--border:#30363d;
  --text:#e6edf3;--text-muted:#8b949e;--text-dim:#484f58;
  --accent:#58a6ff;--accent-hover:#79c0ff;
  --green:#3fb950;--red:#f85149;--yellow:#d29922;--purple:#bc8cff;--orange:#f0883e;
  --radius:8px;--shadow:0 2px 8px rgba(0,0,0,.3);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.5;min-height:100vh}
a{color:var(--accent);text-decoration:none}
button{cursor:pointer;font-family:inherit;font-size:.875rem;border:1px solid var(--border);
  background:var(--surface);color:var(--text);padding:6px 16px;border-radius:var(--radius);
  transition:background .15s}
button:hover{background:var(--border)}
button.primary{background:var(--accent);color:#000;border-color:var(--accent);font-weight:600}
button.primary:hover{background:var(--accent-hover)}
input,select{font-family:inherit;font-size:.875rem;background:var(--bg);
  color:var(--text);border:1px solid var(--border);border-radius:var(--radius);
  padding:8px 12px;outline:none}
input:focus,select:focus{border-color:var(--accent)}
.container{max-width:1200px;margin:0 auto;padding:24px 16px}

/* Header */
header{display:flex;align-items:center;justify-content:space-between;padding:16px 0;
  border-bottom:1px solid var(--border);margin-bottom:24px;flex-wrap:wrap;gap:10px}
header h1{font-size:1.25rem;display:flex;align-items:center;gap:8px}
header .nav-links{display:flex;gap:8px;align-items:center}
header .nav-links a{font-size:.8rem;padding:5px 12px;border:1px solid var(--border);border-radius:var(--radius)}
header .nav-links a:hover{border-color:var(--accent);text-decoration:none}

/* Login */
#login-page{display:flex;align-items:center;justify-content:center;min-height:100vh}
.login-box{background:var(--surface);padding:40px;border-radius:12px;border:1px solid var(--border);
  width:100%;max-width:400px;box-shadow:var(--shadow)}
.login-box h1{font-size:1.5rem;margin-bottom:8px;text-align:center}
.login-box p{color:var(--text-muted);text-align:center;margin-bottom:24px;font-size:.875rem}
.login-box .logo{text-align:center;font-size:2.5rem;margin-bottom:16px}
.login-box input{margin-bottom:16px;width:100%}
.login-box button{width:100%}
.login-error{color:var(--red);font-size:.8rem;margin-bottom:12px;display:none}

/* Filters */
.filters{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;align-items:center}
.filters select,.filters input{width:auto}
.filters label{font-size:.8rem;color:var(--text-muted)}

/* Table */
.table-wrap{overflow-x:auto;margin-bottom:20px}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border)}
th{background:var(--surface);color:var(--text-muted);font-weight:600;font-size:.75rem;
  text-transform:uppercase;letter-spacing:.5px;position:sticky;top:0}
tr{cursor:pointer;transition:background .1s}
tr:hover td{background:rgba(88,166,255,.04)}
tr.selected td{background:rgba(88,166,255,.08)}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:600}
.badge.completed{background:rgba(63,185,80,.15);color:var(--green)}
.badge.failed{background:rgba(248,81,73,.15);color:var(--red)}
.badge.running{background:rgba(88,166,255,.15);color:var(--accent)}
.badge.pending{background:rgba(210,153,34,.15);color:var(--yellow)}
.badge.generate{background:rgba(188,140,255,.15);color:var(--purple)}
.badge.plot{background:rgba(240,136,62,.15);color:var(--orange)}
.mono{font-family:monospace;font-size:.8rem;color:var(--text-muted)}
.time-cell{white-space:nowrap;font-size:.8rem;color:var(--text-muted)}

/* Pagination */
.pagination{display:flex;align-items:center;justify-content:center;gap:8px;margin:20px 0}
.pagination button{min-width:36px;padding:6px 10px}
.pagination button.active{border-color:var(--accent);color:var(--accent)}
.pagination button:disabled{opacity:.3;cursor:default}
.pagination .info{font-size:.8rem;color:var(--text-muted)}

/* Detail panel */
.detail-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;z-index:100;
  justify-content:center;align-items:flex-start;padding:40px 16px;overflow-y:auto}
.detail-overlay.show{display:flex}
.detail-panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  width:100%;max-width:800px;box-shadow:var(--shadow);margin:auto}
.detail-header{display:flex;justify-content:space-between;align-items:center;
  padding:16px 20px;border-bottom:1px solid var(--border)}
.detail-header h2{font-size:1rem}
.detail-body{padding:20px}
.detail-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px}
.detail-meta .item{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:12px}
.detail-meta .item .lbl{font-size:.7rem;text-transform:uppercase;color:var(--text-muted);letter-spacing:.5px}
.detail-meta .item .val{margin-top:2px;font-size:.9rem;word-break:break-all}
.detail-section{margin-top:20px}
.detail-section h3{font-size:.9rem;color:var(--accent);margin-bottom:8px;display:flex;align-items:center;gap:6px}
.detail-section pre{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);
  padding:14px;font-size:.82rem;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto;
  font-family:'SF Mono',SFMono-Regular,Consolas,monospace;line-height:1.5}
.detail-image{text-align:center;margin-top:16px}
.detail-image img{max-width:100%;max-height:500px;border-radius:var(--radius);border:1px solid var(--border)}
.detail-image button{margin-top:8px}
.error-box{padding:12px;background:rgba(248,81,73,.08);border:1px solid var(--red);
  border-radius:var(--radius);color:var(--red);font-size:.85rem;margin-top:12px}
.desc-box{padding:12px;background:rgba(63,185,80,.06);border:1px solid rgba(63,185,80,.2);
  border-radius:var(--radius);font-size:.85rem;margin-top:12px;line-height:1.6}

/* Empty state */
.empty{text-align:center;padding:60px 20px;color:var(--text-muted)}
.empty .icon{font-size:3rem;margin-bottom:12px}
.empty p{font-size:.9rem}

/* Spinner */
.spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite;
  vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-row td{text-align:center;padding:30px;color:var(--text-muted)}
</style>
</head>
<body>

<!-- LOGIN -->
<div id="login-page">
  <div class="login-box">
    <div class="logo">&#127820;</div>
    <h1>PaperBanana</h1>
    <p>History - Sign in with admin key</p>
    <div class="login-error" id="login-error"></div>
    <input type="password" id="admin-key-input" placeholder="Enter Admin Key" autofocus>
    <button class="primary" onclick="doLogin()">Sign In</button>
  </div>
</div>

<!-- MAIN -->
<div id="main-page" style="display:none">
<div class="container">
  <header>
    <h1>&#127820; Generation History</h1>
    <div class="nav-links">
      <a href="/adm" target="_blank">Admin</a>
      <a href="/doc" target="_blank">API Docs</a>
    </div>
  </header>

  <!-- Filters -->
  <div class="filters">
    <div>
      <label>Endpoint</label><br>
      <select id="f-endpoint" onchange="reloadHistory()">
        <option value="">All</option>
        <option value="generate">generate</option>
        <option value="plot">plot</option>
      </select>
    </div>
    <div>
      <label>Status</label><br>
      <select id="f-status" onchange="reloadHistory()">
        <option value="">All</option>
        <option value="completed">completed</option>
        <option value="failed">failed</option>
        <option value="running">running</option>
        <option value="pending">pending</option>
      </select>
    </div>
    <div>
      <label>API Key</label><br>
      <select id="f-key" onchange="reloadHistory()">
        <option value="">All keys</option>
      </select>
    </div>
    <div style="margin-left:auto;align-self:flex-end">
      <button onclick="reloadHistory()">Refresh</button>
    </div>
  </div>

  <!-- Table -->
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th style="width:40px">#</th>
        <th>Task ID</th>
        <th>Endpoint</th>
        <th>Key</th>
        <th>Status</th>
        <th>Created</th>
        <th>Duration</th>
      </tr></thead>
      <tbody id="history-tbody">
        <tr class="loading-row"><td colspan="7"><span class="spinner"></span> Loading...</td></tr>
      </tbody>
    </table>
  </div>

  <!-- Pagination -->
  <div class="pagination" id="pagination"></div>
</div>
</div>

<!-- Detail overlay -->
<div class="detail-overlay" id="detail-overlay" onclick="if(event.target===this)closeDetail()">
  <div class="detail-panel">
    <div class="detail-header">
      <h2 id="detail-title">Task Detail</h2>
      <button onclick="closeDetail()">Close</button>
    </div>
    <div class="detail-body" id="detail-body">
      <div style="text-align:center;padding:40px"><span class="spinner"></span></div>
    </div>
  </div>
</div>

<script>
const API = '';
let adminKey = localStorage.getItem('pb_admin_key') || '';
let currentPage = 1;
const PAGE_SIZE = 20;

function authHeaders() {
  return {'Authorization': 'Bearer ' + adminKey, 'Content-Type': 'application/json'};
}

// --- Auth ---
async function doLogin() {
  const key = document.getElementById('admin-key-input').value.trim();
  if (!key) return;
  try {
    const r = await fetch(API + '/api/admin/keys', {headers: {'Authorization': 'Bearer ' + key}});
    if (!r.ok) throw new Error();
    adminKey = key;
    localStorage.setItem('pb_admin_key', key);
    showMain();
  } catch(e) {
    const el = document.getElementById('login-error');
    el.textContent = 'Authentication failed.';
    el.style.display = 'block';
  }
}
document.getElementById('admin-key-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') doLogin();
});

async function showMain() {
  document.getElementById('login-page').style.display = 'none';
  document.getElementById('main-page').style.display = 'block';
  await loadKeyFilter();
  await reloadHistory();
}

// --- Key filter dropdown ---
async function loadKeyFilter() {
  try {
    const r = await fetch(API + '/api/admin/keys', {headers: authHeaders()});
    const keys = await r.json();
    const sel = document.getElementById('f-key');
    keys.forEach(k => {
      const o = document.createElement('option');
      o.value = k.key;
      o.textContent = k.name + ' (' + k.key.substring(0,6) + '...' + k.key.substring(k.key.length-4) + ')';
      sel.appendChild(o);
    });
  } catch(e) {}
}

// --- History list ---
async function reloadHistory() {
  currentPage = currentPage || 1;
  await loadHistory(currentPage);
}

async function loadHistory(page) {
  currentPage = page;
  const tbody = document.getElementById('history-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="7"><span class="spinner"></span> Loading...</td></tr>';

  const params = new URLSearchParams({page, size: PAGE_SIZE});
  const ep = document.getElementById('f-endpoint').value;
  const st = document.getElementById('f-status').value;
  const ky = document.getElementById('f-key').value;
  if (ep) params.append('endpoint', ep);
  if (st) params.append('status', st);
  if (ky) params.append('api_key', ky);

  try {
    const r = await fetch(API + '/api/admin/history?' + params, {headers: authHeaders()});
    if (r.status === 401) { adminKey=''; localStorage.removeItem('pb_admin_key'); location.reload(); return; }
    const data = await r.json();
    renderHistory(data);
  } catch(e) {
    tbody.innerHTML = '<tr class="loading-row"><td colspan="7" style="color:var(--red)">Failed to load</td></tr>';
  }
}

function renderHistory(data) {
  const tbody = document.getElementById('history-tbody');
  tbody.innerHTML = '';

  if (data.items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty"><div class="icon">&#128196;</div><p>No records found</p></div></td></tr>';
    renderPagination(data);
    return;
  }

  const offset = (data.page - 1) * data.size;
  data.items.forEach((item, i) => {
    const tr = document.createElement('tr');
    tr.onclick = () => openDetail(item.task_id);

    const dur = calcDuration(item.created_at, item.completed_at);
    const shortId = item.task_id.substring(0, 12) + '...';
    const keyLabel = item.key_name || item.api_key.substring(0,10) + '...';

    tr.innerHTML =
      '<td style="color:var(--text-dim)">' + (data.total - offset - i) + '</td>' +
      '<td class="mono">' + esc(shortId) + '</td>' +
      '<td><span class="badge ' + item.endpoint + '">' + item.endpoint + '</span></td>' +
      '<td>' + esc(keyLabel) + '</td>' +
      '<td><span class="badge ' + item.status + '">' + item.status + '</span></td>' +
      '<td class="time-cell">' + fmtTime(item.created_at) + '</td>' +
      '<td class="time-cell">' + dur + '</td>';
    tbody.appendChild(tr);
  });
  renderPagination(data);
}

function renderPagination(data) {
  const el = document.getElementById('pagination');
  if (data.pages <= 1) { el.innerHTML = '<span class="info">' + data.total + ' records</span>'; return; }

  let html = '<button ' + (data.page<=1?'disabled':'') + ' onclick="loadHistory(' + (data.page-1) + ')">&laquo;</button>';

  const start = Math.max(1, data.page - 2);
  const end = Math.min(data.pages, data.page + 2);
  if (start > 1) html += '<button onclick="loadHistory(1)">1</button>';
  if (start > 2) html += '<span class="info">...</span>';
  for (let p = start; p <= end; p++) {
    html += '<button class="' + (p===data.page?'active':'') + '" onclick="loadHistory(' + p + ')">' + p + '</button>';
  }
  if (end < data.pages - 1) html += '<span class="info">...</span>';
  if (end < data.pages) html += '<button onclick="loadHistory(' + data.pages + ')">' + data.pages + '</button>';

  html += '<button ' + (data.page>=data.pages?'disabled':'') + ' onclick="loadHistory(' + (data.page+1) + ')">&raquo;</button>';
  html += '<span class="info">' + data.total + ' records</span>';
  el.innerHTML = html;
}

// --- Detail ---
async function openDetail(taskId) {
  const overlay = document.getElementById('detail-overlay');
  const body = document.getElementById('detail-body');
  document.getElementById('detail-title').textContent = 'Task ' + taskId.substring(0, 16) + '...';
  body.innerHTML = '<div style="text-align:center;padding:40px"><span class="spinner"></span> Loading detail...</div>';
  overlay.classList.add('show');

  try {
    const r = await fetch(API + '/api/admin/history/' + taskId, {headers: authHeaders()});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    renderDetail(d);
  } catch(e) {
    body.innerHTML = '<div class="error-box">Failed to load: ' + esc(e.message) + '</div>';
  }
}

function renderDetail(d) {
  const body = document.getElementById('detail-body');
  document.getElementById('detail-title').textContent = 'Task ' + d.task_id.substring(0,16) + '...';

  let html = '<div class="detail-meta">';
  html += metaItem('Task ID', '<span style="font-family:monospace;font-size:.8rem">' + d.task_id + '</span>');
  html += metaItem('Endpoint', '<span class="badge ' + d.endpoint + '">' + d.endpoint + '</span>');
  html += metaItem('Type', d.diagram_type);
  html += metaItem('Status', '<span class="badge ' + d.status + '">' + d.status + '</span>');
  html += metaItem('API Key', '<span style="font-family:monospace;font-size:.8rem">' + d.api_key.substring(0,6) + '...' + d.api_key.substring(d.api_key.length-4) + '</span>' + (d.key_name ? ' (' + esc(d.key_name) + ')' : ''));
  html += metaItem('Created', fmtTime(d.created_at));
  if (d.completed_at) html += metaItem('Completed', fmtTime(d.completed_at));
  html += metaItem('Duration', calcDuration(d.created_at, d.completed_at));
  if (d.webhook_url) {
    html += metaItem('Webhook URL', '<span style="font-size:.8rem;word-break:break-all">' + esc(d.webhook_url) + '</span>');
    const whBadge = d.webhook_status === 'delivered' ? 'completed' : d.webhook_status === 'failed' ? 'failed' : 'running';
    html += metaItem('Webhook', '<span class="badge ' + whBadge + '">' + (d.webhook_status || 'pending') + '</span>' +
      (d.webhook_attempts ? ' (' + d.webhook_attempts + ' attempts)' : '') +
      (d.webhook_last_error ? '<div style="font-size:.75rem;color:var(--red);margin-top:4px">' + esc(d.webhook_last_error) + '</div>' : ''));
  }
  html += '</div>';

  // Input
  html += '<div class="detail-section"><h3>&#128229; Input Parameters</h3>';
  if (d.input_params && Object.keys(d.input_params).length > 0) {
    if (d.endpoint === 'generate') {
      html += '<div style="margin-bottom:8px"><strong style="font-size:.8rem;color:var(--text-muted)">Source Context:</strong></div>';
      html += '<pre>' + esc(d.input_params.source_context || '') + '</pre>';
      html += '<div style="margin-top:10px;margin-bottom:8px"><strong style="font-size:.8rem;color:var(--text-muted)">Caption:</strong></div>';
      html += '<pre>' + esc(d.input_params.caption || '') + '</pre>';
      html += '<div style="margin-top:6px;font-size:.8rem;color:var(--text-muted)">Iterations: ' + (d.input_params.iterations || 3) + '</div>';
    } else if (d.endpoint === 'plot') {
      html += '<div style="margin-bottom:8px"><strong style="font-size:.8rem;color:var(--text-muted)">Data JSON:</strong></div>';
      let prettyData = d.input_params.data_json || '';
      try { prettyData = JSON.stringify(JSON.parse(prettyData), null, 2); } catch(e) {}
      html += '<pre>' + esc(prettyData) + '</pre>';
      html += '<div style="margin-top:10px;margin-bottom:8px"><strong style="font-size:.8rem;color:var(--text-muted)">Intent:</strong></div>';
      html += '<pre>' + esc(d.input_params.intent || '') + '</pre>';
      html += '<div style="margin-top:6px;font-size:.8rem;color:var(--text-muted)">Iterations: ' + (d.input_params.iterations || 3) + '</div>';
    } else {
      html += '<pre>' + esc(JSON.stringify(d.input_params, null, 2)) + '</pre>';
    }
  } else {
    html += '<pre style="color:var(--text-muted)">(no input recorded)</pre>';
  }
  html += '</div>';

  // Output
  html += '<div class="detail-section"><h3>&#128228; Output</h3>';
  if (d.error) {
    html += '<div class="error-box"><strong>Error:</strong> ' + esc(d.error) + '</div>';
  }
  if (d.description) {
    html += '<div class="desc-box"><strong style="display:block;margin-bottom:4px;color:var(--green)">Description:</strong>' + esc(d.description) + '</div>';
  }
  if (d.image_base64) {
    html += '<div class="detail-image">';
    html += '<img src="data:image/png;base64,' + d.image_base64 + '" alt="Generated">';
    html += '<br><button onclick="dlImg(\\'' + d.task_id + '\\')">Download PNG</button>';
    html += '</div>';
  } else if (d.status === 'completed') {
    html += '<div style="color:var(--text-muted);font-size:.85rem;margin-top:8px">(image file no longer available on disk)</div>';
  }
  if (d.status === 'pending' || d.status === 'running') {
    html += '<div style="color:var(--yellow);font-size:.85rem;margin-top:8px">Task is still in progress...</div>';
  }
  html += '</div>';

  body.innerHTML = html;
}

function metaItem(label, value) {
  return '<div class="item"><div class="lbl">' + label + '</div><div class="val">' + value + '</div></div>';
}

function closeDetail() {
  document.getElementById('detail-overlay').classList.remove('show');
}

function dlImg(taskId) {
  const img = document.querySelector('.detail-image img');
  if (!img) return;
  const a = document.createElement('a');
  a.href = img.src;
  a.download = taskId + '.png';
  a.click();
}

// --- Helpers ---
function esc(s) {
  if (!s) return '';
  const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
}

function fmtTime(iso) {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    const pad = n => String(n).padStart(2,'0');
    return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()) + ' ' +
           pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  } catch(e) { return iso; }
}

function calcDuration(start, end) {
  if (!start || !end) return '-';
  try {
    const ms = new Date(end) - new Date(start);
    if (ms < 0) return '-';
    const secs = Math.round(ms / 1000);
    if (secs < 60) return secs + 's';
    const mins = Math.floor(secs / 60);
    const remSecs = secs % 60;
    return mins + 'm ' + remSecs + 's';
  } catch(e) { return '-'; }
}

// --- Init ---
if (adminKey) {
  fetch(API + '/api/admin/keys', {headers: authHeaders()})
    .then(r => { if (r.ok) showMain(); else { adminKey=''; document.getElementById('login-page').style.display='flex'; }})
    .catch(() => { document.getElementById('login-page').style.display='flex'; });
} else {
  document.getElementById('login-page').style.display = 'flex';
}
</script>
</body>
</html>
"""


@app.get("/history", response_class=HTMLResponse)
async def history_page():
    return HISTORY_HTML


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------


@app.post("/api/generate", response_model=TaskSubmitted, status_code=202)
async def generate(req: GenerateRequest, api_key: str = Depends(verify_api_key)):
    task_id = uuid.uuid4().hex
    settings = Settings.from_yaml(
        os.environ.get("PAPERBANANA_CONFIG", "configs/openrouter.yaml"),
        refinement_iterations=req.iterations,
    ) if _settings is None else _settings.model_copy(
        update={"refinement_iterations": req.iterations},
    )

    gen_input = GenerationInput(
        source_context=req.source_context,
        communicative_intent=req.caption,
        diagram_type=DiagramType.METHODOLOGY,
    )

    wh_url, wh_include, _wh_sec = _resolve_webhook(api_key, req.webhook_url, req.webhook_include_image)

    record = TaskRecord(
        task_id=task_id, status=TaskStatus.PENDING,
        diagram_type="methodology", api_key=api_key,
        webhook_url=wh_url, webhook_include_image=wh_include,
    )
    _tasks[task_id] = record

    _deduct_quota(api_key, task_id, "generate")
    _save_task_history(task_id, api_key, "generate", "methodology", {
        "source_context": req.source_context, "caption": req.caption, "iterations": req.iterations,
    }, webhook_url=wh_url, webhook_include_image=wh_include)

    asyncio.create_task(_run_generation(task_id, gen_input, settings))
    return TaskSubmitted(task_id=task_id, status=TaskStatus.PENDING)


@app.post("/api/plot", response_model=TaskSubmitted, status_code=202)
async def plot(req: PlotRequest, api_key: str = Depends(verify_api_key)):
    try:
        raw_data = json.loads(req.data_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON in data_json: {exc}")

    task_id = uuid.uuid4().hex
    settings = Settings.from_yaml(
        os.environ.get("PAPERBANANA_CONFIG", "configs/openrouter.yaml"),
        refinement_iterations=req.iterations,
    ) if _settings is None else _settings.model_copy(
        update={"refinement_iterations": req.iterations},
    )

    gen_input = GenerationInput(
        source_context=f"Data for plotting:\n{req.data_json}",
        communicative_intent=req.intent,
        diagram_type=DiagramType.STATISTICAL_PLOT,
        raw_data=raw_data,
    )

    wh_url, wh_include, _wh_sec = _resolve_webhook(api_key, req.webhook_url, req.webhook_include_image)

    record = TaskRecord(
        task_id=task_id, status=TaskStatus.PENDING,
        diagram_type="statistical_plot", api_key=api_key,
        webhook_url=wh_url, webhook_include_image=wh_include,
    )
    _tasks[task_id] = record

    _deduct_quota(api_key, task_id, "plot")
    _save_task_history(task_id, api_key, "plot", "statistical_plot", {
        "data_json": req.data_json, "intent": req.intent, "iterations": req.iterations,
    }, webhook_url=wh_url, webhook_include_image=wh_include)

    asyncio.create_task(_run_generation(task_id, gen_input, settings))
    return TaskSubmitted(task_id=task_id, status=TaskStatus.PENDING)


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, api_key: str = Depends(verify_api_key)):
    record = _tasks.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.api_key != api_key:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(
        task_id=record.task_id,
        status=record.status,
        diagram_type=record.diagram_type,
        image_base64=record.image_base64,
        description=record.description,
        error=record.error,
    )


@app.get("/api/tasks/{task_id}/image")
async def get_task_image(task_id: str, api_key: str = Depends(verify_api_key)):
    record = _tasks.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.api_key != api_key:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.status != TaskStatus.COMPLETED or record.image_path is None:
        raise HTTPException(status_code=404, detail="Image not available yet")
    return FileResponse(record.image_path, media_type="image/png", filename=f"{task_id}.png")


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@app.post("/api/admin/keys", status_code=201)
async def create_key(req: CreateKeyRequest, _: str = Depends(verify_admin)):
    db = _get_db()
    key = _generate_api_key()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO api_keys (key, name, quota_remaining, quota_total, total_used, active, created_at, "
        "webhook_url, webhook_secret) VALUES (?, ?, ?, ?, 0, 1, ?, ?, ?)",
        (key, req.name, req.quota, req.quota, now, req.webhook_url, req.webhook_secret),
    )
    db.commit()
    return ApiKeyInfo(
        key=key, name=req.name,
        quota_remaining=req.quota, quota_total=req.quota,
        total_used=0, active=True, created_at=now,
        webhook_url=req.webhook_url,
    )


@app.get("/api/admin/keys")
async def list_keys(_: str = Depends(verify_admin)):
    db = _get_db()
    rows = db.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
    return [
        ApiKeyInfo(
            key=r["key"], name=r["name"],
            quota_remaining=r["quota_remaining"], quota_total=r["quota_total"],
            total_used=r["total_used"], active=bool(r["active"]),
            created_at=r["created_at"],
            webhook_url=r["webhook_url"],
        )
        for r in rows
    ]


@app.get("/api/admin/keys/{key}")
async def get_key(key: str, _: str = Depends(verify_admin)):
    db = _get_db()
    row = db.execute("SELECT * FROM api_keys WHERE key = ?", (key,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    logs = db.execute(
        "SELECT id, task_id, endpoint, created_at FROM usage_log WHERE key = ? ORDER BY created_at DESC LIMIT 100",
        (key,),
    ).fetchall()
    return ApiKeyDetail(
        key=row["key"], name=row["name"],
        quota_remaining=row["quota_remaining"], quota_total=row["quota_total"],
        total_used=row["total_used"], active=bool(row["active"]),
        created_at=row["created_at"],
        webhook_url=row["webhook_url"],
        usage_log=[dict(r) for r in logs],
    )


@app.patch("/api/admin/keys/{key}")
async def update_key(key: str, req: UpdateKeyRequest, _: str = Depends(verify_admin)):
    db = _get_db()
    row = db.execute("SELECT * FROM api_keys WHERE key = ?", (key,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")

    updates: list[str] = []
    params: list[Any] = []
    if req.quota_remaining is not None:
        updates.append("quota_remaining = ?")
        params.append(req.quota_remaining)
    if req.quota_total is not None:
        updates.append("quota_total = ?")
        params.append(req.quota_total)
    if req.active is not None:
        updates.append("active = ?")
        params.append(int(req.active))
    if req.webhook_url is not None:
        updates.append("webhook_url = ?")
        params.append(req.webhook_url if req.webhook_url else None)
    if req.webhook_secret is not None:
        updates.append("webhook_secret = ?")
        params.append(req.webhook_secret if req.webhook_secret else None)

    if updates:
        params.append(key)
        db.execute(f"UPDATE api_keys SET {', '.join(updates)} WHERE key = ?", params)
        db.commit()

    updated = db.execute("SELECT * FROM api_keys WHERE key = ?", (key,)).fetchone()
    return ApiKeyInfo(
        key=updated["key"], name=updated["name"],
        quota_remaining=updated["quota_remaining"], quota_total=updated["quota_total"],
        total_used=updated["total_used"], active=bool(updated["active"]),
        created_at=updated["created_at"],
        webhook_url=updated["webhook_url"],
    )


@app.delete("/api/admin/keys/{key}", status_code=204)
async def delete_key(key: str, _: str = Depends(verify_admin)):
    db = _get_db()
    row = db.execute("SELECT key FROM api_keys WHERE key = ?", (key,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    db.execute("DELETE FROM usage_log WHERE key = ?", (key,))
    db.execute("DELETE FROM api_keys WHERE key = ?", (key,))
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Admin history endpoints
# ---------------------------------------------------------------------------


@app.get("/api/admin/history")
async def list_history(
    page: int = 1,
    size: int = 20,
    endpoint: str | None = None,
    status: str | None = None,
    api_key: str | None = None,
    _: str = Depends(verify_admin),
):
    db = _get_db()
    where_clauses: list[str] = []
    params: list[Any] = []
    if endpoint:
        where_clauses.append("endpoint = ?")
        params.append(endpoint)
    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if api_key:
        where_clauses.append("api_key = ?")
        params.append(api_key)
    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    total = db.execute("SELECT COUNT(*) as cnt FROM task_history" + where_sql, params).fetchone()["cnt"]
    offset = (max(page, 1) - 1) * size
    rows = db.execute(
        "SELECT task_id, api_key, key_name, endpoint, diagram_type, status, created_at, completed_at "
        "FROM task_history" + where_sql + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [size, offset],
    ).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),
    }


@app.get("/api/admin/history/{task_id}")
async def get_history_detail(task_id: str, _: str = Depends(verify_admin)):
    db = _get_db()
    row = db.execute("SELECT * FROM task_history WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found in history")
    result = dict(row)
    result["input_params"] = json.loads(result["input_params"]) if result["input_params"] else {}
    # If completed and image_path exists, load base64
    if result.get("image_path") and Path(result["image_path"]).exists():
        try:
            img = load_image(result["image_path"])
            result["image_base64"] = image_to_base64(img)
        except Exception:
            result["image_base64"] = None
    else:
        result["image_base64"] = None
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
