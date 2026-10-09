"""Import local OSINT tool reports into a Ghost case file.

`ghost ingest` parses a file on disk. It does not open sockets, spawn
processes, or call `investigate`.

Formats actually emitted (verified against upstream CLIs):

Sherlock (`sherlock-project`)
    CSV from `--csv`. Header is exactly
    `username,name,url_main,url_user,exists,http_status,response_time_s`.
    `exists` is a QueryStatus string: Claimed, Available, Unknown, Illegal, WAF.
    TXT from `--txt`: one profile URL per line, then
    `Total Websites Username Detected On : N` (N must match the URL count).
    Console transcript (stdout, including ANSI SGR colors): 
    `[*] Checking username NAME on:`, `[+] Site: URL`, optional
    `[-] Site: reason` from `--print-all`, and
    `[*] Search completed with N results`. Lines after that footer are ignored.
    JSON is not a Sherlock results format. `--json` / `-j` loads a site
    manifest and is rejected. Ghost also accepts a JSON array of CSV rows,
    or an object keyed by site name whose values use those CSV fields, so a
    direct serialization of the CSV / in-memory result dict can be imported.
    None of these files carry a tool version.

Maigret
    `--json simple`: one JSON object keyed by site name. Values are the
    claimed-site result objects written by `generate_json_report` (extra
    keys are kept out of the case file but not rejected, because Maigret
    dumps the whole site result). Required: `username`, `url_user`, and
    `status.status == "Claimed"`. When `status.url` is present it must
    equal `url_user` exactly.
    `--json ndjson`: one such object per line, plus `sitename`.
    An empty simple object is a valid no-hit report. No tool version.

Holehe
    CSV from `--csv` / `export_csv`, which uses the first result dict's keys.
    Accepted headers, in order:
    `name,domain,method,frequent_rate_limit,rateLimit,exists,emailrecovery,phoneNumber,others`
    or the launcher error row
    `name,domain,rateLimit,error,exists,emailrecovery,phoneNumber,others`.
    Booleans are the strings `True` and `False`. `others` is stored as the
    raw cell (Holehe stringifies dicts; Ghost does not evaluate them).
    The queried email is not a column. Pass `--case`, or keep the official
    filename `holehe_<unix-timestamp>_<email>_results.csv`. No tool version.

Every imported record stores provenance: tool name, tool version or null,
UTC ingest timestamp, SHA-256 of the raw file bytes, and the URL exactly as
it appeared (or null when the format has no URL). The file is rejected
before any database write when validation fails. The write itself is one
SQLite transaction.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ghost.backend.db import (
    get_investigation,
    init_db,
    list_investigations,
    save_ingest_into_investigation,
    save_investigation,
)

MAX_INGEST_BYTES = 50 * 1024 * 1024
PROVENANCE_KEYS = ("tool", "tool_version", "ingested_at", "source_sha256", "url")
TOOLS = ("sherlock", "maigret", "holehe")

_SHERLOCK_COLUMNS = [
    "username",
    "name",
    "url_main",
    "url_user",
    "exists",
    "http_status",
    "response_time_s",
]
_SHERLOCK_EXISTS = {"Claimed", "Available", "Unknown", "Illegal", "WAF"}
_SHERLOCK_JSON_KEYS = set(_SHERLOCK_COLUMNS)
_FLOAT_TOKEN = re.compile(r"[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?")
_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
_CLAIMED_RE = re.compile(r"^\[\+\](?: \[\d+ms\])? (?P<site>.+?): (?P<url>\S+)$")
_NOT_FOUND_RE = re.compile(r"^\[-\](?: \[\d+ms\])? (?P<site>.+?): (?P<detail>.+)$")
_HEADER_RE = re.compile(r"^\[\*\] Checking username (?P<username>.+) on:$")
_FOOTER_RE = re.compile(r"^\[\*\] Search completed with (?P<count>\d+) results$")
_TOTAL_RE = re.compile(r"^Total Websites Username Detected On : (?P<count>\d+)$")
_HOLEHE_STANDARD = [
    "name",
    "domain",
    "method",
    "frequent_rate_limit",
    "rateLimit",
    "exists",
    "emailrecovery",
    "phoneNumber",
    "others",
]
_HOLEHE_ERROR = [
    "name",
    "domain",
    "rateLimit",
    "error",
    "exists",
    "emailrecovery",
    "phoneNumber",
    "others",
]
_HOLEHE_FILENAME = re.compile(r"^holehe_(\d+)_(.+)_results\.csv$")
_PAGE_SIZE = 200


class IngestError(ValueError):
    """The file is not a valid tool report. Nothing was written."""


class IngestResult:
    """Outcome of one successful ingest."""

    def __init__(self, investigation: dict, imported_records: int, source_sha256: str, created: bool):
        self.investigation = investigation
        self.imported_records = imported_records
        self.source_sha256 = source_sha256
        self.created = created


def ingest_file(
    path: Path | str,
    tool: str,
    *,
    case: str | None = None,
    scope: str = "authorized tool ingest",
    authorized_use: bool = False,
    ingested_at: datetime | None = None,
) -> IngestResult:
    """Parse a local tool report and store it as a Ghost case.

    Validation finishes before the database write. A failed write rolls back.
    """
    tool_name = _require_tool(tool)
    source = Path(path)
    if case is not None:
        if case == "" or case != case.strip():
            raise IngestError("--case must be a non-empty id or name without surrounding whitespace")

    raw = _read_capped(source)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise IngestError(f"{source.name} is not valid UTF-8") from exc

    moment = ingested_at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise IngestError("ingested_at must be timezone-aware")
    moment = moment.astimezone(timezone.utc)

    parsed = _parse_tool(tool_name, text, source_name=source.name)
    records = [
        _stamp_record(record, tool=tool_name, digest=digest, ingested_at=moment, source_name=source.name)
        for record in parsed["records"]
    ]

    init_db()
    existing, created_target = _resolve_case(case) if case is not None else (None, None)
    if existing is None and created_target is None:
        subject = parsed["subject"]
        if not subject:
            raise IngestError(
                f"{tool_name} report has no subject. Pass --case <id or name> to choose the case file"
            )
        created_target = subject
        input_type = parsed["input_type"]
    elif existing is None:
        input_type = parsed["input_type"]
    else:
        input_type = existing["input_type"]

    if existing is None:
        investigation_id = str(uuid.uuid4())
        target = created_target
        hits = sum(1 for record in records if record["status"] == "Claimed")
        payload = {
            "id": investigation_id,
            "target": target,
            "input_type": input_type,
            "scope": scope,
            "authorized_use": authorized_use,
            "status": "completed",
            "started_at": moment.isoformat(),
            "completed_at": moment.isoformat(),
            "summary": f"Imported {len(records)} {tool_name} records ({hits} claimed).",
            "risk_score": 0.0,
            "errors": [],
            "findings": {"ingest": {"records": records}},
            "correlations": {},
        }
        try:
            save_investigation(payload)
        except IngestError:
            raise
        except Exception as exc:
            raise IngestError("Database write failed; import rolled back") from exc
        created = True
    else:
        investigation_id = existing["id"]
        current = existing.get("findings", {}).get("ingest")
        if current is None:
            merged_records = []
        elif isinstance(current, dict) and isinstance(current.get("records"), list):
            merged_records = list(current["records"])
        else:
            raise IngestError("Existing ingest findings are not a record list; refusing to import")
        merged_records.extend(records)
        try:
            save_ingest_into_investigation(
                investigation_id,
                {"records": merged_records},
                completed_at=moment.isoformat(),
                mark_authorized=authorized_use,
            )
        except IngestError:
            raise
        except Exception as exc:
            raise IngestError("Database write failed; import rolled back") from exc
        created = False

    stored = get_investigation(investigation_id)
    if stored is None:
        raise IngestError("Database write failed; import rolled back")
    return IngestResult(stored, len(records), digest, created)


def _require_tool(tool: str) -> str:
    name = (tool or "").strip().lower()
    if name not in TOOLS:
        raise IngestError(f"tool must be one of: {', '.join(TOOLS)}")
    return name


def _read_capped(path: Path) -> bytes:
    if not path.is_file():
        raise IngestError(f"{path} is not a file")
    size = path.stat().st_size
    if size > MAX_INGEST_BYTES:
        raise IngestError(
            f"Refusing to read {path.name}: {size} bytes exceeds the {MAX_INGEST_BYTES} byte ingest limit"
        )
    data = path.read_bytes()
    if len(data) > MAX_INGEST_BYTES:
        raise IngestError(
            f"Refusing to import {path.name}: file grew past the {MAX_INGEST_BYTES} byte ingest limit"
        )
    if not data:
        raise IngestError(f"{path.name} is empty")
    return data


def _parse_tool(tool: str, text: str, *, source_name: str) -> dict:
    if tool == "sherlock":
        return _parse_sherlock(text)
    if tool == "maigret":
        return _parse_maigret(text)
    return _parse_holehe(text, source_name=source_name)


def _stamp_record(record: dict, *, tool: str, digest: str, ingested_at: datetime, source_name: str) -> dict:
    url = record.get("url")
    if url is not None and not isinstance(url, str):
        raise IngestError("internal: record URL must be a string or null")
    provenance = {
        "tool": tool,
        "tool_version": None,
        "ingested_at": ingested_at.isoformat(),
        "source_sha256": digest,
        "url": url,
    }
    if tuple(provenance) != PROVENANCE_KEYS:
        raise IngestError("internal: provenance keys drifted")
    stamped = dict(record)
    stamped["tool"] = tool
    stamped["source_name"] = source_name
    stamped["provenance"] = provenance
    return stamped


def _resolve_case(case: str) -> tuple[dict | None, str | None]:
    """Return (existing investigation, new target name).

    Order: exact id, unique id prefix, unique target name. No match means the
    value is a new case name. Ambiguous matches raise.
    """
    exact = get_investigation(case)
    if exact is not None:
        return exact, None

    summaries = _all_summaries()
    prefix_hits = [item for item in summaries if item.get("id", "").startswith(case)]
    if len(prefix_hits) > 1:
        raise IngestError(f"Case prefix {case!r} is ambiguous ({len(prefix_hits)} investigations)")
    if len(prefix_hits) == 1:
        found = get_investigation(prefix_hits[0]["id"])
        if found is None:
            raise IngestError(f"Case {case!r} disappeared during ingest; nothing was written")
        return found, None

    name_hits = [item for item in summaries if item.get("target") == case]
    if len(name_hits) > 1:
        raise IngestError(f"Case name {case!r} matches {len(name_hits)} investigations")
    if len(name_hits) == 1:
        found = get_investigation(name_hits[0]["id"])
        if found is None:
            raise IngestError(f"Case {case!r} disappeared during ingest; nothing was written")
        return found, None
    return None, case


def _all_summaries() -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        batch = list_investigations(limit=_PAGE_SIZE, offset=offset)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return rows


def _parse_sherlock(text: str) -> dict:
    if _looks_like_sherlock_json(text):
        return _parse_sherlock_json(text)
    cleaned_lines = [_strip_sgr(line) for line in text.splitlines()]
    if any(line.startswith("[+]") or line.startswith("[-]") or line.startswith("[*]") for line in cleaned_lines):
        return _parse_sherlock_console(text)
    first = cleaned_lines[0] if cleaned_lines else ""
    if first.startswith("username,") or "url_user" in first.split(","):
        return _parse_sherlock_csv(text)
    return _parse_sherlock_txt(text)


def _looks_like_sherlock_json(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return True
    if not stripped.startswith("["):
        return False
    # Console transcripts also start with '[' via [*], [+], and [-].
    if stripped.startswith("[*") or stripped.startswith("[+") or stripped.startswith("[-]"):
        return False
    return True


def _parse_sherlock_csv(text: str) -> dict:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = list(reader.fieldnames or [])
    if header != _SHERLOCK_COLUMNS:
        raise IngestError(
            "sherlock CSV: header must be " + ",".join(_SHERLOCK_COLUMNS) + f" (got {','.join(header) or 'none'})"
        )
    records = []
    usernames = set()
    for index, row in enumerate(reader, start=2):
        if None in row and row[None]:
            raise IngestError(f"sherlock CSV: row {index} has extra columns")
        where = f"sherlock CSV row {index}"
        username = _csv_cell(row, "username", where)
        name = _csv_cell(row, "name", where)
        url_main = _csv_cell(row, "url_main", where)
        url_user = _csv_cell(row, "url_user", where)
        exists = _csv_cell(row, "exists", where)
        http_status = _csv_cell(row, "http_status", where)
        response_time = _csv_cell(row, "response_time_s", where)
        if username == "":
            raise IngestError(f"{where}: username is empty")
        if url_user == "":
            raise IngestError(f"{where}: url_user is empty")
        if exists not in _SHERLOCK_EXISTS:
            raise IngestError(f"{where}: exists must be one of {', '.join(sorted(_SHERLOCK_EXISTS))}")
        if http_status != "" and not http_status.isdigit():
            raise IngestError(f"{where}: http_status must be an integer or empty")
        if response_time != "" and not _FLOAT_TOKEN.fullmatch(response_time):
            raise IngestError(f"{where}: response_time_s must be a number or empty")
        usernames.add(username)
        records.append(
            {
                "source_format": "csv",
                "platform": name,
                "subject": username,
                "status": exists,
                "url": url_user,
                "fields": {
                    "username": username,
                    "name": name,
                    "url_main": url_main,
                    "url_user": url_user,
                    "exists": exists,
                    "http_status": http_status,
                    "response_time_s": response_time,
                },
            }
        )
    if len(usernames) > 1:
        raise IngestError("sherlock CSV: file contains more than one username; refusing to import")
    subject = next(iter(usernames)) if usernames else None
    return {"subject": subject, "input_type": "username", "records": records}


def _parse_sherlock_txt(text: str) -> dict:
    lines = [line for line in text.splitlines() if line.strip() != ""]
    if not lines:
        raise IngestError("sherlock TXT: file has no records")
    urls = []
    total = None
    for index, line in enumerate(lines):
        if _TOTAL_RE.fullmatch(line):
            if index != len(lines) - 1:
                raise IngestError("sherlock TXT: total line must be the last non-empty line")
            total = int(_TOTAL_RE.fullmatch(line).group("count"))
            continue
        if "://" not in line or any(ch.isspace() for ch in line):
            raise IngestError(f"sherlock TXT: unrecognized line {index + 1}")
        urls.append(line)
    if total is not None and total != len(urls):
        raise IngestError(
            f"sherlock TXT: total says {total} websites but {len(urls)} URL lines were present"
        )
    records = [
        {
            "source_format": "txt",
            "platform": "",
            "subject": None,
            "status": "Claimed",
            "url": url,
            "fields": {"url_user": url},
        }
        for url in urls
    ]
    return {"subject": None, "input_type": "username", "records": records}


def _parse_sherlock_console(text: str) -> dict:
    username = None
    claimed = 0
    footer_count = None
    seen_footer = False
    records = []
    for index, raw_line in enumerate(text.splitlines(), start=1):
        if raw_line.strip() == "":
            continue
        clean = _strip_sgr(raw_line)
        if seen_footer:
            continue
        header = _HEADER_RE.fullmatch(clean)
        if header:
            found = header.group("username")
            if found not in raw_line:
                raise IngestError(f"sherlock console line {index}: username was altered by color codes")
            if username is not None and username != found:
                raise IngestError("sherlock console: file contains more than one username")
            username = found
            continue
        claimed_match = _CLAIMED_RE.fullmatch(clean)
        if claimed_match:
            url = claimed_match.group("url")
            site = claimed_match.group("site")
            if url not in raw_line or site not in raw_line:
                raise IngestError(f"sherlock console line {index}: refusing to modify a color-coded field")
            records.append(
                {
                    "source_format": "console",
                    "platform": site,
                    "subject": None,
                    "status": "Claimed",
                    "url": url,
                    "fields": {"name": site, "url_user": url},
                }
            )
            claimed += 1
            continue
        if _NOT_FOUND_RE.fullmatch(clean):
            continue
        footer = _FOOTER_RE.fullmatch(clean)
        if footer:
            footer_count = int(footer.group("count"))
            seen_footer = True
            continue
        raise IngestError(f"sherlock console: unrecognized line {index}")
    if footer_count is not None and footer_count != claimed:
        raise IngestError(
            f"sherlock console: footer says {footer_count} results but {claimed} claimed lines were present"
        )
    for record in records:
        record["subject"] = username
    return {"subject": username, "input_type": "username", "records": records}


def _parse_sherlock_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError(f"sherlock JSON: {exc.msg} at line {exc.lineno}") from exc
    if _looks_like_site_manifest(data):
        raise IngestError(
            "sherlock JSON: this looks like a site manifest. "
            "Sherlock --json loads site data and does not write a results file"
        )
    if isinstance(data, list):
        rows = [_sherlock_json_row(item, f"sherlock JSON item {index}") for index, item in enumerate(data, start=1)]
    elif isinstance(data, dict):
        rows = []
        for site_name, item in data.items():
            if not isinstance(site_name, str) or site_name == "":
                raise IngestError("sherlock JSON: site names must be non-empty strings")
            rows.append(_sherlock_json_row(item, f"sherlock JSON site {site_name}", site_name=site_name))
    else:
        raise IngestError("sherlock JSON: expected an object keyed by site or an array of CSV rows")
    usernames = {row["subject"] for row in rows if row["subject"]}
    if len(usernames) > 1:
        raise IngestError("sherlock JSON: file contains more than one username; refusing to import")
    subject = next(iter(usernames)) if len(usernames) == 1 else None
    return {"subject": subject, "input_type": "username", "records": rows}


def _looks_like_site_manifest(data) -> bool:
    if not isinstance(data, dict):
        return False
    for value in data.values():
        if isinstance(value, dict) and ("urlMain" in value or "errorType" in value):
            return True
    return False


def _sherlock_json_row(item, where: str, site_name: str | None = None) -> dict:
    if not isinstance(item, dict):
        raise IngestError(f"{where}: expected an object")
    extra = set(item) - _SHERLOCK_JSON_KEYS
    if extra:
        raise IngestError(f"{where}: unexpected keys {', '.join(sorted(extra))}")
    if "url_user" not in item or "exists" not in item:
        raise IngestError(f"{where}: url_user and exists are required")
    url_user = item["url_user"]
    exists = item["exists"]
    if not isinstance(url_user, str) or url_user == "":
        raise IngestError(f"{where}: url_user must be a non-empty string")
    if not isinstance(exists, str) or exists not in _SHERLOCK_EXISTS:
        raise IngestError(f"{where}: exists must be one of {', '.join(sorted(_SHERLOCK_EXISTS))}")
    username = item.get("username")
    if username is not None and (not isinstance(username, str) or username == ""):
        raise IngestError(f"{where}: username must be a non-empty string")
    name = item.get("name", site_name if site_name is not None else "")
    if not isinstance(name, str):
        raise IngestError(f"{where}: name must be a string")
    if site_name is not None and "name" in item and item["name"] != site_name:
        raise IngestError(f"{where}: name does not match the site key")
    url_main = item.get("url_main", "")
    if not isinstance(url_main, str):
        raise IngestError(f"{where}: url_main must be a string")
    http_status = item.get("http_status", "")
    if isinstance(http_status, bool) or (
        http_status != "" and not isinstance(http_status, int) and not (isinstance(http_status, str) and http_status.isdigit())
    ):
        raise IngestError(f"{where}: http_status must be an integer, a digit string, or empty")
    response_time = item.get("response_time_s", "")
    if isinstance(response_time, bool) or (
        response_time != ""
        and not isinstance(response_time, (int, float))
        and not (isinstance(response_time, str) and _FLOAT_TOKEN.fullmatch(response_time))
    ):
        raise IngestError(f"{where}: response_time_s must be a number or empty")
    platform = site_name if site_name is not None else name
    return {
        "source_format": "json",
        "platform": platform,
        "subject": username,
        "status": exists,
        "url": url_user,
        "fields": {
            "username": username,
            "name": name,
            "url_main": url_main,
            "url_user": url_user,
            "exists": exists,
            "http_status": http_status,
            "response_time_s": response_time,
        },
    }


def _parse_maigret(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return _parse_maigret_ndjson(text, exc)
    if isinstance(data, dict) and _is_maigret_record(data):
        records = [_validate_maigret_record(data, "maigret ndjson line 1", require_sitename=True)]
        return _finish_maigret(records, "ndjson")
    if isinstance(data, dict) and _is_maigret_simple(data):
        records = []
        for site_name, value in data.items():
            if not isinstance(site_name, str) or site_name == "":
                raise IngestError("maigret simple JSON: site names must be non-empty strings")
            records.append(
                _validate_maigret_record(
                    value,
                    f"maigret simple JSON site {site_name}",
                    require_sitename=False,
                    site_key=site_name,
                )
            )
        return _finish_maigret(records, "simple")
    if isinstance(data, list):
        raise IngestError("maigret JSON: expected a simple object or ndjson lines, not an array")
    raise IngestError("maigret JSON: not a simple report or an ndjson record")


def _parse_maigret_ndjson(text: str, first_error: json.JSONDecodeError) -> dict:
    lines = text.splitlines()
    if not any(line.strip() for line in lines):
        raise IngestError(f"maigret JSON: {first_error.msg}") from first_error
    records = []
    for index, line in enumerate(lines, start=1):
        if line.strip() == "":
            raise IngestError(f"maigret ndjson line {index}: blank lines are not part of the format")
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IngestError(
                f"maigret report is neither simple JSON ({first_error.msg}) nor ndjson (line {index}: {exc.msg})"
            ) from exc
        records.append(_validate_maigret_record(obj, f"maigret ndjson line {index}", require_sitename=True))
    return _finish_maigret(records, "ndjson")


def _is_maigret_record(value) -> bool:
    return isinstance(value, dict) and isinstance(value.get("url_user"), str) and isinstance(value.get("status"), dict)


def _is_maigret_simple(data: dict) -> bool:
    if _is_maigret_record(data):
        return False
    return all(isinstance(value, dict) for value in data.values())


def _validate_maigret_record(obj, where: str, *, require_sitename: bool, site_key: str | None = None) -> dict:
    if not _is_maigret_record(obj):
        raise IngestError(f"{where}: each site needs string url_user and object status")
    url_user = obj["url_user"]
    if url_user == "":
        raise IngestError(f"{where}: url_user is empty")
    username = obj.get("username")
    if not isinstance(username, str) or username == "":
        raise IngestError(f"{where}: username must be a non-empty string")
    status = obj["status"]
    if status.get("status") != "Claimed":
        raise IngestError(f"{where}: status.status must be Claimed (Maigret JSON reports omit the rest)")
    status_url = status.get("url")
    if status_url is not None:
        if not isinstance(status_url, str):
            raise IngestError(f"{where}: status.url must be a string")
        if status_url != url_user:
            raise IngestError(f"{where}: status.url does not match url_user")
    sitename = obj.get("sitename")
    if require_sitename:
        if not isinstance(sitename, str) or sitename == "":
            raise IngestError(f"{where}: ndjson records must include sitename")
    elif sitename is not None and sitename != site_key:
        raise IngestError(f"{where}: sitename does not match the site key")
    site_name = status.get("site_name")
    if site_name is not None and not isinstance(site_name, str):
        raise IngestError(f"{where}: status.site_name must be a string")
    if site_key is not None and isinstance(site_name, str) and site_name != site_key:
        raise IngestError(f"{where}: status.site_name does not match the site key")
    url_main = obj.get("url_main")
    if url_main is not None and not isinstance(url_main, str):
        raise IngestError(f"{where}: url_main must be a string")
    http_status = obj.get("http_status", None)
    if http_status is not None and http_status != "" and (isinstance(http_status, bool) or not isinstance(http_status, int)):
        raise IngestError(f"{where}: http_status must be an integer or empty")
    ids = status.get("ids", {})
    if ids is None:
        ids = {}
    if not isinstance(ids, dict):
        raise IngestError(f"{where}: status.ids must be an object")
    tags = status.get("tags", [])
    if tags is None:
        tags = []
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise IngestError(f"{where}: status.tags must be a list of strings")
    platform = sitename or site_key or (site_name if isinstance(site_name, str) else "")
    return {
        "source_format": "ndjson" if require_sitename else "simple",
        "platform": platform or "",
        "subject": username,
        "status": "Claimed",
        "url": url_user,
        "fields": {
            "username": username,
            "sitename": sitename if isinstance(sitename, str) else site_key,
            "site_name": site_name if isinstance(site_name, str) else None,
            "url_user": url_user,
            "url_main": url_main,
            "http_status": http_status,
            "ids": ids,
            "tags": tags,
        },
    }


def _finish_maigret(records: list[dict], source_format: str) -> dict:
    for record in records:
        record["source_format"] = source_format
    usernames = {record["subject"] for record in records}
    if len(usernames) > 1:
        raise IngestError("maigret report contains more than one username; refusing to import")
    subject = next(iter(usernames)) if usernames else None
    return {"subject": subject, "input_type": "username", "records": records}


def _parse_holehe(text: str, *, source_name: str) -> dict:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = list(reader.fieldnames or [])
    if header == _HOLEHE_STANDARD:
        bool_columns = ["frequent_rate_limit", "rateLimit", "exists"]
        has_error = False
    elif header == _HOLEHE_ERROR:
        bool_columns = ["rateLimit", "error", "exists"]
        has_error = True
    else:
        raise IngestError(
            "holehe CSV: header must be the standard module columns "
            "(name,domain,method,frequent_rate_limit,rateLimit,exists,emailrecovery,phoneNumber,others) "
            "or the error-row columns "
            "(name,domain,rateLimit,error,exists,emailrecovery,phoneNumber,others)"
        )
    records = []
    for index, row in enumerate(reader, start=2):
        if None in row and row[None]:
            raise IngestError(f"holehe CSV: row {index} has extra columns")
        where = f"holehe CSV row {index}"
        name = _csv_cell(row, "name", where)
        domain = _csv_cell(row, "domain", where)
        if name == "" or domain == "":
            raise IngestError(f"{where}: name and domain are required")
        flags = {column: _bool_cell(row, column, where) for column in bool_columns}
        emailrecovery = _csv_cell(row, "emailrecovery", where)
        phone = _csv_cell(row, "phoneNumber", where)
        others = _csv_cell(row, "others", where)
        method = _csv_cell(row, "method", where) if not has_error else ""
        exists = flags["exists"]
        fields = {
            "name": name,
            "domain": domain,
            "method": method,
            "frequent_rate_limit": flags.get("frequent_rate_limit"),
            "rateLimit": flags["rateLimit"],
            "exists": exists,
            "error": flags.get("error"),
            "emailrecovery": emailrecovery,
            "phoneNumber": phone,
            "others": others,
        }
        records.append(
            {
                "source_format": "csv",
                "platform": name,
                "subject": None,
                "status": "Claimed" if exists else "Available",
                "url": None,
                "fields": fields,
            }
        )
    subject = _holehe_subject_from_filename(source_name)
    for record in records:
        record["subject"] = subject
    return {"subject": subject, "input_type": "email", "records": records}


def _holehe_subject_from_filename(source_name: str) -> str | None:
    match = _HOLEHE_FILENAME.fullmatch(source_name)
    if not match:
        return None
    email = match.group(2)
    if email.count("@") != 1 or "/" in email or "\\" in email or any(ch.isspace() for ch in email):
        return None
    return email


def _csv_cell(row: dict, key: str, where: str) -> str:
    if key not in row or row[key] is None:
        raise IngestError(f"{where}: missing {key}")
    value = row[key]
    if not isinstance(value, str):
        raise IngestError(f"{where}: {key} must be a string")
    if "\x00" in value:
        raise IngestError(f"{where}: {key} contains a NUL byte")
    return value


def _bool_cell(row: dict, key: str, where: str) -> bool:
    value = _csv_cell(row, key, where)
    if value == "True":
        return True
    if value == "False":
        return False
    raise IngestError(f"{where}: {key} must be True or False")


def _strip_sgr(text: str) -> str:
    return _SGR_RE.sub("", text)
