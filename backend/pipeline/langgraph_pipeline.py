import os
import time
import requests
import operator
import re
from typing import TypedDict, Annotated, List

from django.conf import settings

try:
    from langchain_groq import ChatGroq
except Exception:  # pragma: no cover
    ChatGroq = None
from langgraph.graph import StateGraph, END


# =========================
# LLM + Embeddings
# =========================
MODEL_GENE = os.getenv("RAG_MODEL_GENE", "llama-3.1-8b-instant")
MODEL_PATHWAY = os.getenv("RAG_MODEL_PATHWAY", "llama-3.1-8b-instant")
MODEL_DRUG = os.getenv("RAG_MODEL_DRUG", "mixtral-8x7b-32768")
MODEL_LITERATURE = os.getenv("RAG_MODEL_LITERATURE", "mixtral-8x7b-32768")
MODEL_AGGREGATOR = os.getenv("RAG_MODEL_AGGREGATOR", "llama-3.1-8b-instant")

MODEL_FALLBACKS = [
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]


def _build_llm(model_name):
    # Create lazily so env/.env changes take effect after restart
    if ChatGroq is None:
        raise RuntimeError(
            "langchain-groq is not installed. Install it and set GROQ_API_KEY."
        )
    groq_api_key = getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise RuntimeError("Missing GROQ_API_KEY for Groq access.")
    return ChatGroq(
        api_key=groq_api_key,
        model=model_name,
        temperature=0.1,
        max_tokens=RAG_MAX_OUTPUT_TOKENS
    )


def _invoke_with_model(model_name, prompt):
    # Try requested model first, then safe fallbacks if model is unavailable/decommissioned.
    candidates = [model_name] + [m for m in MODEL_FALLBACKS if m != model_name]
    last_err = None

    for candidate in candidates:
        for attempt in range(RAG_RETRY_COUNT):
            try:
                return _build_llm(candidate).invoke(prompt)
            except Exception as err:
                last_err = err
                err_str = str(err).lower()
                is_rate_limit = (
                    "429" in err_str
                    or "rate limit" in err_str
                    or "rate_limit_exceeded" in err_str
                    or "tokens per minute" in err_str
                )
                is_model_unavailable = (
                    "model_decommissioned" in err_str
                    or "decommissioned" in err_str
                    or "not found" in err_str
                    or "does not exist" in err_str
                )

                if is_model_unavailable:
                    # Move to next candidate model immediately.
                    break

                if not is_rate_limit or attempt == (RAG_RETRY_COUNT - 1):
                    raise

                wait_s = RAG_RETRY_SLEEP_SEC
                m = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", err_str)
                if m:
                    wait_s = max(wait_s, float(m.group(1)) + 0.75)
                time.sleep(wait_s)

    raise RuntimeError(
        f"Groq invocation failed for models {candidates}. Last error: {last_err}"
    )

API_DELAY = float(os.getenv("RAG_API_DELAY", "0.1"))
RAG_MAX_OUTPUT_TOKENS = int(os.getenv("RAG_MAX_OUTPUT_TOKENS", "420"))
RAG_MAX_INPUT_CHARS = int(os.getenv("RAG_MAX_INPUT_CHARS", "380"))
RAG_RETRY_COUNT = int(os.getenv("RAG_RETRY_COUNT", "3"))
RAG_RETRY_SLEEP_SEC = float(os.getenv("RAG_RETRY_SLEEP_SEC", "7"))
RAG_LLM_DELAY_SEC = float(os.getenv("RAG_LLM_DELAY_SEC", "1.5"))
RAG_LITERATURE_CHUNK_CHARS = int(os.getenv("RAG_LITERATURE_CHUNK_CHARS", "220"))


# =========================
# Safe request helper
# =========================
def safe_request(url, params=None):
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        return None


# =========================
# API Fetchers
# =========================
def fetch_ncbi_gene(gene):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "gene",
        "term": gene,
        "retmode": "json"
    }
    res = safe_request(url, params=params)

    if not res or not res["esearchresult"]["idlist"]:
        return None

    gene_id = res["esearchresult"]["idlist"][0]

    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    return safe_request(summary_url, params={
        "db": "gene",
        "id": gene_id,
        "retmode": "json"
    })


