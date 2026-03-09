# AI Restaurant Recommendation Service — Architecture

## Overview
This project is an **AI-powered restaurant recommendation service** that:
- Collects **user preferences**: **price**, **place/location**, **rating**, **cuisine**
- Uses the Hugging Face dataset **`ManikaSaini/zomato-restaurant-recommendation`** as the primary restaurant catalog
- Retrieves the most relevant restaurants and calls an **LLM** to produce **clear, structured recommendations** (with reasons and trade-offs)

Primary goals:
- **Relevance**: recommendations match the user’s constraints and intent
- **Clarity**: results are easy to compare and act on
- **Safety**: the system does not hallucinate restaurants outside the dataset unless explicitly configured

Non-goals (initially):
- Real-time availability, booking, live pricing, or delivery ETA
- Multi-city geospatial routing/ETA optimization

## Key Requirements
### Inputs
- **price**: budget range or category (e.g., “low”, “medium”, “high” or numeric range)
- **place**: city/area/locality (string; optionally later lat/long)
- **rating**: minimum rating threshold or preference (e.g., “>= 4.2”)
- **cuisine**: one or multiple cuisines (e.g., “Italian”, “South Indian”)

### Outputs
- A **ranked list** of recommended restaurants with:
  - name
  - locality/city
  - cuisine(s)
  - cost indicator / price range (as available in dataset)
  - rating (as available)
  - **why it matches** the user’s preferences
  - optional: “best for” tags (family, date, quick bite) if derivable from dataset fields

## High-Level System Design
### Core Components
- **Client** (CLI / simple web UI): captures user preferences and displays recommendations
- **API service** (recommendation backend):
  - validation & normalization of preferences
  - retrieval + ranking
  - LLM orchestration
  - response formatting
- **Data layer**:
  - dataset ingestion from Hugging Face
  - cleaning / schema normalization
  - storage for queryable restaurant records
  - optional: vector index for semantic retrieval
- **Observability & evaluation**:
  - logging (requests, retrieval results, LLM outputs)
  - offline evaluation for quality and regressions

### Recommended Architecture Pattern
Use a **Retrieval-Augmented Generation (RAG)** style pipeline:
1. **Filter** candidates deterministically (place, price, rating, cuisine) from structured fields
2. **Rank** candidates (rule-based + optional embeddings for fuzzy matches)
3. **Ground** the LLM with the top-K restaurants and ask it to write the final recommendations

This prevents hallucinations and keeps the LLM focused on explanation and clarity.

## Data Source & Data Model
### Dataset
- Source: Hugging Face dataset **`ManikaSaini/zomato-restaurant-recommendation`**
- Used as a read-only “catalog” for restaurants and metadata.

### Data Contracts (Conceptual)
Define a canonical restaurant record regardless of dataset quirks:

- `restaurant_id`: stable id if present, else derived hash
- `name`
- `city`
- `locality` / `area`
- `address` (optional)
- `cuisines`: list of strings
- `average_cost_for_two` or `price_category` (dataset-dependent)
- `rating`: float (dataset-dependent)
- `votes` / `reviews_count` (optional)
- `url` (optional)
- `raw`: original row fields retained for traceability (optional)

### Storage Options
Pick based on project scope:
- **Phase 1–2**: local file cache (parquet/csv) + in-memory filtering
- **Phase 3+**: lightweight DB (SQLite/Postgres) for structured filters
- **Phase 3+ (optional)**: vector DB/index (FAISS / Chroma) for semantic retrieval

## Request/Response Contracts (Conceptual)
### Request
```json
{
  "price": "low|medium|high or numeric_range",
  "place": "string",
  "min_rating": 4.0,
  "cuisines": ["Italian", "Mexican"],
  "top_k": 5
}
```

### Response
```json
{
  "recommendations": [
    {
      "name": "Restaurant A",
      "place": "Koramangala, Bengaluru",
      "cuisines": ["Italian", "Pizza"],
      "price": "medium",
      "rating": 4.3,
      "why_recommended": [
        "Matches your Italian preference",
        "Within your medium budget",
        "Rating above 4.0 near Koramangala"
      ],
      "consider_if": "Good for casual dining; may be busy on weekends."
    }
  ],
  "explanation": "How the system interpreted preferences and ranked results.",
  "data_source": "hf://datasets/ManikaSaini/zomato-restaurant-recommendation"
}
```

## Recommendation & Ranking Logic
### Deterministic Filtering (must-have constraints)
- **Place filter**: exact/normalized match on city/locality; fallback to fuzzy match (optional)
- **Cuisine filter**: intersection with requested cuisines (at least one match), configurable strictness
- **Rating filter**: \(rating \ge min\_rating\) when rating is available
- **Price filter**: map user budget to dataset field(s) (range/bins)

