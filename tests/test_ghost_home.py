"""GHOST_HOME resolution, permissions, and legacy database copy."""

from __future__ import annotations

import errno
import json
import logging
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from ghost.backend.db import init_db
from ghost.core.doctor import has_error, run_doctor_checks
from ghost.core.paths import (
    data_path_doctor_detail,
    migrate_legacy_database,
    mode_bits,
    prepare_storage,
    resolve_layout,
)


def _check(checks, name: str):
    return next(item for item in checks if item.name == name)


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    """Point platformdirs at tmp and clear home/database overrides."""
    monkeypatch.setattr("ghost.core.paths.user_data_dir", lambda app: str(tmp_path / "xdg"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GHOST_HOME", raising=False)
    return tmp_path


class TestResolutionPrecedence:
    def test_platformdirs_when_unset(self, isolated_env):
        layout = resolve_layout({})
        home = isolated_env / "xdg"
        assert layout.source == "platformdirs"
        assert layout.home == home
        assert layout.data_dir == home / "data"
        assert layout.investigations_dir == home / "investigations"
        assert layout.database_path == home / "data" / "ghost.db"

    def test_ghost_home_beats_platformdirs(self, isolated_env):
        home = isolated_env / "custom"
        layout = resolve_layout({"GHOST_HOME": str(home)})
        assert layout.source == "GHOST_HOME"
        assert layout.home == home
        assert layout.data_dir == home / "data"
        assert layout.investigations_dir == home / "investigations"
        assert layout.database_path == home / "data" / "ghost.db"

    def test_database_url_beats_ghost_home_and_platformdirs(self, isolated_env):
        home = isolated_env / "custom"
        database = isolated_env / "explicit" / "case.db"
        layout = resolve_layout(
            {
                "DATABASE_URL": f"sqlite:///{database}",
                "GHOST_HOME": str(home),
            }
        )
        assert layout.source == "DATABASE_URL"
        assert layout.database_path == database
        assert layout.home == home
        assert layout.investigations_dir == home / "investigations"

    def test_relative_database_url_resolves_under_home_data_dir(self, isolated_env):
        home = isolated_env / "custom"
        layout = resolve_layout(
            {
                "DATABASE_URL": "sqlite:///ghost.db",
                "GHOST_HOME": str(home),
            }
        )
        assert layout.source == "DATABASE_URL"
        assert layout.database_path == home / "data" / "ghost.db"

    def test_blank_values_fall_through_to_platformdirs(self, isolated_env):
        layout = resolve_layout({"DATABASE_URL": "   ", "GHOST_HOME": "  "})
        assert layout.source == "platformdirs"
        assert layout.home == isolated_env / "xdg"

    def test_ghost_home_expands_user(self, isolated_env, monkeypatch):
        monkeypatch.setenv("HOME", str(isolated_env / "login"))
        layout = resolve_layout({"GHOST_HOME": "~/ghost-data"})
        assert layout.source == "GHOST_HOME"
        assert layout.home == isolated_env / "login" / "ghost-data"


class TestPermissions:
    def test_home_and_database_are_owner_only(self, isolated_env):
        previous = os.umask(0)
        try:
            home = isolated_env / "private"
            layout = prepare_storage({"GHOST_HOME": str(home)})
            init_db(layout.database_path)
        finally:
            os.umask(previous)

        assert mode_bits(layout.home) == 0o700
        assert mode_bits(layout.data_dir) == 0o700
        assert mode_bits(layout.investigations_dir) == 0o700
        assert mode_bits(layout.database_path) == 0o600
        assert stat.S_IMODE(layout.home.stat().st_mode) & 0o077 == 0
        assert stat.S_IMODE(layout.database_path.stat().st_mode) & 0o077 == 0

    def test_existing_directory_is_tightened(self, isolated_env):
        home = isolated_env / "loose"
        home.mkdir(mode=0o755)
        layout = prepare_storage({"GHOST_HOME": str(home)})
        assert mode_bits(layout.home) == 0o700
        assert mode_bits(layout.data_dir) == 0o700


def _marker(path: Path) -> str | None:
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT value FROM marker").fetchone()
    finally:
        conn.close()
    return None if row is None else row[0]


class TestLegacyMigration:
    def _legacy(self, root: Path) -> Path:
        legacy = root / "package" / "data" / "ghost.db"
        legacy.parent.mkdir(parents=True)
        conn = sqlite3.connect(legacy)
        conn.execute("CREATE TABLE marker (value TEXT)")
        conn.execute("INSERT INTO marker (value) VALUES ('legacy-sqlite')")
        conn.commit()
        conn.close()
        os.chmod(legacy, 0o644)
        return legacy

    def test_copies_and_does_not_move(self, isolated_env, monkeypatch):
        legacy = self._legacy(isolated_env)
        monkeypatch.setattr("ghost.core.paths.LEGACY_DB_PATH", legacy)

        def fail_move(*_args, **_kwargs):
            raise AssertionError("legacy database must be copied, not moved")

        monkeypatch.setattr("ghost.core.paths.shutil.move", fail_move)
        home = isolated_env / "home"
        source_inode = legacy.stat().st_ino
        layout = prepare_storage({"GHOST_HOME": str(home)})

        assert _marker(layout.database_path) == "legacy-sqlite"
        assert _marker(legacy) == "legacy-sqlite"
        assert legacy.stat().st_ino == source_inode
        assert legacy.stat().st_ino != layout.database_path.stat().st_ino
        assert mode_bits(legacy) == 0o644
        assert mode_bits(layout.database_path) == 0o600

    def test_backup_includes_uncheckpointed_wal_row(self, isolated_env, monkeypatch):
        legacy = isolated_env / "package" / "data" / "ghost.db"
        legacy.parent.mkdir(parents=True)
        writer = sqlite3.connect(legacy)
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE marker (value TEXT)")
        writer.execute("INSERT INTO marker (value) VALUES ('wal-only')")
        writer.commit()
        wal = Path(str(legacy) + "-wal")
        assert wal.exists()
        assert wal.stat().st_size > 0
        main_only = isolated_env / "main-only.db"
        main_only.write_bytes(legacy.read_bytes())
        untouched = sqlite3.connect(main_only)
        try:
            with pytest.raises(sqlite3.OperationalError):
                untouched.execute("SELECT value FROM marker").fetchone()
        finally:
            untouched.close()

        monkeypatch.setattr("ghost.core.paths.LEGACY_DB_PATH", legacy)
        try:
            layout = prepare_storage({"GHOST_HOME": str(isolated_env / "home")})
            assert _marker(layout.database_path) == "wal-only"
            assert legacy.exists()
            assert _marker(legacy) == "wal-only"
        finally:
            writer.close()

    @pytest.mark.parametrize("err", [errno.EPERM, errno.ENOTSUP])
    def test_link_oserror_falls_back_to_exclusive_copy(self, isolated_env, monkeypatch, err):
        legacy = self._legacy(isolated_env)
        monkeypatch.setattr("ghost.core.paths.LEGACY_DB_PATH", legacy)

        def no_link(*_args, **_kwargs):
            raise OSError(err, os.strerror(err))

        monkeypatch.setattr("ghost.core.paths.os.link", no_link)
        layout = prepare_storage({"GHOST_HOME": str(isolated_env / "home")})
        assert _marker(layout.database_path) == "legacy-sqlite"
        assert _marker(legacy) == "legacy-sqlite"
        assert legacy.stat().st_ino != layout.database_path.stat().st_ino

    def test_link_and_exclusive_copy_failure_does_not_crash(self, isolated_env, monkeypatch, caplog):
        legacy = self._legacy(isolated_env)
        monkeypatch.setattr("ghost.core.paths.LEGACY_DB_PATH", legacy)

        def no_link(*_args, **_kwargs):
            raise OSError(errno.EPERM, "Operation not permitted")

        def no_open(*_args, **_kwargs):
            raise OSError(errno.ENOTSUP, "Operation not supported")

        monkeypatch.setattr("ghost.core.paths.os.link", no_link)
        monkeypatch.setattr("ghost.core.paths.os.open", no_open)
        home = isolated_env / "home"
        with caplog.at_level(logging.WARNING, logger="ghost.core.paths"):
            layout = prepare_storage({"GHOST_HOME": str(home)})
        assert layout.home == home
        assert not layout.database_path.exists()
        assert _marker(legacy) == "legacy-sqlite"
        assert any("Could not migrate" in record.getMessage() for record in caplog.records)

    def test_logs_once(self, isolated_env, monkeypatch, caplog):
        legacy = self._legacy(isolated_env)
        monkeypatch.setattr("ghost.core.paths.LEGACY_DB_PATH", legacy)
        home = isolated_env / "home"
        with caplog.at_level(logging.WARNING, logger="ghost.core.paths"):
            first = prepare_storage({"GHOST_HOME": str(home)})
            second = prepare_storage({"GHOST_HOME": str(home)})
        assert first.database_path == second.database_path
        messages = [record.getMessage() for record in caplog.records if record.name == "ghost.core.paths"]
        assert len(messages) == 1
        assert "Copied legacy Ghost database" in messages[0]
        assert str(legacy) in messages[0]
        assert "left the original in place" in messages[0]

    def test_does_not_overwrite_existing_database(self, isolated_env, monkeypatch, caplog):
        legacy = self._legacy(isolated_env)
        monkeypatch.setattr("ghost.core.paths.LEGACY_DB_PATH", legacy)
        home = isolated_env / "home"
        dest = home / "data" / "ghost.db"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"keep-me")

        with caplog.at_level(logging.WARNING, logger="ghost.core.paths"):
            layout = prepare_storage({"GHOST_HOME": str(home)})

        assert layout.database_path.read_bytes() == b"keep-me"
        assert _marker(legacy) == "legacy-sqlite"
        assert legacy.exists()
        assert caplog.records == []

    def test_skips_when_database_url_is_set(self, isolated_env, monkeypatch, caplog):
        legacy = self._legacy(isolated_env)
        monkeypatch.setattr("ghost.core.paths.LEGACY_DB_PATH", legacy)
        home = isolated_env / "home"
        database = isolated_env / "external" / "explicit.db"

        with caplog.at_level(logging.WARNING, logger="ghost.core.paths"):
            layout = prepare_storage(
                {
                    "DATABASE_URL": f"sqlite:///{database}",
                    "GHOST_HOME": str(home),
                }
            )

        assert layout.source == "DATABASE_URL"
        assert not database.exists()
        assert not (home / "data" / "ghost.db").exists()
        assert _marker(legacy) == "legacy-sqlite"
        assert caplog.records == []

    def test_migrate_helper_skips_when_database_url_set(self, isolated_env):
        legacy = self._legacy(isolated_env)
        dest = isolated_env / "new" / "ghost.db"
        copied = migrate_legacy_database(
            dest,
            database_url="sqlite:///somewhere.db",
            legacy_path=legacy,
        )
        assert copied is False
        assert not dest.exists()
        assert legacy.exists()

    def test_same_path_is_not_copied_onto_itself(self, isolated_env):
        legacy = self._legacy(isolated_env)
        copied = migrate_legacy_database(legacy, database_url="", legacy_path=legacy)
        assert copied is False
        assert _marker(legacy) == "legacy-sqlite"


class TestDoctorDataPath:
    def test_reports_platformdirs(self, isolated_env):
        detail = data_path_doctor_detail({})
        assert detail == f"{isolated_env / 'xdg' / 'data'} (platformdirs)"
        checks = run_doctor_checks()
        # Live process env, not the empty mapping above.
        assert _check(checks, "data path").ok is True
        assert _check(checks, "data path").detail.endswith("(platformdirs)")

    def test_reports_ghost_home(self, isolated_env, monkeypatch):
        home = isolated_env / "from-env"
        monkeypatch.setenv("GHOST_HOME", str(home))
        checks = run_doctor_checks()
        assert _check(checks, "data path").detail == f"{home / 'data'} (GHOST_HOME)"

    def test_reports_database_url(self, isolated_env, monkeypatch):
        database = isolated_env / "explicit" / "ghost.db"
        monkeypatch.setenv("GHOST_HOME", str(isolated_env / "ignored"))
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
        checks = run_doctor_checks()
        assert _check(checks, "data path").detail == f"{database} (DATABASE_URL)"

    def test_doctor_json_includes_source(self, isolated_env, monkeypatch):
        from click.testing import CliRunner

        from ghost.ui.cli import cli

        home = isolated_env / "json-home"
        monkeypatch.setenv("GHOST_HOME", str(home))
        result = CliRunner().invoke(cli, ["doctor", "--json"])
        payload = json.loads(result.output)
        detail = next(item["detail"] for item in payload["checks"] if item["name"] == "data path")
        assert detail == f"{home / 'data'} (GHOST_HOME)"


class TestStartupWarnings:
    def test_chmod_failure_warns_and_continues(self, isolated_env, monkeypatch, caplog):
        def boom(_path, _mode):
            raise OSError(errno.EPERM, "Operation not permitted")

        monkeypatch.setattr("ghost.core.paths.os.chmod", boom)
        home = isolated_env / "home"
        with caplog.at_level(logging.WARNING, logger="ghost.core.paths"):
            layout = prepare_storage({"GHOST_HOME": str(home)})
        assert layout.home == home
        assert home.is_dir()
        assert any("Could not set mode 0700 on GHOST_HOME" in record.getMessage() for record in caplog.records)

    def test_unowned_home_warns_and_continues(self, isolated_env, monkeypatch, caplog):
        current_uid = os.getuid()
        monkeypatch.setattr("ghost.core.paths.os.getuid", lambda: current_uid + 1)
        home = isolated_env / "home"
        with caplog.at_level(logging.WARNING, logger="ghost.core.paths"):
            layout = prepare_storage({"GHOST_HOME": str(home)})
        assert layout.home == home
        assert any("is not owned by the current user" in record.getMessage() for record in caplog.records)

    def test_doctor_warns_when_legacy_reports_exist(self, isolated_env, monkeypatch, tmp_path):
        package = tmp_path / "pkg"
        report = package / "investigations" / "abc" / "report.html"
        report.parent.mkdir(parents=True)
        report.write_text("old", encoding="utf-8")
        monkeypatch.setattr("ghost.core.paths.PACKAGE_DIR", package)
        checks = run_doctor_checks()
        warning = _check(checks, "legacy reports")
        assert warning.ok is False
        assert warning.severity == "warn"
        assert str(package / "investigations") in warning.detail
        assert "not migrated" in warning.detail

    def test_doctor_ignores_empty_legacy_reports_dir(self, isolated_env, monkeypatch, tmp_path):
        package = tmp_path / "pkg"
        (package / "investigations").mkdir(parents=True)
        monkeypatch.setattr("ghost.core.paths.PACKAGE_DIR", package)
        checks = run_doctor_checks()
        assert all(item.name != "legacy reports" for item in checks)

    def test_doctor_warns_when_ghost_home_is_relative(self, isolated_env, monkeypatch):
        monkeypatch.chdir(isolated_env)
        monkeypatch.setenv("GHOST_HOME", "relative-home")
        checks = run_doctor_checks()
        warning = _check(checks, "GHOST_HOME")
        assert warning.ok is False
        assert warning.severity == "warn"
        assert "relative" in warning.detail
        assert str(isolated_env) in warning.detail
        assert has_error([warning]) is False

    def test_doctor_accepts_absolute_ghost_home(self, isolated_env, monkeypatch):
        monkeypatch.setenv("GHOST_HOME", str(isolated_env / "absolute"))
        checks = run_doctor_checks()
        assert all(item.name != "GHOST_HOME" for item in checks)
