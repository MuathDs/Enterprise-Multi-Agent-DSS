"""
DataMaster-DSS — Secure retrieval module (Azure AI Search)
===========================================================
Implements the RAG retrieval tier the thesis describes (§2.2, §5.1, §5.3),
with data sovereignty enforced in TWO layers, not one:

  Layer 1 — PHYSICAL ISOLATION (index-per-department, Figure 5.1):
      Each department has its own index (dss-finance-index, dss-hr-index, ...).
      A query can only ever touch the index of the agent it was routed to,
      and main.py's enforce_scope() has already verified the user may use
      that agent. Cross-departmental traversal is structurally impossible,
      not merely filtered out.

  Layer 2 — DOCUMENT-LEVEL SECURITY TRIMMING (within an index):
      Every document carries a `group_ids` collection. Every query carries
      an OData filter built from the user's group claims:
          group_ids/any(g: search.in(g, 'Finance,Finance-Confidential', ','))
      Azure AI Search evaluates the filter BEFORE ranking, so unauthorized
      documents never enter the candidate set — they are not retrieved and
      then hidden; they are never retrieved. In production the group values
      are Microsoft Entra ID group object-IDs read from the JWT `groups`
      claim; in the demo they are the User.scopes strings.

Why both layers: an index-per-department design alone makes every analyst
see everything in their department; trimming alone (single shared index)
makes isolation a filter bug away from a breach. Together they satisfy the
thesis's "zero data leakage" claim in a way you can defend in an interview.

Runs in SIMULATION mode without Azure credentials — and the simulation
store enforces the exact same filter semantics, so security trimming is
demonstrable locally (see __main__ at the bottom).

Env for live mode:
  AZURE_SEARCH_ENDPOINT      https://<service>.search.windows.net
  AZURE_SEARCH_API_KEY       admin key (ingestion) or query key (retrieval)
  AZURE_OPENAI_ENDPOINT      (optional) enables vector/hybrid search
  AZURE_OPENAI_API_KEY
  AZURE_OPENAI_EMBED_DEPLOYMENT   e.g. text-embedding-3-small
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Mode detection — mirrors main.py's SIMULATION convention
# ---------------------------------------------------------------------------
SEARCH_SIMULATION = not (os.getenv("AZURE_SEARCH_ENDPOINT") and os.getenv("AZURE_SEARCH_API_KEY"))
EMBEDDINGS_ENABLED = bool(os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT") and os.getenv("AZURE_OPENAI_API_KEY"))

DEPARTMENTS = ["Finance", "HR", "Strategy", "Legal", "IT", "Ops", "Sales"]
EMBED_DIMENSIONS = int(os.getenv("DSS_EMBED_DIMENSIONS", "1536"))


def index_name(department: str) -> str:
    """Layer 1: one index per department. dss-finance-index, dss-hr-index, ..."""
    if department not in DEPARTMENTS:
        raise ValueError(f"No index exists for department '{department}'.")
    return f"dss-{department.lower()}-index"


# ---------------------------------------------------------------------------
# Retrieved record — the unit the generation tier consumes
# ---------------------------------------------------------------------------
@dataclass
class RetrievedRecord:
    doc_id: str
    content: str
    source: str            # citation string, thesis format: "Finance_DB / Table: Q1_2024"
    department: str
    score: float = 0.0
    group_ids: list[str] = field(default_factory=list)

    @property
    def citation(self) -> str:
        return self.source


# ---------------------------------------------------------------------------
# Layer 2: the security filter
# ---------------------------------------------------------------------------
def build_security_filter(user_groups: list[str]) -> str:
    """OData filter for document-level trimming.

    Uses search.in with an explicit delimiter so group names containing
    spaces are safe. Single quotes are escaped per OData rules ('' = ').
    A user with no groups gets a filter that matches nothing — deny by
    default, never fail open.
    """
    if not user_groups:
        return "group_ids/any(g: search.in(g, '', '|'))"  # matches no documents
    safe = [g.replace("'", "''") for g in user_groups]
    joined = "|".join(safe)
    return f"group_ids/any(g: search.in(g, '{joined}', '|'))"


# ---------------------------------------------------------------------------
# Embeddings (optional — enables hybrid search)
# ---------------------------------------------------------------------------
async def embed_query(text: str) -> Optional[list[float]]:
    if not EMBEDDINGS_ENABLED:
        return None
    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
    )
    resp = await client.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBED_DEPLOYMENT"], input=text,
    )
    return resp.data[0].embedding


# ---------------------------------------------------------------------------
# SIMULATION STORE — same schema, same filter semantics, zero Azure required
# ---------------------------------------------------------------------------
# Note the *-Confidential documents: demo-analyst (groups: Finance, General)
# cannot retrieve them; demo-admin can. That asymmetry IS the security-
# trimming demo for the thesis defense and the LinkedIn video.
_SIM_DOCS: dict[str, list[dict]] = {
    "Finance": [
        {"doc_id": "fin-001", "group_ids": ["Finance"],
         "source": "Finance_DB / Table: Q1_2024",
         "content": "Q1 2024 approved budget: 2,500,000 SAR total. IT infrastructure "
                    "allocation: 600,000 SAR (24%). Utilization to date: 80%."},
        {"doc_id": "fin-002", "group_ids": ["Finance"],
         "source": "ERP Record #2024-Q1 / Centralized Ledger",
         "content": "Cloud infrastructure spending Q1: 480,000 SAR against the "
                    "600,000 SAR IT allocation. Remaining headroom: 120,000 SAR."},
        {"doc_id": "fin-901", "group_ids": ["Finance-Confidential"],
         "source": "Finance_DB / Restricted: M&A_Reserve",
         "content": "CONFIDENTIAL: 1,200,000 SAR reserved for the pending Jazan "
                    "acquisition. Board-eyes-only until Q3 announcement."},
    ],
    "HR": [
        {"doc_id": "hr-001", "group_ids": ["HR"],
         "source": "HR_DB / Policy: Hiring_2026",
         "content": "2026 hiring plan: 3 AI Engineers, base salary 12,000 SAR/month, "
                    "Saudization tier compliant. Annual leave: 25 working days."},
        {"doc_id": "hr-002", "group_ids": ["HR"],
         "source": "HR_DB / Policy: Leave_2026",
         "content": "Leave policy: 25 days annual, 5 days emergency, parental leave "
                    "per 2026 Saudi Labor Law amendments."},
    ],
    "Strategy": [
        {"doc_id": "str-001", "group_ids": ["Strategy"],
         "source": "Strategy_DB / Memo: Board_Q3",
         "content": "Board directive: consolidate southern-region operations before "
                    "the Q3 review; align expansion with Vision 2030 digital targets."},
    ],
    "Legal": [
        {"doc_id": "leg-001", "group_ids": ["Legal"],
         "source": "Legal_DB / Register: Contracts_2026",
         "content": "All active contracts reviewed and compliant with the 2026 Saudi "
                    "Labor Law amendments. Next audit: October 2026."},
    ],
    "IT": [
        {"doc_id": "it-001", "group_ids": ["IT"],
         "source": "IT_DB / Log: SecOps_Current",
         "content": "Firewall ruleset update in progress. Azure license renewal on "
                    "schedule. No open critical incidents."},
        {"doc_id": "it-901", "group_ids": ["IT-Confidential"],
         "source": "IT_DB / Restricted: Pentest_2026",
         "content": "CONFIDENTIAL: Q2 penetration test found 2 high-severity findings "
                    "in the VPN gateway; remediation due before July 15."},
    ],
    "Ops": [
        {"doc_id": "ops-001", "group_ids": ["Ops"],
         "source": "Ops_DB / Project: Abha_Branch",
         "content": "Abha branch setup on schedule; budget 400,000 SAR; go-live "
                    "targeted for Q4."},
    ],
    "Sales": [
        {"doc_id": "sal-001", "group_ids": ["Sales"],
         "source": "Sales_DB / Plan: SR_Targets",
         "content": "Target: 15% market share in the Southern Region by year-end; "
                    "pipeline currently at 11.2%."},
    ],
}


def _sim_search(department: str, query: str, user_groups: list[str], top: int) -> list[RetrievedRecord]:
    """Keyword-overlap scoring, but the SECURITY SEMANTICS are identical to
    the live path: group check happens before scoring, deny-by-default."""
    allowed = set(user_groups)
    q_terms = {t for t in query.lower().split() if len(t) > 2}
    results = []
    for doc in _SIM_DOCS.get(department, []):
        if not allowed.intersection(doc["group_ids"]):
            continue  # trimmed BEFORE ranking, exactly like the OData filter
        overlap = sum(1 for t in q_terms if t in doc["content"].lower())
        results.append(RetrievedRecord(
            doc_id=doc["doc_id"], content=doc["content"], source=doc["source"],
            department=department, score=float(overlap), group_ids=doc["group_ids"],
        ))
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top] if any(r.score > 0 for r in results) else results[:min(top, 2)]


# ---------------------------------------------------------------------------
# THE PUBLIC API — called from main.py's chat endpoint
# ---------------------------------------------------------------------------
async def secure_retrieve(
    department: str,
    query: str,
    user_groups: list[str],
    top: int = 4,
) -> list[RetrievedRecord]:
    """Security-trimmed retrieval against the department's isolated index.

    Preconditions (enforced upstream in main.py, re-stated here so this
    module is safe even if called directly):
      * `department` must be a real department — index_name() raises otherwise.
      * The caller must already have passed enforce_scope(); we still apply
        the group filter, so a scope bug upstream cannot leak documents.
    """
    if department == "General":
        return []  # the general assistant has no knowledge base by design

    if SEARCH_SIMULATION:
        return _sim_search(department, query, user_groups, top)

    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.aio import SearchClient
    from azure.search.documents.models import VectorizedQuery

    client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=index_name(department),                    # Layer 1
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"]),
    )
    security_filter = build_security_filter(user_groups)      # Layer 2

    vector_queries = []
    vector = await embed_query(query)
    if vector is not None:
        vector_queries.append(VectorizedQuery(
            vector=vector, k_nearest_neighbors=top, fields="content_vector",
        ))

    records: list[RetrievedRecord] = []
    async with client:
        results = await client.search(
            search_text=query,                 # keyword leg (BM25)
            vector_queries=vector_queries,     # vector leg -> hybrid via RRF
            filter=security_filter,            # trimming happens pre-ranking
            top=top,
            select=["doc_id", "content", "source", "group_ids"],
        )
        async for r in results:
            records.append(RetrievedRecord(
                doc_id=r["doc_id"], content=r["content"], source=r["source"],
                department=department, score=r["@search.score"],
                group_ids=r.get("group_ids", []),
            ))
    return records


def format_context(records: list[RetrievedRecord]) -> str:
    """Grounding block injected into the agent's prompt (thesis §6.2 stage 2).
    Numbered so the model can cite [1], [2] and the frontend can map them
    back to the Evidence Layer citation chips."""
    if not records:
        return "No records were retrieved. You must answer: 'Information not found'."
    lines = ["Retrieved organizational records (answer ONLY from these):"]
    for i, r in enumerate(records, 1):
        lines.append(f"[{i}] (source: {r.source})\n{r.content}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# INGESTION — index schema + upload, for standing up the live indexes
# ---------------------------------------------------------------------------
def ensure_department_index(department: str) -> None:
    """Create (or update) the department's index with the security-trimming
    schema. group_ids is filterable (required for trimming) and retrievable
    only for debugging — set hidden=True in production."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration, SearchableField, SearchField,
        SearchFieldDataType, SearchIndex, SimpleField, VectorSearch,
        VectorSearchProfile,
    )

    fields = [
        SimpleField(name="doc_id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source", type=SearchFieldDataType.String),
        SimpleField(
            name="group_ids",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,   # <- this is what makes trimming possible
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True, vector_search_dimensions=EMBED_DIMENSIONS,
            vector_search_profile_name="dss-vector-profile",
        ),
    ]
    index = SearchIndex(
        name=index_name(department),
        fields=fields,
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="dss-hnsw")],
            profiles=[VectorSearchProfile(
                name="dss-vector-profile", algorithm_configuration_name="dss-hnsw",
            )],
        ),
    )
    client = SearchIndexClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"]),
    )
    client.create_or_update_index(index)


