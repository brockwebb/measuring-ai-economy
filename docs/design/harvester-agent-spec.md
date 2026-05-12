# Design Specification: AI Economy Measurement Harvester Agent

**Project:** measuring-ai-economy  
**Handoff target:** Claude Code / Wintermute pipeline  
**Version:** 0.1.0  
**Date:** 2026-05-11  

---

## 1. Purpose

Build an autonomous harvesting agent that scrapes, fetches, and ingests documents related to **measuring AI's economic impact** — with emphasis on federal statistics, historical IT/technology measurement literature, and current AI policy/regulation. The agent deposits normalized documents into Wintermute's inbox (`~/.wintermute/inbox/`) for standard pipeline processing (triage → staging → extraction → KG ingestion).

This is a **data acquisition agent**, not an analysis tool. It finds things, fetches things, normalizes things, and hands them off. Wintermute handles triage scoring, entity extraction, and graph integration.

---

## 2. Scope

### In scope
- Federal Register: all AI-related rules, proposed rules, notices, executive orders, presidential documents (1994–present)
- Economics literature on measuring information technology / computers in the economy (Solow Paradox, productivity measurement, quality adjustment, hedonic pricing, digital economy satellite accounts)
- Historical technology measurement: electrification, telephony, railroads, containerization — how statistical agencies adapted measurement to new technologies
- Current AI measurement frameworks, indices, and adoption surveys (Census BTOS, Anthropic Economic Index, Stanford AI Index, OECD indicators)
- Federal statistical methodology: BLS productivity measurement, BEA GDP accounting changes, Census survey design for technology adoption
- NBER working papers, Fed research, BEA/BLS technical papers on measurement methodology
- Superforecasting methodology and prediction market literature (as measurement meta-framework)

### Out of scope (for now)
- OSINT, information warfare, crypto, military AI, psychological measurement (covered in research map but not priority for initial harvest)
- Building the KG itself (Wintermute handles this)
- Analysis, synthesis, or reporting
- Any scraping that requires login credentials or paid subscriptions

---

## 3. Architecture

```
┌─────────────────────────────────────────────────┐
│                  HARVEST AGENT                   │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Source    │  │ Fetcher  │  │ Normalizer    │  │
│  │ Registry │→ │ Pool     │→ │ (→ inbox/)    │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│       ↑              ↑                           │
│  ┌──────────┐  ┌──────────┐                      │
│  │ Seed     │  │ Adaptive │                      │
│  │ Lists    │  │ Expander │                      │
│  └──────────┘  └──────────┘                      │
└────────────────────┬────────────────────────────┘
                     │ drops files
                     ↓
          ~/.wintermute/inbox/
                     │
                     ↓ (Wintermute pipeline)
          triage → staging → extraction → KG
```

### Components

**Source Registry** — YAML config listing every source endpoint with its type (API, RSS, HTML scrape, bulk download), domain, cadence, and pagination strategy.

**Seed Lists** — Initial query terms, author lists, citation seeds, and known-good document IDs that bootstrap each source. Derived from the research notes already collected.

**Fetcher Pool** — Per-source fetcher modules. Each knows how to authenticate (if needed), paginate, respect rate limits, and extract raw content. Fetchers are stateless — they check `seen.db` before fetching and skip known items.

**Adaptive Expander** — Given a fetched document, extracts references, cited authors, cited institutions, and related terms. Feeds new targets back into the Source Registry as candidate queries. This is the "intelligence" — the agent follows citation chains, discovers adjacent literature, and expands the frontier. Runs as a second pass after initial fetch, not inline.

**Normalizer** — Converts fetched content into Wintermute inbox format (markdown + YAML frontmatter or raw PDF dropped into inbox). Minimal processing — just enough metadata for Wintermute's triage to work.

---

## 4. Source Specifications

### 4.1 Federal Register API

**Endpoint:** `https://www.federalregister.gov/api/v1/documents.json`  
**Auth:** None required  
**Rate limit:** Undocumented but be polite — 1 req/sec max  
**Pagination:** `page` parameter, 20 results default, 1000 max per page  
**Coverage:** 1994–present  

