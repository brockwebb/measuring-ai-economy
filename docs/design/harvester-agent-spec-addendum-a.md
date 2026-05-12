# Addendum A: Alternative Data Source Discovery & Cross-Dataset Normalization

**Parent document:** `harvester-agent-spec.md` v0.1.0  
**Companion document:** `../notes/ai-economy-ontology-stack.md`  
**Date:** 2026-05-11  

---

## A1. Problem Statement

The harvester spec (v0.1.0) focuses on academic literature, federal documents, and structured research APIs. But the most actionable AI economy measurement data increasingly comes from **alternative data sources** — corporate spend platforms, job posting aggregators, web traffic analytics, government open data portals, patent databases, and private-sector indices.

These sources expose a fundamental normalization problem: **everyone measures "AI adoption" differently, and nobody's taxonomy matches anyone else's.**

Consider the current state as of mid-2026:

- **Census BTOS** asks businesses if they "use AI goods and services" via survey. Reports ~20% adoption after question redesign.
- **Ramp AI Index** counts corporate card + invoice payments to known AI vendors across 50,000+ businesses. Reports 50.4% adoption.
- **Anthropic Economic Index** maps actual Claude API usage to O*NET task codes. Measures task-level augmentation/automation, not firm-level adoption.
- **Stanford AI Index** aggregates dozens of secondary sources into a 400+ page annual report. Defines its own composite indicators.
- **OECD AI Indicators** map AI capabilities against human-ability domains for cross-country comparison.
- **LinkedIn/Indeed job postings** measure demand for AI skills via posting text. Different NLP pipelines produce different skill taxonomies.

These are not different measurements of the same thing. They are measurements of **different constructs** (survey self-report, payment behavior, task-level API usage, job demand signals) that all get called "AI adoption." The gap between them is not error — it **is** the signal.

The harvester needs to catalog these sources, capture their native taxonomies, and flag normalization requirements so downstream analysis doesn't produce apples-to-oranges comparisons disguised as precision.

The ontology stack document (`ai-economy-ontology-stack.md`) provides the Rosetta Stone architecture: NAICS/NAPCS/SOC/O*NET as the federal spine, ISIC/CPC/ISCO for international comparison, SKOS for crosswalk publication. This addendum specifies what the harvester should **collect** and how it should **tag** alternative data for that normalization pipeline.

---

## A2. Alternative Data Sources to Harvest

### A2.1 Corporate Spend / Transaction Data

**Ramp AI Index**
- URL: `https://ramp.com/data` and `https://ramp.com/leading-indicators/`
- What it measures: Share of US businesses with paid AI subscriptions, by vendor and sector
- Methodology: Anonymized corporate card + invoice payments from 50,000+ Ramp customers
- Cadence: Monthly index posts, quarterly spending reports
- Economist: Ara Kharazian (ex-Square, ex-Cornerstone Research)
- Access: HTML scrape of blog posts + PDF reports
- Credibility: Methodologically transparent, cited in NYT/WSJ/FT/NPR Planet Money. Sample bias toward tech-forward SMBs who use a modern expense platform — not representative of all US businesses, but leading indicator of adoption curve.
- **Key normalization note:** "Adoption" = has a corporate payment to a known AI vendor. Misses: free-tier usage, personal accounts expensed differently, open-source/self-hosted AI, AI embedded in non-AI vendor products (e.g., AI features in Salesforce). Likely overcounts relative to Census BTOS for their panel, but their panel underrepresents large enterprises and traditional industries.
- Harvest: scrape monthly index posts, extract vendor market share time series, sector breakdowns, methodology notes

**Ramp "Ramp Rate" Dataset**
- Tracks fastest-growing SaaS vendors by category across their panel
- Useful for detecting which AI-adjacent tools (coding assistants, writing tools, data platforms) are gaining traction before they show up in official statistics

### A2.2 Government Open Data