async def upload_records(department: str, docs: list[dict]) -> None:
    """Upload documents. Each doc: {doc_id, content, source, group_ids}.
    Embeds content if an embedding deployment is configured."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.aio import SearchClient

    payload = []
    for d in docs:
        item = dict(d)
        vec = await embed_query(d["content"])
        if vec is not None:
            item["content_vector"] = vec
        payload.append(item)

    client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=index_name(department),
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"]),
    )
    async with client:
        await client.upload_documents(documents=payload)


async def seed_all_indexes() -> None:
    """One-shot bootstrap: create every department index and load the sample
    corpus. Usage:  python -c 'import asyncio, retrieval; asyncio.run(retrieval.seed_all_indexes())'"""
    if SEARCH_SIMULATION:
        raise RuntimeError("Set AZURE_SEARCH_ENDPOINT / AZURE_SEARCH_API_KEY first.")
    for dept in DEPARTMENTS:
        ensure_department_index(dept)
        await upload_records(dept, _SIM_DOCS.get(dept, []))


# ---------------------------------------------------------------------------
# Security-trimming self-demonstration
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    async def demo():
        analyst_groups = ["Finance", "General"]                       # demo-analyst
        admin_groups = ["Finance", "Finance-Confidential", "IT",
                        "IT-Confidential", "HR", "Strategy", "Legal",
                        "Ops", "Sales", "General"]                    # demo-admin
        q = "budget reserve acquisition"
        print("Filter (analyst):", build_security_filter(analyst_groups))
        a = await secure_retrieve("Finance", q, analyst_groups)
        b = await secure_retrieve("Finance", q, admin_groups)
        print(f"\nAnalyst retrieves {len(a)} docs:", [r.doc_id for r in a])
        print(f"Admin   retrieves {len(b)} docs:", [r.doc_id for r in b])
        assert not any(r.doc_id == "fin-901" for r in a), "LEAK: analyst saw confidential doc"
        assert any(r.doc_id == "fin-901" for r in b), "Admin should see confidential doc"
        print("\nSecurity trimming verified: fin-901 (M&A reserve) visible to admin only.")

    asyncio.run(demo())
