# Ghost storage adapter boundary

Ghost v2 currently supports SQLite as the durable local case-file store. PostgreSQL is a roadmap item for hosted and team deployments, but it should not be advertised as supported until the storage boundary below exists in code and tests.

## Authorized-use position

Storage work must preserve Ghost's defensive OSINT posture:

- Every investigation record keeps `authorized_use` and `scope`.
- Export/import flows do not strip provenance, errors, module metadata, or authorization context.
- New adapters must not introduce silent fallbacks that write case data to a different backend than the operator configured.
- Tests and demos should use synthetic or explicitly authorized targets.

## Adapter contract

A production storage adapter must support these operations before Ghost claims a non-SQLite backend:

- `init()`: create or migrate schema with an explicit schema version marker.
- `save_investigation(investigation)`: persist the complete investigation, findings, graph entities, relationships, errors, scope, and authorization metadata.
- `get_investigation(id)`: fetch a complete case file by exact investigation ID.
- `list_investigations(limit, offset)`: return newest-first case summaries without loading every finding.
- `get_graph_data(id)`: return graph nodes and links for the dashboard/API.
- `delete_investigation(id)`: delete an investigation and all dependent rows atomically.

## Non-negotiable behavior

- Unsupported `DATABASE_URL` schemes fail loudly during startup or doctor checks.
- Writes are transactional: partial case files are not acceptable.
- Deletes cascade to findings, entities, and relationships.
- Common lookup paths are indexed: investigation target, status, created/start time, finding investigation ID, entity investigation ID, and relationship investigation ID.
- `ghost doctor --json` reports backend readiness without scraping human terminal output.

## Operator verification gate

Before a demo, deployment, or release candidate, run:

```bash
ghost doctor --json
```

The `database` check is the source of truth for storage readiness. A configured
SQLite URL must resolve to the exact local database path Ghost will initialize
and write to. A non-SQLite URL must return a hard database error until a real
adapter implementation and contract test suite exist.

Do not treat a successful default SQLite doctor run as evidence that a custom
`DATABASE_URL` is supported. The configured URL itself must pass the doctor
check, otherwise Ghost could appear healthy while writing case data somewhere
other than the operator intended.

## PostgreSQL readiness checklist

PostgreSQL remains `PENDING` until all of these are true:

- Storage functions are behind an interface with SQLite and Postgres implementations.
- Contract tests run against SQLite and Postgres using the same fixtures.
- CI has a Postgres service job or a documented local integration gate.
- Migration/version handling is explicit for both adapters.
- README and roadmap distinguish "SQLite supported" from "Postgres supported" without ambiguity.
