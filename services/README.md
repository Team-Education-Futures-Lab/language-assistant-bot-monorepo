# Microservices Architecture - ChatBot Application

## Overview

The ChatBot application now uses a **microservices architecture** with the following components:

```
┌────────────────────────────────────────────────────────────────────────────┐
│    Frontend (React - Port 3000) │ Dashboard (Port 3001)                    │
│  (mbo-language-assistant-chatbot)│ (Future Management Interface)           │
└────────────────┬────────────────┼─────────────────────────────────────────┘
                 │                │
                 ▼                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│              API Gateway (Port 5000) - Central Backend                     │
│         Routes requests to appropriate microservices                        │
└────────────────┬────────────────┬─────────────────────┬──────────────────┤┐
            ┌────▼──┐     ┌───────▼──┐     ┌──────────▼─┐     ┌────────────▼─┐
            │ Text  │     │ Speech   │     │ Retrieve   │     │  Database    │
              │ 5001  │     │ 5002     │     │ 5003       │     │ Manager 5004 │
              └───────┘     └──────────┘     └────────────┘     └──────┬───────┘
                │
                └───────────────┐
                       ▼
                   ┌────────────────┐
                   │ Realtime Voice │
                   │ 5005           │
                   └────────────────┘
                                                                      │
        ┌─────────────────────────────────────────────────────────────┘
        │
        ▼
    ┌─────────────────────────────────────────────────┐
    │  Supabase PostgreSQL (Remote)                   │
    │  with pgvector + Course Materials               │
    │  Subjects | Chunked Content                     │
    └─────────────────────────────────────────────────┘
```

## Architecture Components

### 1. **API Gateway** (Central Backend)
- **Port**: 5000
- **Location**: `/services/api-gateway/api_gateway.py`
- **Purpose**: Acts as the single entry point for all client requests
- **Responsibilities**:
  - Routes text queries to Text Input Service
  - Routes speech queries to Speech Input Service
  - Health checks for all services
  - Error handling and request validation

### 2. **Text Input Service**
- **Port**: 5001
- **Location**: `/services/mbo-language-assistant-bot-text-input-service/text_service.py`
- **Purpose**: Processes text-based queries
- **Responsibilities**:
  - Retrieves context from PostgreSQL vector database
  - Sends queries to Ollama LLM
  - Returns text-based answers
  - Optional text-to-speech conversion

### 3. **Speech Input Service**
- **Port**: 5002
- **Location**: `/services/mbo-language-assistant-bot-speech-input-service/speech_service.py`
- **Purpose**: Processes speech-based queries
- **Responsibilities**:
  - Transcribes audio to text (via Google Speech Recognition)
  - Calls Retrieve Service to fetch context
  - Sends prompt to Ollama directly
  - Converts responses back to audio (text-to-speech)
  - Returns both text and audio responses

### 4. **Retrieve Service**
- **Port**: 5003
- **Location**: `/services/mbo-language-assistant-bot-retrieve-service/retrieve_service.py`
- **Purpose**: Centralized retrieval from PostgreSQL vector database
- **Responsibilities**:
  - Connects to PGVector index
  - Retrieves top-k relevant chunks for a question
  - Returns formatted context and source files

### 5. **Realtime Voice Service**
- **Port**: 5005
- **Location**: `/services/openai-service/realtime_voice_service.py`
- **Purpose**: Streams chat-page microphone audio over WebSocket and bridges it to OpenAI Realtime.
- **Responsibilities**:
  - Accepts browser PCM audio chunks via WebSocket
  - Detects end-of-speech with silence timing compatible with the speech workflow settings
  - Streams partial transcript events back to the chat UI
  - Retrieves course-material context and requests a streamed OpenAI text/audio answer
  - Streams assistant text and audio back to the browser during generation

### 6. **Database Manager Service** ⭐ NEW
- **Port**: 5004
- **Location**: `/services/database-manager/database_manager.py`
- **Purpose**: CRUD API for managing course materials and subjects
- **Database**: Remote Supabase PostgreSQL with pgvector
- **Responsibilities**:
  - Full CRUD operations on subjects and chunks
  - Bulk data ingestion for course materials
  - Integration with admin dashboard
  - Centralized course material management
- **Quick Start**: See [QUICKSTART_DATABASE_MANAGER.md](./QUICKSTART_DATABASE_MANAGER.md)
- **API Reference**: See [DATABASE_MANAGER_API.md](./DATABASE_MANAGER_API.md)
- **Supabase Setup**: See [SUPABASE_SETUP.md](./SUPABASE_SETUP.md)

### 7. **Frontend (React)**
- **Port**: 3000
- **Location**: `/mbo-language-assistant-chatbot/`
- **Purpose**: User interface for chatbot
- **Features**:
  - Text input field with send button
  - Microphone button for voice input
  - Real-time message display
  - Conversation history management

