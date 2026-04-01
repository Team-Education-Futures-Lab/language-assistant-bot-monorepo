# Quick Start Guide - Microservices Chatbot

This guide will get you up and running with the microservices-based chatbot application in under 15 minutes.

## Prerequisites Checklist
- [ ] Python 3.8+ installed
- [ ] Node.js 14+ installed
- [ ] PostgreSQL running with course materials loaded
- [ ] Ollama running on localhost:11434

## Step 1: Install Python Dependencies (5 minutes)

Open PowerShell and run these commands in separate directories:

**API Gateway:**
```powershell
cd "C:\path\to\services\mbo-language-assistant-bot-api-gateway"
pip install -r requirements.txt
```

**Text Service:**
```powershell
cd "C:\path\to\services\mbo-language-assistant-bot-text-input-service"
pip install -r requirements.txt
```

**Speech Service:**
```powershell
cd "C:\path\to\services\mbo-language-assistant-bot-speech-input-service"
pip install -r requirements.txt
```

**Retrieve Service:**
```powershell
cd "C:\path\to\services\mbo-language-assistant-bot-retrieve-service"
pip install -r requirements.txt
```

## Step 2: Install Node Dependencies (3 minutes)

```powershell
cd "C:\path\to\mbo-language-assistant-chatbot"
npm install
```

## Step 3: Start All Services (5 minutes)

Open 5 separate terminal windows and run:

### Terminal 1 - Retrieve Service
```powershell
cd "C:\path\to\services\mbo-language-assistant-bot-retrieve-service"
python retrieve_service.py
```
Expected output: `Retrieve Service is ready to receive requests...`

### Terminal 2 - Text Input Service
```powershell
cd "C:\path\to\services\mbo-language-assistant-bot-text-input-service"
python text_service.py
```
Expected output: `Text Input Service is ready to receive requests...`

### Terminal 3 - Speech Input Service
```powershell
cd "C:\path\to\services\mbo-language-assistant-bot-speech-input-service"
python speech_service.py
```
Expected output: `Speech Input Service is ready to receive requests...`

### Terminal 4 - API Gateway
```powershell
cd "C:\path\to\services\mbo-language-assistant-bot-api-gateway"
python api_gateway.py
```
Expected output: `API Gateway is ready to receive requests...`

### Terminal 5 - React Frontend
```powershell
cd "C:\path\to\mbo-language-assistant-chatbot"
npm start
```
Expected output: Automatically opens `http://localhost:3000` in browser

## Step 4: Verify Everything Works

1. **Check API Gateway**: Visit `http://localhost:5000/health`
   - Should show all services as "healthy"

2. **Test in UI**:
   - Type a question and hit Send → should get a response
   - Click microphone 🎤, speak a question, click again → should transcribe and respond

## Troubleshooting

### "Failed to fetch" error in browser
- ✅ Check API Gateway is running on port 5000
- ✅ Check Text Service is running on port 5001
- ✅ Check Retrieve Service is running on port 5003
- ✅ Open browser console (F12) for more details

### Speech not working
- ✅ Allow microphone access when browser asks
- ✅ Speak clearly and audibly
- ✅ Check Speech Service is running on port 5002

### Python module not found errors
- ✅ Make sure you're in the correct service directory
- ✅ Run `pip install -r requirements.txt` in that directory
- ✅ Use full path if needed: `python -m pip install -r requirements.txt`

### Port already in use
- ✅ Check what's using the port: `netstat -ano | findstr :5000`
- ✅ Change port in service code or kill the process using the port

## Common Tasks

### Change Ollama Model
Edit the service and change:
```python
OLLAMA_MODEL_NAME = "mistral"  # or any model from 'ollama list'
```

### Change Database
Edit the service and change:
```python
DB_NAME = "your_database"
COLLECTION_NAME = "your_collection"
```

### Run on Different Ports
Set environment variables before starting:
```powershell
$env:GATEWAY_PORT = 5000
$env:TEXT_SERVICE_PORT = 5001
$env:SPEECH_SERVICE_PORT = 5002
python api_gateway.py
```

## System Architecture

```
User Browser (3000)
      ↓
API Gateway (5000) - Routes requests
      ├→ Text Service (5001) - Text queries
      ├→ Speech Service (5002) - Voice queries
      └→ Retrieve Service (5003) - Context retrieval
            ├→ Text Service (5001) calls Retrieve + Ollama
            └→ Speech Service (5002) calls Retrieve + Ollama
```

## Next Steps

After verifying everything works:
1. Explore the API endpoints by reading API_ENDPOINTS.md
2. Customize the UI by editing `/chatgpt-clone/src/`
3. Add new services for additional features
4. Deploy to production using Docker

## Support

All services log their output to the terminal. Check these logs for debugging:
- API Gateway logs show routing details
- Text Service logs show database queries
- Speech Service logs show transcription results
- React console (F12) shows frontend errors
