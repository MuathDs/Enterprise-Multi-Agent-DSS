"""
DataMaster-DSS — FastAPI backend
=================================
Replaces the in-app logic of the Streamlit prototype (app.py) with the
architecture the thesis actually describes:

  Next.js frontend ──JWT──▶ FastAPI (this file) ──▶ Azure OpenAI / AI Foundry
                              │
                              ├── Token-quota governance (pre-check + post-account, HTTP 429)
                              ├── Word-boundary agent routing (fixes app.py substring bug)
                              ├── SSE streaming responses
                              └── Audit log (thesis §5.3 "Auditability and Logging")

Run:  uvicorn main:app --reload --port 8000
Env (optional — without these, the server runs in SIMULATION mode and says so):
  AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import retrieval  # secure RAG tier: index-per-department + security trimming

# ---------------------------------------------------------------------------
# App + CORS (Next.js dev server)
# ---------------------------------------------------------------------------
app = FastAPI(title="DataMaster-DSS API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SIMULATION = not os.getenv("AZURE_OPENAI_API_KEY")

# ---------------------------------------------------------------------------
# 1. AUTH — HTTPBearer stub, shaped for Microsoft Entra ID
# ---------------------------------------------------------------------------
# Production path (thesis §5.3 RBAC, done properly):
#   * Frontend acquires a JWT from Entra ID (MSAL).
#   * Validate signature against the tenant JWKS
#     (https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys),
#     check `aud`, `iss`, expiry; read roles from the `roles`/`groups` claim.
#   * Pass the user's group claims to Azure AI Search as a security-trimming
#     filter so retrieval itself is permission-scoped — that is what makes
#     "departmental data isolation" a real guarantee instead of a UI toggle.
#
# Demo path (below): the bearer token *is* the user id, so the quota and
# audit mechanics are fully exercisable without a tenant.
security = HTTPBearer(auto_error=False)


class User(BaseModel):
    user_id: str
    role: str = "analyst"
    scopes: list[str] = ["Finance", "General"]   # which AGENTS may be used (RBAC gate)
    groups: list[str] = []                        # which DOCUMENTS may be retrieved
    # (security trimming — in production these are Entra ID group object-IDs
    #  from the JWT `groups` claim; scope != groups: an analyst may use the
    #  Finance agent yet still be trimmed out of Finance-Confidential records)


DEMO_USERS = {
    "demo-analyst": User(user_id="demo-analyst", role="analyst",
                         scopes=["Finance", "General"],
                         groups=["Finance", "General"]),
    "demo-admin": User(user_id="demo-admin", role="admin",
                       scopes=["Finance", "HR", "Strategy", "Legal", "IT", "Ops", "Sales", "General"],
                       groups=["Finance", "Finance-Confidential", "HR", "Strategy", "Legal",
                               "IT", "IT-Confidential", "Ops", "Sales", "General"]),
}


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    if creds is None:
        raise HTTPException(401, "Missing bearer token.")
    user = DEMO_USERS.get(creds.credentials)
    if user is None:
        # In production: validate JWT here instead of dict lookup.
        raise HTTPException(401, "Invalid token. Demo tokens: demo-analyst, demo-admin.")
    return user


# ---------------------------------------------------------------------------
# 2. TOKEN-QUOTA GOVERNANCE — the thesis's financial layer, implemented
# ---------------------------------------------------------------------------
# Design (matches abstract + §1.4 objective 3):
#   * Per-user monthly limit, stored server-side (swap dict → Redis/Azure
#     Table for multi-instance deployments; the interface stays identical).
#   * PRE-CHECK: estimate the request before any model call — never start
#     work the user can't pay for.
#   * POST-ACCOUNT: record actual usage from the model's usage object.
#   * Hard stop = HTTP 429 with a structured body the frontend renders.
class QuotaStore:
    def __init__(self) -> None:
        self._limits: dict[str, int] = {}
        self._used: dict[str, int] = {}
        self.default_limit = int(os.getenv("DSS_DEFAULT_QUOTA", "5000"))

    def limit(self, user_id: str) -> int:
        return self._limits.get(user_id, self.default_limit)

    def used(self, user_id: str) -> int:
        return self._used.get(user_id, 0)

    def remaining(self, user_id: str) -> int:
        return max(0, self.limit(user_id) - self.used(user_id))

    def charge(self, user_id: str, tokens: int) -> None:
        self._used[user_id] = self.used(user_id) + tokens

    def set_limit(self, user_id: str, limit: int) -> None:
        self._limits[user_id] = limit


quota = QuotaStore()


def estimate_tokens(text: str) -> int:
    """Cheap pre-flight estimate (~4 chars/token). For billing-grade accuracy
    swap in tiktoken; the pre-check only needs to be conservative."""
    return math.ceil(len(text) / 4) + 64  # +64 headroom for system prompt


def enforce_quota(user: User, query: str) -> int:
    est = estimate_tokens(query)
    if quota.remaining(user.user_id) < est:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exhausted",
                "message": "Token quota exhausted for this user.",
                "used": quota.used(user.user_id),
                "limit": quota.limit(user.user_id),
            },
        )
    return est


# ---------------------------------------------------------------------------
# 3. ROUTING — ported from app.py, with the substring bug fixed
# ---------------------------------------------------------------------------
# app.py used `any(x in p_low for x in [...])`, i.e. raw substring matching:
#   "I need three laptops"  -> "hr" in "three"  -> HR agent   (wrong)
#   "Why is it waiting?"    -> "it" in "waiting"-> IT agent   (wrong)
# Latin keywords now match on word boundaries; Arabic keeps substring
# matching (Arabic morphology attaches prefixes, so \b is too strict).
#
# Branch order is still precedence order — documented, because it explains
# thesis TC-01 ("What is the IT budget?" → Finance: 'budget' matches first).
# The honest upgrade path is an LLM/embedding intent classifier; this
# function then becomes the deterministic fallback tier.
AGENT_MATRIX: list[tuple[str, list[str]]] = [
    ("Finance",  ["ميزانية", "budget", "فلوس", "مالية", "ريال", "sar"]),
    ("HR",       ["موظف", "راتب", "hr", "توظيف", "salary", "hiring"]),
    ("Strategy", ["قرار", "strategy", "ceo", "استراتيجية", "رؤية", "vision"]),
    ("Legal",    ["قانون", "محامي", "عقد", "legal", "نظام", "امتثال", "contract", "compliance"]),
    ("IT",       ["أمن", "معلومات", "it", "تقنية", "سيرفر", "security", "اختراق", "server", "firewall"]),
    ("Ops",      ["سلاسل", "إمداد", "ops", "عمليات", "لوجستي", "مخزن", "logistics", "warehouse"]),
    ("Sales",    ["سوق", "مبيعات", "sales", "منافسين", "market", "competitors"]),
]

AGENT_PERSONAS = {
    "Finance": "You are the Finance Analyst agent. Answer strictly from the provided finance records.",
    "HR": "You are the HR Advisor agent. Answer strictly from the provided HR policy records.",
    "Strategy": "You are the Strategy agent advising the CEO. Answer strictly from provided records.",
    "Legal": "You are the Legal & Compliance agent. Answer strictly from provided legal records.",
    "IT": "You are the IT & Security agent. Answer strictly from provided IT records.",
    "Ops": "You are the Operations & Supply Chain agent. Answer strictly from provided records.",
    "Sales": "You are the Sales & Market agent. Answer strictly from provided records.",
    "General": "You are the general assistant. If a question belongs to a department, say which one.",
}


def route_query(query: str) -> dict:
    q = query.lower()
    for agent, keywords in AGENT_MATRIX:
        for kw in keywords:
            if re.fullmatch(r"[a-z]+", kw):
                if re.search(rf"\b{re.escape(kw)}\b", q):
                    return {"agent": agent, "matched_keyword": kw, "method": "keyword_boundary"}
            elif kw in q:
                return {"agent": agent, "matched_keyword": kw, "method": "keyword_substring_ar"}
    return {"agent": "General", "matched_keyword": None, "method": "fallback"}


# ---------------------------------------------------------------------------
# 4. RBAC scope check — retrieval is denied, not just hidden (thesis TC-03)
# ---------------------------------------------------------------------------
def enforce_scope(user: User, agent: str) -> None:
    if agent not in user.scopes:
        raise HTTPException(
            403,
            detail={
                "error": "scope_denied",
                "message": f"Role '{user.role}' is not authorized for the {agent} agent.",
                "agent": agent,
            },
        )


# ---------------------------------------------------------------------------
# 5. AUDIT LOG — thesis §5.3 "every interaction ... logged for governance"
# ---------------------------------------------------------------------------
AUDIT: list[dict] = []


def audit(user: User, event: str, **kw) -> None:
    AUDIT.append({
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user.user_id,
        "event": event,
        **kw,
    })
    # Production: ship to Azure Application Insights / OpenTelemetry instead
    # of a list — the call site stays the same.


# ---------------------------------------------------------------------------
# 6. GENERATION — real Azure OpenAI path, honest simulation fallback
# ---------------------------------------------------------------------------
SIM_ANSWERS = {  # SIMULATION ONLY — replaced by RAG retrieval + LLM in prod
    "Finance": ("Based on the Muath IT Q1 report, the approved budget is 2.5M SAR, "
                "with 600K SAR allocated to IT infrastructure.",
                ["Finance_DB / Table: Q1_2024"]),
    "HR": ("Current hiring policy requires 3 AI Engineers at a 12,000 SAR base salary.",
           ["HR_DB / Policy: Hiring_2026"]),
    "Strategy": ("Strategic directive: consolidate southern-region operations before Q3 board review.",
                 ["Strategy_DB / Memo: Board_Q3"]),
    "Legal": ("All current contracts comply with the 2026 Saudi Labor Law amendments.",
              ["Legal_DB / Register: Contracts_2026"]),
    "IT": ("IT security is active. Firewall rules updating; Azure licenses renew on schedule.",
           ["IT_DB / Log: SecOps_Current"]),
    "Ops": ("Abha branch setup is on schedule with a 400K SAR budget.",
            ["Ops_DB / Project: Abha_Branch"]),
    "Sales": ("Targeting 15% market share in the Southern Region by year-end.",
              ["Sales_DB / Plan: SR_Targets"]),
    "General": ("I'm the DataMaster general assistant. Ask about a department and I'll route you.",
                []),
}


async def generate(
    agent: str,
    query: str,
    records: list["retrieval.RetrievedRecord"],
) -> AsyncGenerator[tuple[str, int], None]:
    """Yields (text_chunk, tokens_so_far). The RAG hook is now filled:
    `records` arrive already security-trimmed from retrieval.secure_retrieve(),
    are injected as the ONLY permitted knowledge, and the grounding rule
    forces 'Information not found' when retrieval came back empty —
    the thesis's hallucination-mitigation contract (§6.2 stages 2–3)."""
    if not SIMULATION:
        from openai import AsyncAzureOpenAI  # finally earns its place in requirements.txt
        client = AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        )
        grounding = retrieval.format_context(records)
        stream = await client.chat.completions.create(
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            stream=True,
            stream_options={"include_usage": True},
            messages=[
                {"role": "system", "content": AGENT_PERSONAS[agent] +
                 " Answer ONLY from the retrieved records below. Cite record numbers"
                 " like [1]. If the answer is not in the records, say"
                 " 'Information not found' — never improvise.\n\n" + grounding},
                {"role": "user", "content": query},
            ],
        )
        total = 0
        async for chunk in stream:
            if chunk.usage:
                total = chunk.usage.total_tokens
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content, total
        return

    # --- simulation mode: synthesize from the retrieved (trimmed) records,
    # so what streams back is provably what retrieval allowed through ---
    import asyncio
    if records:
        text = " ".join(
            f"[{i}] {r.content}" for i, r in enumerate(records[:2], 1)
        )
    elif agent == "General":
        text, _ = SIM_ANSWERS["General"]
    else:
        text = "Information not found in your authorized records."
    running = estimate_tokens(query)
    for word in text.split(" "):
        await asyncio.sleep(0.02)
        running += 1
        yield word + " ", running


