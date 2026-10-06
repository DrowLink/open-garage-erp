# Open Garage ERP Roadmap

Each checkbox is scoped for one autonomous daily run. Work top-to-bottom within dependency constraints; parenthetical `depends:` references prerequisites in plain language.

## Daily Development Contract

> **After this multi-feature bootstrap MVP, complete exactly one checkbox per daily run.** The initial staged MVP is the one bootstrap exception. Pick the first dependency-ready unchecked item. Use strict vertical TDD and preserve RED then GREEN evidence. Run the full regression suite, lint, compile, security checks, and a realistic API smoke. Obtain independent staged-diff review before checking the item. Update README and relevant docs. Create one verified commit and push the current branch to `origin`. Never publish failed, unreviewed, secret-bearing, or misleading work. Report the item, commit SHA/message, test results, quality/security checks, review verdict, and push result.

## Foundation, security, and auth

- [x] Add injected settings with a safe local relative SQLite default.
- [x] Enable SQLite foreign-key enforcement on every connection.
- [x] Add one consistent JSON envelope for validation, HTTP, and route-not-found errors.
- [x] Add UTC creation and update timestamps to initial entities.
- [x] Add a health endpoint and human-facing root landing page.
- [x] Add isolated temporary-database pytest fixtures.
- [x] Pin Python dependencies and CI actions.
- [x] Introduce Alembic and generate the initial schema migration.
- [ ] Add a startup check that refuses malformed non-SQLite database URLs.
- [ ] Add password hashing primitives with Argon2id (depends: auth user model design).
- [ ] Add a shop-scoped user model and migration (depends: Alembic).
- [ ] Add session-token login and logout endpoints (depends: user model, password hashing).
- [ ] Add role definitions for owner, service advisor, technician, and accountant (depends: user model).
- [ ] Enforce role authorization on one protected test endpoint (depends: login, roles).
- [ ] Add configurable request-body size limits.
- [ ] Add API rate limiting for authentication endpoints (depends: login).

## Customers and vehicles

- [x] Create, list, and get customers with validated input.
- [x] Create, list, and get customer-linked vehicles.
- [x] Reject vehicle creation for an unknown customer.
- [ ] Add customer update with optimistic timestamp checks.
- [ ] Add customer archive without destructive deletion (depends: customer update).
- [ ] Add customer list pagination and stable cursors.
- [ ] Add customer search by normalized name, email, or phone.
- [ ] Add duplicate-customer warning rules.
- [ ] Normalize and validate VIN check digits.
- [ ] Add vehicle update with immutable ownership audit event (depends: audit events).
- [ ] Add vehicle odometer history entries.
- [ ] Add customer vehicle-history endpoint (depends: vehicle pagination).

## Appointments and intake

- [ ] Add appointment model and migration (depends: Alembic, customers, vehicles).
- [ ] Add appointment create endpoint with UTC start and duration.
- [ ] Reject overlapping appointments for the same service bay.
- [ ] Add appointment list filtered by date window.
- [ ] Add appointment reschedule endpoint with conflict validation.
- [ ] Add appointment cancellation reason.
- [ ] Add intake checklist template model.
- [ ] Add vehicle intake condition report with odometer.

## Estimates and work orders

- [x] Create, list, and get repair orders linked to vehicles.
- [x] Store and validate estimates as non-negative integer cents.
- [x] Define repair-order status enum and validated transition graph.
- [x] Return conflict errors for forbidden status transitions.
- [ ] Add estimate line items for labor, parts, fees, and discounts.
- [ ] Calculate estimate subtotal and total from line items.
- [ ] Add customer estimate approval token with expiration.
- [ ] Record immutable estimate approval timestamp and actor.
- [ ] Add repair-order concern, cause, and correction fields.
- [ ] Add repair-order technician assignment (depends: technician role).
- [ ] Add repair-order priority and promised-completion timestamp.
- [ ] Add repair-order change history feed.

## Labor and time

- [ ] Add labor operation catalog model (depends: Alembic).
- [ ] Add labor operation create and list endpoints.
- [ ] Attach quoted labor hours to estimate lines (depends: estimate line items).
- [ ] Add technician clock-in record for a repair order (depends: technician role).
- [ ] Add technician clock-out with duration calculation.
- [ ] Prevent overlapping open time entries per technician.
- [ ] Add manual time adjustment with reason and actor.
- [ ] Add billed-versus-actual labor variance endpoint.

