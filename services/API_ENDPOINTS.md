# API Endpoints Documentation

## API Gateway (Port 5000)

The API Gateway is the central entry point for all client requests. It routes requests to appropriate services based on the input type.

### Base URL
```
http://localhost:5000
```

---

## Health & Status Endpoints

### 1. Basic Health Check
```
GET /
```

**Description**: Simple health check endpoint

**Response:**
```json
{
  "status": "ok",
  "message": "API Gateway is running",
  "services": {
    "text_service": "http://localhost:5001",
    "speech_service": "http://localhost:5002"
  }
}
```

**Status Code**: 200

---

### 2. Detailed Health Check
```
GET /health
```

**Description**: Comprehensive health status of API Gateway and all connected services

**Response (All Healthy):**
```json
{
  "status": "healthy",
  "gateway": {
    "host": "localhost",
    "port": 5000
  },
  "services": {
    "text_service": {
      "status": "healthy",
      "url": "http://localhost:5001"
    },
    "speech_service": {
      "status": "healthy",
      "url": "http://localhost:5002"
    }
  }
}
```

**Response (Service Down):**
```json
{
  "status": "degraded",
  "gateway": {
    "host": "localhost",
    "port": 5000
  },
  "services": {
    "text_service": {
      "status": "unreachable",
      "url": "http://localhost:5001",
      "error": "Connection refused"
    },
    "speech_service": {
      "status": "healthy",
      "url": "http://localhost:5002"
    }
  }
}
```

**Status Codes**:
- `200`: All services healthy
- `503`: One or more services unavailable

---

## Query Endpoints

### 3. Text Query Endpoint
```
POST /api/query/text
```

**Description**: Submit a text-based question and get an answer

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "question": "What is photosynthesis?",
  "enable_tts": false
}
```

**Parameters:**
- `question` (required, string): The question to ask
- `enable_tts` (optional, boolean): Whether to generate audio response (default: false)

**Response (Success):**
```json
{
  "status": "success",
  "question": "What is photosynthesis?",
  "answer": "Photosynthesis is the process by which plants convert light energy into chemical energy...",
  "context_found": true,
  "sources": ["biology.txt", "science.txt"],
  "service": "Text Input Service"
}
```

**Response (Error - No Context):**
```json
{
  "status": "success",
  "question": "What is photosynthesis?",
  "answer": "I cannot find an answer to your question based on the provided materials.",
  "context_found": false,
  "sources": []
}
```

**Response (Error - Service Unavailable):**
```json
{
  "status": "error",
  "message": "Could not connect to Text Service at http://localhost:5001. Is it running?"
}
```

**Status Codes:**
- `200`: Success
- `400`: Bad request (missing question field)
- `503`: Text Service unavailable
- `504`: Request timeout

---

### 4. Speech Query Endpoint
```
POST /api/query/speech
```

**Description**: Submit an audio file with a question and get a text/audio response

**Headers:**
```
Content-Type: multipart/form-data
```

**Form Data:**
- `audio` (required, file): Audio file (WAV, MP3, OGG, FLAC, etc.)
- `enable_tts` (optional, string): "true" or "false" - whether to return audio response (default: "true")

**Example (cURL):**
```bash
curl -X POST http://localhost:5000/api/query/speech \
  -F "audio=@/path/to/audio.wav" \
  -F "enable_tts=false"
```

**Response (Success):**
```json
{
  "status": "success",
  "user_question": "What is photosynthesis?",
  "answer": "Photosynthesis is the process by which plants convert light energy into chemical energy...",
  "audio_available": false,
  "service": "Speech Input Service"
}
```

**Response (With Audio):**
```json
{
  "status": "success",
  "user_question": "What is photosynthesis?",
  "answer": "Photosynthesis is...",
  "audio_available": true,
  "audio": "UklGRiYAAABXQVZFZm10IBAAAA..."  // Base64 encoded WAV audio
}
```

**Status Codes:**
- `200`: Success
- `400`: Missing audio file or transcription failed
- `503`: Speech Service unavailable
- `504`: Request timeout

---

### 5. Unified Query Endpoint
```
POST /api/query
```

**Description**: Single endpoint that accepts both text and speech queries. Auto-detects based on Content-Type.

**For Text Queries:**
```
Content-Type: application/json

{
  "question": "Your question here",
  "enable_tts": false
}
```

**For Speech Queries:**
```
Content-Type: multipart/form-data

- audio: Audio file
- enable_tts: true or false
```

**Example (Text - cURL):**
```bash
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is photosynthesis?", "enable_tts": false}'
```

**Example (Speech - cURL):**
```bash
curl -X POST http://localhost:5000/api/query \
  -F "audio=@audio.wav" \
  -F "enable_tts=false"
