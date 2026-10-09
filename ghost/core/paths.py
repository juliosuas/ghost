"""Writable Ghost home outside the installed package.

Resolution precedence for the database location is:

1. ``DATABASE_URL`` when it is set
2. ``GHOST_HOME``
3. ``platformdirs.user_data_dir("ghost")``

Investigations and reports always live under the resolved home
(``GHOST_HOME`` or the platformdirs directory), in ``investigations/``.
The default database file is ``<home>/data/ghost.db``.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from platformdirs import user_data_dir

logger = logging.getLogger(__name__)

# In-package tree (site-packages/ghost or the source package). Legacy installs
# wrote ghost.db here; upgrades copy that file out and leave it in place.
PACKAGE_DIR = Path(__file__).resolve().parent.parent
LEGACY_DB_PATH = PACKAGE_DIR / "data" / "ghost.db"

DIR_MODE = 0o700
DB_MODE = 0o600

_SOURCE_DATABASE_URL = "DATABASE_URL"
_SOURCE_GHOST_HOME = "GHOST_HOME"
_SOURCE_PLATFORMDIRS = "platformdirs"


@dataclass(frozen=True)
class GhostLayout:
    """Resolved on-disk locations and which setting won for the database."""

    home: Path
    data_dir: Path
    investigations_dir: Path
    database_path: Path
    source: str


def _environ(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def _env_value(environ: Mapping[str, str], name: str) -> str | None:
    value = environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def resolve_database_path(database_url: str, *, data_dir: Path) -> Path:
    """Resolve a SQLite database URL against ``data_dir`` for relative paths.

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
            path = data_dir / path
        return path

    raise ValueError(
        f"Unsupported DATABASE_URL scheme '{parsed.scheme}'. "
        "Ghost v2 currently supports sqlite:///path/to/ghost.db. "
        "PostgreSQL support is planned behind the storage adapter boundary."
    )


def resolve_layout(environ: Mapping[str, str] | None = None) -> GhostLayout:
    """Return the home, data directory, investigations directory, and database path."""
    env = _environ(environ)
    ghost_home = _env_value(env, "GHOST_HOME")
    database_url = _env_value(env, "DATABASE_URL")

    if ghost_home:
        home = Path(ghost_home).expanduser()
        home_source = _SOURCE_GHOST_HOME
    else:
        home = Path(user_data_dir("ghost"))
        home_source = _SOURCE_PLATFORMDIRS
    if not home.is_absolute():
        home = (Path.cwd() / home).resolve()

    data_dir = home / "data"
    investigations_dir = home / "investigations"
    if database_url:
        database_path = resolve_database_path(database_url, data_dir=data_dir)
        source = _SOURCE_DATABASE_URL
    else:
        database_path = data_dir / "ghost.db"
        source = home_source

    return GhostLayout(
        home=home,
        data_dir=data_dir,
        investigations_dir=investigations_dir,
        database_path=database_path,
        source=source,
    )


def data_path_doctor_detail(environ: Mapping[str, str] | None = None) -> str:
    """Human-readable data path plus the source that won precedence."""
    env = _environ(environ)
    database_url = _env_value(env, "DATABASE_URL")
    if database_url:
        try:
            layout = resolve_layout(env)
        except ValueError as exc:
            return f"{exc} (DATABASE_URL)"
        return f"{layout.database_path} (DATABASE_URL)"
    layout = resolve_layout(env)
    return f"{layout.data_dir} ({layout.source})"


def _chmod(path: Path, mode: int) -> None:
    """Apply ``mode``. A mounted path we do not own must not abort startup."""
    try:
        os.chmod(path, mode)
    except OSError as exc:
        logger.warning("Could not set mode %o on %s: %s", mode, path, exc)


def ensure_private_dir(path: Path) -> None:
    """Create ``path`` and force mode 0700 (mkdir's mode is masked by umask)."""
    path.mkdir(parents=True, exist_ok=True)
    _chmod(path, DIR_MODE)


def ensure_private_home(path: Path) -> None:
    """Create the GHOST_HOME directory at mode 0700.

    A failed chmod, or a directory owned by someone else, is logged and does
    not abort startup. Importing config calls :func:`prepare_storage`, which
    calls this.
    """
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, DIR_MODE)
    except OSError as exc:
        logger.warning("Could not set mode 0700 on GHOST_HOME %s: %s", path, exc)
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        return
    try:
        owner = path.stat().st_uid
    except OSError as exc:
        logger.warning("Could not stat GHOST_HOME %s: %s", path, exc)
        return
    if owner != getuid():
        logger.warning("GHOST_HOME %s is not owned by the current user (uid %s)", path, getuid())