## Inventory and purchasing

- [ ] Add inventory part and location models (depends: Alembic).
- [ ] Add part create, list, and get endpoints.
- [ ] Add append-only stock movement records.
- [ ] Calculate on-hand quantity from stock movements.
- [ ] Add low-stock threshold and query endpoint.
- [ ] Add vendor model and create/list endpoints.
- [ ] Add purchase order header and status model.
- [ ] Add purchase order line items linked to parts.
- [ ] Receive a purchase order into stock atomically.
- [ ] Reserve inventory for a repair-order line item (depends: estimate lines).

## Invoicing, payments, and accounting

- [ ] Add invoice model generated from an approved repair order.
- [ ] Snapshot invoice line descriptions, quantities, and integer-cent prices.
- [ ] Calculate invoice tax using explicit integer rounding rules.
- [ ] Add invoice finalize action that prevents further line edits.
- [ ] Add offline payment record with method and reference.
- [ ] Prevent payments exceeding invoice balance without explicit credit flow.
- [ ] Add refund record linked to an original payment.
- [ ] Add accounts-receivable aging summary.
- [ ] Add daily sales journal export as CSV.
- [ ] Add configurable chart-of-accounts mapping.

## CRM and communications

- [ ] Add customer communication preference fields.
- [ ] Record communication consent changes with timestamp and actor.
- [ ] Add reusable message template model.
- [ ] Add appointment reminder render preview (depends: appointments, templates).
- [ ] Add outbound message queue table.
- [ ] Add idempotent email delivery worker interface.
- [ ] Add repair-ready notification event (depends: completed repair status).
- [ ] Add customer follow-up task creation.

## Reporting

- [x] Add dashboard counts and repair-order estimate total.
- [ ] Add dashboard date-range filters.
- [ ] Add revenue summary from finalized invoices (depends: invoicing).
- [ ] Add labor utilization report (depends: technician time entries).
- [ ] Add parts margin report (depends: invoice and inventory lines).
- [ ] Add customer retention cohort report.
- [ ] Add repair-order cycle-time report.
- [ ] Add CSV export for one filtered report.

## Integrations

- [ ] Define versioned webhook event envelope.
- [ ] Add signed outbound webhook delivery.
- [ ] Add webhook retries with exponential backoff and dead-letter state.
- [ ] Add inbound webhook idempotency keys.
- [ ] Add accounting export adapter protocol.
- [ ] Add one sandbox accounting CSV adapter.
- [ ] Add parts-catalog provider adapter protocol.
- [ ] Add calendar iCalendar appointment export (depends: appointments).

## UI, PWA, and accessibility

- [x] Add an accessible basic HTML landing page linking to API docs.
- [ ] Add server-rendered application shell with navigation.
- [ ] Add responsive customer list page.
- [ ] Add customer detail page with vehicles.
- [ ] Add repair-order board grouped by status.
- [ ] Add keyboard-operable status transition controls.
- [ ] Add visible focus styles and skip navigation link.
- [ ] Add automated WCAG smoke checks for primary pages.
- [ ] Add web app manifest and install icons.
- [ ] Add read-only offline repair-order cache with clear stale indicator.

## Observability, DevOps, and docs

- [x] Add README quickstart, API examples, scope, and safety warning.
- [x] Add architecture notes and known-gap documentation.
- [x] Add MIT license, security policy, and contribution contract.
- [x] Add pinned GitHub Actions test, lint, and compile workflow.
- [ ] Add structured JSON request logging with correlation IDs.
- [ ] Add metrics endpoint protected from public exposure.
- [ ] Add database query timing instrumentation.
- [ ] Add startup readiness check that executes a database query.
- [ ] Add tested container image and non-root runtime user.
- [ ] Add Docker Compose development stack.
- [ ] Add dependency vulnerability scan to CI with a pinned tool version.
- [ ] Add OpenAPI snapshot regression test.
- [ ] Add deployment backup and restore runbook.
- [ ] Add release checklist and semantic version policy.
