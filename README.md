# Student Showcase Platform

A full-stack platform for students to showcase their projects, built with Django and React.

## Tech Stack

- **Backend:** Django 5.2 + Django REST Framework
- **Database:** PostgreSQL
- **Auth:** JWT (djangorestframework-simplejwt) + GitHub OAuth (django-allauth)
- **Caching / Task Queue:** Redis (via Memurai on Windows) + Celery + Celery Beat
- **Object Storage:** MinIO (S3-compatible, local) — private bucket for user/project media, public-read bucket for static site hosting
- **Frontend:** React (Vite) + Tailwind CSS v4 + shadcn/ui (Base UI, Nova preset) + TanStack Query + react-router-dom

## Project Structure

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js + npm
- PostgreSQL installed and running
- MinIO server (local S3-compatible storage) — see [Object Storage Setup](#object-storage-setup)
- Redis-compatible server (Memurai on Windows) — see [Redis / Celery Setup](#redis--celery-setup)
- A GitHub OAuth App (for GitHub login) — see [GitHub OAuth Setup](#github-oauth-setup)
- A GitHub Personal Access Token (for GitHub metadata sync) — see [GitHub Metadata Sync](#github-metadata-sync)

### 1. Clone the repository

```bash
git clone <repo-url>
cd "Student Showcase platform"
```

### 2. Create and activate virtual environment

```bash
python -m venv myvenv
myvenv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up PostgreSQL database

Open pgAdmin 4 or psql and create the database:

```sql
CREATE DATABASE showcase_db;
```

### 5. Create `.env` file

Create a `.env` file in the project root with the following:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=showcase_db
DB_USER=postgres
DB_PASSWORD=your-postgres-password
DB_HOST=localhost
DB_PORT=5432
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_ACCESS_TOKEN=your-github-personal-access-token
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=student-showcase-media
MINIO_DEMOS_BUCKET_NAME=student-showcase-demos
MINIO_ENDPOINT_URL=http://127.0.0.1:9000
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Create superuser (optional)

```bash
python manage.py createsuperuser
```

### 8. Run the development server

```bash
python manage.py runserver
```

Visit `http://localhost:8000/` in your browser.

> **Note:** Use `localhost:8000`, not `127.0.0.1:8000`, when testing GitHub login — the OAuth callback URL is registered against `localhost` on GitHub's side.

### GitHub OAuth Setup

1. Go to [GitHub Developer Settings → OAuth Apps](https://github.com/settings/developers) and register a new OAuth App:
   - **Homepage URL:** `http://localhost:8000`
   - **Authorization callback URL:** `http://localhost:8000/accounts/github/login/callback/`
2. Copy the generated **Client ID** and **Client Secret** into `.env`.
3. In Django Admin (`/admin/`):
   - Go to **Sites** and set the domain to `localhost:8000`, and confirm `SITE_ID` in `settings.py` matches this site's ID.
   - Go to **Social Applications → Add**, select provider **GitHub**, paste the Client ID/Secret, and add `localhost:8000` under **Chosen sites**.
4. Test the flow at: `http://localhost:8000/accounts/github/login/`

### Object Storage Setup

Local development uses [MinIO](https://min.io) as an S3-compatible storage backend (no cloud account required).

1. Download MinIO Server: `https://dl.min.io/server/minio/release/windows-amd64/minio.exe`
2. Start the server:
   ```bash
   minio.exe server D:\minio\data --console-address ":9001"
   ```
3. Open the console at `http://127.0.0.1:9001` (default login: `minioadmin` / `minioadmin`).
4. Create two buckets:
   - `student-showcase-media` — **private**. Holds avatars, cover images, screenshots, and demo files. Accessed only via short-lived signed URLs.
   - `student-showcase-demos` — **public-read**. Holds deployed static-site files (`demos/{project_slug}/...`), served directly without signing.
5. To set the demos bucket to public-read, download MinIO Client (`https://dl.min.io/client/mc/release/windows-amd64/mc.exe`) and run:
   ```bash
   mc.exe alias set myminio http://127.0.0.1:9000 minioadmin minioadmin
   mc.exe anonymous set download myminio/student-showcase-demos
   ```

> In production, swap MinIO for AWS S3 or Cloudflare R2, and attach a CDN (CloudFront / Cloudflare) in front of the public bucket for global caching.

### Redis / Celery Setup

Local development uses [Memurai](https://www.memurai.com) as a Redis-compatible server on Windows.

1. Install Memurai (default port `6379`).
2. Verify it's running: `memurai-cli.exe ping` → should return `PONG`.
3. Redis database `0` is used for Celery (broker + result backend); database `1` is used for Django's cache.
4. Run the Celery worker and beat scheduler in separate terminals:
   ```bash
   celery -A core worker -l info --pool=solo
   celery -A core beat -l info
   ```
   (`--pool=solo` is required on Windows.)

### GitHub Metadata Sync

1. Generate a GitHub Personal Access Token at `https://github.com/settings/tokens` (scope: `public_repo`).
2. Add it to `.env` as `GITHUB_ACCESS_TOKEN`.
3. `sync_all_approved_projects` runs automatically every 6 hours via Celery Beat, syncing stars/forks/language/README for every approved project with a GitHub URL. It can also be triggered manually from the Django shell:
   ```python
   from github_integration.tasks import sync_all_approved_projects
   sync_all_approved_projects.delay()
   ```

### 9. Frontend setup

The React frontend lives in a separate `frontend/` folder.

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173/` in your browser. The backend must be running at `http://localhost:8000` (CORS is configured to allow `http://localhost:5173`).

## Data Model

- **Category** — a single category per project (e.g. "Web Development"), auto-generated slug.
- **Tag** — reusable tech-stack labels (e.g. "React", "Django"), many-to-many with projects.
- **Project** — owner (FK to User), title, slug, description, category, tech_stack, github_url, live_demo_url, cover_image, demo_file (single-file live demo), static_site_url (auto-hosted static site link), status (`draft` / `submitted` / `approved` / `rejected`), rejection_reason, views_count, likes_count, timestamps.
- **ProjectScreenshot** — one-to-many additional images per project, automatically watermarked (student username + timestamp) via a background Celery task after upload.
- **Like** — one row per (project, user) pair, enforced unique — powers the like/unlike toggle.
- **Comment** — project comments; text is sanitized with `bleach` on save to strip any HTML/XSS payloads.
- **SourceSnippet** — small, view-only code snippets attached to a project (filename, language, text content) — never a full repo download.
- **GitHubMeta** — one-to-one with Project; stores stars, forks, primary language, last commit date, and a cached/sanitized README (raw markdown + rendered HTML), refreshed periodically by Celery.

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|--------------|
| POST | `/api/auth/register/` | Register a new user (username, email, password, role) |
| POST | `/api/auth/login/` | Log in with username/password — returns `access` + `refresh` JWT tokens |
| POST | `/api/auth/refresh/` | Exchange a valid `refresh` token for a new `access` token |
| GET | `/accounts/github/login/` | Start GitHub OAuth login flow |

### Profile

| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | `/api/users/me/` | Get the logged-in user's profile |
| PATCH | `/api/users/me/` | Update the logged-in user's profile (`avatar`, `bio`, `batch`, `github_username`) |

### Projects

| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | `/api/projects/` | List projects. Supports `?search=`, `?category=`, `?tech_stack=`, `?batch=`, `?ordering=-likes_count`/`-views_count`/`-created_at`, and pagination (`?page=`). Results are cached for 60s. |
| POST | `/api/projects/` | Create a new project (owner set automatically, starts as `draft`) |
| GET | `/api/projects/{slug}/` | Full project detail if authenticated; a limited public-safe subset (title, category, cover_image) if not |
| PATCH | `/api/projects/{slug}/` | Update a project — owner only |
| DELETE | `/api/projects/{slug}/` | Delete a project — owner only |
| POST | `/api/projects/{slug}/screenshots/` | Upload one or more screenshots (`images` field, repeatable) — owner only. Each is watermarked in the background. |
| POST | `/api/projects/{slug}/submit/` | Move a project from `draft` to `submitted` — owner only |
| POST | `/api/projects/{slug}/approve/` | Approve a `submitted` project — instructor/admin only |
| POST | `/api/projects/{slug}/reject/` | Reject a `submitted` project with a `reason` — instructor/admin only |
| POST | `/api/projects/{slug}/like/` | Toggle like/unlike for the current user |
| GET | `/api/projects/{slug}/demo-url/` | Get a short-lived (5 min) signed URL for the project's `demo_file`. Restricted to allowed origins (see below). |
| POST | `/api/projects/{slug}/static-site/` | Upload a `.zip` of a static site (HTML/CSS/JS); deployed asynchronously to the public demos bucket — owner only |
| GET | `/api/projects/{slug}/static-site-url/` | Get the permanent public URL of the deployed static site |
| GET | `/api/projects/{slug}/github-meta/` | Get cached GitHub stars/forks/language and sanitized README (raw + HTML) |
| GET | `/api/projects/{slug}/source-preview/` | List view-only source code snippets for a project |

### Comments

| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | `/api/projects/{slug}/comment/` | List comments for a project |
| POST | `/api/projects/{slug}/comment/` | Add a comment (sanitized against XSS) |
| DELETE | `/api/projects/{slug}/comments/{comment_id}/` | Delete a comment — comment author or admin/instructor only |

**Authenticated requests** must include the header:
```
Authorization: Bearer <access_token>
```

**Validation rules:**
- Avatar: JPG/PNG only, max 2MB.
- Project screenshots: JPG/PNG/WEBP, max 5MB each — multiple files upload independently, so one invalid file doesn't block the rest.
- `github_url` must match `https://github.com/<user>/<repo>`.
- `live_demo_url` must start with `http://` or `https://`.
- Static site upload must be a `.zip`, max 20MB.
- Status transitions are enforced: only `draft` → `submitted`, and only `submitted` → `approved`/`rejected`.
- Comment text is sanitized (all HTML tags stripped) before saving.

### Admin

| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | `/admin/` | Django admin panel (superuser login) |

## Permissions

- `IsAuthenticatedOrReadOnly` — anyone can view projects; only logged-in users can create/modify.
- `IsOwnerOrReadOnly` — only a project's owner can update or delete it.
- `IsInstructorOrAdmin` — only users with role `instructor` or `admin` can approve/reject submissions.
- `PublicProjectSerializer` vs `ProjectDetailSerializer` — unauthenticated requests to a project's detail endpoint only ever receive a minimal, safe field set.
- `DemoOriginValidationMiddleware` — the `demo-url` endpoint only accepts requests with an `Origin`/`Referer` from an allowed list (`DEMO_ALLOWED_ORIGINS` in settings), blocking cross-site embedding while still allowing direct API tool testing.

## Background Tasks (Celery)

| Task | Trigger | Purpose |
|------|---------|---------|
| `watermark_screenshot` | On screenshot upload | Overlays student username + timestamp onto the uploaded image |
| `sync_github_meta` | Manually, or via `sync_all_approved_projects` | Fetches stars/forks/language/README for one project from the GitHub API |
| `sync_all_approved_projects` | Every 6 hours (Celery Beat) | Queues `sync_github_meta` for every approved project with a GitHub URL |
| `deploy_static_site` | On static site ZIP upload | Extracts the ZIP and uploads each file to the public demos bucket at `demos/{project_slug}/...` |

## Frontend

The React app (`frontend/`) covers:

- **Explore page** (`/`) — a responsive project grid (1 column mobile, 3 desktop) with a debounced search box and a sticky filter sidebar (category, tech stack), backed by TanStack Query.
- **Project Detail page** (`/projects/:slug`) — a hero section (cover image, title, owner, like button) plus four tabs:
  - **Overview** — markdown-rendered project description (`react-markdown`)
  - **Live Demo** — an iframe loading the project's signed demo URL
  - **GitHub** — stars/forks/language and the sanitized README preview
  - **Comments** — comment list plus a form to add new comments
- **Login / Register pages** — placeholders, to be wired up to the JWT auth endpoints.

## Testing

All endpoints above have been tested and verified working via Postman:
- Register → creates a new user
- Login → returns valid `access`/`refresh` tokens
- Profile GET/PATCH → returns and updates profile data, including avatar file upload
- GitHub OAuth → full authorize flow tested in-browser; new users are created automatically on first GitHub login
- Project CRUD → create, list, detail, update all tested, with ownership enforced (non-owners get `403`)
- Multi-image screenshot upload → multiple files accepted in one request, invalid files reported without blocking valid ones; watermarking confirmed visible in uploaded images
- Wizard-style creation → project created with minimal fields, then updated incrementally (links, media) before final submit
- Status workflow → full `draft → submitted → approved`/`rejected` cycle tested, with role-based permission enforced on approve/reject
- Likes/comments → toggle and XSS-sanitization tested
- Search/filters/ordering/pagination → tested individually and combined
- GitHub metadata sync → `fetch_repo_meta`/`fetch_repo_readme` and both Celery tasks tested end-to-end
- Auth-gated project detail, signed demo URLs, origin validation, watermarking, and view-only source preview → all tested individually and together
- Static site auto-hosting → ZIP upload, background deploy, and public URL serving HTML/CSS/JS all tested end-to-end
- Frontend Explore → Project Detail flow → tested with live backend data

## Week Checkpoints

- **Week 1** — Auth system complete: register, login, JWT refresh, GitHub OAuth, and profile update all working end to end.
- **Week 2** — A project can go from `draft` all the way to `approved` through the full workflow: create → add screenshots → submit → instructor approve.
- **Week 3** — Likes, comments, search, filters, pagination, and caching all working together on the projects list.
- **Week 4** — Project detail API returns GitHub metadata and cached/rendered README content.
- **Week 5** — Full "layered protection" model functional: auth gate, signed URLs, origin validation, watermarking, and view-only source preview.
- **Week 6** — End-to-end frontend flow (Explore → Project Detail, live demo, GitHub tab, comments) working against the real backend.

## License

This project is for academic purposes.