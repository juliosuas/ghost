"""Local tool-report ingest. Synthetic fixtures only (demo_user, example.com)."""

import csv
import hashlib
import sqlite3
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import pytest
from click.testing import CliRunner

from ghost.backend.db import get_investigation, init_db, list_investigations, save_investigation
from ghost.core.ingest import MAX_INGEST_BYTES, PROVENANCE_KEYS, IngestError, ingest_file
from ghost.core.investigator import Investigation
from ghost.core.report_generator import ReportGenerator
from ghost.ui.cli import cli

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ingest"
FROZEN = datetime(2026, 10, 9, 8, 33, tzinfo=timezone.utc)
EXACT_URL = "https://example.com/demo_user/%2e%2e?x=1&y=2"
XSS_NAME = "<script>alert(1)</script>"
IMG_NAME = "<img src=x onerror=alert(1)>"
MD_NAME = "[click](javascript:alert(1))"
JS_URL = "javascript:alert(document.domain)"


@pytest.fixture(autouse=True)
def _setup_test_db(tmp_path, monkeypatch):
    monkeypatch.setattr("ghost.backend.db.DB_PATH", tmp_path / "ghost.db")
    init_db()


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag.lower())
        self.attrs.extend(attrs)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def _ingest(name, tool, **kwargs):
    return ingest_file(FIXTURES / name, tool, ingested_at=FROZEN, **kwargs)


def _records(investigation):
    return investigation["findings"]["ingest"]["records"]


