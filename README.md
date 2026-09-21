# AI Study Assistant

Student uploads notes/PDF → AI reads the material → generates a summary and MCQs → frontend displays the result.

## Project Structure

```
AI-Study-Assistant/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py        # Environment configuration
│   │   ├── foundry.py       # Azure AI Foundry integration
│   │   ├── main.py          # FastAPI app and /api/study endpoint
│   │   └── models.py        # Pydantic request/response models
│   └── tests/
├── .env.example             # Example environment variables
├── requirements.txt         # Python dependencies
└── FOUNDRY_HANDOVER.md    # Original handover document
```

## Backend Setup

1. **Create and activate a virtual environment:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env and fill in your Azure credentials
   ```

4. **Run the server:**

   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```

## API Usage

### Health Check

```bash
curl http://localhost:8000/health
```

### Generate Summary

```bash
curl -X POST http://localhost:8000/api/study \
  -F "file=@/path/to/notes.pdf" \
  -F "action=summary"
```

### Generate MCQs

```bash
curl -X POST http://localhost:8000/api/study \
  -F "file=@/path/to/notes.pdf" \
  -F "action=mcqs"
```

## Response Format

```json
{
  "summary": "...",
  "key_points": ["...", "..."],
  "mcqs": [
    {
      "question": "...",
      "options": ["...", "...", "...", "..."],
      "correct_answer": "...",
      "explanation": "..."
    }
  ]
}
```

## Important Notes

- Do **not** commit `.env` or Azure secrets to Git.
- Keep AI calls minimal to preserve Azure credits.
- Reuse the existing test vector store during development unless necessary.
