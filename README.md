# Tarun Tomar · Personal Portfolio

A real, server-rendered portfolio application: HTML/Jinja2, CSS, vanilla JavaScript,
Flask, SQLAlchemy, PostgreSQL, Gunicorn, and S3-compatible persistent object storage.
No frontend framework, build pipeline, external font service, or client-side database.
Lucide icons are vendored locally with their license.

## What you receive

- Eight public pages plus project/article detail pages, custom error pages, and SEO files.
- Database-backed project search, category/technology filters, sorting, pagination, featured projects.
- Session-authenticated admin studio; project, category, skills, education, experience,
  achievements and article CRUD; profile/photo/resume editing; contact inbox.
- Draft isolation, safe plain-text rich case-study sections, galleries, image previews,
  confirmation dialogs, image ordering and alt text, optional external links.
- Light/dark themes, mobile navigation, reduced-motion support and visible keyboard focus.
- Real migrations, tests, GitHub Actions, Render Blueprint and optional local Docker services.

**Not a claim of live deployment.** This package runs locally. A live Render URL,
real S3 credentials, GitHub connection, domain and production smoke checks require
configuration in your own accounts. Google Sites screenshots were not provided;
the initial visual design follows the written brief, not a verified recreation.

No invented projects, employment, certifications, metrics or achievements are seeded.
Starter skills reflect supplied interests, not asserted proficiency. Review them in admin.
Education dates deliberately read “Dates to be added.” Social URLs/email start empty;
add them through Profile & resume. There is no fake photo or fake resume.

## 1. Local setup (Python 3.12)

Unzip, open a terminal in the `portfolio` directory, then:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell alternative: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env
# Windows: Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the generated random value into SECRET_KEY in `.env`.
Development-only fallback: keep `DATABASE_URL=sqlite:///portfolio.db` and
`STORAGE_BACKEND=local`. SQLite and local files live in the ignored `instance/`
directory. They are never valid production storage in this application.

```bash
flask --app app:create_app db upgrade
flask --app app:create_app seed-content
flask --app app:create_app create-admin
flask --app app:create_app run --debug
```

The CLI prompts for email and a confirmed password (at least 14 characters).
Use a unique password stored in a password manager. There is no default admin,
no public registration, and no automatic admin creation on application boot.
Open http://127.0.0.1:5000 and http://127.0.0.1:5000/admin/login.
Debug is for local development only; production explicitly disables it.

`seed-content` is an explicit initial-setup command, **not part of each deployment**.
It adds missing starter groups when empty; running it after intentionally deleting
all skills/education will recreate those starter entries. It does not overwrite edits.

### PostgreSQL for local development

Use an existing PostgreSQL instance or the optional compose file:

```bash
export LOCAL_POSTGRES_PASSWORD='choose-a-local-password'
docker compose up -d
```

PowerShell: `$env:LOCAL_POSTGRES_PASSWORD='choose-a-local-password'`.
Set `.env` DATABASE_URL to
`postgresql://portfolio:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:5432/portfolio`.
Set `RATELIMIT_STORAGE_URI=redis://127.0.0.1:6379/0` if desired.
Run `db upgrade`, `seed-content`, and `create-admin` against that database.
Switching database URLs does **not** move SQLite data to PostgreSQL. Initialize
PostgreSQL directly for real content, or perform a separately reviewed data migration.
Never run `docker compose down -v` if you need to retain the database volume.

## 2. Architecture and folder map

```text
app.py                app factory, security policy, errors, admin CLI
wsgi.py               Gunicorn entry point
config.py             environment configuration, PostgreSQL URL normalization
extensions.py         db, migrations, CSRF, sessions, rate limiter
models.py             typed relational models and constraints
services.py           validation, queries, serialization
storage.py            image/PDF validation, optimization, local/S3 adapter
seed.py               supplied profile and editable starter content only
routes/
  main.py             public Jinja pages, media authorization, SEO
  projects.py         public read-only APIs
  admin.py            protected admin pages and CRUD APIs
  contact.py          contact submission, honeypot, rate limits
 templates/           base, partials, individual public pages, admin pages
 static/
  css/                tokens, public styles, responsive rules, animation, admin
  js/                 ES modules, filters, contact, theme, image previews
  vendor/             local Lucide bundle and license
 migrations/          committed initial Alembic revision
 tests/               route, auth, CSRF, validation, CRUD and storage tests
 render.yaml          web + PostgreSQL + shared Key Value rate limiter
```