def fetch_pubmed(gene, cancer_term="lung cancer"):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    params = {
        "db": "pubmed",
        "term": f"{gene} {cancer_term}",
        "retmax": 5,
        "retmode": "json"
    }

    res = safe_request(url, params=params)
    if not res:
        return []
    return res.get("esearchresult", {}).get("idlist", [])


def fetch_ebi_protein(gene):
    url = f"https://www.ebi.ac.uk/proteins/api/proteins/{gene}"

    headers = {"Accept": "application/json"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        pass

    return None


def fetch_drugbank(gene):
    url = f"https://dgidb.org/api/v2/interactions.json?genes={gene}"

    res = safe_request(url)

    if not res:
        return []

    drugs = []

    for match in res.get("matchedTerms", []):
        for interaction in match.get("interactions", []):
            drugs.append(interaction.get("drugName"))

    return drugs


def normalize_data(gene, ncbi, ebi, papers):
    return {
        "gene": gene,
        "gene_summary": str(ncbi)[:500] if ncbi else "",
        "protein_info": str(ebi)[:500] if ebi else "",
        "papers": papers[:5]
    }


def _clip_text(value, limit=RAG_MAX_INPUT_CHARS):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit]


def _compact_list(values, max_items=3):
    items = [str(v).strip() for v in (values or []) if str(v).strip()]
    return ", ".join(items[:max_items]) if items else "none"


def _normalize_agent_output(text, max_lines):
    cleaned = _sanitize_text(text)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines) if lines else cleaned
    return "\n".join(lines[:max_lines])


def _chunk_text(value, chunk_chars=RAG_LITERATURE_CHUNK_CHARS):
    text = str(value or "").strip()
    if not text:
        return []
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + chunk_chars])
        i += chunk_chars
    return chunks


def _build_evidence_context(state):
    return f"""
Evidence payload:
- NCBI: {'yes' if state.get('ncbi_raw') else 'no'} | {_clip_text(state.get('ncbi_raw') or 'N/A', 220)}
- PubMed PMIDs: {_compact_list(state.get('papers'), 3)}
- EBI: {'yes' if state.get('ebi_raw') else 'no'} | {_clip_text(state.get('ebi_raw') or 'N/A', 220)}
- DGIdb hits: {_compact_list(state.get('drugbank_hits'), 3)}
""".strip()


# =========================
# State Schema
# =========================
class AgentState(TypedDict):
    gene: str
    shap_score: float
    cancer_type: str
    cancer_term: str
    drug_candidates: List[str]
    top_genes: List[str]
    top_drugs: List[str]
    papers: List[str]
    drugbank_hits: List[str]
    ncbi_raw: str
    ebi_raw: str

    gene_context: str
    pathway_context: str
    drug_context: str
    literature_context: str

    gene_report: str
    pathway_report: str
    drug_report: str
    literature_report: str

    final_report: str
    messages: Annotated[List, operator.add]


def _sanitize_text(text):
    if not text:
        return ""
    # Remove markdown bold markers to keep output plain text.
    return text.replace("**", "").strip()


def _normalize_cancer_type(value):
    return "colorectal" if str(value or "").strip().lower() == "colorectal" else "lung"


def _cancer_term(cancer_type):
    return "colorectal cancer" if cancer_type == "colorectal" else "lung cancer"


def _agent_prompt(state, agent_name, focus, role_rules):
    evidence_context = _build_evidence_context(state)
    return f"""
You are {agent_name} in a multi-agent biomarker validation pipeline.
Return plain text only. Do not use markdown bold markers or asterisks.
Be concise and role-specific.

Use exactly this structure:
Reasoning:
- exactly 3 points, each 12-22 words
- each point must cover a different idea

Validation:
- Top gene being validated: {state['gene']}
- SHAP signal from upstream XAI: {state['shap_score']}
- Top genes from previous pipeline steps: [{_compact_list(state['top_genes'], 3)}]
- Top drugs from previous pipeline steps: [{_compact_list(state['top_drugs'], 3)}]
- Clinically plausible: yes/no, reason: one short sentence
- Output exactly these 10 lines total:
  1) Reasoning:
  2) - point 1
  3) - point 2
  4) - point 3
  5) Validation:
  6) - Top gene being validated: ...
  7) - SHAP signal from upstream XAI: ...
  8) - Top genes from previous pipeline steps: ...
  9) - Top drugs from previous pipeline steps: ...
  10) - Clinically plausible: yes/no, reason: ...
- Do not output any extra lines.

Evidence-use policy (mandatory):
1) First, use the Evidence payload from pipeline APIs.
2) If evidence is missing, use model-derived multi-source knowledge briefly (NCBI/PubMed/UniProt/DGIdb).

Evidence payload:
{evidence_context}

Focus for this agent:
{focus}

Role-specific rules (must follow):
{role_rules}
""".strip()


