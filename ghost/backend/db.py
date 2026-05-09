"""SQLite database layer for Ghost investigations."""

import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import unquote, urlparse

from ghost.core.config import config, DATA_DIR

SCHEMA_VERSION = 2


def resolve_database_path(database_url: str) -> Path:
    """Resolve Ghost's configured SQLite database URL to a filesystem path.

    Ghost v2 uses SQLite as the durable default because it is robust enough for
    local investigations, easy to back up, and avoids the old JSON-file storage
    limitation raised in early feedback. Other database engines are explicit
    roadmap items instead of silently falling back to an unexpected path.
    """
    parsed = urlparse(database_url)

    if parsed.scheme in ("", "sqlite"):
        if parsed.scheme == "":
            path = Path(database_url)
        elif parsed.netloc and parsed.netloc != "localhost":
            # sqlite://relative.db is parsed as netloc=relative.db; accept it as
            # a local filename for developer ergonomics.
            path = Path(unquote(parsed.netloc + parsed.path))
        else:
            raw_path = unquote(parsed.path)
            # urlparse keeps the leading slash from sqlite:/// and absolute
            # POSIX paths can arrive as //Users/... when formatted naively.
            if raw_path.startswith("//"):
                raw_path = raw_path[1:]
            elif raw_path.startswith("/") and raw_path.count("/") == 1:
                # sqlite:///ghost.db should behave like the documented local
                # relative path, resolving under Ghost's data directory.
                raw_path = raw_path[1:]
            path = Path(raw_path)

        if str(path) in ("", ":memory:"):
            return Path(":memory:")
        if not path.is_absolute():
            path = DATA_DIR / path
        return path

    raise ValueError(
        f"Unsupported DATABASE_URL scheme '{parsed.scheme}'. "
        "Ghost v2 currently supports sqlite:///path/to/ghost.db. "
        "PostgreSQL support is planned behind the storage adapter boundary."
    )


DB_PATH = resolve_database_path(config.database_url)


