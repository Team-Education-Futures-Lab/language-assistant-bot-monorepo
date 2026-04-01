# MBO Language Assistant Dashboard

Professional teacher dashboard for managing course materials and subjects.

## Features

- ✅ Create, Read, Update, Delete subjects
- ✅ Manage chunks (course material) per subject
- ✅ Real-time status updates
- ✅ Professional Tailwind CSS design
- ✅ Responsive sidebar navigation
- ✅ Bulk content management

## Setup

```bash
cd mbo-language-assistant-dashboard
npm install
npm start
```

Dashboard will open at `http://localhost:3000`

## Requirements

- Database Manager Service running on `http://localhost:5004`
- Node.js 14+
- npm or yarn

## API Integration

Connects to Database Manager Service endpoints:
- GET `/subjects` - List all subjects
- POST `/subjects` - Create subject
- PUT `/subjects/{id}` - Update subject
- DELETE `/subjects/{id}` - Delete subject
- GET `/subjects/{id}/chunks` - Get chunks
- POST `/subjects/{id}/chunks` - Add chunk
- DELETE `/chunks/{id}` - Delete chunk