# ---------------------------------------------------------------------------
# 7. API
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


@app.post("/api/chat")
async def chat(body: ChatRequest, user: User = Depends(get_current_user)):
    """SSE stream: `route` event → `delta` events → `done` event (usage)."""
    estimate = enforce_quota(user, body.query)          # governance: pre-check
    route = route_query(body.query)
    enforce_scope(user, route["agent"])                 # RBAC layer 0: agent gate

    # RAG with sovereignty layers 1+2: department-isolated index, then
    # document-level trimming on the user's group claims. Records that the
    # user's groups don't cover never enter the pipeline at all.
    records = await retrieval.secure_retrieve(
        department=route["agent"], query=body.query, user_groups=user.groups,
    )
    audit(user, "chat.routed", query=body.query, retrieved=len(records),
          doc_ids=[r.doc_id for r in records], **route)

    async def event_stream():
        t0 = time.perf_counter()
        yield f"event: route\ndata: {json.dumps({**route, 'records': len(records)})}\n\n"
        final_tokens = estimate
        async for chunk, tokens in generate(route["agent"], body.query, records):
            final_tokens = max(final_tokens, tokens)
            yield f"event: delta\ndata: {json.dumps({'text': chunk})}\n\n"
        quota.charge(user.user_id, final_tokens)        # governance: post-account
        done = {
            "tokens": final_tokens,
            "remaining": quota.remaining(user.user_id),
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "citations": [r.citation for r in records],  # real provenance, not canned
            "simulation": SIMULATION,
        }
        audit(user, "chat.completed", agent=route["agent"], tokens=final_tokens)
        yield f"event: done\ndata: {json.dumps(done)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/usage")
def usage(user: User = Depends(get_current_user)):
    return {"user": user.user_id, "used": quota.used(user.user_id),
            "limit": quota.limit(user.user_id), "remaining": quota.remaining(user.user_id)}


@app.get("/api/audit")
def get_audit(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Audit log is admin-only.")
    return AUDIT[-200:]


@app.put("/api/quota/{target_user}")
def set_quota(target_user: str, limit: int, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Quota administration is admin-only.")
    quota.set_limit(target_user, limit)
    audit(user, "quota.updated", target=target_user, limit=limit)
    return {"user": target_user, "limit": limit}


@app.get("/api/health")
def health():
    return {"status": "online", "mode": "simulation" if SIMULATION else "azure",
            "agents": [a for a, _ in AGENT_MATRIX] + ["General"]}