### 8. **Admin Dashboard** (Future)
- **Purpose**: Manage course materials via Database Manager API
- **Features**:
  - Create/Edit/Delete subjects
  - Upload course materials
  - View/Manage chunks
  - System administration

## Setup Instructions

### Quick Start: Docker Compose (Recommended)

The easiest way to start all services (including the new Database Manager):

```bash
cd services/

# Copy environment template (and fill in your Supabase credentials)
cp .env.example .env

# Start all services with one command
docker compose up --build

# Services will be available at:
# - API Gateway: http://localhost:5000
# - Text Service: http://localhost:5001
# - Speech Service: http://localhost:5002
# - Retrieve Service: http://localhost:5003
# - Database Manager: http://localhost:5004 ⭐ NEW
# - Frontend: http://localhost:3000
```

**First time?** [QUICKSTART_DATABASE_MANAGER.md](./QUICKSTART_DATABASE_MANAGER.md) has step-by-step setup.

### Manual Setup (Multiple Terminals)

Prerequisites
- Python 3.8+
- Node.js 14+
- PostgreSQL (local) OR Supabase (remote)
- Ollama (running on localhost:11434)

#### Step 1: Install Backend Dependencies

**Database Manager Service:**
```bash
cd services/database-manager
pip install -r requirements.txt
```

**Retrieve Service:**
```bash
cd services/mbo-language-assistant-bot-retrieve-service
pip install -r requirements.txt
```

**Text Input Service:**
```bash
cd services/mbo-language-assistant-bot-text-input-service
pip install -r requirements.txt
```

**Speech Input Service:**
```bash
cd services/mbo-language-assistant-bot-speech-input-service
pip install -r requirements.txt
```

**API Gateway:**
```bash
cd services/api-gateway
pip install -r requirements.txt
```

#### Step 2: Start the Backend Services (5 terminals needed)

**Terminal 1 - Database Manager (Port 5004):**
```bash
cd services/database-manager
export DB_HOST=YOUR_SUPABASE_HOST
export DB_USER=postgres
export DB_PASSWORD=YOUR_PASSWORD
export DB_NAME=postgres
python database_manager.py
```

**Terminal 2 - Retrieve Service (Port 5003):**
```bash
cd services/mbo-language-assistant-bot-retrieve-service
python retrieve_service.py
```

**Terminal 3 - Text Input Service (Port 5001):**
```bash
cd services/mbo-language-assistant-bot-text-input-service
python text_service.py
```

**Terminal 4 - Speech Input Service (Port 5002):**
```bash
cd services/mbo-language-assistant-bot-speech-input-service
python speech_service.py
```

**Terminal 5 - API Gateway (Port 5000):**
```bash
cd services/api-gateway
python api_gateway.py
```

**Terminal 6 - React Frontend (Port 3000):**
```bash
cd mbo-language-assistant-chatbot
npm start
```

#### Step 3: Verify Services Are Running

Check the health of all services:
```bash
# Database Manager health check
curl http://localhost:5004/health

# API Gateway health check
curl http://localhost:5000/health

# Text Service health check
curl http://localhost:5001/health

# Speech Service health check
curl http://localhost:5002/health

# Retrieve Service health check
curl http://localhost:5003/health
```

## API Endpoints

### Database Manager API Endpoints ⭐ NEW

For complete API documentation, see [DATABASE_MANAGER_API.md](./DATABASE_MANAGER_API.md)

```
GET /health                          - Health check
GET /subjects                        - List all subjects
POST /subjects                       - Create subject
GET /subjects/{id}                   - Get specific subject
PUT /subjects/{id}                   - Update subject
DELETE /subjects/{id}                - Delete subject
GET /subjects/{id}/chunks            - Get chunks for subject
POST /subjects/{id}/chunks           - Add chunk to subject
POST /subjects/{id}/chunks/bulk      - Bulk upload chunks
GET /chunks/{id}                     - Get specific chunk
PUT /chunks/{id}                     - Update chunk
DELETE /chunks/{id}                  - Delete chunk
```

### API Gateway Endpoints

#### Health Check
```
GET /health
```
Returns the status of all services and dependencies.

#### Text Query
```
POST /api/query/text
Content-Type: application/json

{
  "question": "Your question here",
  "enable_tts": false
}
```

#### Speech Query
```
POST /api/query/speech
Content-Type: multipart/form-data

- audio: Audio file (WAV, MP3, OGG, FLAC)
- enable_tts: Whether to return audio response (optional, default: true)
```

#### Unified Query (Auto-detects input type)
```
POST /api/query
```
For text:
```
Content-Type: application/json

{
  "question": "Your question here",
  "enable_tts": false
}
```

