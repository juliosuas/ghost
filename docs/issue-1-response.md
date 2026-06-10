# GitHub issue #1 response draft

Thanks for calling this out. You are right: JSON-file persistence is not the right long-term storage model for an OSINT workspace that needs investigations, entities, relationships, provenance, and reports to remain auditable over time.

The current v2 branch moves Ghost in that direction instead of adding more collection modules first.

What changed:

- Ghost now treats SQLite as the supported v2 default storage layer.
- `DATABASE_URL` is configurable and resolves local SQLite paths explicitly.
- Unsupported database schemes now fail loudly instead of silently writing somewhere unexpected.
- The database has a schema version marker, indexes for common investigation/entity/finding lookups, and WAL/busy-timeout settings for local reliability.
- Investigations now store scope and authorized-use metadata so a case file can show why/under what authority it was created.
- Reports include provenance: generated timestamp, target metadata, modules run, source URLs, source URL count, module errors, and global errors.
- The CLI exposes saved case files with `ghost list` and `ghost show <id-or-prefix>` so persisted investigations are visible outside the web/API layer.
- Case files can now be exported, imported, and deleted from the CLI with `ghost export`, `ghost import`, and `ghost delete`.
- `ghost doctor --json` exposes machine-readable readiness checks for CI, cron, and future API startup checks without scraping terminal output.

Current local verification:

- `pytest -q`: 56 passed.
- `ruff check .`: passed.
- `ruff format --check .`: passed.
- `ghost doctor --json`: ok, 0 errors, 0 warnings.

Current position:

SQLite is the default for v2 because it is easy to run locally, works for single-user/self-audit workflows, and keeps the install lightweight. It also gives us queryable, durable investigations without forcing users to run infrastructure before they can try the product.

PostgreSQL is still the right roadmap direction for multi-user/team deployments, higher write concurrency, and hosted Ghost. I am keeping that behind a storage-adapter boundary rather than pretending it exists today.

What I am not claiming yet:

- Ghost does not have a production Postgres backend today.
- The storage adapter boundary still needs to be extracted and tested before Postgres support should be advertised.
- SQLite is the serious local default, not the final answer for team/hosted deployments.

Near-term storage roadmap:

1. Keep hardening SQLite case-file workflows.
2. Add signed report bundles and retention policies for teams.
3. Add a storage adapter interface.
4. Add Postgres support once the API/dashboard needs multi-user concurrency.

So the short answer is: agreed, JSON is not enough. v2 now uses SQLite as the serious local default, and Postgres is planned deliberately instead of as a half-shipped config flag.