**Data.gov AI Datasets**
- URL: `https://catalog.data.gov/dataset/?tags=artificial-intelligence`
- What it contains: Federal agency AI use case inventories (required by EO 13960 / Advancing American AI Act), AI-related datasets, R&D program descriptions
- Access: CKAN API at `https://catalog.data.gov/api/3/`
- **Key harvest targets:**
  - Agency AI use case inventories (USDA, DOT, DHS, ICE, HHS, etc.) — these are the raw data behind the OMB AI Use Case Inventory work
  - NITRD AI R&D Strategic Plan documents
  - State/local government AI algorithm inventories (NYC LL35, Connecticut PA 23-16)
- **Normalization note:** Each agency defines "AI use case" differently. Some include simple rule-based automation, others restrict to ML/DL. The OMB harmonization work and the federal survey concept mapper taxonomy are directly applicable here.

**AI.gov / OSTP AI Resources**
- URL: `https://ai.gov`
- Aggregates federal AI policy documents, EOs, OMB memos, NIST standards
- Overlaps with Federal Register but includes additional context and cross-references

**USASpending.gov**
- URL: `https://api.usaspending.gov/`
- What it measures: Federal contract and grant spending
- Relevant queries: contracts with PSC codes for AI/ML services, NAICS codes for software/cloud/R&D
- **Normalization note:** AI spending is buried in broader IT/professional services contracts. Need keyword search of contract descriptions + PSC/NAICS filtering.

### A2.3 Labor Market / Job Posting Data

**Indeed / LinkedIn / Glassdoor Hiring Trends**
- No direct API access for most; rely on published indices and reports
- Indeed Hiring Lab: `https://www.hiringlab.org/` — publishes AI job posting trends
- LinkedIn Economic Graph: periodic AI talent reports
- What they measure: demand-side signal for AI skills and roles
- **Normalization note:** Job posting taxonomies are proprietary. "AI engineer" on LinkedIn ≠ "Machine Learning Engineer" on Indeed ≠ SOC 15-2051 "Data Scientists" ≠ O*NET "15-2051.00." The SOC-to-posting crosswalk is non-trivial. The NICE Framework provides finer cybersecurity/AI workforce granularity below SOC.

**Lightcast (formerly Burning Glass / EMSI)**
- Major job posting aggregator used by BLS and academic researchers
- Published reports on AI skill demand
- Harvest published reports and methodology papers; actual data requires license

### A2.4 Web Traffic / App Analytics

**Similarweb**
- Publishes periodic reports on AI tool traffic (visits to ChatGPT, Claude, etc.)
- Free tier provides limited data; research reports are scrapeable
- What it measures: consumer/business engagement via web visits, not necessarily adoption or payment

**Sensor Tower / data.ai (app analytics)**
- Track mobile app downloads and usage for AI apps
- Published rankings and trend reports are harvestable

### A2.5 Patent / Innovation Data

**USPTO PatentsView API**
- URL: `https://patentsview.org/apis/api-endpoints`
- What it measures: Patent grants and applications by CPC classification
- Key CPC codes: G06N (machine learning, neural networks), G06F 40 (NLP), G06V (image recognition)
- Access: Free REST API, bulk download
- **Normalization note:** CPC/IPC classifications map to inventive activity, not deployment. A patent in G06N doesn't mean the technology is in production. But patent velocity by technology area is a leading indicator. The ontology stack document specifies CPC-to-NAICS innovation mappings as a priority crosswalk.

**WIPO AI Patent Landscape**
- Periodic reports on global AI patent trends
- Uses WIPO's own AI search strategy across IPC/CPC codes

### A2.6 AI Vendor / Platform Data

**Anthropic Economic Index**
- Already in main spec, but worth noting: this is the most granular task-level AI usage data publicly available. Maps actual API calls to O*NET occupational tasks.
- **Normalization note:** Measures Claude usage only. Not total AI adoption. But the O*NET task mapping makes it directly comparable to GPTs-are-GPTs exposure framework.