For speech:
```
Content-Type: multipart/form-data

- audio: Audio file
- enable_tts: Whether to return audio response
```

### Text Input Service Endpoints

#### Health Check
```
GET /health
```

#### Query
```
POST /query
Content-Type: application/json

{
  "question": "Your question here",
  "enable_tts": false
}
```

### Speech Input Service Endpoints

#### Health Check
```
GET /health
```

#### Transcribe
```
POST /transcribe
Content-Type: multipart/form-data

- audio: Audio file
```

#### Synthesize
```
POST /synthesize
Content-Type: application/json

{
  "text": "Text to convert to speech"
}
```

#### Query
```
POST /query
Content-Type: multipart/form-data

- audio: Audio file
- enable_tts: Whether to return audio response
```

## Environment Variables

Each service can be configured via environment variables:

### Database Manager Service ⭐ NEW
```
SERVICE_HOST=0.0.0.0
SERVICE_PORT=5004
DB_HOST=db.xxx.supabase.co        # Your Supabase host
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password_here     # Your Supabase password
DB_NAME=postgres
```

See [SUPABASE_SETUP.md](./SUPABASE_SETUP.md) for detailed setup instructions.

### API Gateway
```
GATEWAY_HOST=localhost
GATEWAY_PORT=5000
TEXT_SERVICE_URL=http://localhost:5001
SPEECH_SERVICE_URL=http://localhost:5002
RETRIEVE_SERVICE_URL=http://localhost:5003
DB_MANAGER_SERVICE_URL=http://localhost:5004
```

### Text Input Service
```
SERVICE_HOST=localhost
SERVICE_PORT=5001
RETRIEVE_SERVICE_URL=http://localhost:5003
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL_NAME=llama3
```

### Speech Input Service
```
SERVICE_HOST=localhost
SERVICE_PORT=5002
RETRIEVE_SERVICE_URL=http://localhost:5003
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL_NAME=llama3
```

### Retrieve Service
```
SERVICE_HOST=localhost
SERVICE_PORT=5003
DB_USER=user
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=school-db
COLLECTION_NAME=course_materials_vectors
```

## Using the Application

### Text-Based Input
1. Open the React app in browser (`http://localhost:3000`)
2. Type your question in the input field
3. Press Enter or click the Send button
4. The API Gateway routes the request to the Text Input Service
5. Response is displayed in real-time

### Speech-Based Input
1. Open the React app in browser (`http://localhost:3000`)
2. Click the Microphone button 🎤
3. Speak your question
4. Click the Microphone button again to stop recording
5. The API Gateway routes to Speech Input Service:
   - Audio is transcribed to text
  - Context is fetched from Retrieve Service
  - Prompt is sent to Ollama for answer generation
   - Response is displayed
   - (Optional) Response can be converted back to audio
6. Both transcription and answer are shown in the chat

## Troubleshooting

### Service Connection Issues
1. **Ensure all services are running** in separate terminals
2. **Check port availability**: Make sure ports 5000, 5001, 5002, 5003 are not in use
3. **Verify health endpoints**: Each service should respond to `/health` endpoint
4. **Check API Gateway logs**: Should show routing information

### Speech Recognition Issues
- **Microphone not working**: Check browser permissions for microphone access
- **Poor transcription**: Speak clearly and ensure minimal background noise
- **Audio format issues**: Try WAV format first, as it's most compatible

### Database Connection Issues
- **Ensure PostgreSQL is running** with the loaded course materials
- **Check credentials** in environment variables match your setup
- **Verify the database** and collection names are correct

### Ollama Connection Issues
- **Ensure Ollama is running** on port 11434
- **Check model name**: Use `ollama list` to see available models
- **Verify API endpoint**: Should be `http://localhost:11434`

## Benefits of Microservices Architecture

✅ **Scalability**: Each service can be scaled independently based on demand
✅ **Maintainability**: Services are decoupled and easier to maintain
✅ **Flexibility**: Easy to add new services (image processing, document analysis, etc.)
✅ **Resilience**: Failure in one service doesn't bring down the entire system
✅ **Technology Freedom**: Each service can use different tech stacks
✅ **Independent Deployment**: Services can be deployed separately
✅ **Parallel Development**: Teams can work on services independently

## Future Enhancements

- Add authentication/authorization layer
- Implement rate limiting and request throttling
- Add caching layer (Redis) for frequently asked questions
- Implement request queuing for high-traffic scenarios
- Add monitoring and logging (ELK stack, Prometheus, Grafana)
- Add Docker containerization for easy deployment
- Implement service discovery (Consul, Eureka)
- Add API versioning for backward compatibility

## Support

For issues or questions:
1. Check service health: `curl http://localhost:5000/health`
2. Review service logs in their respective terminals
3. Verify all dependencies are installed
4. Ensure database and Ollama are running
