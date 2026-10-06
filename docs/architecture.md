# Architecture

## Shape

Open Garage ERP is a modular monolith: one FastAPI process, SQLAlchemy 2 ORM models, Pydantic request/response schemas, and SQLite for the initial local deployment. `create_app(settings)` is the composition root and permits isolated test configuration.

```text
HTTP client -> FastAPI routes/errors -> Pydantic validation
                                  -> SQLAlchemy Session -> SQLite
```

## Decisions

- **Application factory:** settings and database URL are injected before tables are created. Tests therefore use a unique temporary SQLite file.
- **Persistence:** SQLAlchemy 2 typed declarative models and short request-scoped sessions. Startup parses and validates the configured database URL before engine creation, rejecting malformed URLs and non-SQLite dialects. SQLite `PRAGMA foreign_keys=ON` is installed for every engine connection. Alembic owns versioned schema changes; `uv run alembic upgrade head` applies the initial migration.
- **Money:** estimates are non-negative integers in cents, avoiding binary floating-point ambiguity.
- **Time:** models store UTC timestamps; API serialization emits ISO 8601 with `Z`.
- **Workflow:** repair order status is a closed API enum. Allowed edges are `draft -> approved|cancelled`, `approved -> in_progress|cancelled`, and `in_progress -> completed|cancelled`; terminal states have no outgoing edges.
- **Errors:** API errors use `{ "error": { "code", "message", "details" } }`, including validation and unknown routes.
- **Boundaries:** customer, vehicle, and repair-order behavior is currently routed in the composition module to keep the MVP legible. Split domain routers/services when update operations or migrations make that separation valuable.

## Data model

- Customer 1—N Vehicle (`vehicles.customer_id`, restricted deletion)
- Vehicle 1—N RepairOrder (`repair_orders.vehicle_id`, restricted deletion)

Tables carry integer primary keys plus `created_at` and `updated_at`. VIN is optional and unique when provided. Repair order description and estimate are a frozen snapshot for this MVP.

## Known gaps

There is no authentication/authorization, concurrency control, audit event stream, pagination, or production database adapter yet. The dashboard performs aggregate queries directly. These are explicit roadmap items rather than hidden claims.