### Schema and relationships

- AdminUser: unique email, scrypt hash, timestamps; no public registration.
- Project: unique indexed slug; indexed draft/published status; case-study fields,
  URLs, featured flag, display order, timestamps, optional category and thumbnail.
- Technology ↔ Project: normalized many-to-many association; no free-form SQL.
- ProjectCategory: editable unique category name and order; deleting a category
  makes its projects uncategorized rather than deleting projects.
- ProjectImage → Project and Asset: ordered gallery with editable alt text;
  deleting a project deletes its gallery rows, not shared asset blobs immediately.
- Asset: random storage key, generated safe filename, MIME type, bytes, purpose.
- Profile (id=1): editable identity, about/goals/contact/SEO text and photo/resume refs.
- Skill, Education, Experience, Achievement: independent ordered entries, editable
  descriptions and proficiency labels without invented numeric ratings.
- BlogPost: unique slug, summary/body, category, JSON tags, publication timestamp,
  optional thumbnail and draft/published check constraint.
- ContactMessage: submitted fields, UTC timestamps, read/archive flags.

All normal content editing is database-driven. No source edits are needed to
publish a project. Site-wide CSS customization is available in `static/css/tokens.css`.
The hero's editorial “Finding meaning in the data” copy and generic explanatory
labels are design copy; personal headline, introduction and biography remain editable.

## 3. Admin workflow

1. Sign in at `/admin/login`; counts and recently updated projects appear on Overview.
2. Open Categories and add or rename categories; lower display order comes first.
3. Create a project: title, stable unique slug, short description are required.
   Fill in optional problem/objectives/workflow/results and external links.
4. Upload a thumbnail/gallery if available. Add alt text after the first save;
   existing gallery IDs can be reordered in the editor. Remove images explicitly.
5. Save as Draft, review privately through the admin editor, then set Published.
   Public pages and APIs never expose drafts or their unreferenced images.
6. Feature a published project to include it on the homepage. The first three
   published featured projects appear in display order (then newest first).
7. Edit later: cards and detail content are updated from the same database row.
   Changing a slug changes the public URL; old-slug redirects are not implemented.
8. Delete requires both a browser confirmation and a server-side confirmation value.
9. Profile & resume controls biography, name/headline, photo, PDF and social links.
   Other sidebar sections support adding, editing, reordering, and removing entries.
10. Articles have draft/published states. Blog and project bodies are **plain text**
    with preserved line breaks, not arbitrary HTML or a WYSIWYG editor.
11. Inbox supports read, archive/unarchive and confirmed deletion. Times are UTC.

Uploaded resume PDFs download as attachments (no unsafe embedded PDF execution).
The resume page remains informative without a PDF. No automated SMTP notifications
are included; every valid contact message is saved and visible in the inbox.

## 4. Persistent production uploads (required)

Render's normal service filesystem is ephemeral. PostgreSQL stores structured
content and media metadata; an **external private S3-compatible bucket** stores
all image and resume bytes. Web service redeployments do not own either store.
Do not put permanent uploads in `static/`, the Git repository, or a temporary disk.

1. Create a private AWS S3 bucket (or compatible provider such as Cloudflare R2).
2. Enable encryption/versioning and establish a backup/retention policy appropriate
   for your content. For AWS, block public access. Do not make drafts publicly readable.