**Harvest strategy:**
1. Search with `conditions[term]` for AI-related terms (see seed queries below)
2. Filter by `conditions[type][]` = rule, proposed_rule, notice, presidential_document
3. Sort by `conditions[publication_date][gte]` descending (most recent first)
4. For each result: fetch full text via `full_text_xml_url` or `body_html_url`
5. Extract: document_number, title, abstract, agencies, publication_date, type, citation, full_text, PDF URL
6. Store raw JSON + extracted text as inbox item

**Seed queries (start broad, narrow adaptively):**
```yaml
federal_register_queries:
  tier_1_current:  # Run first, most recent
    - "artificial intelligence"
    - "machine learning"
    - "generative AI"
    - "automated decision"
    - "algorithmic"
    - "AI risk management"
    - "AI safety"
    - "foundation model"
  tier_2_regulatory:
    - "Executive Order 14110"   # Biden AI EO
    - "Executive Order 14179"   # Trump AI EO (if applicable)
    - "OMB M-24-10"             # OMB AI governance memo
    - "NIST AI"
    - "AI governance"
    - "automated systems"
    - "predictive analytics" AND "federal"
  tier_3_statistical:
    - "information technology" AND "measurement"
    - "productivity measurement"
    - "digital economy"
    - "technology adoption survey"
    - "Business Trends and Outlook Survey"
    - "computer use" AND "statistical"
  tier_4_historical:
    - "hedonic price" 
    - "quality adjustment"
    - "satellite account"
    - "computer services" AND "national accounts"
```

**Agencies of interest (filter/boost):**
- Office of Management and Budget (OMB)
- Office of Science and Technology Policy (OSTP)  
- National Institute of Standards and Technology (NIST)
- Bureau of Labor Statistics (BLS)
- Bureau of Economic Analysis (BEA)
- Census Bureau
- Federal Trade Commission (FTC)
- Department of Commerce
- Department of Defense (AI-related only)
- Office of the National Cyber Director

### 4.2 NBER Working Papers

**Endpoint:** No formal API. Use OpenAlex or Semantic Scholar to find NBER papers by institution + topic.  
**Alt:** NBER has RSS feeds per program: `https://www.nber.org/rss/new.xml`  
**Strategy:** Query Semantic Scholar for papers with `venue:NBER` and relevant keywords. Follow citation chains from known seeds.

**Seed papers (from research notes):**
```yaml
nber_seeds:
  - doi: "10.3386/w34745"   # Behavioral Economics of AI: LLM Biases
  - doi: "10.3386/w35046"   # Forecasting Economic Effects of AI
  - doi: "10.3386/w32966"   # Rapid Adoption of Generative AI
  # Historical seeds — Solow Paradox era:
  - query: "Solow productivity paradox computers"
  - query: "Brynjolfsson productivity information technology"
  - query: "Jorgenson capital measurement computers"
  - query: "Nordhaus quality adjusted price index"
  - query: "Triplett hedonic price index"
  - query: "Gordon productivity growth"
  - query: "David computer dynamo"  # Paul David's electrification analogy
```

### 4.3 Semantic Scholar Graph API

**Endpoint:** `https://api.semanticscholar.org/graph/v1/`  
**Auth:** Free API key (already have one per Wintermute config)  
**Rate limit:** 1 req/sec unauthenticated, 10 req/sec with key  
**Use:** Primary citation graph explorer. Given a seed paper, fetch references and citations. Score by relevance to measurement constructs.

**Operations:**
1. `GET /paper/{paperId}` — metadata, abstract, references, citations
2. `GET /paper/search?query=...` — keyword search
3. `GET /paper/{paperId}/references` — outbound citations
4. `GET /paper/{paperId}/citations` — inbound citations (who cited this)

**Expansion logic:**
- From each seed paper, fetch all references and citations
- Score each by title/abstract keyword match against construct families
- Papers above threshold become new seeds (breadth-first, depth-limited to 3 hops)
- Track expansion frontier in `seen.db` to avoid re-crawling

### 4.4 OpenAlex API

**Endpoint:** `https://api.openalex.org/`  
**Auth:** None required (polite pool with email in `mailto` param)  
**Rate limit:** 10 req/sec with `mailto`, 1 req/sec without  
**Use:** Bulk metadata, institution filtering, concept tagging. Complements Semantic Scholar.