class TestSherlockFormats:
    def test_csv_keeps_url_time_and_provenance(self):
        result = _ingest("sherlock-demo_user.csv", "sherlock", authorized_use=True)
        investigation = result.investigation
        assert result.created is True
        assert investigation["target"] == "demo_user"
        assert investigation["input_type"] == "username"
        assert investigation["authorized_use"] is True
        records = _records(investigation)
        assert len(records) == 2
        claimed = records[0]
        assert claimed["url"] == EXACT_URL
        assert claimed["status"] == "Claimed"
        assert claimed["fields"]["response_time_s"] == "0.4200"
        assert claimed["fields"]["http_status"] == "200"
        assert tuple(claimed["provenance"]) == PROVENANCE_KEYS
        assert claimed["provenance"]["tool"] == "sherlock"
        assert claimed["provenance"]["tool_version"] is None
        assert claimed["provenance"]["ingested_at"] == FROZEN.isoformat()
        assert claimed["provenance"]["url"] == EXACT_URL
        digest = hashlib.sha256((FIXTURES / "sherlock-demo_user.csv").read_bytes()).hexdigest()
        assert claimed["provenance"]["source_sha256"] == digest == result.source_sha256
        profiles = [entity for entity in investigation["entities"] if entity["entity_type"] == "profile"]
        assert [entity["value"] for entity in profiles] == [EXACT_URL]
        assert profiles[0]["metadata"]["provenance"]["url"] == EXACT_URL

    def test_txt_requires_case_and_checks_the_total(self):
        with pytest.raises(IngestError, match="no subject"):
            _ingest("sherlock-demo_user.txt", "sherlock")
        assert list_investigations() == []

        result = _ingest("sherlock-demo_user.txt", "sherlock", case="demo_user")
        records = _records(result.investigation)
        assert [record["url"] for record in records] == [
            "https://example.com/demo_user",
            "https://example.com/other/demo_user",
        ]
        assert all(record["status"] == "Claimed" for record in records)

    def test_txt_total_mismatch_imports_nothing(self, tmp_path):
        path = tmp_path / "bad.txt"
        path.write_text("https://example.com/demo_user\nTotal Websites Username Detected On : 2\n", encoding="utf-8")
        with pytest.raises(IngestError, match="total says 2"):
            ingest_file(path, "sherlock", case="demo_user", ingested_at=FROZEN)
        assert list_investigations() == []

    def test_console_transcript_and_ansi(self, tmp_path):
        result = _ingest("sherlock-demo_user-console.txt", "sherlock")
        records = _records(result.investigation)
        assert len(records) == 1
        assert records[0]["platform"] == "Example"
        assert records[0]["url"] == "https://example.com/demo_user"
        assert records[0]["subject"] == "demo_user"

        colored = (
            "\x1b[92m[*]\x1b[0m Checking username demo_user on:\n"
            "\x1b[97m[\x1b[92m+\x1b[97m]\x1b[92m Example: \x1b[0mhttps://example.com/demo_user\n"
            "\x1b[92m[*]\x1b[0m Search completed with 1 results\n"
        )
        path = tmp_path / "color.txt"
        path.write_text(colored, encoding="utf-8")
        colored_result = ingest_file(path, "sherlock", ingested_at=FROZEN)
        assert _records(colored_result.investigation)[0]["url"] == "https://example.com/demo_user"

    def test_json_object_and_rejects_site_manifest(self, tmp_path):
        result = _ingest("sherlock-demo_user.json", "sherlock")
        record = _records(result.investigation)[0]
        assert record["url"] == "https://example.com/demo_user"
        assert record["fields"]["http_status"] == 200
        assert record["provenance"]["tool_version"] is None

        manifest = tmp_path / "sites.json"
        manifest.write_text(
            '{"Example": {"urlMain": "https://example.com", "errorType": "status_code"}}',
            encoding="utf-8",
        )
        with pytest.raises(IngestError, match="site manifest"):
            ingest_file(manifest, "sherlock", ingested_at=FROZEN)
        assert get_investigation(result.investigation["id"])["findings"]["ingest"]["records"][0]["url"] == (
            "https://example.com/demo_user"
        )

    def test_csv_header_and_second_row_errors_write_nothing(self, tmp_path):
        bad_header = tmp_path / "bad.csv"
        bad_header.write_text("username,url\ndemo_user,https://example.com/demo_user\n", encoding="utf-8")
        with pytest.raises(IngestError, match="header must be"):
            ingest_file(bad_header, "sherlock", ingested_at=FROZEN)

        bad_row = tmp_path / "row.csv"
        bad_row.write_text(
            "username,name,url_main,url_user,exists,http_status,response_time_s\n"
            "demo_user,Example,https://example.com/,https://example.com/demo_user,Claimed,200,0.1\n"
            "demo_user,Other,https://example.com/,https://example.com/other,Maybe,200,0.1\n",
            encoding="utf-8",
        )
        with pytest.raises(IngestError, match="exists must be"):
            ingest_file(bad_row, "sherlock", ingested_at=FROZEN)
        assert list_investigations() == []


class TestMaigretFormats:
    def test_simple_json(self):
        result = _ingest("maigret-demo_user-simple.json", "maigret")
        record = _records(result.investigation)[0]
        assert result.investigation["target"] == "demo_user"
        assert record["url"] == "https://example.com/demo_user"
        assert record["platform"] == "Example"
        assert record["source_format"] == "simple"
        assert record["fields"]["ids"]["bio"] == "demo_user synthetic fixture"
        assert record["provenance"]["tool"] == "maigret"
        assert record["provenance"]["tool_version"] is None
        assert record["provenance"]["url"] == record["url"]

    def test_ndjson_and_rejects_a_bad_line(self, tmp_path):
        result = _ingest("maigret-demo_user.ndjson", "maigret")
        records = _records(result.investigation)
        assert [record["url"] for record in records] == [
            "https://example.com/demo_user",
            "https://example.org/demo_user",
        ]
        assert records[0]["source_format"] == "ndjson"

        path = tmp_path / "bad.ndjson"
        good = (FIXTURES / "maigret-demo_user.ndjson").read_text(encoding="utf-8").splitlines()[0]
        path.write_text(good + "\n{not json}\n", encoding="utf-8")
        before = len(list_investigations())
        with pytest.raises(IngestError, match="ndjson"):
            ingest_file(path, "maigret", ingested_at=FROZEN)
        assert len(list_investigations()) == before

    def test_status_url_must_match_exactly(self, tmp_path):
        path = tmp_path / "mismatch.json"
        path.write_text(
            '{"Example": {"username": "demo_user", "url_user": "https://example.com/demo_user", '
            '"status": {"status": "Claimed", "url": "https://example.com/other"}}}\n',
            encoding="utf-8",
        )
        with pytest.raises(IngestError, match="does not match"):
            ingest_file(path, "maigret", ingested_at=FROZEN)
        assert list_investigations() == []