```

**Responses**: Same as text or speech endpoints depending on input type

---

## Text Input Service (Port 5001)

### Base URL
```
http://localhost:5001
```

### 6. Health Check
```
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "service": "Text Input Service",
  "api_running": true,
  "database_connected": true,
  "service_host": "localhost",
  "service_port": 5001,
  "ollama_url": "http://localhost:11434/api/generate",
  "database_url": "postgresql://localhost:5432/schooldb"
}
```

### 7. Query Endpoint
```
POST /query
```

**Request:**
```json
{
  "question": "What is photosynthesis?",
  "enable_tts": false
}
```

**Response:**
```json
{
  "status": "success",
  "question": "What is photosynthesis?",
  "answer": "...",
  "context_found": true,
  "sources": ["biology.txt"],
  "tts_enabled": false,
  "service": "Text Input Service"
}
```

---

## Speech Input Service (Port 5002)

### Base URL
```
http://localhost:5002
```

### 8. Health Check
```
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "service": "Speech Input Service",
  "dependencies": {
    "text_service": {
      "url": "http://localhost:5001",
      "status": "healthy"
    },
    "ollama": {
      "url": "http://localhost:11434/api/generate",
      "status": "healthy"
    }
  },
  "service_host": "localhost",
  "service_port": 5002
}
```

### 9. Transcribe Audio
```
POST /transcribe
```

**Headers:**
```
Content-Type: multipart/form-data
```

**Form Data:**
- `audio` (required, file): Audio file to transcribe

**Response:**
```json
{
  "status": "success",
  "text": "What is photosynthesis?",
  "confidence": "high",
  "service": "Speech Input Service"
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Speech could not be understood"
}
```

### 10. Text to Speech
```
POST /synthesize
```

**Headers:**
```
Content-Type: application/json
```

**Request:**
```json
{
  "text": "This is the answer to your question."
}
```

**Response:**
Audio file in WAV format with headers:
```
Content-Type: audio/wav
Content-Disposition: attachment; filename=response.wav
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Error converting text to speech: ..."
}
```

### 11. Speech Query
```
POST /query
```

**Headers:**
```
Content-Type: multipart/form-data
```

**Form Data:**
- `audio` (required, file): Audio file with question
- `enable_tts` (optional, string): "true" or "false"

**Response:**
```json
{
  "status": "success",
  "user_question": "What is photosynthesis?",
  "answer": "Photosynthesis is the process...",
  "audio_available": false,
  "service": "Speech Input Service"
}
```

---

## Error Responses

### Common Error Formats

**400 Bad Request:**
```json
{
  "status": "error",
  "message": "Missing 'question' field in request body"
}
```

**404 Not Found:**
```json
{
  "status": "error",
  "message": "Endpoint not found"
}
```

**500 Internal Server Error:**
```json
{
  "status": "error",
  "message": "Internal server error"
}
```

**503 Service Unavailable:**
```json
{
  "status": "error",
  "message": "Could not connect to Text Service at http://localhost:5001. Is it running?"
}
```

**504 Gateway Timeout:**
```json
{
  "status": "error",
  "message": "Text Service request timed out"
}
```

---

## Rate Limits & Timeouts

- **Request Timeout**: 60 seconds for all queries
- **Audio File Size**: Max 100MB (configurable)
- **Response Time**: Typically 2-10 seconds for Ollama responses

---

## Testing APIs with Postman/Insomnia

### Import Collection

1. Create new request
2. Set method to POST
3. Set URL to desired endpoint
4. Add headers and body as shown above
5. Click "Send"

### Example Requests

**Text Query in Postman:**
```
POST http://localhost:5000/api/query/text
Headers: Content-Type: application/json
Body (raw, JSON):
{
  "question": "What is photosynthesis?",
  "enable_tts": false
}
```

**Speech Query in Postman:**
```
POST http://localhost:5000/api/query/speech
Headers: (auto-set by Postman)
Body (form-data):
  audio: [select audio.wav file]
  enable_tts: false
```

---

## Troubleshooting API Calls

### Service Not Responding
1. Check service is running: `curl http://localhost:SERVICE_PORT/health`
2. Verify port is not in use: `netstat -ano | findstr :SERVICE_PORT`
3. Check service logs for errors

### Timeout Errors
1. Ensure Ollama is running: `ollama serve`
2. Check network connectivity
3. Increase timeout if on slow network

### Invalid JSON Response
1. Check Content-Type header matches request format
2. Verify request body is valid JSON
3. Check service logs for parsing errors

---

## Rate Limiting (Future Implementation)

To avoid service overload:
- Implement rate limiting: 10 requests/minute per IP
- Queue long-running requests
- Add request prioritization

See rate-limiting branch for implementation.