# =========================
# Agents
# =========================
def gene_agent(state):
    cancer_term = state.get("cancer_term", "lung cancer")
    prompt = _agent_prompt(
        state,
        "Gene Agent",
        f"Analyze the biological role of {state['gene']} in {cancer_term} progression and biomarker relevance.",
        "- Focus on gene function and biomarker relevance; avoid pathway/drug details."
    )
    result = _invoke_with_model(MODEL_GENE, prompt)
    state["gene_report"] = _normalize_agent_output(result.content, 10)
    time.sleep(RAG_LLM_DELAY_SEC)
    return state


def pathway_agent(state):
    prompt = _agent_prompt(
        state,
        "Pathway Agent",
        f"Explain key signaling pathways involving {state['gene']} and how they support or weaken biomarker confidence.",
        "- Focus on pathway/network context; avoid repeating chromosome/location facts."
    )
    result = _invoke_with_model(MODEL_PATHWAY, prompt)
    state["pathway_report"] = _normalize_agent_output(result.content, 10)
    time.sleep(RAG_LLM_DELAY_SEC)
    return state


def drug_agent(state):
    prompt = _agent_prompt(
        state,
        "Drug Agent",
        f"Evaluate therapeutic relevance of drugs for {state['gene']}: {state['drug_candidates'][:3]}.",
        "- Focus on targetability/actionability; if no drugs, state this clearly and keep concise."
    )
    result = _invoke_with_model(MODEL_DRUG, prompt)
    state["drug_report"] = _normalize_agent_output(result.content, 10)
    time.sleep(RAG_LLM_DELAY_SEC)
    return state


def literature_agent(state):
    cancer_term = state.get("cancer_term", "lung cancer")
    evidence_seed = " | ".join([
        _clip_text(state.get("ncbi_raw", ""), 260),
        _clip_text(state.get("ebi_raw", ""), 260),
        _compact_list(state.get("papers", []), 5),
    ])
    chunks = _chunk_text(evidence_seed, RAG_LITERATURE_CHUNK_CHARS)[:3]
    chunk_notes = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_prompt = f"""
You are Literature Agent using chunked evidence analysis.
Gene: {state['gene']}
Chunk {idx}/{len(chunks)}:
{chunk}
Return exactly 2 short bullet points on evidence strength and conflicts.
""".strip()
        chunk_result = _invoke_with_model(MODEL_LITERATURE, chunk_prompt)
        chunk_notes.append(_sanitize_text(chunk_result.content))
        time.sleep(RAG_LLM_DELAY_SEC)

    prompt = _agent_prompt(
        state,
        "Literature Agent",
        f"Summarize literature support and conflicting evidence for {state['gene']} in {cancer_term}. Chunk insights: {' | '.join(chunk_notes[:3])}",
        "- Focus on evidence strength/consistency/conflicts; avoid deep drug mechanism claims."
    )
    result = _invoke_with_model(MODEL_LITERATURE, prompt)
    state["literature_report"] = _normalize_agent_output(result.content, 10)
    time.sleep(RAG_LLM_DELAY_SEC)
    return state