**OpenAI Usage Research**
- Periodic papers on ChatGPT usage patterns
- Less structured than Anthropic's but larger user base

**Hugging Face Hub Statistics**
- Model downloads, dataset usage, trending models
- API accessible: `https://huggingface.co/api/`
- Measures developer/researcher adoption, not business adoption

### A2.7 Private Sector Indices and Reports

**McKinsey Global AI Survey** (annual)
- What it measures: Enterprise AI adoption, use cases, ROI by industry
- Access: Published reports, scrapeable
- **Normalization note:** Self-selected survey of McKinsey clients. Enterprise bias.

**Deloitte / PwC / BCG AI surveys**
- Similar enterprise surveys with different methodologies
- Harvest for cross-reference but flag sample selection differences

**CB Insights / Crunchbase / PitchBook**
- VC funding data for AI startups
- Measures investment, not adoption or economic impact
- Published reports and trend analyses are harvestable

### A2.8 International Comparison Sources

**Eurostat ICT Usage by Enterprises Survey**
- URL: `https://ec.europa.eu/eurostat/web/digital-economy-and-society/database`
- AI adoption questions added in recent waves
- Enables direct EU-US comparison (with crosswalk caveats)

**OECD.AI Policy Observatory**
- URL: `https://oecd.ai/en/`
- Country-level AI policy indicators, compute trends, adoption metrics
- Some data available via API

---

## A3. The Normalization Problem

### A3.1 Why this matters

Without normalization metadata, the KG will contain nodes like:

- "AI adoption rate: 50.4%" (Ramp, March 2026, US, corporate card payments to AI vendors, 50K+ Ramp customers)
- "AI adoption rate: 20%" (Census BTOS, late 2025, US, survey self-report, nationally representative sample)
- "AI adoption rate: 47.6%" (Ramp, February 2026, same methodology, different month)

If these get ingested as comparable data points, the graph is poisoned. They're three different measurements of three related-but-distinct constructs.

### A3.2 Data Source Registry Schema

Every alternative data source gets a registry entry capturing its measurement metadata:

```yaml
source_registry_entry:
  source_id: "ramp_ai_index"
  source_name: "Ramp AI Index"
  provider: "Ramp"
  provider_type: "fintech_platform"      # fintech_platform | statistical_agency | research_org | consulting_firm | tech_vendor | academic | international_org | government_portal
  
  # What does this source actually measure?
  measurement:
    construct: "paid_ai_vendor_adoption"  # NOT just "ai_adoption"
    unit_of_analysis: "business"          # business | worker | task | product | patent | contract | transaction
    unit_definition: "US business with active Ramp corporate card or invoice account"
    population: "50,000+ US businesses using Ramp expense management"
    sampling_frame: "Ramp customer base — skews tech-forward SMBs"
    representativeness: "non-representative; leading-indicator panel"
    measurement_method: "payment transaction analysis"
    question_wording: null                # no survey question — behavioral measurement
    adoption_definition: "At least one corporate card or invoice payment to a known AI vendor in the measurement period"
    temporal_resolution: "monthly"
    geographic_coverage: "US"
    
  # How does this map to the ontology stack?
  taxonomy_mapping:
    industry_classification: "NAICS (implied by Ramp's sector categories, not official NAICS codes)"
    occupation_classification: null
    product_classification: "Ramp's own vendor category list (maps approximately to NAPCS software/cloud)"
    crosswalk_status: "requires_manual_mapping"
    crosswalk_notes: "Ramp sectors (tech, finance, professional services, retail, etc.) need mapping to NAICS 2-digit codes. Vendor list needs mapping to NAPCS product codes."
    
  # Provenance
  provenance:
    access_method: "html_scrape"
    url: "https://ramp.com/data"
    cadence: "monthly"
    first_available: "2023-01"
    data_format: "embedded in blog posts; charts with approximate values"
    machine_readable: false
    api_available: false
    
  # Normalization requirements
  normalization:
    difficulty: "medium"                  # low | medium | high | requires_deep_work
    can_auto_extract: true                # can we scrape time series programmatically?
    requires_taxonomy_mapping: true       # needs crosswalk to ontology stack
    requires_construct_disambiguation: true  # "adoption" ≠ Census "adoption"
    comparable_sources:
      - source_id: "census_btos"
        comparison_caveats: "Different population (Ramp customers vs nationally representative), different construct (payment vs survey self-report), different adoption definition"
      - source_id: "anthropic_economic_index"
        comparison_caveats: "Different unit of analysis (firm vs task), different construct (paid subscription vs API task usage)"
    rosetta_stone_keys:                   # which ontology stack entities enable comparison
      - "NAICS sector → industry alignment"
      - "adoption_definition → construct family disambiguation"
```