### Ranking (nice-to-have preferences)
Combine signals:
- rating (normalized)
- votes/reviews count (confidence weight, if available)
- cuisine match score (exact matches > partial)
- locality match score (exact > partial/fuzzy)
- optional: semantic similarity between user “free-text intent” and restaurant description (if available)

Produce a final score:
\[
score = w_r \cdot rating + w_v \cdot popularity + w_c \cdot cuisineMatch + w_p \cdot placeMatch + w_b \cdot budgetFit
\]
Weights can be tuned offline in later phases.

## LLM Orchestration
### LLM Responsibilities
The LLM should:
- convert ranked candidates into **human-friendly** recommendations
- provide **reasons** and **trade-offs**
- keep content grounded in provided restaurant records

The LLM must NOT:
- invent restaurants not included in the provided candidate list
- claim facts not present in the grounded data (e.g., “live wait time”)

### Prompting Strategy (Grounded)
Provide the LLM:
- user preferences (normalized)
- top-K candidate restaurant records as structured JSON
- explicit instructions to only use provided data
- required output schema (JSON)

### Guardrails
- **Schema validation** for LLM output (JSON schema / pydantic style)
- **Source-of-truth constraint**: recommendations must reference an input candidate id/name
- **Fallback**: if LLM fails validation, return a templated non-LLM response using retrieval results

## End-to-End Data Flow
1. Client sends preferences to API
2. API validates and normalizes preferences
3. API queries restaurant catalog:
   - structured filtering
   - ranking
4. API selects top-K and calls LLM with grounded context
5. API validates LLM output and returns response
6. Logs are stored for evaluation (with redaction of any sensitive input)

## Security & Privacy
- Avoid collecting PII; if user input contains it, redact before logging.
- Store API keys/secrets in environment variables (never in git).
- Rate-limit LLM calls if exposed publicly.

## Observability & Quality
### Logging
- request metadata (without PII)
- retrieval candidates + scores
- LLM latency, token usage (if available)
- output validation success/failure

### Offline Evaluation
Maintain a small test set of preference queries:
- measure constraint satisfaction (place/cuisine/rating/budget)
- measure diversity (avoid repeating same chain)
- measure clarity (format completeness, readability)

## Project Phases (Milestone-Oriented)
### Phase 0 — Architecture & Contracts (this document)
**Deliverables**
- `ARCHITECTURE.md` with system design, data flow, and phase plan
- defined request/response contracts and success metrics

**Exit criteria**
- architecture reviewed; scope and guardrails agreed

### Phase 1 — Data Acquisition & Catalog Build
**Goal**
Turn the Hugging Face dataset into a reliable, queryable restaurant catalog.

**Deliverables**
- dataset loader (HF download + caching)
- schema normalization (canonical fields)
- basic statistics report (missing values, field distributions)

**Exit criteria**
- can load the dataset repeatably and produce canonical records

### Phase 2 — Deterministic Recommendation (No LLM)
**Goal**
Provide correct recommendations using filtering + ranking only.

**Deliverables**
- preference normalization (price/place/rating/cuisine)
- deterministic filter + ranking function
- minimal API endpoint or CLI interface

**Exit criteria**
- returns sensible top-K results for a test set of queries
- constraints are respected (no out-of-place or wrong cuisine results)

### Phase 3 — Add LLM for Explanation & Presentation (Grounded)
**Goal**
Use the LLM (via **Groq**) to improve clarity while keeping results grounded in retrieved restaurants.

**Deliverables**
- prompt template + output schema
- Groq LLM integration (provider wrapper + configuration)
- validator + retry/fallback behavior
- structured, user-friendly response formatting

**Exit criteria**
- LLM output passes schema validation reliably
- no hallucinated restaurants (checked via automated assertion)

### Phase 4 — Evaluation, Tuning, and Production Hardening
**Goal**
Improve quality, reliability, and operational readiness.

**Deliverables**
- offline eval suite + regression checks
- parameter tuning for ranking weights
- caching (dataset + LLM responses), rate limiting
- monitoring dashboards/alerts (basic)

**Exit criteria**
- measurable quality improvements on evaluation set
- stable performance and predictable cost

### Phase 5 — UI Page (Final)
**Goal**
Deliver a user-facing UI page to run the end-to-end experience.

**Deliverables**
- a simple UI page to enter preferences (price/place/rating/cuisine)
- results page section with ranked recommendations + “why recommended”
- “no results” UX (suggest relaxing constraints) + basic loading/error states

**Exit criteria**
- users can complete the flow end-to-end via the UI page smoothly

## Suggested Repository Layout (when you start implementation)
*(Not created yet; proposed structure for later.)*
- `docs/` (additional design notes, datasets notes)
- `data/` (cached dataset artifacts; gitignored)
- `src/`
  - `api/` (routes/controllers)
  - `core/` (ranking, normalization, contracts)
  - `llm/` (prompting, validators, providers)
  - `data/` (ingestion, schema mapping)
  - `eval/` (offline evaluation)
- `tests/`