**Key queries:**
```
/works?filter=concepts.id:C154945302,publication_year:>1985
  (C154945302 = "Productivity" concept)
/works?filter=concepts.id:C41008148,institutions.country_code:US
  (C41008148 = "Artificial intelligence")
/works?search="Solow paradox"&filter=publication_year:>1985
/works?search="hedonic price index" AND "computer"
/works?search="digital economy satellite account"
```

### 4.5 Federal Reserve Research

**FRED API:** `https://api.stlouisfed.org/fred/` (free key required)  
**FEDS Notes:** HTML scrape from `https://www.federalreserve.gov/econres/notes/`  
**Working Papers:** `https://www.federalreserve.gov/econres/feds/`  

**Strategy:** 
- FEDS Notes: scrape index page, filter by AI/technology/productivity keywords
- FRED: not for papers but for time series metadata — tag series related to productivity, IT investment, computer prices
- Working papers: same keyword filter approach

### 4.6 BLS / BEA Technical Papers

**BLS:** `https://www.bls.gov/opub/mlr/` (Monthly Labor Review archives)  
**BEA:** `https://www.bea.gov/research/papers` and `https://apps.bea.gov/scb/` (Survey of Current Business)  

**Strategy:** HTML scrape of paper indices. These are the agencies that actually had to figure out how to measure computers. Their technical papers from 1985–2005 are the historical gold mine.

**Seed topics:**
```yaml
bls_bea_seeds:
  - "computer price index"
  - "hedonic regression"
  - "quality adjustment methodology"
  - "multifactor productivity"
  - "information technology capital"
  - "digital economy"
  - "satellite account"
  - "software investment"
  - "intangible capital"
  - "output measurement"
  - "e-commerce"
  - "Internet impact"
```

### 4.7 Census Bureau

**BTOS data:** `https://www.census.gov/econ/btos`  
**Technical papers:** `https://www.census.gov/library/working-papers.html`  
**Strategy:** BTOS is the current AI adoption survey. Also harvest any Census working papers on technology adoption measurement methodology.

### 4.8 Historical Technology Measurement Literature

This is the most intellectually valuable and hardest to automate. The agent should use Semantic Scholar/OpenAlex citation chains from known seed papers.

**Seed authors (follow their publication lists):**
```yaml
historical_measurement_authors:
  # Solow Paradox / IT Productivity
  - "Robert Solow"
  - "Erik Brynjolfsson"
  - "Daniel Sichel"
  - "Dale Jorgenson"
  - "Robert Gordon"
  - "William Nordhaus"
  - "Jack Triplett"
  - "Paul David"           # electrification analogy
  - "Timothy Bresnahan"
  - "Shane Greenstein"
  
  # Federal statistical methodology
  - "Brent Moulton"        # BEA quality adjustment
  - "Charles Hulten"       # intangible capital
  - "Carol Corrado"        # intangible investment
  - "Jonathan Haskel"      # intangibles + productivity
  - "Marshall Reinsdorf"   # BEA price measurement
  - "Ana Aizcorbe"         # BEA computer prices
  - "Ernst Berndt"         # hedonic methods
  
  # Technology adoption measurement
  - "Nathan Rosenberg"     # technology diffusion
  - "Carlota Perez"        # techno-economic paradigm shifts
  - "W. Brian Arthur"      # increasing returns, technology
  
  # Superforecasting / prediction
  - "Philip Tetlock"
  - "Daniel Kahneman"
```

### 4.9 arXiv

**RSS:** `http://export.arxiv.org/rss/` per category  
**API:** `http://export.arxiv.org/api/query`  
**Categories:** `econ.GN`, `cs.AI`, `cs.CY`, `stat.AP`  
**Strategy:** Keyword search within categories. Lower priority than structured APIs since Wintermute already has arXiv ingestion. Focus here on economics-specific categories that current pipeline may miss.

---

## 5. Adaptive Expansion Protocol

The agent doesn't just run static queries. It learns from what it finds.