### A3.3 Construct Disambiguation Registry

The KG needs a **construct disambiguation layer** — a controlled vocabulary that maps every source's native "adoption" or "productivity" or "exposure" term to a precise construct definition:

```yaml
construct_registry:
  paid_ai_vendor_adoption:
    definition: "Firm has made at least one payment to a known AI vendor"
    sources: [ramp_ai_index]
    related_constructs: [survey_ai_adoption, task_level_ai_usage, ai_skill_demand]
    ontology_stack_link: "EconomicConstruct:Adoption subtype"
    measurement_level: "binary per firm, aggregated to share"
    
  survey_ai_adoption:
    definition: "Firm self-reports using AI goods and services in response to survey question"
    sources: [census_btos, eurostat_ict_enterprise, mckinsey_ai_survey]
    question_sensitivity: "HIGH — adoption rate doubles when question wording changes"
    ontology_stack_link: "EconomicConstruct:Adoption subtype"
    
  task_level_ai_usage:
    definition: "Observed AI API calls mapped to occupational task taxonomy"
    sources: [anthropic_economic_index]
    ontology_stack_link: "O*NET task → EconomicConstruct:Adoption"
    
  ai_skill_demand:
    definition: "Job postings requiring AI-related skills"
    sources: [indeed_hiring_lab, linkedin_talent_insights, lightcast]
    ontology_stack_link: "SOC/O*NET/NICE → EconomicConstruct:Employment"
    measurement_level: "count or share of postings"
    
  ai_patent_activity:
    definition: "Patent applications/grants classified under AI-relevant CPC codes"
    sources: [uspto_patentsview, wipo_ai_landscape]
    ontology_stack_link: "CPC G06N → Innovation measurement"
    measurement_level: "count, share, growth rate"
```

### A3.4 Connection to Existing Normalization Infrastructure

The project has two existing assets directly relevant to this normalization problem:

1. **Federal Survey Concept Mapper** — taxonomy classification system for survey harmonization. This handles the case where Census BTOS, Eurostat ICT, and McKinsey all ask about "AI adoption" with different question wording, different response options, and different sampling frames. The concept mapper's taxonomy can serve as the crosswalk layer between survey-based adoption measures.

2. **OMB AI Use Case Inventory work** — normalization of how different federal agencies define and categorize AI use cases. Each agency submitted use cases in different formats with different granularity. The harmonization patterns from that work apply directly to normalizing private-sector alternative data.

The harvester should tag each data source with:
- Which concept mapper taxonomy entries apply
- Whether existing crosswalks cover the mapping, or new crosswalk work is needed
- Difficulty estimate for normalization (auto-triageable vs. requires deep work)

---

## A4. Harvester Implementation: Data Source Discovery Module

### A4.1 New component: Source Discovery Crawler

Add to the architecture:

