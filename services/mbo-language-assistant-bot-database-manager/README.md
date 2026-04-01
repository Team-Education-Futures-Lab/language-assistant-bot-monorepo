# MBO Language Assistant - Database Manager Service

Flask-based REST service for managing subjects, course-material chunks, prompts, and system settings in Supabase.

This service is part of the MBO language assistant stack and is designed to:
- manage subject metadata
- ingest learning materials (TXT/PDF) and split them into chunks
- store and manage prompts used by LLM-facing services
- expose settings such as per-subject retrieval configuration

## Tech Stack

- Python 3.11
- Flask + Flask-CORS
- Supabase Python client
- python-dotenv
- pypdf

## Repository Structure

- database_manager.py: main Flask API service and endpoint definitions
- requirements.txt: Python dependencies
- Dockerfile: container build instructions
- models.py: SQLAlchemy model definitions (reference/legacy model layer)
- migrations/: SQL migrations for Supabase schema updates
- uploads/: temporary upload folder used during file processing
- .env: local environment variables (ignored by Git)
- .gitignore: excludes local secrets and machine artifacts

## Environment Variables

Create a .env file in the project root with at least:

```env
SERVICE_HOST=localhost
SERVICE_PORT=5004
LOG_LEVEL=INFO

SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=<your-supabase-key>
```

Notes:
- SUPABASE_KEY should be treated as secret.
- .env is included in .gitignore and should never be committed.

## Local Development

1. Create and activate a virtual environment

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows CMD
.venv\Scripts\activate.bat
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the service

```bash
python database_manager.py
```

Default base URL:

```text
http://localhost:5004
```

## Docker

Build image:

```bash
docker build -t mbo-db-manager .
```

Run container (explicit startup command):

```bash
docker run --rm -p 5004:5004 --env-file .env mbo-db-manager python database_manager.py
```

Note:
- The Dockerfile currently exposes port 5004 and installs dependencies, but does not define a default CMD.

## API Overview

Health:
- GET /health

Subjects:
- GET /subjects
- POST /subjects
- GET /subjects/{subject_id}
- PUT /subjects/{subject_id}
- DELETE /subjects/{subject_id}

Prompts (global):
- GET /prompts
- POST /prompts
- GET /prompts/{prompt_id}
- PUT/PATCH /prompts/{prompt_id}
- DELETE /prompts/{prompt_id}
- GET /prompts/active

Uploads and Chunks:
- POST /subjects/{subject_id}/upload
- DELETE /subjects/{subject_id}/uploads/{upload_name}
- GET /subjects/{subject_id}/chunks
- POST /subjects/{subject_id}/chunks
- POST /subjects/{subject_id}/chunks/bulk
- GET /chunks/{chunk_id}
- PUT /chunks/{chunk_id}
- DELETE /chunks/{chunk_id}

Settings:
- GET /settings
- POST /settings
- GET /settings/{key}
- DELETE /settings/{key}

## File Upload Behavior

- Supported extensions: txt, pdf, docx, doc
- Max file size: 50 MB
- Current extraction support:
  - txt: supported
  - pdf: supported
  - doc/docx: accepted by extension check, but text extraction currently returns no content

## Database and Migrations

Migrations are under migrations/.

Current migration file:
- 001_create_prompts_table.sql

To apply manually in Supabase:
1. Open Supabase SQL Editor.
2. Run SQL from migrations/001_create_prompts_table.sql.

## Security Notes

- Keep SUPABASE_KEY only in .env or secure runtime secret storage.
- Avoid logging secret values from request payloads or settings.
- Do not commit .env, local databases, or temporary uploads.

## Troubleshooting

- Supabase init fails:
  - Verify SUPABASE_URL and SUPABASE_KEY are present and valid.
- Upload fails with no extracted content:
  - Confirm file type is supported for extraction (TXT/PDF currently best supported).
- Port conflict on 5004:
  - Change SERVICE_PORT in .env and rerun.

## License

Add your preferred license for open-source or internal use.
