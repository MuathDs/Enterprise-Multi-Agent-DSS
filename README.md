# DataMaster-DSS — Enterprise Edition

Multi-agent Decision Support System with RAG, security-trimmed retrieval,
token-quota governance, and SSE streaming.

Architecture: Next.js frontend -> FastAPI backend -> Azure AI Foundry / AI Search
(runs in fully-local simulation mode without any Azure credentials).

## Run

Terminal 1 (backend):
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Terminal 2 (frontend):
    cd frontend
    npm run dev

Open http://localhost:3000

## 60-second verification

1. Sidebar status dot is green with a "Simulation mode" badge.
2. As Financial Analyst ask: "What is the budget reserve for the acquisition?"
   -> trace shows 2 records, no confidential content.
3. Switch to Administrator, same question -> 3 records, CONFIDENTIAL answer
   with the Restricted citation.
4. Back as Analyst ask: "What is the salary for new hires?" -> red 403 scope denial.

## Demo identities

| Bearer token  | Role    | Agent scope       | Document groups                  |
|---------------|---------|-------------------|-----------------------------------|
| demo-analyst  | analyst | Finance, General  | Finance, General                 |
| demo-admin    | admin   | all departments   | all + *-Confidential              |

## Going live on Azure

Fill `backend/.env` (see `.env.example`), then bootstrap the indexes:
    python -c "import asyncio, retrieval; asyncio.run(retrieval.seed_all_indexes())"