```
┌─────────────────────────────────────────────────┐
│                  HARVEST AGENT                   │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Source    │  │ Fetcher  │  │ Normalizer    │  │
│  │ Registry │→ │ Pool     │→ │ (→ inbox/)    │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│       ↑              ↑                           │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Seed     │  │ Adaptive │  │ Source        │  │
│  │ Lists    │  │ Expander │  │ Discovery     │  │
│  └──────────┘  └──────────┘  │ Crawler  [NEW]│  │
│                              └───────────────┘  │
└────────────────────┬────────────────────────────┘
```

The Source Discovery Crawler does NOT fetch full documents. It:
1. Crawls known data portals (data.gov, OECD, Eurostat) for AI-tagged datasets
2. Monitors tech company research/data blogs for new published indices
3. Checks RSS feeds of economics blogs and newsletters for references to new data sources
4. For each discovered source, creates a `source_registry_entry` (Section A3.2)
5. Flags sources that need human review for normalization difficulty assessment
6. Deposits source registry entries into `~/.wintermute/sources/harvest/discovered_sources/`

### A4.2 Seed sources for discovery

```yaml
data_discovery_seeds:
  government_portals:
    - url: "https://catalog.data.gov/api/3/"
      query_tags: ["artificial-intelligence", "machine-learning", "automation"]
      type: "ckan_api"
    - url: "https://api.usaspending.gov/"
      query: "AI contracts by NAICS/PSC"
      type: "rest_api"
    - url: "https://ai.gov"
      type: "html_scrape"
    
  private_indices:
    - url: "https://ramp.com/data"
      type: "html_scrape"
      cadence: "monthly"
    - url: "https://www.hiringlab.org/"
      type: "html_scrape"
      cadence: "weekly"
    - url: "https://patentsview.org/apis/api-endpoints"
      type: "rest_api"
      
  international:
    - url: "https://ec.europa.eu/eurostat/web/digital-economy-and-society/database"
      type: "html_scrape"
    - url: "https://oecd.ai/en/"
      type: "html_scrape"
      
  economics_newsletters:
    - url: "https://arakharazian.substack.com/"   # Ramp economist
      type: "rss"
    - url: "https://www.nber.org/rss/new.xml"
      type: "rss"
```

### A4.3 Source registry output format

Each discovered or manually registered source gets a YAML file:

```
~/.wintermute/sources/harvest/source_registry/
├── ramp_ai_index.yaml
├── census_btos.yaml
├── anthropic_economic_index.yaml
├── data_gov_ai.yaml
├── usaspending_ai.yaml
├── indeed_hiring_lab.yaml
├── patentsview_ai.yaml
├── eurostat_ict.yaml
├── oecd_ai.yaml
└── ...
```

### A4.4 harvest_state.db additions

```sql
-- New table for source registry
CREATE TABLE data_sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT,
    provider TEXT,
    provider_type TEXT,
    construct TEXT,              -- what does it actually measure
    unit_of_analysis TEXT,
    population_description TEXT,
    sampling_frame TEXT,
    representativeness TEXT,
    measurement_method TEXT,
    temporal_resolution TEXT,
    geographic_coverage TEXT,
    access_url TEXT,
    access_method TEXT,
    machine_readable BOOLEAN,
    normalization_difficulty TEXT,  -- low | medium | high | deep_work
    crosswalk_status TEXT,         -- mapped | partial | unmapped | not_applicable
    ontology_mappings TEXT,        -- JSON: which ontology stack entities apply
    discovery_date TEXT,
    last_checked TEXT,
    status TEXT                    -- active | proposed | rejected | dormant
);

-- New table for construct disambiguation
CREATE TABLE construct_mappings (
    construct_id TEXT PRIMARY KEY,
    construct_name TEXT,
    definition TEXT,
    source_ids TEXT,               -- JSON array of source_ids that use this construct
    ontology_entity TEXT,          -- link to ontology stack entity
    comparable_constructs TEXT,    -- JSON array of related construct_ids
    comparison_caveats TEXT
);
```

---

## A5. Normalization Triage Categories

Not all data sources require the same level of normalization work. The harvester should classify each source into one of four categories:

