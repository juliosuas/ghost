"""Ghost Flask API — serves dashboard and investigation endpoints."""

import asyncio
import threading
import json
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS

from ghost.core.config import config
from ghost.core.investigator import GhostInvestigator, Investigation
from ghost.backend.db import (
    init_db,
    save_investigation,
    get_investigation,
    list_investigations,
    get_graph_data,
)

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "ui"))
CORS(app)

# Initialise database on startup
init_db()

# In-memory tracking of running investigations
_running: dict[str, str] = {}  # id -> status message


# ── Static dashboard ────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "dashboard.html")


@app.route("/ui/<path:filename>")
def ui_static(filename):
    return send_from_directory(app.static_folder, filename)


# ── API endpoints ───────────────────────────────────────────────────

@app.route("/api/investigate", methods=["POST"])
def start_investigation():
    """Start a new investigation.

    Expects JSON body with at least one of: name, email, phone, username.
    Optional: input_type, modules (list).
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

    modules = data.get("modules")

    # Create investigation record immediately so the client can poll
    investigator = GhostInvestigator()
    inv = Investigation(target, input_type)
    inv.status = "running"
    save_investigation(inv.to_dict())

    inv_id = inv.id
    _running[inv_id] = "starting"

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                investigator.investigate_async(target, input_type, modules)
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
    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    main()