def get_connection() -> sqlite3.Connection:
    if str(DB_PATH) != ":memory:":
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                target TEXT NOT NULL,
                input_type TEXT NOT NULL,
                scope TEXT DEFAULT '',
                authorized_use INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                started_at TEXT NOT NULL,
                completed_at TEXT,
                summary TEXT DEFAULT '',
                risk_score REAL DEFAULT 0.0,
                errors TEXT DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                value TEXT NOT NULL,
                platform TEXT DEFAULT '',
                confidence REAL DEFAULT 0.0,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                module_name TEXT NOT NULL,
                data TEXT NOT NULL DEFAULT '{}',
                collected_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                source_entity_id INTEGER NOT NULL,
                target_entity_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,
                evidence TEXT DEFAULT '',
                confidence REAL DEFAULT 0.0,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (source_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (target_entity_id) REFERENCES entities(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_investigations_target ON investigations(target);
            CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);
            CREATE INDEX IF NOT EXISTS idx_investigations_created_at ON investigations(created_at);
            CREATE INDEX IF NOT EXISTS idx_entities_investigation ON entities(investigation_id);
            CREATE INDEX IF NOT EXISTS idx_entities_type_value ON entities(entity_type, value);
            CREATE INDEX IF NOT EXISTS idx_findings_investigation ON findings(investigation_id);
            CREATE INDEX IF NOT EXISTS idx_relationships_investigation ON relationships(investigation_id);
        """)
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(investigations)").fetchall()
        }
        if "scope" not in existing_columns:
            conn.execute("ALTER TABLE investigations ADD COLUMN scope TEXT DEFAULT ''")
        if "authorized_use" not in existing_columns:
            conn.execute("ALTER TABLE investigations ADD COLUMN authorized_use INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )


# ── Investigation CRUD ──────────────────────────────────────────────

def save_investigation(inv_dict: dict):
    """Save or update a full investigation from Investigation.to_dict()."""
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO investigations
                (id, target, input_type, scope, authorized_use, status, started_at, completed_at, summary, risk_score, errors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inv_dict["id"],
            inv_dict["target"],
            inv_dict["input_type"],
            inv_dict.get("scope", ""),
            1 if inv_dict.get("authorized_use", False) else 0,
            inv_dict["status"],
            inv_dict["started_at"],
            inv_dict["completed_at"],
            inv_dict.get("summary", ""),
            inv_dict.get("risk_score", 0.0),
            json.dumps(inv_dict.get("errors", [])),
        ))

        # Store each module's findings
        conn.execute("DELETE FROM findings WHERE investigation_id = ?", (inv_dict["id"],))
        for module_name, data in inv_dict.get("findings", {}).items():
            conn.execute(
                "INSERT INTO findings (investigation_id, module_name, data) VALUES (?, ?, ?)",
                (inv_dict["id"], module_name, json.dumps(data, default=str)),
            )

        # Extract and store entities + relationships from correlations
        _store_entities_and_relationships(conn, inv_dict)


def _store_entities_and_relationships(conn, inv_dict):
    """Extract entities from findings/correlations and store them."""
    investigation_id = inv_dict["id"]
    conn.execute("DELETE FROM entities WHERE investigation_id = ?", (investigation_id,))
    conn.execute("DELETE FROM relationships WHERE investigation_id = ?", (investigation_id,))

    entity_map = {}  # (type, value) -> entity_id

    def _ensure_entity(etype, value, platform="", confidence=0.5, metadata=None):
        key = (etype, value)
        if key in entity_map:
            return entity_map[key]
        cur = conn.execute(
            "INSERT INTO entities (investigation_id, entity_type, value, platform, confidence, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (investigation_id, etype, value, platform, confidence, json.dumps(metadata or {})),
        )
        eid = cur.lastrowid
        entity_map[key] = eid
        return eid

    # Central target entity
    target_eid = _ensure_entity("target", inv_dict["target"], confidence=1.0)

    # Entities from findings
    findings = inv_dict.get("findings", {})

    # Username profiles
    for profile in findings.get("username", {}).get("profiles", []):
        if profile.get("status") == "found":
            eid = _ensure_entity("profile", profile.get("url", ""), platform=profile.get("platform", ""))
            conn.execute(
                "INSERT INTO relationships (investigation_id, source_entity_id, target_entity_id, relationship_type, confidence) VALUES (?, ?, ?, ?, ?)",
                (investigation_id, target_eid, eid, "has_profile", 0.8),
            )

    # Social profiles
    for profile in findings.get("social", {}).get("profiles", []):
        platform = profile.get("platform", "")
        eid = _ensure_entity("profile", profile.get("url", profile.get("username", "")), platform=platform)
        conn.execute(
            "INSERT INTO relationships (investigation_id, source_entity_id, target_entity_id, relationship_type, confidence) VALUES (?, ?, ?, ?, ?)",
            (investigation_id, target_eid, eid, "has_profile", 0.9),
        )

    # Email entities
    email_data = findings.get("email", {})
    if email_data.get("email"):
        eid = _ensure_entity("email", email_data["email"])
        conn.execute(
            "INSERT INTO relationships (investigation_id, source_entity_id, target_entity_id, relationship_type, confidence) VALUES (?, ?, ?, ?, ?)",
            (investigation_id, target_eid, eid, "has_email", 0.9),
        )

    # Breaches
    for breach in email_data.get("breaches", {}).get("breaches", []):
        eid = _ensure_entity("breach", breach.get("name", ""), metadata=breach)
        email_key = ("email", email_data.get("email", inv_dict["target"]))
        src = entity_map.get(email_key, target_eid)
        conn.execute(
            "INSERT INTO relationships (investigation_id, source_entity_id, target_entity_id, relationship_type, evidence, confidence) VALUES (?, ?, ?, ?, ?, ?)",
            (investigation_id, src, eid, "breached_in", breach.get("date", ""), 0.95),
        )

    # Identities from correlations
    for identity in inv_dict.get("correlations", {}).get("identities", []):
        _ensure_entity(
            identity.get("type", "identity"),
            identity.get("value", ""),
            confidence=identity.get("confidence", 0.5),
        )

    # Locations
    for loc in inv_dict.get("correlations", {}).get("locations", []):
        _ensure_entity("location", loc.get("value", ""), metadata={
            k: loc[k] for k in ("lat", "lon", "source") if k in loc
        })


def get_investigation(investigation_id: str) -> dict | None:
    """Retrieve a full investigation by ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,)).fetchone()
        if not row:
            return None

        inv = dict(row)
        inv["authorized_use"] = bool(inv.get("authorized_use", 0))
        inv["errors"] = json.loads(inv.get("errors", "[]"))

        # Load findings
        findings_rows = conn.execute(
            "SELECT module_name, data FROM findings WHERE investigation_id = ?",
            (investigation_id,),
        ).fetchall()
        inv["findings"] = {r["module_name"]: json.loads(r["data"]) for r in findings_rows}

        # Load entities
        entities = conn.execute(
            "SELECT * FROM entities WHERE investigation_id = ?",
            (investigation_id,),
        ).fetchall()
        inv["entities"] = [dict(e) for e in entities]
        for e in inv["entities"]:
            e["metadata"] = json.loads(e.get("metadata", "{}"))

        # Load relationships
        rels = conn.execute(
            "SELECT * FROM relationships WHERE investigation_id = ?",
            (investigation_id,),
        ).fetchall()
        inv["relationships"] = [dict(r) for r in rels]

        return inv


def list_investigations(limit: int = 50, offset: int = 0) -> list[dict]:
    """List all investigations, newest first."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                target,
                input_type,
                scope,
                authorized_use,
                status,
                started_at,
                completed_at,
                risk_score,
                summary
            FROM investigations
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        investigations = [dict(r) for r in rows]
        for investigation in investigations:
            investigation["authorized_use"] = bool(investigation.get("authorized_use", 0))
        return investigations


def get_graph_data(investigation_id: str) -> dict | None:
    """Return D3.js-compatible force-directed graph data."""
    with get_db() as conn:
        row = conn.execute("SELECT id FROM investigations WHERE id = ?", (investigation_id,)).fetchone()
        if not row:
            return None

        entities = conn.execute(
            "SELECT id, entity_type, value, platform, confidence FROM entities WHERE investigation_id = ?",
            (investigation_id,),
        ).fetchall()

        relationships = conn.execute(
            "SELECT source_entity_id, target_entity_id, relationship_type, confidence FROM relationships WHERE investigation_id = ?",
            (investigation_id,),
        ).fetchall()

        nodes = []
        for e in entities:
            nodes.append({
                "id": e["id"],
                "label": e["value"][:60],
                "type": e["entity_type"],
                "platform": e["platform"],
                "confidence": e["confidence"],
            })

        links = []
        entity_ids = {e["id"] for e in entities}
        for r in relationships:
            if r["source_entity_id"] in entity_ids and r["target_entity_id"] in entity_ids:
                links.append({
                    "source": r["source_entity_id"],
                    "target": r["target_entity_id"],
                    "type": r["relationship_type"],
                    "confidence": r["confidence"],
                })

        return {"nodes": nodes, "links": links}


def delete_investigation(investigation_id: str) -> bool:
    """Delete an investigation and all related data."""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM investigations WHERE id = ?", (investigation_id,))
        return cur.rowcount > 0
