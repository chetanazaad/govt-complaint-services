# Government Complaint Navigation Platform

A production-ready FastAPI backend that helps Indian citizens navigate government complaint procedures using AI-powered intent classification and a comprehensive local knowledge base.

## Architecture

```
User Query → Input Sanitization → Cache Check → Keyword Match → LLM Fallback → Response
```

- **LLM is ONLY used for intent extraction** — never for factual data
- **All contact details come from local JSON** — deterministic and safe
- **Keyword matching runs first** — avoids unnecessary API calls

## Quick Start

### 1. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Set up environment
```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### 3. Run locally
```bash
uvicorn main:app --reload --port 8000
```

### 4. Open API docs
Visit `http://localhost:8000/docs`

## API Endpoints

### `POST /interpret`
Classify a user complaint using natural language.

**Request:**
```json
{ "query": "There is no electricity in my area since morning" }
```

**Response:**
```json
{
  "category": "Electricity",
  "problem": "Power Outage",
  "confidence": 0.9,
  "source": "keyword",
  "disclaimer": "This is an AI-assisted classification..."
}
```

### `POST /resolve`
Get detailed resolution steps for a classified complaint.

**Request:**
```json
{ "category": "Electricity", "problem": "Power Outage" }
```

**Response:**
```json
{
  "category": "Electricity",
  "problem": "Power Outage",
  "primary_action": {
    "department": "State Electricity Distribution Company (DISCOM)",
    "complaint_link": "https://www.upenergy.in/complaint",
    "helpline": "1912",
    "description": "Register a complaint for power outage..."
  },
  "escalation": { ... },
  "rti": { ... },
  "disclaimer": "..."
}
```

### `GET /categories`
List all available complaint categories and problems.

### `GET /health`
Health check with cache statistics.

## Deploy to Render

1. Push to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your repo
4. Configure:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `OPENROUTER_API_KEY`

## Project Structure

```
backend/
├── main.py              # FastAPI app + endpoints
├── services/
│   ├── llm_service.py   # OpenRouter LLM integration
│   ├── matcher.py       # Keyword matching + JSON lookup
│   └── cache.py         # In-memory LRU cache
├── data/
│   └── complaints.json  # Knowledge base (10 entries)
├── models/
│   └── schemas.py       # Pydantic request/response models
├── utils/
│   └── helpers.py       # Input sanitization
├── requirements.txt
└── .env.example
```

## Supported Categories

| Category | Problems |
|----------|----------|
| Electricity | Power Outage, High Bill |
| Police | FIR Not Filed, Cybercrime |
| Land | Land Dispute, Mutation Not Done |
| Transport | Bad Road Condition, Overcharging by Auto/Taxi |
| Water | Water Supply Issue, Illegal Borewell |