3. Create a bucket-scoped service identity; use this least-privilege policy, replacing
   `YOUR_BUCKET`. No `s3:*` or account-wide access is needed:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
    "Resource": "arn:aws:s3:::YOUR_BUCKET/portfolio/*"
  }]
}
```

4. Set the storage environment variables described below. AWS can leave endpoint
   URL empty; R2 uses its S3 API endpoint and usually `S3_REGION=auto`.
5. Files upload through authenticated Flask requests, not directly from frontend JS.
   Browser CORS settings are not needed for this server-mediated upload flow.
6. Images must decode as JPG/PNG/WebP, are size/pixel limited, re-encoded as WebP,
   stripped of metadata, and bounded to 1800px. SVG/HTML uploads are rejected.
7. PDFs are header/parser checked, must be unencrypted, and known document actions
   are rejected. PDFs are attachment downloads; **this is not an antivirus scanner**.
   Only upload trusted documents; add a malware scanner if your threat model needs it.
8. A `/media/<id>` request checks public ownership or admin authentication, then
   issues a five-minute signed GET URL. Stable database asset IDs are stored, never
   expiring URLs. A signed URL already issued can remain usable until it expires
   after unpublishing. Disable credential access or remove the object if immediate
   revocation is essential.
9. Replacing/removing a reference hides it publicly; unreferenced assets can be
   inspected and cleaned after 24 hours:

```bash
flask --app app:create_app cleanup-assets
flask --app app:create_app cleanup-assets --apply
```

Use the second command only after reviewing the first. Failed requests attempt
blob cleanup. A process crash between object upload and DB commit can leave an
orphan object without an Asset row: periodically reconcile bucket keys to Asset
records or use provider inventory. Do not configure blanket age-based deletion of
all objects, which would delete still-referenced content.

Limits: each file at most 10 MB, entire multipart request at most 16 MB, gallery at
most 20 images. Save galleries in multiple edits if needed. Old files in a former
local-development configuration are not automatically uploaded to S3.

## 5. Environment variables

| Variable | Development | Production |
|---|---|---|
| APP_ENV | `development` | `production` |
| SECRET_KEY | random persistent key | required, random 32+ chars; use 64 hex chars |
| DATABASE_URL | SQLite fallback or PostgreSQL | Render PostgreSQL internal connection string |
| SITE_URL | http://127.0.0.1:5000 | real HTTPS canonical origin, no trailing slash |
| TRUST_PROXY | `false` | `true` only behind Render's trusted proxy |
| STORAGE_BACKEND | `local` or `s3` | **s3** required |
| S3_BUCKET | when using S3 | private bucket name |
| S3_REGION | `us-east-1` default | actual region or compatible provider value |
| S3_ENDPOINT_URL | blank for AWS | blank for AWS; full endpoint for R2/compatible |
| S3_ACCESS_KEY_ID | when using S3 | bucket-scoped credential |
| S3_SECRET_ACCESS_KEY | when using S3 | secret credential |
| RATELIMIT_STORAGE_URI | `memory://` | Redis/Valkey `redis://` or `rediss://` connection |

Admin credentials are provisioned through CLI, not environment variables or source.
`ADMIN_EMAIL`, `ADMIN_PASSWORD`, SMTP and generic upload-configuration blobs are
not read by this app. Explicit, documented storage keys above replace those generic
placeholders. Never place database, S3, Redis or session secrets in frontend files.
Redis stores rate-limit counters only, not messages or portfolio content.

## 6. Deploy to Render — exact manual workflow

Official deployment reference: https://render.com/docs/deploy-flask

### A. Put the code in GitHub

