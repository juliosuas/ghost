"""Ghost Flask API — serves dashboard and investigation endpoints."""

import asyncio
import hmac
import threading
import time
from collections import defaultdict
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

from ghost.core.config import config, validate_flask_runtime
from ghost.core.investigator import GhostInvestigator, Investigation
from ghost.backend.db import (
    get_graph_data,
    get_investigation,
    init_db,
    list_investigations,
    save_investigation,
)

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "ui"))
if config.secret_key:
    app.secret_key = config.secret_key

# Local tool: allow same-host dashboard origins only, never Access-Control-Allow-Origin: *.
_cors_origins = list(
    dict.fromkeys(
        [
            f"http://127.0.0.1:{config.port}",
            f"http://localhost:{config.port}",
            "http://127.0.0.1:5000",
            "http://localhost:5000",
        ]
    )
)
CORS(app, origins=_cors_origins, supports_credentials=False)

# Initialise database on startup
init_db()

# In-memory tracking of running investigations
_running: dict[str, str] = {}  # id -> status message

_rate_lock = threading.Lock()
_rate_hits: dict[str, list[float]] = defaultdict(list)

_PUBLIC_API_PATHS = frozenset({"/api/health"})


def reset_rate_limiter() -> None:
    """Clear in-memory rate-limit buckets (tests)."""
    with _rate_lock:
        _rate_hits.clear()


def _extract_api_token() -> str:
    auth = request.headers.get("Authorization", "")
    scheme, _, remainder = auth.partition(" ")
    if scheme.lower() == "bearer" and remainder.strip():
        return remainder.strip()
    return (request.headers.get("X-Ghost-Token") or "").strip()


def _tokens_match(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


def _client_key() -> str:
    return request.remote_addr or "unknown"


@app.before_request
def _protect_api() -> tuple | None:
    if not request.path.startswith("/api/"):
        return None
    if request.method == "OPTIONS":
        return None
    if request.path in _PUBLIC_API_PATHS:
        return None

    limited = _enforce_rate_limit()
    if limited is not None:
        return limited

    expected = (config.api_token or "").strip()
    provided = _extract_api_token()
    if not expected or not _tokens_match(provided, expected):
        return jsonify({"error": "unauthorized"}), 401
    return None


def _enforce_rate_limit() -> tuple | None:
    limit = max(1, int(config.rate_limit_requests))
    period = max(1, int(config.rate_limit_period))
    now = time.monotonic()
    key = _client_key()
    with _rate_lock:
        window = [stamp for stamp in _rate_hits[key] if now - stamp < period]
        if len(window) >= limit:
            _rate_hits[key] = window
            return jsonify({"error": "rate limit exceeded"}), 429
        window.append(now)
        _rate_hits[key] = window
    return None


# ── Static dashboard ────────────────────────────────────────────────


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "dashboard.html")


@app.route("/ui/<path:filename>")
def ui_static(filename):
    return send_from_directory(app.static_folder, filename)


# ── API endpoints ───────────────────────────────────────────────────


@app.route("/api/health", methods=["GET"])
def health():
    """Liveness probe — no case data, no token required."""
    return jsonify({"status": "ok"})


@app.route("/api/investigate", methods=["POST"])
def start_investigation():
    """Start a new investigation.

    Expects JSON body with at least one of: name, email, phone, username.
    Optional: input_type, modules (list), scope.
    authorized_use is case-file metadata (not authentication); it is still
    recorded on the investigation when the caller sets it true.
    """
    data = request.get_json(silent=True) or {}

    # Determine target — accept explicit target or pick first provided field
    target = data.get("target", "")
    input_type = data.get("input_type", "auto")

    if not target:
        for field in ("email", "username", "name", "phone"):
            if data.get(field):
                target = data[field]
                if input_type == "auto":
                    input_type = field
                break

    if not target:
        return jsonify({"error": "Provide at least one of: target, name, email, phone, username"}), 400

    # Product policy / case metadata — not a substitute for GHOST_API_TOKEN.
    if data.get("authorized_use") is not True:
        return jsonify(
            {
                "error": "authorized_use must be true for API investigations",
                "detail": "Only run Ghost for authorized security research, journalism, law enforcement, or self-audits.",
            }
        ), 400

    modules = data.get("modules")
    scope = data.get("scope", "authorized API investigation")

    # Create investigation record immediately so the client can poll
    investigator = GhostInvestigator()
    inv = Investigation(target, input_type, scope=scope, authorized_use=True)
    inv.status = "running"
    save_investigation(inv.to_dict())

    inv_id = inv.id
    _running[inv_id] = "starting"

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                investigator.investigate_async(target, input_type, modules, scope=scope, authorized_use=True)
            )
            # Overwrite with actual ID so DB record matches
            result.id = inv_id
            save_investigation(result.to_dict())
        except Exception as e:
            inv.status = "error"
            inv.errors.append(str(e))
            inv.id = inv_id
            save_investigation(inv.to_dict())
        finally:
            _running.pop(inv_id, None)
            loop.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify({"id": inv_id, "status": "running", "target": target}), 202


@app.route("/api/investigations", methods=["GET"])
def list_all():
    """List all investigations, newest first."""
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    return jsonify(list_investigations(limit, offset))


@app.route("/api/investigation/<investigation_id>", methods=["GET"])
def get_one(investigation_id):
    """Get full investigation results."""
    inv = get_investigation(investigation_id)
    if not inv:
        abort(404)
    # If still running, add a hint
    if investigation_id in _running:
        inv["status"] = "running"
    return jsonify(inv)


@app.route("/api/investigation/<investigation_id>/graph", methods=["GET"])
def get_entity_graph(investigation_id):
    """Return D3.js force-directed graph data for an investigation."""
    data = get_graph_data(investigation_id)
    if data is None:
        abort(404)
    return jsonify(data)


# ── Run ─────────────────────────────────────────────────────────────


def main():
    try:
        validate_flask_runtime(config)
    except ValueError as exc:
        raise SystemExit(f"Ghost API refused to start: {exc}") from exc
    if config.secret_key:
        app.secret_key = config.secret_key
    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    main()
