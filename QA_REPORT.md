# Quality assurance report — 2026-10-23

## Executed successfully

| Verification | Result |
|---|---|
| Python test suite, isolated SQLite development database | 70 passed |
| Same suite, actual local PostgreSQL 16 database | 70 passed |
| Initial Alembic migration, SQLite and actual local PostgreSQL | Applied successfully |
| Chromium browser checks | 40 recorded checks passed |
| Public page layout matrix | 8 pages × 4 widths (360, 768, 1024, 1440px), no horizontal overflow |
| Admin browser layout matrix | 6 admin pages × 4 widths, no horizontal overflow |
| Browser runtime | No unexpected JavaScript or console errors |
| Dependency compatibility | pip check: no broken requirements |

See `tests/results/sqlite.txt`, `tests/results/postgres.txt`, and
`tests/results/browser-report.json` for actual recorded output. Screenshots in the
sibling `preview/` directory show the running local application, not design mockups.

## Coverage

Automated tests keep CSRF enabled and exercise public routes, protected pages and
APIs, valid/invalid login, logout, password hashing, initial admin CLI, rate limits,
project create/update/delete, duplicate slug conflicts, drafts, publication,
featured homepage display, search/category/technology filters, sorting/pagination,
SQL wildcard escaping and injection-shaped input, escaped XSS-shaped content,
profile/ordered-content CRUD, category deletion, blog draft/publish/delete, contact
validation/honeypot/inbox archive/read/delete, image validation/optimization,
private draft media, gallery removal, failed-upload cleanup, PDF attachment
validation/removal, S3 adapter behavior, security headers, 404s and production
configuration guards. A fresh application instance was checked against the same
stored data/uploads to test local application-restart persistence.

Browser automation additionally checks real navigation and mobile hamburger use,
theme persistence, AJAX project search, contact form submission, keyboard skip
link, reduced motion, admin sign-in, creation, publish, feature, edit, cancellation
of deletion, confirmed deletion, and logout. Browser-created projects were removed.
Test database files, test admin accounts, passwords, temporary uploads, logs with
request details and local environment secrets are not bundled in the source ZIP.
CI-only fixture credentials remain clearly marked in tests/workflow configuration.

## Boundaries — not verified and not claimed

- No live GitHub repository was created and no service was deployed to Render.
- No real AWS S3/R2 bucket was accessed. S3 put/sign operations were tested with a
  mocked adapter; production credential permissions, upload, signing and downloads
  still require the documented live checks in your account.
- Real Render redeployment and persistence across that redeployment were not tested.
  Local database/app-restart tests are not evidence of a completed cloud deployment.
- No independent security audit, penetration test, antivirus scan or assistive-
  technology certification was performed. Browser coverage uses Chromium, not
  separate Safari/Firefox/device-lab runs.
- SMTP notifications, MFA, a WYSIWYG editor, CAPTCHA, audit logs and old-slug redirects
  are not implemented; the optional email feature is not needed for stored messages.
- Google Sites screenshots and personal assets were not supplied. Styling follows
  the brief; personal content still needs review, actual resume/photo/social links,
  education dates, and your real published projects.

Follow README sections 4–6 before calling the site production-ready. Never use
pytest's destructive test database fixture against production.