Create a new empty private or public repository in GitHub. From **inside portfolio/**:

```bash
git init
git add .
git status                 # confirm .env and instance/ are NOT staged
git commit -m "Build Flask portfolio"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Use GitHub authentication/SSH as appropriate. Do not put credentials in the remote URL.
If you commit the enclosing directory instead, set Render Root Directory to `portfolio`.

### B. Create persistent services and object storage

1. In Render, create a **PostgreSQL** database. Select a suitable current plan/region,
   note its database name and internal connection string, and use the same region as web.
2. Create a Render **Key Value** instance (Redis-compatible) for shared rate limits.
   Keep internal access restricted; obtain its internal connection URL.
3. Create/configure the private S3 bucket and service credentials from section 4.
   Do not assume creating the web service creates these storage services.

### C. Create the web service

1. New → Web Service → connect your GitHub repository/branch.
2. Runtime: Python. Root directory: blank if app files are at repository root.
3. Build command: `pip install -r requirements.txt`
4. Pre-deploy command: `flask --app app:create_app db upgrade`
5. Start command:
   `gunicorn --workers 2 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT wsgi:app`
6. Health check: `/healthz`. This performs a database `SELECT 1` (not an S3/Redis probe).
7. Add all production variables in section 5 through Render's Environment settings.
   Use its PostgreSQL/Key Value **internal** URLs. The app normalizes postgres:// and
   postgresql:// to psycopg 3. Do not use a SQLite URL in production.
8. Set SITE_URL to the assigned `https://YOUR_SERVICE.onrender.com` URL (update after
   initial service creation if necessary). Configure trusted proxy only on Render.
9. Deploy and inspect logs. The committed migration runs before Gunicorn starts.
   If your selected service does not support a pre-deploy command, run migration in
   its supported one-off job/shell before serving traffic; do not call `db.create_all`
   on every worker startup. Choose a service with Shell access for the CLI workflow.

### D. Initialize content and the first admin

After the migration succeeds, use the Render service **Shell**:

```bash
flask --app app:create_app db current
flask --app app:create_app seed-content
flask --app app:create_app create-admin
```

Enter your real email and unique password at the secure prompts. Do not paste it
into source code or command arguments. Run this once, not on every deployment.
If needed: `flask --app app:create_app reset-admin-password`.
Rotate SECRET_KEY to invalidate all active sessions after a credential compromise.

### E. Verify the live service

1. Open `/healthz`; confirm 200 and `{"status":"ok"}`.
2. Open every public page and `/does-not-exist` (must return 404).
3. Verify unauthenticated `/api/admin/projects` returns 401; `/admin` redirects to login.
4. Log in, edit profile, upload your actual photo and resume, and add real social links.
5. Create a draft project with a unique slug and image. Public APIs must not show it;
   its detail page and image should return 404 to a separate signed-out browser.
6. Publish and feature it. Verify listing, search/category/technology filters,
   project details, thumbnail, gallery, homepage and resume attachment download.
7. Submit a contact message; verify Inbox, timestamp, read/archive/delete behavior.
8. Redeploy the **same** web service without deleting the database or bucket.
9. Verify project/contact/profile rows and image/resume downloads still work.
10. Test 360, 768, 1024 and 1440px, mobile navigation, dark/light persistence, keyboard
    navigation and reduced-motion preference. Review logs for 500s.
11. When using a custom domain, update SITE_URL and confirm canonical/sitemap URLs.
    Enable platform TLS, define database backups and monitor service errors.

### Blueprint alternative

`render.yaml` describes the web service, a PostgreSQL database and shared Key Value
rate limiter. In Render choose **New → Blueprint**, connect the repo, review plan
availability/region and provide the S3 and SITE_URL prompted values. Leave the S3
endpoint blank for AWS. The Blueprint does not create your S3 bucket or admin account.
After deployment, perform steps D and E. Render's plan IDs/features can evolve;
validate the Blueprint in the current dashboard before applying.

Blueprint reference: https://render.com/docs/blueprint-spec
Filesystem reference: https://render.com/docs/disks
S3 signing reference: https://docs.aws.amazon.com/boto3/latest/guide/s3-presigned-urls.html

## 7. API contract

Responses use `{"data": ...}` or `{"error":{"code":422,"message":"..."}}`.
Contact/auth operations return a `message`. Lists return pagination metadata.
Public APIs expose only published content. Public mutations do not exist except
contact submission and login/logout. Every admin operation checks session auth.

| Method | Endpoint | Access / purpose |
|---|---|---|
| GET | /api/home, /api/profile, /api/skills, /api/categories | public content |
| GET | /api/projects | published, `q`, `category` (ID), `technology` (name), `sort`, `page` |
| GET | /api/projects/{slug} | published details |
| GET | /api/blog, /api/blog/{slug} | published notes; `q`, `category`, `page` |
| POST | /api/contact | CSRF + validation + honeypot + rate limits |
| GET | /api/auth/session | session state + CSRF token, no password data |
| POST | /api/auth/login, /api/auth/logout | session authentication |
| GET, POST | /api/admin/projects | authenticated paginated list / create |
| GET, PATCH, DELETE | /api/admin/projects/{id} | authenticated detail / edit / confirmed delete |
| GET, PATCH, POST | /api/admin/profile | authenticated profile + multipart uploads |
| GET, POST | /api/admin/content/{resource} | skills, education, experience, achievements, categories |
| PATCH, DELETE | /api/admin/content/{resource}/{id} | authenticated edit/order/delete |
| GET, POST | /api/admin/blog | paginated articles / create |
| GET, PATCH, DELETE | /api/admin/blog/{id} | article detail / edit / publish / delete |
| GET | /api/admin/messages | authenticated paginated inbox |
| PATCH, DELETE | /api/admin/messages/{id} | read/archive / confirmed delete |

Publish/unpublish with `PATCH {"status":"published"}` / `{"status":"draft"}`.
Feature/unfeature with `PATCH {"featured":true}` / false. All deletes require
`{"confirm":"delete"}`; the UI additionally uses an explicit confirmation dialog.
Optional project properties remain optional; required: title, slug, short_description.
Technologies accept a JSON array or comma-separated multipart field. `images` can
be repeated multipart file fields. `remove_image_ids` and `image_order` accept an
array or comma-separated IDs. Use `image_alt_<ID>` to update existing alt text.
HTTP: 201 create, 200 read/update, 204 delete, 400 CSRF/malformed JSON, 401 auth,
404 missing/unpublished, 409 uniqueness conflict, 413 request size, 422 validation,
429 rate limit, 500 unexpected failure, 503 unhealthy database.

### Session + CSRF example

A same-origin browser client first fetches `/api/auth/session` with credentials.
It sends the returned token in `X-CSRFToken` for login. Fetch a **new token** after
login because the session is rotated, then use it for every POST/PATCH/DELETE.
Do not disable CSRF to make an API client work. This is a same-origin, session API,
not an anonymous cross-origin API. Flask's HTTPS CSRF referrer checks remain enabled.

```javascript
let session = await fetch('/api/auth/session').then(r => r.json());
await fetch('/api/auth/login', {
  method: 'POST', credentials: 'same-origin',
  headers: {'Content-Type':'application/json', 'X-CSRFToken':session.csrf_token},
  body: JSON.stringify({email: YOUR_EMAIL, password: YOUR_PASSWORD})
});
session = await fetch('/api/auth/session').then(r => r.json());
// Use session.csrf_token in subsequent authenticated mutations.
```

Rate limits: login 5/minute + 30/hour (per source IP, per endpoint), contact
2/minute + 5/hour; global limit 300/minute. Multiple users on a shared IP share
these quotas. Production requires shared Redis so Gunicorn workers cannot each
keep independent counters. No password or message body is intentionally logged.

## 8. Migrations and updates

Never edit the applied initial migration to evolve a deployed database.

```bash
# In development after editing models.py:
flask --app app:create_app db migrate -m "Describe schema change"
# Inspect the generated revision, test on a copy, commit it, then:
flask --app app:create_app db upgrade
```

Back up production PostgreSQL before schema changes. Application and database
rollback are distinct operations; do not blindly downgrade destructive migrations.
Assets have their own bucket backup/version policy. Never put secrets in migrations.

## 9. Testing

```bash
pip install -r requirements-dev.txt
pytest -q
# PostgreSQL tests DESTROY all portfolio model tables in this disposable DB:
TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost/portfolio_test' pytest -q
```

The test fixture refuses a database name without “test”, but this is not a substitute
for using a separate database. Do not point tests at production. SQLite tests use
isolated temporary files; PostgreSQL tests run against your supplied disposable DB.
CSRF remains enabled in tests. Browser smoke script:

```bash
python -m playwright install chromium
# Start the app separately, then run public/responsive browser checks:
python tests/browser_smoke.py --base-url http://127.0.0.1:5000 --output artifacts/browser
```

Browser screenshots/report go to ignored `artifacts/`. The browser script checks
public navigation/404, no overflow at required widths, mobile menu, theme
persistence, reduced motion, keyboard focus, and actual AJAX contact submission.
Use it against a disposable local environment: it submits a clearly marked test message.
Do not claim live Render redeployment/persistence is verified by local tests.
See `QA_REPORT.md` for the exact checks executed with this delivery.

## 10. Troubleshooting

| Symptom | Action |
|---|---|
| Build cannot find requirements | Confirm repo root/Render Root Directory; build from portfolio/ |
| Gunicorn module not found | Use `wsgi:app`; set root directory correctly |
| Database connection refused | Check internal URL, region, database availability, password encoding |
| `No module named psycopg2` | Install requirements; URL is normalized to psycopg 3 by config.py |
| Missing relation / profile table | Run `db upgrade` against the SAME DATABASE_URL as the web service |
| DB starts but empty content | Run `seed-content` once; configure real content through admin |
| CSRF expired / 400 | Reload; use fresh token after login; ensure stable SECRET_KEY and correct HTTPS origin/referrer |
| Session keeps logging out | Check stable key, HTTPS cookies, trusted proxy; changing network/browser can invalidate strong sessions |
| Media 404 | Check publication/reference status, object key and Asset row; drafts are intentionally private |
| S3 AccessDenied | Check bucket name/region/endpoint and Get/Put/DeleteObject permission for portfolio/* |
| Signature mismatch | Correct endpoint/region, credential pair and system clock; don't persist expiring signed URLs |
| Upload 413 | Request limit 16 MB; upload gallery in multiple saves |
| Upload 422 | Check real file format/pixel limit/PDF actions; renaming a file does not make it valid |
| Project 409 | Use a unique lowercase slug; existing rows keep their slugs |
| Feature not on homepage | Must be published and featured; only first three by display order appear |
| 429 on login/contact | Wait for quota reset; check trusted source IP forwarding |
| Rate limiter connection failure | Check shared Key Value URL, network access and service availability |
| Content lost after deployment | Confirm same PostgreSQL URL and bucket; don't recreate/delete backing services |

## 11. Security and operational boundaries

- Scrypt password hashing, session rotation on login, HTTPOnly/SameSite cookies,
  secure production cookies, CSRF including JSON APIs, input bounds, URL validation,
  ORM queries, autoescaped templates, strict same-origin script CSP, no public writes
  to portfolio content, authorization on media, and production startup guards.
- ProxyFix trusts exactly one proxy hop only when explicitly enabled. Do not enable
  it for a directly internet-exposed standalone server with untrusted forwarded headers.
- Image files are decoded/re-encoded; no path from an uploaded filename is used.
- Public text supports literal text, not executable HTML. External links use safe
  schemes, and links opening new tabs use noopener/noreferrer.
- No audit log, MFA, CAPTCHA, antivirus service, SMTP notifications, full-text search
  engine, WYSIWYG editor, old-slug redirects or asynchronous job queue are included.
  Add these deliberately as requirements grow; don't mistake them for implemented features.
- Health checks probe DB connectivity only. Add independent external storage/Redis
  monitoring and backups. This delivery is not an independent penetration test.
- Before public launch, enter actual personal assets, inspect content, configure
  secrets and storage, test live redeployment, and review platform logs/backups.
