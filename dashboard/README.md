# MBO Language Assistant Dashboard

Admin dashboard for managing subjects, chunks, prompts, and runtime settings.

## Current Architecture

- Frontend calls the API gateway only (`/api/query/*`).
- Gateway proxies requests to database-manager/realtime services.
- Sidebar branding now uses `yonder_logo.png` with label `Dashboard`.
- Browser tab icon also uses `yonder_logo.png`.

## Features

- Subjects CRUD
- Chunk management (create/delete/upload)
- Prompt management
- Runtime settings management
- Gateway health check on startup

## Environment Variables

Use `.env.example` as template.

```env
PORT_FOR_DEVELOPMENT=3001
REACT_APP_API_BASE_URL=http://localhost:5000
```

## Local Development

```bash
npm install
npm start
```

Default URL: `http://localhost:3001`

## Build

```bash
npm run build
```

## Required Gateway Endpoints

- `GET /api/query/health`
- `GET/POST /api/query/subjects`
- `GET/PUT/DELETE /api/query/subjects/{id}`
- `POST /api/query/subjects/{id}/upload`
- `DELETE /api/query/subjects/{id}/uploads/{upload_name}`
- `GET/POST /api/query/subjects/{id}/chunks`
- `GET/PUT/DELETE /api/query/chunks/{id}`
- `GET/POST /api/query/prompts`
- `GET/PUT/DELETE /api/query/prompts/{id}`
- `GET/POST /api/query/settings`
- `GET/PUT/PATCH/DELETE /api/query/settings/{key}`

## Notes

- This dashboard should point to the gateway URL, not directly to database-manager.
- If API URL is missing, `src/api.js` throws a clear configuration error.
