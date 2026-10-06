# Open Garage ERP

Open Garage ERP is an early, API-first ERP foundation for automotive repair shops. The MVP tracks customers, their vehicles, repair orders, estimates in integer cents, workflow status, and high-level dashboard counts.

> **Status:** initial MVP with an Alembic-managed schema. Authentication, authorization, and production deployment hardening are roadmap work. Do not expose this version directly to the public internet.

## Quickstart

Requirements: Python 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn open_garage_erp.main:app --reload
```

Open <http://127.0.0.1:8000>, interactive docs at <http://127.0.0.1:8000/docs>, or `GET /health`.

The default database is the local relative file `./data/open-garage.db`. Override it with `OPEN_GARAGE_DATABASE_URL`. Startup fails fast when the value is not a valid SQLAlchemy URL or does not select SQLite; the MVP accepts only file-backed SQLite storage without URI query options. Run `uv run alembic upgrade head` before starting the app; application startup never creates or changes tables. Tests migrate and inject an isolated database under pytest's temporary directory; they never use the application default.

## API examples

```bash
# Customer
curl -sS -X POST http://127.0.0.1:8000/api/customers \
  -H 'content-type: application/json' \
  -d '{"name":"Ada Lovelace","email":"ada@example.com"}'

# Vehicle (replace customer_id as needed)
curl -sS -X POST http://127.0.0.1:8000/api/vehicles \
  -H 'content-type: application/json' \
  -d '{"customer_id":1,"year":2020,"make":"Honda","model":"Civic","vin":"1M8GDM9AXKP042788"}'

# Repair order; money is always integer cents
curl -sS -X POST http://127.0.0.1:8000/api/repair-orders \
  -H 'content-type: application/json' \
  -d '{"vehicle_id":1,"description":"Brake inspection","estimate_cents":12550}'

# Move through draft -> approved -> in_progress -> completed
curl -sS -X PATCH http://127.0.0.1:8000/api/repair-orders/1/status \
  -H 'content-type: application/json' -d '{"status":"approved"}'

curl -sS http://127.0.0.1:8000/api/dashboard/summary
```

Resource APIs support create, ordered list, and get-by-ID. Repair orders also support status updates. Errors share this shape:

```json
{"error":{"code":"not_found","message":"Customer 999 not found","details":null}}
```

## Development and verification

```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run python -m compileall -q src tests
uv run alembic upgrade head
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the daily one-item workflow, [ROADMAP.md](ROADMAP.md) for dependency-aware work, [docs/architecture.md](docs/architecture.md) for design decisions, and [SECURITY.md](SECURITY.md) for private reporting guidance.

## Scope and license

This release deliberately keeps one deployable service and SQLite storage. It has no auth, invoicing, inventory, or UI beyond the landing page and generated OpenAPI UI. Licensed under the [MIT License](LICENSE).