### 5.1 Citation chain following
When a fetched paper has a reference list:
1. Extract all DOIs / titles from references
2. Check each against `seen.db`
3. For unseen items, score title against seed keywords
4. If score > threshold, add to fetch queue with source = "citation_chain" and `parent_id` pointing to the citing paper
5. Limit depth to 3 hops from any seed. Log but don't fetch beyond that.

### 5.2 Author following
When a high-scoring paper is found:
1. Extract author list
2. If author is in seed author list, fetch their recent publication list (Semantic Scholar author endpoint)
3. If author is NOT in seed list but appears in 3+ high-scoring papers, add them as a discovered author and fetch their list
4. Log all discovered authors for human review

### 5.3 Term discovery
When processing abstracts of high-scoring papers:
1. Extract noun phrases and technical terms not in current seed queries
2. If a term appears in 5+ high-scoring paper abstracts, propose it as a new seed query
3. Don't auto-add — log to `expansion_proposals.yaml` for human review
4. This prevents drift while allowing the agent to surface terminology it doesn't know about

### 5.4 Temporal strategy: present-backward
```
Phase 1: 2024–present (current AI measurement landscape)
Phase 2: 2020–2024 (pre-ChatGPT AI measurement + COVID economic disruption)  
Phase 3: 2010–2020 (deep learning era, early AI adoption measurement)
Phase 4: 1995–2010 (Internet measurement era — the most recent completed analogy)
Phase 5: 1985–1995 (Solow Paradox era — the intellectual foundation)
Phase 6: Pre-1985 (electrification, telephony, earlier technology transitions — selective)
```

Each phase runs to reasonable saturation before moving to the next. "Saturation" = new queries returning >80% already-seen items.

---

## 6. Output Format

### 6.1 Inbox items

Each harvested document lands in `~/.wintermute/inbox/` as either:

**Option A — Markdown with frontmatter** (for text-extractable sources):
```yaml
---
id: harvest-YYYYMMDD-HHMMSS-<6char-hash>
source_url: <canonical URL>
source_type: <federal_register|nber_paper|journal_article|technical_report|working_paper|government_report|dataset_description>
source_api: <federal_register_api|semantic_scholar|openalex|html_scrape|arxiv_api>
captured_at: <ISO 8601>
title: "<title>"
authors: ["<author>"]
published_date: <date>
harvest_campaign: "ai-economy-measurement"
harvest_phase: <1-6>
harvest_depth: <0 for seed, 1-3 for citation chain>
harvest_parent: <parent item id if from citation chain, null otherwise>
doi: <if available>
arxiv_id: <if available>
semantic_scholar_id: <if available>
openalex_id: <if available>
federal_register_number: <if FR document>
agencies: ["<agency>"]  # for FR documents
document_type: <rule|proposed_rule|notice|executive_order|paper|report>
tags: []  # minimal — let Wintermute's triage add these
---

<extracted text / abstract / full content>
```

**Option B — Raw PDF** dropped into `inbox/` with a companion `.meta.yaml` sidecar containing the same frontmatter fields. For documents where PDF is the authoritative format (BLS technical papers, BEA working papers, some NBER papers).

### 6.2 Harvest state

