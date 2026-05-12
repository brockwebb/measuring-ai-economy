# CC Task: Bootstrap measuring-ai-economy Project

## Scope
Initialize the private repo with Seldon tracking from day one. Set up feed discovery
and scaffold the three workstreams. Capture the measurement analogy framework.

## Prerequisites
- `gh repo create brockwebb/measuring-ai-economy --private`
- Brock's existing notes on measuring AI in the economy
- Seldon init for provenance tracking from the start

## Steps

### 1. Repo Init + Seldon
```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git init
gh repo create brockwebb/measuring-ai-economy --private --source=. --push
```
Then: `seldon_go` to initialize the project graph.

### 2. AlignedNews — Confirmed Feed Endpoints
AlignedNews has **documented RSS and JSON API** (confirmed from their about page):
- RSS Feed: standard RSS format, top signals
- JSON API: structured data with metadata
- About/methodology: https://alignednews.com (the "How It Works" page)

**Architecture notes (for SFV paper cross-reference):**
AlignedNews implements the SFV pattern without naming it:
- 63 hand-curated X lists (domain expertise / human judgment layer)
- Weaviate vector DB (state management)
- Multi-pass pipeline: keywords -> semantic search -> cross-list amplification (workflow chain)
- AI synthesis with persistent memory (cognitive agent)
- Structured output: RSS, JSON API, 30 editorial sections (machine-readable provenance)
- 100K+ accounts, 3-7K posts per sweep, updated multiple times daily

Discover exact endpoint URLs (try /feed, /rss, /api, etc.) and document in
`feeds/FEED_REGISTRY.md`.

### 3. Feed Discovery — Other Sources
Document candidate feeds in `feeds/FEED_REGISTRY.md`:

**AI News/Signal Aggregators:**
- alignednews.com (Scoble) — RSS + JSON API confirmed
- techmeme.com/feed.xml
- theverge.com AI section RSS
- arstechnica.com AI feed
- FedScoop federal AI coverage

**Economic Data (open source):**
- Census BTOS (biweekly AI adoption) — https://www.census.gov/hfp/btos/
- FRED API (St. Louis Fed) — macro economic indicators
- BLS JOLTS / employment data APIs
- BEA GDP / productivity APIs
- Stanford AI Index (annual)
- OECD AI Policy Observatory
- OMB Federal AI Use Case Inventory (annual, GitHub)

**Market Intelligence:**
- SEC EDGAR API (10-K/10-Q mentions of "artificial intelligence", "machine learning")
- Yahoo Finance API / yfinance (AI sector stocks, semiconductor index)
- Crunchbase / PitchBook (VC funding flows into AI)
- GitHub trending / star velocity for AI repos (proxy for open source AI velocity)

**Historical Analogy Sources (for measurement framework):**
- Solow Paradox literature (computers visible everywhere except productivity stats)
- BLS productivity measurement methodology papers
- BEA digital economy satellite accounts
- Internet adoption measurement retrospectives (FCC broadband data, Pew surveys)
- NBER working papers on technology measurement gaps

### 4. Scaffold Directory Structure
```
measuring-ai-economy/
  README.md
  cc_tasks/
  docs/
    notes/                          <- Brock's existing notes
    measurement_framework.md        <- how to measure AI economic impact
    historical_analogues.md         <- computers, internet measurement precedents
  feeds/
    FEED_REGISTRY.md                <- all feeds with URLs, format, frequency
  data/
    raw/                            <- raw feed snapshots, CSV dumps
    processed/                      <- normalized, deduplicated
  scrapers/                         <- feed consumers, API clients
  analysis/                         <- notebooks, scripts
```

### 5. Write Measurement Framework Outline
In `docs/measurement_framework.md`:

**The Core Problem:**
Census and other statistical agencies don't know how to measure AI's economic impact.
This is not new. They didn't know how to measure computers either.

**Historical Analogues (the intellectual lever):**
- **Solow Paradox (1987)**: "You can see the computer age everywhere but in the
  productivity statistics." It took until the late 1990s — 15+ years after PC
  proliferation — for productivity gains to show up in the data. Why?
  Measurement frameworks were built for manufacturing, not information work.
- **Internet measurement**: Similar lag. BLS didn't have good measures of
  e-commerce impact on prices. CPI methodology debates. Quality adjustment
  problems for digital goods.
- **Key question**: What did we learn *retrospectively* about how we should have
  been measuring computers/internet? Can we apply those lessons *prospectively*
  to AI and skip the 15-year lag?

**What's Different About AI:**
- Combines prior technologies (computing + networking) but accelerated
- Global scale, unprecedented rate of change
- Affects both production AND measurement (AI changes how we collect data)
- Self-referential: Census is using AI while trying to measure AI

**Measurement Dimensions:**
- Adoption rates (BTOS: 3.7% -> 17.3% in 2 years)
- Productivity impact (TFP, labor productivity by sector)
- Labor market effects (displacement, augmentation, new job creation)
- Investment flows (VC, corporate capex, infrastructure)
- Sector transformation (which industries, how fast)
- Quality-adjusted output (the hardest problem — how do you price "better"?)

**The Gap:**
BTOS is the best we have. But it asks broad questions, lumps all AI together,
company-level only, no GenAI specificity. SEED AI's proposed Generative AI
Intensity Index (https://www.seedai.org/research/intensity-index) is one
attempt to fill this gap.

**What This Project Could Produce:**
- A composite index from open source data sources
- A measurement framework paper (feeds into Census/ICSP discussion)
- A working prototype that demonstrates the approach
- Content for the ICSP notebook (meta: using AI to measure AI)

### 6. SFV Paper Cross-Reference
Document in `docs/notes/sfv_connection.md`:

AlignedNews is an existence proof of the SFV pattern in production:
- Independent convergent evolution (Scoble/Levangie didn't read the book)
- Same architecture as Concept Mapper, same pattern as Karpathy's workflows
- Nobody has named it. SFV is the name.
- Add to SFV paper as a case study / existence proof
- The "cognitive AI agent with persistent memory" = state fidelity

### 7. Move Brock's Existing Notes
- Brock to drop existing notes into `docs/notes/`
- Claude Code to review and integrate into framework outline

## Priority Context

**This project is subordinate to:**
1. SFV paper completion (the paper must ship first)
2. Seldon writeup
3. ICSP notebook Phase 2 (where this feeds into)

**This project FEEDS the SFV paper** — AlignedNews is a new existence proof.
It's additive, not a distraction, as long as the engineering itch doesn't
take over. Keep it to framework + feed discovery. Don't build pipelines
until the paper ships.

## Output
- Private GitHub repo with Seldon tracking from day one
- Feed registry with confirmed AlignedNews endpoints + other sources
- Measurement framework outline with historical analogy framing
- SFV cross-reference documented
- Ready for incremental development (after paper ships)

## NOT in scope (yet)
- Building scrapers or feed consumers
- Market data pipeline engineering
- Integration with Wintermute/LeStat
- Composite index prototype
- Full literature review on Solow Paradox
