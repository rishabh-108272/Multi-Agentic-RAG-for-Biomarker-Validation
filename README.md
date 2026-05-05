# Multi-Agentic RAG for Biomarker Validation

## Overview

This project is an end-to-end system designed for biomarker-driven cancer analysis and therapeutic exploration, with a strong emphasis on validation and reasoning. It processes patient data through a structured pipeline to predict cancer subtypes, identify important biological features, map them to relevant genes, and explore potential drug candidates. The central component of the system is a Multi-Agentic RAG (Retrieval-Augmented Generation) validator, which acts as an intelligent reasoning layer on top of the pipeline. It critically evaluates the intermediate results by gathering supporting evidence from biomedical literature and domain knowledge sources, ensuring that predictions and recommendations are not only data-driven but also scientifically grounded. By combining predictive modeling, explainability, and multi-agent evidence validation, the platform produces a comprehensive, interpretable, and research-backed report to support informed decision-making in oncology.

It combines:
- A React + TypeScript frontend for CSV upload, progress tracking, and result visualization.
- A Django + Celery backend (`genix-ai-backend`) that runs a multi-step analysis pipeline.
- A multi-agent RAG stage that assembles biomedical evidence from external sources for interpretation support.

The current implementation supports lung and colorectal classifiers and persists run history for dashboard-style review.

## Repository Structure

```text
Multi-Agentic-RAG-for-Biomarker-Validation/
  README.md
  genix-ai-backend/        # Django API + async pipeline + LangGraph RAG
  project/                 # React/Vite frontend
```

### Frontend (`project`)
- `src/pages/HomePage.tsx`: upload and analysis trigger flow.
- `src/pages/ResultsPage.tsx`: status polling and result rendering.
- `src/lib/api.ts`: HTTP client for backend endpoints.
- `supabase/`: migration scripts and Supabase-related assets.

### Backend (`genix-ai-backend`)
- `pipeline/views.py`: REST endpoints for upload, status, results, summaries, and cleanup.
- `pipeline/tasks.py`: orchestration for the 7-step analysis pipeline.
- `pipeline/ml_classifier.py`: remote subtype classification calls.
- `pipeline/xai_engine.py`: SHAP/LIME-style explainability and feature ranking.
- `pipeline/drug_engine.py`: DGIdb-driven drug candidate retrieval and ranking.
- `pipeline/langgraph_pipeline.py`: multi-agent RAG evidence synthesis.
- `pipeline/models.py`: persisted entities (`PatientAnalysis`, `XAIResult`, `DrugCandidate`, `AgentReport`, `PatientSummaryReport`).

## Core Pipeline

Each analysis run follows these stages:

1. **Input parsing**: CSV input is normalized into a model-ready feature vector.
2. **Subtype prediction**: classifier assigns cancer subtype and confidence.
3. **Explainability**: feature importance is generated (SHAP/LIME strategy with high-dimensional fallbacks).
4. **Gene mapping**: feature identifiers are mapped into biologically interpretable genes.
5. **Drug repurposing**: gene targets are matched to candidate compounds through DGIdb.
6. **Multi-agent RAG**: specialized agents gather and consolidate pathway, literature, and intervention evidence.
7. **Summary synthesis**: patient-level summary and structured outputs are stored and returned to the client.


## Technology Stack

### Frontend
- React 18
- TypeScript
- Vite
- Tailwind CSS
- React Router
- Recharts
- Supabase JS client

### Backend
- Python 3.11
- Django + Django REST Framework
- Celery
- Gunicorn
- Channels
- NumPy / Pandas / Scikit-learn
- SHAP / LIME
- LangChain / LangGraph

### External Services
- Hugging Face Spaces endpoints (classification)
- Groq LLM API (agent reasoning)
- DGIdb (drug-gene interaction data)
- NCBI/PubMed and EBI endpoints (literature and biological context)

## Local Setup

## 1) Backend setup (`genix-ai-backend`)

```bash
cd genix-ai-backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Backend runs at `http://127.0.0.1:8000` by default.

## 2) Frontend setup (`project`)

```bash
cd project
npm install
npm run dev
```

Frontend runs on Vite default host/port (typically `http://127.0.0.1:5173`).

## 3) Optional background workers

If Celery + Redis are configured, start workers separately.  
If unavailable, the backend can fall back to thread-based background execution depending on environment settings.


## Data Persistence

The backend currently uses Django's default SQLite database (`db.sqlite3`) unless overridden.

Persisted entities include:
- Analysis metadata and raw/normalized outputs
- Explainability artifacts
- Drug candidate lists
- Agent-generated report sections
- Final summary report objects


## License

Copyright (c) 2026 Rishabh Verma

All Rights Reserved.

This software and associated documentation files (the "Software") are proprietary. No part of this Software may be copied, modified, published, distributed, sublicensed, or used for commercial or non-commercial purposes without explicit written permission from the copyright holder.