### Category 1: Auto-normalizable
The source uses standard identifiers (NAICS, SOC, DOI, CPC) or provides machine-readable data that maps directly to the ontology stack. The harvester can normalize and ingest without human intervention.

**Examples:** USPTO PatentsView (CPC codes), FRED time series (standard series IDs), OpenAlex (concepts map to controlled vocabulary)

### Category 2: Template-normalizable
The source uses a proprietary taxonomy, but the mapping to the ontology stack is stable and can be encoded as a crosswalk template. Needs initial human setup, then runs automatically.

**Examples:** Ramp sector categories → NAICS 2-digit, Census BTOS sectors → NAICS, Anthropic Economic Index tasks → O*NET codes (already provided by Anthropic)

### Category 3: LLM-assisted normalization
The source provides unstructured or semi-structured data that needs per-item classification. An LLM can do first-pass extraction with human verification. Track provenance: `normalized_by: llm_assisted, model: <model>, confidence: <score>, verified: <bool>`.

**Examples:** Federal agency AI use case inventories (each agency's format differs), job posting skill extraction, data.gov dataset descriptions → construct classification

### Category 4: Deep work required
The source has fundamental comparability issues that can't be resolved by mapping taxonomies. Requires methodological analysis — understanding sampling frame differences, question wording effects, construct definition misalignment. This is research, not engineering.

**Examples:** Reconciling Ramp 50% vs Census 20% adoption — requires modeling the selection effects of Ramp's customer panel. Comparing AI patent activity to AI deployment — requires understanding the patent-to-product lag structure.

---

## A6. Ontology Stack Integration

This addendum does NOT duplicate the ontology stack document. The ontology stack (`ai-economy-ontology-stack.md`) defines:
- The federal spine (NAICS, NAPCS, SOC, O*NET, BEA I-O)
- The international comparison layer (ISIC, CPC, ISCO, SNA/BPM)
- The technical layer (NIST AI RMF, ATT&CK, SPDX, DCAT, PROV-O, SKOS)
- The crypto layer (SNA 2025, BPM7, FATF, FIBO, LEI, DTI)
- The crosswalk strategy and priority crosswalks
- The entity types and relationship types for the graph

The harvester addendum adds:
- **Alternative data source registry** — cataloging non-traditional data sources with measurement metadata
- **Construct disambiguation** — controlled vocabulary for what each source actually measures
- **Normalization triage** — categorizing sources by normalization difficulty
- **Provenance tracking** — recording how data was transformed, by whom/what, with what confidence

The connection point is the ontology stack's **crosswalk strategy**. When the harvester discovers a new data source, it checks:
1. Does this source use any ontology-stack identifiers natively? (NAICS, SOC, CPC, etc.)
2. If not, can its native taxonomy be mapped to an ontology-stack entity?
3. What is the normalization difficulty? (Category 1–4 above)
4. Which of the priority crosswalks from the ontology stack applies?

---

## A7. Implementation Priority

**Phase 0.5** (insert between Phase 0 and Phase 1 of the main spec):
1. Load the ontology stack's federal spine into Neo4j: NAICS hierarchy, SOC/O*NET structure, BEA I-O categories
2. Create source registry entries for all sources in Section A2
3. Create construct disambiguation entries for adoption/productivity/exposure/innovation constructs
4. Mark normalization categories for each source

**Phase 2.5** (insert between Phase 2 and Phase 3):
1. Build data.gov CKAN API crawler for AI-tagged datasets
2. Build Ramp blog scraper for monthly AI Index extraction
3. Build PatentsView API fetcher for AI patent time series
4. Build Indeed Hiring Lab scraper for AI job posting trends

**Ongoing:**
1. Source Discovery Crawler runs monthly, checking for new data sources
2. New sources get registry entries and normalization triage
3. Template crosswalks maintained in `~/.wintermute/sources/harvest/crosswalks/`
4. Construct registry reviewed quarterly as new sources emerge
