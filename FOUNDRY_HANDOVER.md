# AI Study Assistant — Team Handover

## 1. Project Overview

**Repository:** https://github.com/Bhargav-bit567/AI-Study-Assistant

The MVP goal is simple:

> Student uploads study notes/PDF → AI reads the material → generates a summary and MCQs → frontend displays the result.

Current architecture:

```
React Frontend
      │
      │ upload PDF / request
      ▼
Backend API
      │
      │ upload/process document
      ▼
Microsoft Foundry
      │
      ├── AI Study Assistant Agent
      │       └── GPT-5-mini
      │
      └── File Search / Vector Store
              │
              ▼
           Student PDF
```

## 2. Foundry Status

### Agent

- **Name:** `AI-Study-Assistant`
- **Model:** `GPT-5-mini`
- **Current version:** `2`
- **Purpose:** Generate study summaries and MCQs from uploaded notes.
- **Playground:** Tested successfully.

### Agent behavior

The agent is configured to:

- Use uploaded study material as the primary source.
- Create concise summaries.
- Extract important concepts and definitions.
- Include formulas/processes when present.
- Generate MCQs with 4 options.
- Provide the correct answer and a short explanation.
- Mix easy, medium and difficult questions.
- Avoid unsupported/invented information.
- Say when the supplied material does not contain enough information.

### File Search

File Search is enabled.

A test vector index was created:

```
index_helpful_boot_3hdc95y9cq
```

A Computer Networks/Data Communication PDF was uploaded through Foundry and the agent successfully retrieved information from it and generated a summary.

**Important:** the manually attached test PDF/index is for development/testing. Production users should not require manual uploads through the Foundry portal. The backend must handle user uploads programmatically and make the file available to the agent's File Search workflow.

## 3. Backend Responsibilities

The backend team owns the application plumbing.

### Required flow

1. Receive the PDF from the frontend.
2. Upload/process the PDF through the Azure/Foundry file-search workflow.
3. Make the document available to the agent.
4. Call the existing `AI-Study-Assistant` agent.
5. Request either:
   - summary
   - MCQs
6. Return a structured response to the frontend.

Conceptually:

```
POST /api/study
   │
   ├── file: notes.pdf
   └── action: summary | mcqs
            │
            ▼
       Backend
            │
            ▼
   File Search / Vector Store
            │
            ▼
    AI-Study-Assistant
            │
            ▼
        JSON result
            │
            ▼
        Frontend
```

### Suggested API contract

Request:

```http
POST /api/study
Content-Type: multipart/form-data
```

Form fields:

```
file=<PDF>
action=summary
```

or:

```
action=mcqs
```

Suggested response:

```json
{
  "summary": "....",
  "key_points": [
    "....",
    "...."
  ],
  "mcqs": [
    {
      "question": "....",
      "options": [
        "....",
        "....",
        "....",
        "...."
      ],
      "correct_answer": "....",
      "explanation": "...."
    }
  ]
}
```

The exact contract can be changed by the team, but keep it predictable so React does not need to parse free-form AI text.

## 4. Foundry → Backend Integration

In Foundry, **Continue in code** provides the SDK starting point.

The Python integration uses Azure authentication and the Foundry project client, for example:

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
```

The backend should keep Azure credentials/server configuration on the server side.

**Do not expose Azure credentials or secrets in React/frontend code.**

Use:

```
React → Backend → Foundry
```

not:

```
React → Foundry with secrets in browser
```

## 5. Frontend Responsibilities

Frontend should provide:

- PDF/file picker
- Upload button
- Summary generation action
- MCQ generation action
- Summary display
- MCQ display
- Loading/error states

Example UX:

```
[ Upload Notes ]

notes.pdf
     │
     ├── Generate Summary
     └── Generate MCQs
```

## 6. Credit-Saving Rules

The Azure subscription has limited credits, so avoid unnecessary AI calls.

### Testing policy

Use one small PDF for integration testing.

Preferred test sequence:

```
1. Upload one small PDF
2. Make one summary request
3. Make one MCQ request
4. Verify the full pipeline
5. Stop repeated testing
```

Avoid repeatedly:

- re-uploading the same file
- regenerating the same summary
- generating many versions of the same quiz
- creating unnecessary vector stores
- testing every model

The Foundry test index can be reused during development unless there is a real reason to change the setup.

## 7. Important Security / Data Isolation Note

For production, users must not accidentally retrieve another user's documents.

The backend should design the file/vector-store lifecycle so the agent searches the correct document set for the current request/user.

Do not assume the shared manual test index is suitable for all production users.

## 8. What Is Already Done

- [x] Foundry project created
- [x] AI Study Assistant agent created
- [x] GPT-5-mini configured
- [x] Agent instructions configured
- [x] Web Search removed/not required for MVP
- [x] File Search enabled
- [x] Test vector index created
- [x] PDF uploaded for testing
- [x] PDF retrieval verified
- [x] Summary generation verified

## 9. What Still Needs To Be Done

### Backend

- [ ] Set up Python/Node backend
- [ ] Configure Azure authentication securely
- [ ] Receive uploaded PDF
- [ ] Programmatically upload/process the PDF
- [ ] Connect the PDF to File Search
- [ ] Call `AI-Study-Assistant`
- [ ] Return structured JSON
- [ ] Handle errors and empty/unsupported files

### Frontend

- [ ] Upload UI
- [ ] Call backend API
- [ ] Display summary
- [ ] Display MCQs
- [ ] Handle loading/errors

### Integration

- [ ] Test Frontend → Backend → Foundry → Backend → Frontend
- [ ] Verify document isolation
- [ ] Finalize API contract
- [ ] Final end-to-end test with minimal credit usage

## 10. Git Workflow

Recommended team flow:

```
main
 │
 ├── feature/frontend
 ├── feature/backend
 └── feature/foundry-integration
```

Avoid directly pushing experimental work to `main`.

For each feature:

```
create branch
→ make changes
→ test
→ pull request
→ review
→ merge
```

## 11. Current Responsibility Split

### Foundry / AI
**Bhargav**

- Maintain the Foundry agent.
- Maintain agent instructions.
- Maintain File Search configuration.
- Help backend with agent integration.
- Validate AI responses.

### Backend
**Backend teammate**

- API
- file upload
- document processing
- Azure/Foundry SDK integration
- agent invocation
- JSON response
- security and data isolation

### Frontend
**Frontend teammate**

- UI
- file picker/upload
- API integration
- summary page
- MCQ page

## 12. First Backend Task

Do **not** build the whole application first.

First prove this single pipeline:

```
small test PDF
    ↓
Backend
    ↓
Foundry File Search
    ↓
AI-Study-Assistant
    ↓
one summary response
```

Once that works, add MCQs.

Then connect React.

---

## 13. Definition of Done for MVP

The MVP is working when a user can:

1. Open the frontend.
2. Upload a PDF.
3. Click **Generate Summary**.
4. Receive a summary based on that PDF.
5. Click **Generate MCQs**.
6. Receive MCQs based on that PDF.
7. See the results cleanly in the frontend.

No additional agents or complex RAG architecture are required for this MVP.

## 14. Important Notes

- The Foundry Playground is for testing; production requests should come through the backend.
- Do not put Azure secrets in the frontend.
- Do not create a new vector index for every random test.
- Keep AI calls minimal because Azure credits are limited.
- Keep the output structured for frontend integration.