class TestHoleheFormat:
    def test_filename_supplies_the_email_and_others_stay_raw(self):
        result = _ingest("holehe_1710000000_demo_user@example.com_results.csv", "holehe")
        investigation = result.investigation
        assert investigation["target"] == "demo_user@example.com"
        assert investigation["input_type"] == "email"
        records = _records(investigation)
        assert records[0]["status"] == "Claimed"
        assert records[0]["url"] is None
        assert records[0]["provenance"]["url"] is None
        assert records[0]["provenance"]["tool_version"] is None
        assert records[0]["fields"]["others"] == "{'FullName': 'Demo'}"
        assert records[1]["status"] == "Available"
        accounts = [entity for entity in investigation["entities"] if entity["entity_type"] == "account"]
        assert [entity["value"] for entity in accounts] == ["example.com"]

    def test_renamed_file_needs_case(self, tmp_path):
        source = FIXTURES / "holehe_1710000000_demo_user@example.com_results.csv"
        path = tmp_path / "renamed.csv"
        path.write_bytes(source.read_bytes())
        with pytest.raises(IngestError, match="no subject"):
            ingest_file(path, "holehe", ingested_at=FROZEN)
        assert list_investigations() == []


class TestCaseAttachment:
    def test_appends_to_existing_case_without_dropping_findings(self):
        first = _ingest("sherlock-demo_user.csv", "sherlock")
        first.investigation["findings"]["username"] = {
            "profiles": [{"platform": "Example", "url": "https://example.com/kept", "status": "found"}]
        }
        first.investigation["summary"] = "keep this summary"
        save_investigation(
            {
                "id": first.investigation["id"],
                "target": first.investigation["target"],
                "input_type": first.investigation["input_type"],
                "scope": first.investigation["scope"],
                "authorized_use": False,
                "status": "completed",
                "started_at": first.investigation["started_at"],
                "completed_at": first.investigation["completed_at"],
                "summary": "keep this summary",
                "risk_score": 0.2,
                "errors": [],
                "findings": first.investigation["findings"],
            }
        )
        second = _ingest("maigret-demo_user-simple.json", "maigret", case="demo_user")
        assert second.created is False
        assert second.investigation["id"] == first.investigation["id"]
        assert second.investigation["summary"] == "keep this summary"
        assert second.investigation["findings"]["username"]["profiles"][0]["url"] == "https://example.com/kept"
        assert len(_records(second.investigation)) == 3

    def test_second_ingest_replaces_entities_relationships_point_at(self):
        from ghost.backend.db import get_connection

        first = _ingest("sherlock-demo_user.csv", "sherlock", case="demo_user")
        profile_ids = {entity["id"] for entity in first.investigation["entities"] if entity["entity_type"] == "profile"}
        assert profile_ids
        conn = get_connection()
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            rels = conn.execute(
                "SELECT source_entity_id, target_entity_id FROM relationships WHERE investigation_id = ?",
                (first.investigation["id"],),
            ).fetchall()
        finally:
            conn.close()
        assert rels
        assert any(row["target_entity_id"] in profile_ids for row in rels)

        second = _ingest("sherlock-demo_user.csv", "sherlock", case="demo_user")
        assert second.created is False
        assert second.investigation["id"] == first.investigation["id"]
        profiles = [entity for entity in second.investigation["entities"] if entity["entity_type"] == "profile"]
        assert [entity["value"] for entity in profiles] == [EXACT_URL]
        assert len(second.investigation["relationships"]) == 1
        assert second.investigation["relationships"][0]["target_entity_id"] == profiles[0]["id"]
        assert len(_records(second.investigation)) == 4

    def test_ambiguous_case_name_writes_nothing(self):
        _ingest("sherlock-demo_user.csv", "sherlock")
        _ingest("sherlock-demo_user.csv", "sherlock")
        with pytest.raises(IngestError, match="ambiguous|matches"):
            _ingest("maigret-demo_user-simple.json", "maigret", case="demo_user")
        assert len(list_investigations()) == 2
        for summary in list_investigations():
            stored = get_investigation(summary["id"])
            assert len(_records(stored)) == 2


