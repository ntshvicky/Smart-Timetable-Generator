# Smart Timetable Generator

Production-style MVP for school timetable generation from structured Excel data, natural-language rules, and manual timetable edits.

## What Is Built

- FastAPI backend with school/user auth and per-school data isolation.
- Normalized SQLAlchemy models for schools, users, academic years, classes, sections, subjects, teachers, mappings, availability, requirements, constraints, parse logs, uploads, timetables, and timetable entries.
- Excel template export and Excel upload/import with row-level validation.
- Gemini integration for natural-language rule parsing, with deterministic fallback when `GEMINI_API_KEY` is not set.
- Constraint-aware timetable generator with hard checks for teacher/class slot conflicts, teacher availability, eligible teacher mappings, break periods, and subject frequency allocation.
- Manual edit API and UI with conflict validation before saving.
- React + TypeScript admin UI for login/register, import, rule preview/approval, generation, class/teacher views, manual editing, and Excel export.
- Tests for Excel import, validation failure, generation success, impossible schedule, Gemini parser validation, availability conflicts, and manual edit conflicts.

## Practical Defaults

- MySQL is the local default for this workspace. SQLite also works by changing `DATABASE_URL` to `sqlite:///./smart_timetable.db`.
- The generated template uses `Class Subject Requirement` because Excel sheet names are limited to 31 characters. The importer also accepts `Class Subject Weekly Requirement` as an alias.
- Empty periods after all weekly requirements are satisfied are shown as `Free`, not conflicts.
- The scheduler relaxes soft “avoid consecutive subject” preferences before declaring a slot impossible.

## Architecture

```text
backend/app
  api/          FastAPI controllers
  core/         config, database, auth security
  models/       SQLAlchemy ORM models
  schemas/      Pydantic request/response contracts
  services/     auth, Excel, Gemini, scheduling business logic
  scripts/      demo helpers
frontend/src
  api/          typed REST client
  components/   timetable grid and edit modal
  pages/        admin workflow shell
```

## Excel Template

Sheets:

- `Classes`: `class_name`, `section_name`, `class_display_name`
- `Subjects`: `subject_code`, `subject_name`, `category`
- `Teachers`: `teacher_code`, `teacher_name`, `max_periods_per_day`, `max_consecutive_periods`
- `Teacher-Class-Subject Mapping`: `teacher_code`, `class_name`, `section_name`, `subject_code`
- `Teacher Availability`: `teacher_code`, `day`, `period_number`, `available_yes_no`
- `Class Subject Requirement`: `class_name`, `section_name`, `subject_code`, `periods_per_week`, `preferred_first_half`, `preferred_last_period`, `avoid_consecutive_yes_no`
- `School Settings`: `academic_year`, `working_days`, `periods_per_day`, `lunch_after_period`

## API Overview

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/data/template`
- `POST /api/data/upload`
- `GET /api/data/summary`
- `GET /api/data/masters`
- `POST /api/rules/parse`
- `POST /api/rules`
- `GET /api/rules`
- `POST /api/timetables/generate`
- `GET /api/timetables`
- `GET /api/timetables/{id}`
- `PUT /api/timetables/{id}/entries`
- `POST /api/timetables/{id}/validate`
- `GET /api/timetables/{id}/export`

## Run Locally

```bash
cp .env.example .env
./env/bin/python -m pip install -r backend/requirements.txt
MYSQL_PWD=<your-mysql-password> mysql -uroot -e "CREATE DATABASE IF NOT EXISTS smart_timetable_generator CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
PYTHONPATH=backend ./env/bin/uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Deploy On Vercel

The repo includes `vercel.json` and `api/index.py` so Vercel can build the React frontend and serve the FastAPI backend under `/api`.

For a real production deployment, configure these Vercel environment variables:

```bash
DATABASE_URL=<cloud MySQL/PostgreSQL URL reachable from Vercel>
JWT_SECRET=<strong random secret>
GEMINI_API_KEY=<optional Gemini key>
GEMINI_MODEL=gemini-1.5-flash
CORS_ORIGINS=https://<your-vercel-domain>
```

If `DATABASE_URL` is not configured on Vercel, the serverless backend falls back to SQLite in `/tmp`, which is suitable only for a temporary demo because serverless storage is not durable.

## Demo Flow

1. Register a school admin.
2. Download the Excel template from the Data section.
3. Upload the same template to import demo master data.
4. Parse a rule such as `Teacher Ravi is unavailable on Wednesday period 4`.
5. Approve parsed rules if desired.
6. Generate a timetable.
7. Filter by class or teacher, click a slot, edit it, and save.
8. Export the timetable to Excel.

## Gemini

Set `GEMINI_API_KEY` in `.env` to use Gemini. Without a key, the backend uses a deterministic fallback parser that returns the same validated internal schema:

```json
{
  "rule_type": "teacher_unavailable",
  "target_type": "teacher",
  "target_values": ["Ravi"],
  "day_scope": ["Wednesday"],
  "period_scope": [4],
  "priority": "hard",
  "parsed_description": "Teacher Ravi is unavailable on Wednesday period 4",
  "confidence_score": 0.75
}
```

## Test

```bash
PYTHONPATH=backend ./env/bin/python -m pytest backend/tests -q
cd frontend && npm run build
```

Note: this machine currently has Node.js `20.14.0`; Vite builds successfully but warns that it prefers Node `20.19+` or `22.12+`.