def restrict_db_file(path: Path) -> None:
    """Force an on-disk database file to mode 0600."""
    if str(path) == ":memory:" or not path.exists():
        return
    _chmod(path, DB_MODE)


def _backup_sqlite(legacy: Path, temporary: Path) -> None:
    """Consistent snapshot, including uncheckpointed WAL frames."""
    source = sqlite3.connect(legacy)
    try:
        target = sqlite3.connect(temporary)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def _copy_exclusive(temporary: Path, dest: Path) -> bool:
    """Copy ``temporary`` onto a new ``dest``. Never overwrite an existing file."""
    fd = -1
    created = False
    try:
        fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, DB_MODE)
        created = True
        with temporary.open("rb") as src, os.fdopen(fd, "wb") as out:
            fd = -1
            shutil.copyfileobj(src, out)
        return True
    except FileExistsError:
        return False
    except OSError as exc:
        logger.warning(
            "Could not migrate legacy Ghost database to %s (%s); left the original in place",
            dest,
            exc,
        )
        if created:
            dest.unlink(missing_ok=True)
        return False
    finally:
        if fd >= 0:
            os.close(fd)


def _install_backup(temporary: Path, dest: Path) -> bool:
    """Publish ``temporary`` as ``dest`` without overwriting.

    Hardlink when the filesystem allows it. Otherwise exclusive-create and
    copy. A failure is logged by the copy fallback and does not raise.
    """
    try:
        os.link(temporary, dest)
        return True
    except FileExistsError:
        return False
    except OSError:
        return _copy_exclusive(temporary, dest)


def migrate_legacy_database(
    dest: Path,
    *,
    database_url: str | None = None,
    legacy_path: Path | None = None,
) -> bool:
    """Copy the legacy in-package database to ``dest``.

    Uses the SQLite backup API so uncheckpointed WAL frames are included.
    Copies, never moves. Runs only when ``dest`` does not exist and
    ``DATABASE_URL`` is unset. Never overwrites. Leaves the old file in place
    and logs once when a copy is made. Backup or publish failures are logged
    and do not raise.
    """
    if database_url is None:
        database_url = os.environ.get("DATABASE_URL", "")
    if database_url.strip():
        return False

    legacy = LEGACY_DB_PATH if legacy_path is None else legacy_path
    if not legacy.is_file():
        return False
    try:
        if legacy.resolve() == dest.resolve():
            return False
    except OSError:
        return False
    if dest.exists():
        return False

    ensure_private_dir(dest.parent)
    temporary = dest.with_name(f".{dest.name}.migrating")
    published = False
    try:
        try:
            _backup_sqlite(legacy, temporary)
            os.chmod(temporary, DB_MODE)
            published = _install_backup(temporary, dest)
        except (OSError, sqlite3.Error) as exc:
            logger.warning(
                "Could not migrate legacy Ghost database from %s to %s: %s",
                legacy,
                dest,
                exc,
            )
            return False
    finally:
        temporary.unlink(missing_ok=True)

    if not published:
        return False

    os.chmod(dest, DB_MODE)
    logger.warning(
        "Copied legacy Ghost database from %s to %s; left the original in place",
        legacy,
        dest,
    )
    return True


def legacy_reports_warning() -> str | None:
    """Describe in-package investigation files that this migration does not copy."""
    legacy_dir = PACKAGE_DIR / "investigations"
    if not legacy_dir.is_dir():
        return None
    if not any(path.is_file() for path in legacy_dir.rglob("*")):
        return None
    return f"legacy reports remain in {legacy_dir} and were not migrated"


def relative_ghost_home_warning(environ: Mapping[str, str] | None = None) -> str | None:
    """Warn when GHOST_HOME is relative and therefore depends on the cwd."""
    raw = _env_value(_environ(environ), "GHOST_HOME")
    if not raw:
        return None
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return None
    return f"{raw} is relative and resolves against the current working directory ({Path.cwd()})"


def prepare_storage(environ: Mapping[str, str] | None = None) -> GhostLayout:
    """Create the private home tree and copy a legacy database when allowed.

    Importing :mod:`ghost.core.config` calls this as a side effect, before the
    database layer or CLI runs. Permission and migration failures are logged
    and do not raise.
    """
    layout = resolve_layout(environ)
    ensure_private_home(layout.home)
    ensure_private_dir(layout.data_dir)
    ensure_private_dir(layout.investigations_dir)
    if layout.source != _SOURCE_DATABASE_URL and str(layout.database_path) != ":memory:":
        env = _environ(environ)
        migrate_legacy_database(
            layout.database_path,
            database_url=env.get("DATABASE_URL", ""),
        )
    return layout


def mode_bits(path: Path) -> int:
    """Return the permission bits of ``path`` (the 0700/0600 portion)."""
    return stat.S_IMODE(path.stat().st_mode)