The agent maintains its own state (separate from Wintermute's `seen.db` but queryable by it):

```
~/.wintermute/sources/harvest/
├── config.yaml              # source registry + current phase
├── seed_queries.yaml         # all seed terms, authors, DOIs
├── expansion_proposals.yaml  # discovered terms/authors awaiting review
├── harvest_state.db          # SQLite: what's been fetched, when, status
└── logs/
    └── harvest-YYYY-MM-DD.log
```

**harvest_state.db schema:**
```sql
CREATE TABLE fetched_items (
    item_id TEXT PRIMARY KEY,        -- normalized URL or DOI
    source_api TEXT,
    query_used TEXT,
    fetched_at TEXT,                  -- ISO 8601
    status TEXT,                      -- fetched | deposited | skipped | failed
    harvest_phase INTEGER,
    harvest_depth INTEGER,
    parent_id TEXT,                   -- citation chain parent
    title TEXT,
    score_estimate REAL,             -- agent's quick relevance estimate
    inbox_path TEXT                   -- where deposited
);

CREATE TABLE discovered_authors (
    author_name TEXT,
    semantic_scholar_id TEXT,
    discovery_source TEXT,            -- seed | citation_frequency
    paper_count INTEGER,
    high_score_count INTEGER,
    status TEXT                       -- active | proposed | rejected
);

CREATE TABLE query_log (
    query_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_api TEXT,
    query_text TEXT,
    executed_at TEXT,
    results_count INTEGER,
    new_items_count INTEGER,
    phase INTEGER
);
```

---

## 7. Rate Limiting and Politeness

```yaml
rate_limits:
  federal_register:
    requests_per_second: 1
    retry_backoff: [2, 5, 15, 60]
    max_retries: 3
  semantic_scholar:
    requests_per_second: 9    # with API key
    daily_limit: null         # monitor for 429s
    retry_backoff: [1, 3, 10, 30]
  openalex:
    requests_per_second: 9    # with mailto
    retry_backoff: [1, 3, 10]
  arxiv:
    requests_per_second: 0.33  # arxiv asks for 3-sec delay
    retry_backoff: [5, 15, 60]
  html_scrape:
    requests_per_second: 0.5
    retry_backoff: [5, 15, 60]
    respect_robots_txt: true
    user_agent: "WintermuteHarvester/0.1 (research; brock@brockwebb.com)"
```

---

## 8. On the Five-Cs Triage (Opinion Requested)

The Keshav five-Cs (Category, Context, Correctness, Contributions, Clarity) maps to his three-pass paper reading method. For the *harvester agent* specifically, here's the honest assessment:

**It's overengineered for ingest.** The five-Cs require actually reading the paper — that's Keshav's Pass 2 at minimum. The harvester's job is Pass 0: "does this exist, is it relevant enough to fetch, and can I hand it off with clean metadata?" That's a binary + confidence score, not a five-axis rubric.

**Where the five-Cs DO fit:** Wintermute's triage stage, after the document is in staging. The existing `triage_score` + `triage_axes` + `triage_reason` system in Wintermute already captures multi-axis scoring. The five-Cs could be formalized as a structured triage object that replaces or augments the current float:

```yaml
# Proposed: Wintermute triage enhancement (NOT harvester responsibility)
triage:
  score: 0.72
  rubric_version: "0.4.0"
  keshav_pass: 1           # which pass was this scored at
  category: "empirical"    # paper type: empirical, methodological, survey, theoretical, policy, technical_report
  context:                 # connections to existing graph
    - project: "measuring-ai-economy"
      relevance: "direct"
    - entity: "Solow Paradox"
      relationship: "extends"
  correctness: 0.7         # methodology sniff test (0-1)
  contributions: "novel"   # novel | incremental | replication | synthesis | null
  clarity: 0.8             # extraction difficulty signal (0-1, higher = easier to extract)
  reason: "..."
```

**Recommendation:** Don't build the five-Cs into the harvester. Build it as a Wintermute triage upgrade, test it on 20–30 documents already in staging, see if the structured object produces better downstream decisions than the current float. If it does, adopt it. If it just adds fields nobody acts on, drop it.

The harvester should do ONE scoring thing: a quick relevance estimate (0-1) based on title + abstract keyword match against seed terms, used only to prioritize the fetch queue. Everything else is Wintermute's problem.

---

## 9. Initial KG Ontology Seeding

Before the harvester runs, the KG needs skeleton structure for what it's about to receive. This is the "economics of technology measurement" ontology — the conceptual scaffolding.

### 9.1 Core entity types

```yaml
ontology_entities:
  # What we're measuring
  Technology:
    subtypes: [AI, GenAI, Computing, Internet, Electrification, Telephony, Railroad, Containerization]
    properties: [name, era_start, era_end, adoption_curve_type]
  
  EconomicConstruct:
    subtypes: [Productivity, GDP, Employment, Investment, Prices, Output, Adoption, Exposure]
    properties: [name, definition, measurement_challenges]
  
  MeasurementMethod:
    subtypes: [HedonicPricing, SatelliteAccount, SurveyInstrument, IndexConstruction, NaturalExperiment, RCT, Nowcasting, ExpertElicitation]
    properties: [name, description, first_applied_year, limitations]
  
  StatisticalProgram:
    subtypes: [Survey, Census, AdministrativeData, BigData, ModelBasedEstimate]
    properties: [name, agency, frequency, coverage, methodology_url]
  
  # Who
  Agency:
    subtypes: [StatisticalAgency, RegulatoryAgency, ResearchOrg, CentralBank]
    properties: [name, country, mandate]
  
  Researcher:
    properties: [name, affiliation, semantic_scholar_id, research_focus]
  
  # Documents
  Paper:
    subtypes: [WorkingPaper, JournalArticle, TechnicalReport, GovernmentReport, FederalRegisterDocument, PolicyDocument]
    properties: [title, doi, year, venue, document_type]
  
  Dataset:
    properties: [name, provider, frequency, coverage, url]
  
  Benchmark:
    properties: [name, what_measured, saturation_status, version]
```

### 9.2 Core relationship types

```yaml
ontology_relationships:
  # Technology measurement relationships
  MEASURES:           # MeasurementMethod → EconomicConstruct
  APPLIED_TO:         # MeasurementMethod → Technology
  FAILED_TO_CAPTURE:  # MeasurementMethod → EconomicConstruct (the gaps)
  REPLACED_BY:        # MeasurementMethod → MeasurementMethod (methodological evolution)
  
  # Institutional
  ADMINISTERED_BY:    # StatisticalProgram → Agency
  PRODUCES:           # StatisticalProgram → Dataset
  REGULATES:          # FederalRegisterDocument → Technology | Agency
  
  # Knowledge relationships
  AUTHORED_BY:        # Paper → Researcher
  CITES:              # Paper → Paper
  PROPOSES:           # Paper → MeasurementMethod
  CRITIQUES:          # Paper → MeasurementMethod | EconomicConstruct
  EXTENDS:            # Paper → Paper
  
  # Analogical relationships (the intellectual lever)
  ANALOGOUS_TO:       # Technology:AI → Technology:Computing (measurement parallels)
  MEASUREMENT_LAG:    # Technology → EconomicConstruct (time between adoption and measurement catch-up)
  PATTERN_REPEATS:    # MeasurementMethod(era1) → MeasurementMethod(era2)
  
  # Temporal
  PRECEDED_BY:        # Technology → Technology (in measurement evolution)
  CONTEMPORARY_WITH:  # Paper → Paper (same measurement debate era)
```

### 9.3 Bootstrap entities

These should be created before the first harvest run so incoming documents have anchors to connect to:

```yaml
bootstrap_entities:
  technologies:
    - name: "Artificial Intelligence"
      era_start: 2010  # modern deep learning era
      measurement_status: "early/fragmented"
    - name: "Generative AI"
      era_start: 2022
      measurement_status: "pre-measurement"
    - name: "Personal Computing"
      era_start: 1975
      era_end: null  # still ongoing
      measurement_status: "mature but still debated"
    - name: "Internet/E-commerce"
      era_start: 1995
      measurement_status: "mostly resolved"
    - name: "Electrification"
      era_start: 1880
      era_end: 1940
      measurement_status: "historical reference"
    - name: "Telephony"
      era_start: 1876
      era_end: null
      measurement_status: "historical reference"

  measurement_problems:
    - name: "Solow Paradox"
      description: "Computers visible everywhere except productivity statistics (1987)"
      technology: "Personal Computing"
      status: "resolved (late 1990s)"
      lesson: "Measurement frameworks built for manufacturing couldn't capture information work productivity gains. 15-year lag."
    - name: "Quality Adjustment Problem"
      description: "How to measure 'better' when a $1000 computer in 2000 is 100x more powerful than a $3000 computer in 1990"
      technology: "Personal Computing"
      method: "HedonicPricing"
      status: "partially resolved"
    - name: "Digital Economy Measurement Gap"
      description: "GDP doesn't capture consumer surplus from free digital goods, platform effects, data as capital"
      technology: "Internet/E-commerce"
      status: "active research"
    - name: "AI Productivity Measurement Gap"
      description: "Current: BTOS shows 3.7%→17.3% adoption in 2 years but no measurable aggregate productivity or employment effect"
      technology: "Artificial Intelligence"
      status: "active — first inning"

  key_datasets:
    - name: "Census BTOS"
      provider: "Census Bureau"
      frequency: "biweekly"
      coverage: "US businesses"
      what_measures: "AI adoption rates by sector"
      url: "https://www.census.gov/econ/btos"
    - name: "Anthropic Economic Index"
      provider: "Anthropic"
      frequency: "quarterly"
      what_measures: "Real-world AI task usage mapped to O*NET"
      url: "https://www.anthropic.com/economic-index"
    - name: "Stanford AI Index"
      provider: "Stanford HAI"
      frequency: "annual"
      what_measures: "Comprehensive AI landscape (423 pages, 2026 edition)"
      url: "https://hai.stanford.edu/ai-index"
    - name: "BLS Multifactor Productivity"
      provider: "BLS"
      frequency: "annual"
      what_measures: "Total factor productivity including IT capital contribution"
      url: "https://www.bls.gov/mfp/"
    - name: "BEA Digital Economy Satellite Account"
      provider: "BEA"
      frequency: "annual"
      what_measures: "Digital economy contribution to GDP"
      url: "https://www.bea.gov/data/special-topics/digital-economy"
```

---

## 10. Implementation Plan for Claude Code

### Phase 0: Setup (day 1)
1. Create `~/.wintermute/sources/harvest/` directory structure
2. Write `config.yaml` with source registry
3. Write `seed_queries.yaml` from seeds in this spec
4. Create `harvest_state.db` with schema above
5. Bootstrap KG ontology entities in Neo4j (Section 9.3)
6. Verify API access: Federal Register (no key), Semantic Scholar (check existing key), OpenAlex (use mailto)

### Phase 1: Federal Register harvest (days 2–3)
1. Build Federal Register fetcher module
2. Run tier_1 queries (current AI terms), most recent first
3. Run tier_2 queries (regulatory/EO specific)
4. Deposit results in inbox
5. Run tier_3 and tier_4 queries (statistical methodology, historical)
6. Log stats: total fetched, new vs. seen, by agency, by year

### Phase 2: Academic seed harvest (days 3–5)
1. Build Semantic Scholar fetcher module
2. Fetch all seed papers by DOI
3. Build citation chains (depth 1) from seeds
4. Build OpenAlex fetcher for bulk concept queries
5. Run author-list harvests for seed authors
6. Deposit results in inbox

### Phase 3: Federal statistical agency papers (days 5–7)
1. Build HTML scrapers for BLS MLR, BEA SCB/working papers, Census working papers
2. Run historical keyword queries (hedonic pricing, quality adjustment, etc.)
3. Build Fed FEDS Notes scraper
4. Deposit results

### Phase 4: Adaptive expansion (days 7–10)
1. Enable citation chain following (depth 2–3)
2. Enable author discovery
3. Enable term discovery → proposals file
4. Run until Phase 1 (2024–present) reaches saturation
5. Begin Phase 2 (2020–2024) temporal expansion

### Ongoing: launchd job
Once stable, register as a Wintermute launchd job:
- Daily: check Federal Register for new AI-related documents
- Weekly: run Semantic Scholar citation expansion from high-scoring items
- Weekly: check BTOS, Fed Notes, BLS/BEA for new publications
- Monthly: review `expansion_proposals.yaml`, update seed lists

---

## 11. Success Criteria

After Phase 4 completion:
- Federal Register: all AI-related documents 2020–present ingested (estimated 500–2000 documents)
- Academic: 200+ papers on IT/AI productivity measurement in KG
- Historical: key Solow Paradox / hedonic pricing / productivity measurement papers (50–100) ingested with citation chains
- KG: ontology populated with entities from Section 9.3, with incoming documents linked to them
- Expansion: at least 10 discovered authors and 20 discovered terms proposed for review
- Pipeline: running as daily/weekly launchd job with <5% failure rate

---

## 12. What This Spec Does NOT Cover

- How Wintermute triages, scores, or extracts these documents (existing pipeline)
- KG entity extraction or relationship inference (existing Wintermute + Neo4j pipeline)
- Analysis, synthesis, forecasting, or report generation
- The five-Cs triage rubric (recommendation: test separately as Wintermute triage upgrade)
- Paid-access sources (JSTOR, ScienceDirect, etc.)
- Integration with measuring-ai-economy project's own analysis tools