class TestSafety:
    def test_size_cap_constant_and_stat_before_read(self, tmp_path, monkeypatch):
        assert MAX_INGEST_BYTES == 50 * 1024 * 1024
        monkeypatch.setattr("ghost.core.ingest.MAX_INGEST_BYTES", 10)
        path = tmp_path / "big.csv"
        path.write_bytes(b"x" * 11)
        calls = {"open": 0}
        real_open = Path.open

        def wrapped(self, *args, **kwargs):
            if self == path:
                calls["open"] += 1
            return real_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", wrapped)
        with pytest.raises(IngestError, match="Refusing to read"):
            ingest_file(path, "sherlock", ingested_at=FROZEN)
        assert calls["open"] == 0
        assert list_investigations() == []

    def test_bounded_read_rejects_when_stat_underreports(self, tmp_path, monkeypatch):
        monkeypatch.setattr("ghost.core.ingest.MAX_INGEST_BYTES", 10)
        path = tmp_path / "proc-like.csv"
        path.write_bytes(b"x" * 1000)
        real_stat = Path.stat
        real_open = Path.open
        reads = []

        class _ZeroStat:
            def __init__(self, real):
                self.st_mode = real.st_mode
                self.st_size = 0

        def zero_stat(self, *args, **kwargs):
            result = real_stat(self, *args, **kwargs)
            if self == path:
                return _ZeroStat(result)
            return result

        class _BoundedFile:
            def __init__(self, raw):
                self._raw = raw

            def read(self, size=-1):
                reads.append(size)
                return self._raw.read(size)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self._raw.close()
                return False

        def tracking_open(self, *args, **kwargs):
            raw = real_open(self, *args, **kwargs)
            if self == path:
                return _BoundedFile(raw)
            return raw

        monkeypatch.setattr(Path, "stat", zero_stat)
        monkeypatch.setattr(Path, "open", tracking_open)
        with pytest.raises(IngestError, match="grew past"):
            ingest_file(path, "sherlock", ingested_at=FROZEN)
        assert reads == [11]
        assert list_investigations() == []

    def test_read_is_rejected_if_the_file_grows_past_the_cap(self, tmp_path, monkeypatch):
        monkeypatch.setattr("ghost.core.ingest.MAX_INGEST_BYTES", 10)
        path = tmp_path / "grows.csv"
        path.write_bytes(b"x" * 11)
        real_stat = Path.stat

        class _SmallStat:
            def __init__(self, real):
                self.st_mode = real.st_mode
                self.st_size = 1

        def small_stat(self, *args, **kwargs):
            result = real_stat(self, *args, **kwargs)
            if self == path:
                return _SmallStat(result)
            return result

        monkeypatch.setattr(Path, "stat", small_stat)
        with pytest.raises(IngestError, match="grew past"):
            ingest_file(path, "sherlock", ingested_at=FROZEN)
        assert list_investigations() == []

    def test_failed_write_rolls_back_the_whole_import(self, monkeypatch):
        existing = Investigation("demo_user", "username", scope="keep", authorized_use=True)
        existing.status = "completed"
        existing.summary = "original summary"
        existing.findings = {"username": {"profiles": []}}
        save_investigation(existing.to_dict())

        from ghost.backend import db as db_module

        real_get_connection = db_module.get_connection
        armed = {"on": False}

        def wrapped_get_connection(database_path=None):
            conn = real_get_connection(database_path)
            original = conn.execute

            def execute(sql, parameters=()):
                if armed["on"] and isinstance(sql, str) and "INSERT INTO findings" in sql:
                    raise sqlite3.OperationalError("forced failure")
                return original(sql, parameters)

            class _Proxy:
                def execute(self, sql, parameters=()):
                    return execute(sql, parameters)

                def __getattr__(self, name):
                    return getattr(conn, name)

            return _Proxy()

        monkeypatch.setattr(db_module, "get_connection", wrapped_get_connection)
        armed["on"] = True
        with pytest.raises(IngestError, match="rolled back"):
            ingest_file(FIXTURES / "sherlock-demo_user.csv", "sherlock", case=existing.id, ingested_at=FROZEN)
        armed["on"] = False

        stored = get_investigation(existing.id)
        assert stored["summary"] == "original summary"
        assert "ingest" not in stored["findings"]
        assert len(list_investigations()) == 1

    def test_deeply_nested_json_is_an_ingest_error(self, tmp_path):
        nested = "[" * 10000 + "]" * 10000
        sherlock = tmp_path / "nested.json"
        sherlock.write_text(nested, encoding="utf-8")
        with pytest.raises(IngestError, match="sherlock JSON: nesting exceeds"):
            ingest_file(sherlock, "sherlock", ingested_at=FROZEN)

        maigret = tmp_path / "nested-simple.json"
        maigret.write_text(nested, encoding="utf-8")
        with pytest.raises(IngestError, match="maigret JSON: nesting exceeds"):
            ingest_file(maigret, "maigret", ingested_at=FROZEN)

        record = (
            '{"username": "demo_user", "url_user": "https://example.com/demo_user", '
            '"sitename": "Example", "status": {"status": "Claimed", "url": "https://example.com/demo_user"}}'
        )
        ndjson = tmp_path / "nested.ndjson"
        ndjson.write_text(record + "\n" + nested + "\n", encoding="utf-8")
        with pytest.raises(IngestError, match="maigret ndjson line 2: nesting exceeds"):
            ingest_file(ndjson, "maigret", ingested_at=FROZEN)
        assert list_investigations() == []

    def test_csv_field_over_the_reader_limit_is_an_ingest_error(self, tmp_path):
        wide = "a" * (csv.field_size_limit() + 1)
        sherlock = tmp_path / "wide.csv"
        sherlock.write_text(
            "username,name,url_main,url_user,exists,http_status,response_time_s\n"
            f"demo_user,Example,https://example.com/,https://example.com/{wide},Claimed,200,0.1\n",
            encoding="utf-8",
        )
        with pytest.raises(IngestError, match="sherlock CSV: field larger than field limit"):
            ingest_file(sherlock, "sherlock", ingested_at=FROZEN)

        holehe = tmp_path / "wide-holehe.csv"
        holehe.write_text(
            "name,domain,method,frequent_rate_limit,rateLimit,exists,emailrecovery,phoneNumber,others\n"
            f"Example,example.com,register,False,False,True,,,{wide}\n",
            encoding="utf-8",
        )
        with pytest.raises(IngestError, match="holehe CSV: field larger than field limit"):
            ingest_file(holehe, "holehe", case="demo_user@example.com", ingested_at=FROZEN)
        assert list_investigations() == []

    def test_parser_does_not_import_network_or_process_modules(self):
        import ast

        tree = ast.parse(Path(ingest_module_path()).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint({"subprocess", "requests", "aiohttp", "urllib", "socket", "http"})


class TestUntrustedExports:
    def test_html_and_markdown_neutralize_payloads(self, tmp_path):
        path = tmp_path / "xss.csv"
        path.write_text(
            "username,name,url_main,url_user,exists,http_status,response_time_s\n"
            f"demo_user,{XSS_NAME},https://example.com/,{JS_URL},Claimed,200,0.1\n"
            f'demo_user,"{IMG_NAME}",https://example.com/,https://example.com/demo_user,Claimed,200,0.1\n'
            f'demo_user,"{MD_NAME}",https://example.com/,https://example.com/demo_user?q=1,Claimed,200,0.1\n',
            encoding="utf-8",
        )
        result = ingest_file(path, "sherlock", ingested_at=FROZEN)
        stored_urls = [record["url"] for record in _records(result.investigation)]
        assert stored_urls[0] == JS_URL
        assert _records(result.investigation)[0]["platform"] == XSS_NAME
        assert _records(result.investigation)[1]["platform"] == IMG_NAME
        assert _records(result.investigation)[2]["platform"] == MD_NAME

        html_path = tmp_path / "report.html"
        md_path = tmp_path / "report.md"
        ReportGenerator().generate(result.investigation, "html", str(html_path))
        ReportGenerator().generate(result.investigation, "markdown", str(md_path))
        html_out = html_path.read_text(encoding="utf-8")
        md_out = md_path.read_text(encoding="utf-8")

        collector = _TagCollector()
        collector.feed(html_out)
        assert "script" not in collector.tags
        assert "img" not in collector.tags
        assert all(name.lower() != "onerror" for name, _value in collector.attrs)
        hrefs = [value for name, value in collector.attrs if name.lower() == "href"]
        assert all(not str(value).lower().startswith("javascript:") for value in hrefs)
        assert "https://example.com/demo_user" in hrefs
        assert JS_URL in html_out
        assert "&lt;script&gt;" in html_out

        assert "<script>" not in md_out
        assert "<img" not in md_out
        assert "](javascript:" not in md_out
        assert "\\[click\\]" in md_out
        assert "javascript:alert" in md_out

    def test_holehe_others_payload_is_not_evaluated(self, tmp_path):
        path = tmp_path / "holehe_1710000000_demo_user@example.com_results.csv"
        path.write_text(
            "name,domain,method,frequent_rate_limit,rateLimit,exists,emailrecovery,phoneNumber,others\n"
            "example,example.com,register,False,False,True,,,"
            "\"{'FullName': '<script>alert(1)</script>'}\"\n",
            encoding="utf-8",
        )
        result = ingest_file(path, "holehe", ingested_at=FROZEN)
        others = _records(result.investigation)[0]["fields"]["others"]
        assert others == "{'FullName': '<script>alert(1)</script>'}"
        assert not isinstance(others, dict)
        md_path = tmp_path / "holehe.md"
        ReportGenerator().generate(result.investigation, "md", str(md_path))
        assert "<script>" not in md_path.read_text(encoding="utf-8")


class TestCli:
    def test_ingest_command_and_rejects_invalid_files(self):
        result = CliRunner().invoke(
            cli,
            ["ingest", str(FIXTURES / "sherlock-demo_user.csv"), "--tool", "sherlock", "--authorized"],
        )
        assert result.exit_code == 0, result.output
        assert "Created case" in result.output
        stored = list_investigations()
        assert len(stored) == 1
        assert stored[0]["authorized_use"] is True

        rejected = CliRunner().invoke(cli, ["ingest", str(FIXTURES / "sherlock-demo_user.txt"), "--tool", "sherlock"])
        assert rejected.exit_code != 0
        assert "Nothing was imported." in rejected.output
        assert len(list_investigations()) == 1

    def test_command_does_not_run_investigate(self, monkeypatch):
        def boom(*_args, **_kwargs):
            raise AssertionError("investigate was called")

        monkeypatch.setattr("ghost.ui.cli.run_investigation", boom)
        result = CliRunner().invoke(
            cli, ["ingest", str(FIXTURES / "maigret-demo_user-simple.json"), "--tool", "maigret"]
        )
        assert result.exit_code == 0, result.output

    def test_diff_command_is_not_registered(self):
        result = CliRunner().invoke(cli, ["diff"])
        assert result.exit_code != 0
        assert "No such command" in result.output


def ingest_module_path() -> Path:
    import ghost.core.ingest as ingest_module

    return Path(ingest_module.__file__)