def aggregator_agent(state):
    evidence_context = _build_evidence_context(state)
    prompt = f"""
    You are Aggregator Agent.
    Return plain text only and do not use markdown bold markers or asterisks.
    Create a final integrated report with this structure:
    Reasoning:
    - exactly 3 concise synthesis points, each 12-22 words
    Validation:
    - Explicitly validate top gene {state['gene']} against top genes {state['top_genes'][:3]}
    - Explicitly validate top drugs {state['top_drugs'][:3]} and per-gene candidates {state['drug_candidates'][:3]}
    - Final confidence statement for biomarker and therapeutic plausibility
    - For each major claim, mark API-backed or Model-derived multi-source.
    - Output exactly these 8 lines total:
      1) Reasoning:
      2) - synthesis point 1
      3) - synthesis point 2
      4) - synthesis point 3
      5) Validation:
      6) - Top gene/drug validation: ...
      7) - Final confidence statement: ...
      8) - Evidence basis: API-backed and/or model-derived multi-source
    - Do not output any extra lines.

    Evidence-use policy:
    1) Prioritize Evidence payload from pipeline APIs.
    2) If any payload is missing, supplement from model-based multi-source retrieval (NCBI/PubMed/EBI/DGIdb/DrugBank/review literature).
    3) Mention source names used for supplemented claims.

    Evidence payload:
    {evidence_context}

    Gene report:
    {_clip_text(state['gene_report'])}

    Pathway report:
    {_clip_text(state['pathway_report'])}

    Drug report:
    {_clip_text(state['drug_report'])}

    Literature report:
    {_clip_text(state['literature_report'])}
    """
    result = _invoke_with_model(MODEL_AGGREGATOR, prompt)
    state["final_report"] = _normalize_agent_output(result.content, 8)
    return state


# =========================
# Graph
# =========================
graph = StateGraph(AgentState)

graph.add_node("gene_agent", gene_agent)
graph.add_node("pathway_agent", pathway_agent)
graph.add_node("drug_agent", drug_agent)
graph.add_node("literature_agent", literature_agent)
graph.add_node("aggregator_agent", aggregator_agent)

graph.set_entry_point("gene_agent")

graph.add_edge("gene_agent", "pathway_agent")
graph.add_edge("pathway_agent", "drug_agent")
graph.add_edge("drug_agent", "literature_agent")
graph.add_edge("literature_agent", "aggregator_agent")
graph.add_edge("aggregator_agent", END)

app = graph.compile()


# =========================
# Runner
# =========================
def run_langgraph_pipeline(gene, shap_score, drug_candidates, top_genes=None, top_drugs=None, cancer_type="lung"):
    normalized_cancer_type = _normalize_cancer_type(cancer_type)
    cancer_term = _cancer_term(normalized_cancer_type)
    ncbi = fetch_ncbi_gene(gene)
    time.sleep(API_DELAY)

    ebi = fetch_ebi_protein(gene)
    time.sleep(API_DELAY)

    papers = fetch_pubmed(gene, cancer_term)
    time.sleep(API_DELAY)
    drugbank_hits = fetch_drugbank(gene)

    context = normalize_data(gene, ncbi, ebi, papers)

    initial_state = {
        "gene": gene,
        "shap_score": shap_score,
        "cancer_type": normalized_cancer_type,
        "cancer_term": cancer_term,
        "drug_candidates": drug_candidates,
        "top_genes": top_genes or [],
        "top_drugs": top_drugs or [],
        "papers": papers[:5],
        "drugbank_hits": drugbank_hits[:5],
        "ncbi_raw": str(ncbi)[:600] if ncbi else "",
        "ebi_raw": str(ebi)[:600] if ebi else "",
        "gene_context": str(context),
        "pathway_context": "",
        "drug_context": "",
        "literature_context": "",
        "gene_report": "",
        "pathway_report": "",
        "drug_report": "",
        "literature_report": "",
        "final_report": "",
        "messages": []
    }

    result = app.invoke(initial_state)
    sections = [
        {"title": "Gene Agent", "content": _sanitize_text(result.get("gene_report", ""))},
        {"title": "Pathway Agent", "content": _sanitize_text(result.get("pathway_report", ""))},
        {"title": "Drug Agent", "content": _sanitize_text(result.get("drug_report", ""))},
        {"title": "Literature Agent", "content": _sanitize_text(result.get("literature_report", ""))},
        {"title": "Aggregator Agent", "content": _sanitize_text(result.get("final_report", ""))},
    ]

    return {
        "final_report": _sanitize_text(result.get("final_report", "")),
        "sections": sections,
    }