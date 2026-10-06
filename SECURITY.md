# Security Policy

## Supported versions

The project is pre-1.0. Security fixes are applied to the current `main` branch only.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. After the GitHub repository is published, use GitHub's **Report a vulnerability** form under the Security tab. Until private vulnerability reporting is enabled, contact the repository owner privately through their verified GitHub profile.

Include affected endpoints/version, reproduction steps, impact, and any suggested mitigation. Do not include real customer, vehicle, payment, or shop data. Maintainers should acknowledge a complete report within seven days and coordinate disclosure after a fix is available.

## Current security limits

The MVP has no authentication or authorization and is not suitable for direct internet exposure or real sensitive data. SQLite is intended for local/single-instance use. Operators must protect the host, database file, backups, and transport layer. See ROADMAP.md for planned auth, audit logging, rate limiting, dependency scanning, and production database support.
