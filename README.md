# AgriGuide-Backend

Comprehensive README for the AgriGuide-Backend Django project. This document covers repository layout, environment variables, local development, running the app with WSGI (Waitress), tests, and deployment notes.

## Repository overview

- `manage.py` — Django project management entrypoint.
- `requirements.txt` — Python dependencies for the project.
- `backend_ai/` — Django project settings and WSGI/ASGI entrypoints.
  - `settings.py` — main configuration (loads `.env` via `python-dotenv`).
  - `wsgi.py` / `asgi.py` — deployment entrypoints.
- `agriguide_ai/` — main Django app containing models, views, serializers and business logic.
  - `models.py` — custom `User` model and application models (Chat, Community, Tutorials, etc.).
  - `views.py`, `auth_views.py`, `community_views.py`, `lms_views.py`, `twofa_views.py`, `notification_views.py`, `ai_tip_views.py` — API endpoints and handlers.
  - `prompts.py` — AI prompt utilities.
  - `storage_backends.py` — custom storage classes (S3-backed when configured).
  - `serializers.py` — DRF serializers.
  - `tests.py` — test cases for the app.
- `templates/` — Django templates (landing and mobile fallbacks).
- `logs/` — application logs (created at runtime if missing).
- `.env` — local environment variables (not intended to be checked into production/shared repos).

## Important files to inspect

- `backend_ai/settings.py` — review for environment variables, AWS / Gemini / Microsoft configuration, DEBUG behavior, and static/media settings.
- `agriguide_ai/models.py` — database schema and custom user model.
- `agriguide_ai/views.py` — chat endpoints using Google/Generative AI and streaming SSE implementation.

## Environment variables

Configuration is loaded from a `.env` file in the project root (via `dotenv.load_dotenv`). Key variables used across the project include:

- `SECRET_KEY` — Django secret key. Keep secret in production.
- `DEBUG` — `True` for development, `False` in production.
- `DATABASE_URL` — full DB connection string (used by `dj-database-url`).
- Microsoft / Email (2FA): `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_DEFAULT_SENDER`.
- AWS S3: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`.
- AI: `GEMINI_API_KEY` (used by `google-generativeai` package).
- `SECURE_SSL_REDIRECT` — can be set to `True` or `False` to force HTTPS (note: when `DEBUG=True` the project disables SSL cookie/security flags by default in `settings.py`).

Example `.env` (DO NOT commit real secrets):

```env
SECRET_KEY=your_secret_key_here
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
GEMINI_API_KEY=your_gemini_api_key_here
# MICROSOFT_*, AWS_* as required in production
```

The repository already contains a `.env` file template with placeholders — replace with real values when deploying.

## Setup (local development)

1. Create and activate a Python virtual environment (recommended):

```powershell
python -m venv ./virtualenv
./virtualenv/Scripts/Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Prepare `.env` (copy example or update existing `.env`) and ensure `DEBUG=True` for local testing.

4. Run database migrations:

```powershell
python manage.py migrate
```

5. (Optional) Create a superuser:

```powershell
python manage.py createsuperuser
```

6. Start the Django development server (HTTP):

```powershell
python manage.py runserver 0.0.0.0:8000
```

Note: If you see errors about HTTPS ("You're accessing the development server over HTTPS, but it only supports HTTP"), that means the client is trying to connect via `https://127.0.0.1`. Use `http://localhost:8000` or update your frontend to use `http://localhost:8000` instead of `https://127.0.0.1`.

## Running with WSGI (production-like local host)

This repo includes simple wrappers to run Waitress, a production-quality WSGI server that works on Windows.

- `run-wsgi.ps1` — PowerShell wrapper; prefers `./virtualenv` if present.
- `run-wsgi.bat` — Windows batch wrapper.

Examples:

PowerShell:

```powershell
./run-wsgi.ps1
```

CMD:

```
run-wsgi.bat
```

Direct command (activated virtualenv):

```powershell
"./virtualenv/Scripts/waitress-serve.exe" --port=8000 backend_ai.wsgi:application
# or
python -m waitress --port=8000 backend_ai.wsgi:application
```

The server will bind to `0.0.0.0:8000` by default. Use `--port` to change.

## HTTPS / Local testing

If you require HTTPS on localhost for development/testing (e.g., mobile webview that enforces HTTPS), use one of the options:

- Use `ngrok` to provide an HTTPS public endpoint that tunnels to your local server:

```powershell
ngrok http 8000
```

- Generate self-signed certificates and run a HTTPS-capable server (scripts for generating certs were added in the repository: `generate_ssl_certs.py` and `runserver_https.py`). Note that browsers will show a warning for self-signed certs unless you add them to your OS trust store.

## Static & media files

- By default, static files served via WhiteNoise (`whitenoise`) in `settings.py`.
- Media file storage uses local filesystem when AWS S3 credentials are not provided. If `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_STORAGE_BUCKET_NAME` are set, the project uses `django-storages` with S3.

## AI Integration

- The project uses `google-generativeai` (Gemini) and expects `GEMINI_API_KEY` to be set in the environment.
- Chat endpoints in `agriguide_ai/views.py` stream responses and maintain conversation history in the database.

## Email (Microsoft Graph)

- Office 365 / Microsoft Graph credentials are read from env vars: `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`.

## Running tests

Run Django tests with:

```powershell
python manage.py test
```

Note: Some tests may require network access or environment variables (Gemini API, AWS) — run in an environment configured for tests or mock external services.

## Deployment notes

- In production set `DEBUG=False` and configure `ALLOWED_HOSTS` appropriately (see `backend_ai/settings.py`).
- Configure `DATABASE_URL` to point to a managed DB (Postgres, etc.).
- Add `GEMINI_API_KEY`, Microsoft credentials, and AWS credentials to your environment or secrets manager.
- Configure HTTPS (TLS) at the load balancer or web server (nginx, cloud provider) rather than in-Django for best security.

## Common troubleshooting

- HTTPS handshake / "Bad request version" errors: these appear when the client attempts TLS/HTTPS to an HTTP-only server. Ensure your frontend is using `http://localhost:8000` in development, or set up TLS.
- Missing env vars: `settings.py` will warn and raise for critical missing variables when `DEBUG=False`.
- Static/media errors: confirm S3 credentials or ensure `MEDIA_ROOT` exists for local storage.

## Where to look next in the codebase

- `backend_ai/settings.py` — configuration, environment variables, security flags
- `agriguide_ai/models.py` — DB models and relationships
- `agriguide_ai/views.py` — main API endpoints; chat streaming and AI integration
- `agriguide_ai/storage_backends.py` — custom storage backends for S3/local

---

If you'd like, I can:

- Add a `Makefile` or PowerShell script that sets up the venv and runs migrations.
- Add CI config (GitHub Actions) to run tests.
- Generate a minimal `.env.example` file with placeholders.

Tell me which of the above you want next and I will implement it.
"# AgriGuide-Backend" 
