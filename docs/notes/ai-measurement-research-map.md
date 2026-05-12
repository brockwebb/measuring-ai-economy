# AI Measurement Research Map and Scrapeable Source Watchlist

## Executive summary

AI measurement research is no longer a single literature on model benchmarks. It is a cross-domain measurement ecosystem spanning model capability evaluation, sociotechnical impact assessment, psychometrics, labor-market and productivity measurement, information operations, OSINT, cyber threat intelligence, synthetic media, crypto-financial crime, and AI governance. The strongest organizing principle is to separate the **measurement object** from the **construct**: a paper may measure a model, a deployed system, a human-AI workflow, a social outcome, a benchmark instrument, a dataset, an adversarial campaign, or a regulatory control.

For Brock Webb’s research program, the most useful architecture is a **layered watchlist**. Layer 1 should ingest paper and dataset feeds such as [arXiv](https://info.arxiv.org/help/rss.html), [Semantic Scholar](https://www.semanticscholar.org/product/api), [ACL Anthology](https://aclanthology.org), [NeurIPS proceedings](https://papers.nips.cc), [PMLR](https://proceedings.mlr.press), and [Hugging Face Datasets](https://huggingface.co/datasets). Layer 2 should monitor benchmark and evaluation infrastructure such as [Stanford HELM](https://crfm.stanford.edu/helm/), [EleutherAI LM Evaluation Harness](https://github.com/EleutherAI/lm-evaluation-harness), [Hugging Face Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard), [SWE-bench](https://www.swebench.com), [METR](https://metr.org), [MLCommons AILuminate](https://mlcommons.org/ailuminate/), and [Epoch AI benchmarks](https://epoch.ai/benchmarks). Layer 3 should monitor government, standards, and observatory sources such as [NIST AI Resource Center](https://airc.nist.gov), [NIST CAISI](https://www.nist.gov/caisi), [FCSM](https://www.fcsm.gov), [OECD.AI](https://oecd.ai), [UK AI Security Institute](https://www.aisi.gov.uk), [EU AI Office](https://digital-strategy.ec.europa.eu/en/policies/ai-office), [Stanford HAI AI Index](https://hai.stanford.edu/ai-index), [Anthropic Economic Index](https://www.anthropic.com/economic-index), and [Federal Reserve FEDS Notes](https://www.federalreserve.gov/econres/notes/).

The recurring scrape targets should be evaluated by **research value**, **freshness**, **authority**, **machine-readability**, and **construct relevance**. Daily or weekly feeds should prioritize new papers, benchmark updates, datasets, model-evaluation reports, standards drafts, and threat-intelligence updates. Monthly or quarterly sources should track adoption surveys, AI economic indices, disinformation monitors, adversarial-threat reports, crypto-crime reports, and regulatory guidance. Every ingested item should be normalized into a schema with DOI, arXiv ID, Semantic Scholar ID, source tier, domain tags, benchmark names, models evaluated, dataset links, code links, and citation-verification status.

The key methodological warning is that many AI measurement results are **not directly comparable**. Benchmark scores are sensitive to prompts, contamination, versioning, and evaluation harness; occupational exposure is not the same as observed labor-market impact; trust scales are frequently modified in ways that damage validity; OSINT and information-warfare datasets age rapidly because adversaries adapt; and crypto-crime labels often encode investigative heuristics rather than ground truth. The monitoring pipeline should therefore capture not just “what was measured,” but also **instrument version, sampling frame, construct definition, ecological validity, and uncertainty flags**.

## Working taxonomy

### Measurement objects

| Object | What is measured | Typical evidence | Why it matters |
|---|---|---|---|
| Model | Static AI artifact such as an LLM, classifier, embedding model, or detector | Benchmark scores, calibration, hallucination rate, toxicity, latency, cost | Supports model comparison, procurement, and capability tracking |
| System | Deployed AI workflow with tools, prompts, users, feedback loops, and organizational controls | Field experiments, human-AI decision studies, audit logs, production metrics | Captures real operational performance beyond isolated model scores |
| Benchmark or instrument | The evaluation itself, including item pool, scoring protocol, prompt format, and construct definition | Construct-validity analysis, IRT, inter-rater reliability, cross-benchmark agreement | Prevents invalid inferences from saturated, contaminated, or poorly specified tests |
| Dataset | Data used for training, evaluation, monitoring, or ground truth | Datasheets, provenance, representativeness, label quality, temporal splits | Connects AI evaluation to federal data-quality concepts such as utility, objectivity, and integrity |
| Sociotechnical context | Downstream effects on people, institutions, markets, and adversarial ecosystems | Surveys, RCTs, natural experiments, platform takedowns, policy indicators | Measures real-world impact, risk, and governance relevance |

### Construct families

| Construct family | Representative constructs | Anchor sources |
|---|---|---|
| Capability | Reasoning, coding, instruction-following, tool use, autonomy, multimodal performance | [HELM](https://arxiv.org/abs/2211.09110), [BIG-bench](https://github.com/google/BIG-bench), [SWE-bench](https://www.swebench.com), [METR](https://metr.org) |
| Safety and alignment | Harmfulness, jailbreak resistance, deception, persuasion, refusal behavior, calibration | [NIST AI RMF](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf), [NIST Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence), [MLCommons AILuminate](https://mlcommons.org/ailuminate/), [Anthropic persuasiveness measurement](https://www.anthropic.com/research/measuring-model-persuasiveness) |
| Validity and measurement theory | Construct validity, content validity, ecological validity, discriminability, item difficulty, benchmark saturation | [Wallach et al.](https://arxiv.org/abs/2411.10939), [MetricEval](https://aclanthology.org/2023.emnlp-main.676), [OLMES](https://arxiv.org/html/2406.08446v1), [Item Response Theory for LLM benchmarks](https://arxiv.org/abs/2505.15055) |
| Data quality and documentation | Provenance, timeliness, completeness, label quality, representativeness, contamination, documentation | [FCSM Framework for Data Quality](https://nces.ed.gov/fcsm/pdf/FCSM.20.04_A_Framework_for_Data_Quality.pdf), [Datasheets for Datasets](https://dl.acm.org/doi/10.1145/3458723), [Model Cards](https://arxiv.org/abs/1810.03993) |
| Economic and behavioral impact | Adoption, productivity, wages, exposure, trust, overreliance, cognitive offloading, persuasion, wellbeing | [Generative AI at Work](https://academic.oup.com/qje/article/140/2/889/7990658), [Experimental Evidence on Productivity Effects](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4375283), [GPTs are GPTs](https://www.science.org/doi/10.1126/science.adj0998), [Nature Human Behaviour feedback loops](https://www.nature.com/articles/s41562-024-02077-2) |
| Security and adversarial domains | OSINT extraction, information operations, disinformation, cyber TTP extraction, deepfake detection, bot detection, blockchain AML | [EUvsDisinfo dataset](https://arxiv.org/html/2406.12614v1), [Meta Adversarial Threat Reports](https://transparency.meta.com/metasecurity/), [OpenAI influence and cyber operations update](https://cdn.openai.com/threat-intelligence-reports/influence-and-cyber-operations-an-update_October-2024.pdf), [MITRE ATT&CK Evaluations](https://attackevals.mitre-engenuity.org/), [Elliptic2](https://arxiv.org/html/2404.19109v3), [Deepfake-Eval-2024](https://arxiv.org/abs/2503.02857) |

## High-value literature map

### AI evaluation, validity, and governance

| Priority | Source | Measurement contribution | Monitor for |
|---|---|---|---|
| P1 | [Holistic Evaluation of Language Models](https://arxiv.org/abs/2211.09110) | Defines scenario-by-metric evaluation across accuracy, calibration, robustness, fairness, bias, toxicity, and efficiency | HELM releases, scenario coverage, new metric definitions |
| P1 | [OLMES: A Standard for Language Model Evaluations](https://arxiv.org/html/2406.08446v1) | Standardizes prompt format, in-context examples, probability normalization, and task formulation | Evaluation-harness changes and reproducibility guidance |
| P1 | [Evaluating GenAI Systems is a Social Science Measurement Challenge](https://arxiv.org/abs/2411.10939) | Translates social-science measurement logic into GenAI evaluation: background concept, systematized concept, instrument, and measurement | Construct-definition frameworks and benchmark critiques |
| P1 | [MetricEval](https://aclanthology.org/2023.emnlp-main.676) | Applies measurement theory to natural language generation metrics and human evaluation reliability | LLM-as-judge reliability and NLG metric audits |
| P1 | [Datasheets for Datasets](https://dl.acm.org/doi/10.1145/3458723) | Establishes dataset documentation categories for motivation, composition, collection, use, and maintenance | Dataset governance templates and audit checklists |
| P1 | [Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993) | Establishes structured model reporting, subgroup evaluation, and intended-use disclosure | Model reporting, procurement evidence, transparency artifacts |
| P1 | [FCSM Framework for Data Quality](https://nces.ed.gov/fcsm/pdf/FCSM.20.04_A_Framework_for_Data_Quality.pdf) | Defines utility, objectivity, and integrity as federal data-quality domains | Bridges between federal statistical quality and AI evaluation |
| P1 | [NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf) | Provides GOVERN, MAP, MEASURE, and MANAGE functions for trustworthy AI risk management | Federal AI evaluation controls and measurement categories |
| P1 | [NIST Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) | Extends AI RMF to generative AI risks such as confabulation, harmful bias, and human-AI configuration | GenAI-specific risk measurement updates |
| P2 | [Internal Algorithmic Auditing](https://dl.acm.org/doi/10.1145/3351095.3372873) | Defines organizational audit processes for AI accountability across the lifecycle | Audit workflow, documentation artifacts, governance roles |
| P2 | [Sociotechnical Safety Evaluation of Generative AI Systems](https://arxiv.org/abs/2310.11986) | Distinguishes capability evaluation, human-interaction evaluation, and systemic-impact evaluation | Evaluation designs that go beyond isolated model tests |
| P2 | [Foundation Models report](https://arxiv.org/abs/2108.07258) | Frames opportunities, risks, applications, and measurement agenda for foundation models | Cross-domain risk and capability taxonomy updates |

### Economic, behavioral, and psychological measurement

| Priority | Source | Measurement contribution | Monitor for |
|---|---|---|---|
| P1 | [Generative AI at Work](https://academic.oup.com/qje/article/140/2/889/7990658) | Field experiment estimating productivity effects of AI assistance in customer support | Causal workplace-AI designs, heterogeneous effects by skill |
| P1 | [Experimental Evidence on the Productivity Effects of Generative AI](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4375283) | Pre-registered writing-task experiment measuring time savings and output quality | Replications across task types and durable-learning effects |
| P1 | [GPTs are GPTs](https://www.science.org/doi/10.1126/science.adj0998) | Defines task-level occupational exposure using human and model annotations of O*NET tasks | Recalibration of exposure indices as capabilities shift |
| P1 | [Rapid Adoption of Generative AI](https://www.nber.org/system/files/working_papers/w32966/w32966.pdf) | Uses nationally representative survey data to track GenAI adoption | Demographic and occupational diffusion metrics |
| P1 | [Anthropic Economic Index](https://www.anthropic.com/economic-index) | Maps real-world Claude usage to O*NET-style tasks and augmentation/automation patterns | Quarterly task-level usage shifts and productivity estimates |
| P1 | [Federal Reserve FEDS Notes](https://www.federalreserve.gov/econres/notes/) | Triangulates AI adoption estimates across business and population surveys | Survey wording, weighting, and sampling-frame reconciliation |
| P1 | [OECD AI Capability Indicators](https://www.oecd.org/en/publications/2025/06/introducing-the-oecd-ai-capability-indicators_7c0731f0.html) | Tracks AI capabilities against human-ability domains for policy analysis | Annual capability-indicator updates |
| P2 | [How Human-AI Feedback Loops Alter Human Judgements](https://www.nature.com/articles/s41562-024-02077-2) | Measures bias amplification through repeated human-AI interaction | Feedback-loop designs and social-judgment outcomes |
| P2 | [Consequences of AI Training on Human Decision-Making](https://pmc.ncbi.nlm.nih.gov/articles/PMC11331131/) | Measures how people alter behavior when their actions are used to train AI | RLHF/data-quality implications |
| P2 | [Science of Human-AI Decision Making survey](https://arxiv.org/abs/2112.11471) | Taxonomizes empirical human-AI decision studies and outcome variables | Study designs, overreliance measures, ecological validity |
| P2 | [Trust in AI questionnaire validation](https://arxiv.org/abs/2403.00582) | Compares and validates AI trust instruments across contexts | Psychometric scale selection and trust/distrust separation |
| P2 | [Trust in Automated Systems scale review](https://journals.sagepub.com/doi/10.1177/10711813251357911) | Documents validity problems caused by modifying trust scales | Instrument drift and validity warnings |
| P2 | [Generative AI personalized persuasion](https://pmc.ncbi.nlm.nih.gov/articles/PMC10897294/) | Measures LLM personalization effects on persuasion | Persuasion measurement, microtargeting, attitude shifts |
| P2 | [LLM persuasion meta-analysis](https://www.nature.com/articles/s41598-025-30783-y) | Synthesizes LLM persuasiveness studies and heterogeneity | Moderator analysis and effect-size stability |

### OSINT, information warfare, cyber, and crypto measurement

| Priority | Source | Measurement contribution | Monitor for |
|---|---|---|---|
| P1 | [AIT OSINT Summer2024 Dataset](https://zenodo.org/records/14228995) | Provides cybersecurity OSINT news items for NLP clustering and entity extraction | OSINT dataset releases and entity/linking benchmarks |
| P1 | [NLP-Based Techniques for Cyber Threat Intelligence](https://arxiv.org/abs/2311.08807) | Surveys NLP methods for IoC extraction, TTP mapping, and CTI report parsing | CTI extraction benchmarks and ATT&CK-aligned tasks |
| P1 | [EUvsDisinfo dataset](https://arxiv.org/html/2406.12614v1) | Provides multilingual pro-Kremlin disinformation cases for detection research | Multilingual disinformation datasets and label updates |
| P1 | [vera.ai datasets](https://www.veraai.eu/category/datasets) | Releases multimodal misinformation and verification datasets | Dataset additions, benchmark revisions, media modalities |
| P1 | [Deepfake-Eval-2024](https://arxiv.org/abs/2503.02857) | Measures in-the-wild synthetic media detection under real-world distribution shift | Detector decay, cross-modal robustness, new dataset releases |
| P1 | [NewsGuard AI Misinformation Monitor](https://www.newsguardtech.com/special-reports/ai-tracking-center) | Recurring audits of chatbots against known false claims | Monthly model-level misinformation fail rates |
| P1 | [Meta Adversarial Threat Reports](https://transparency.meta.com/metasecurity/) | Longitudinal public record of coordinated inauthentic behavior and platform enforcement | CIB takedowns, actor TTPs, platform-level indicators |
| P1 | [OpenAI influence and cyber operations update](https://cdn.openai.com/threat-intelligence-reports/influence-and-cyber-operations-an-update_October-2024.pdf) | Introduces operational reporting on AI-enabled influence and cyber campaigns | Breakout Scale, disrupted operations, AI-enabled TTPs |
| P1 | [MITRE ATT&CK Evaluations](https://attackevals.mitre-engenuity.org/) | Evaluates EDR/XDR products against emulated adversary techniques | Detection coverage, false positives, technique-level analytics |
| P1 | [MITRE ATT&CK](https://attack.mitre.org) | Provides machine-readable tactics, techniques, procedures, and STIX/TAXII bundles | CTI ontology updates and technique revisions |
| P1 | [Elliptic2](https://arxiv.org/html/2404.19109v3) | Provides large-scale labeled Bitcoin subgraphs for AML and illicit-finance detection | Blockchain graph-learning benchmarks and AML typologies |
| P1 | [Chainalysis Crypto Crime Reports](https://www.chainalysis.com/reports/) | Tracks illicit on-chain activity, ransomware, hacks, sanctions evasion, and mixing | Annual and monthly crypto-crime measurement updates |
| P2 | [FATF publications](https://www.fatf-gafi.org/en/publications.html) | Sets international AML/CFT guidance for virtual assets and VASPs | Regulatory measurement requirements and jurisdictional risk |
| P2 | [MGTAB](https://github.com/GraphDet/MGTAB) | Provides multi-relational graph benchmark for bot and stance detection | Bot-detection benchmark updates and social graph methods |

## Scrapeable and monitorable source watchlist

### P1 feeds and APIs

| Source | URL | Domain | Cadence | Access method | Extract |
|---|---|---|---|---|---|
| arXiv AI/ML/NLP/stat feeds | [arXiv RSS](https://info.arxiv.org/help/rss.html) | Papers | Daily | RSS/API | Title, authors, abstract, arXiv ID, categories, PDF |
| Semantic Scholar Graph API | [Semantic Scholar API](https://www.semanticscholar.org/product/api) | Papers/citation graph | Continuous | REST API | S2 ID, citations, references, OA PDF, venue, year |
| ACL Anthology | [ACL Anthology](https://aclanthology.org) | NLP proceedings | Nightly/per conference | Bulk BibTeX/HTML | Abstract, BibTeX, venue, paper URL |
| NeurIPS Proceedings | [NeurIPS papers](https://papers.nips.cc) | ML proceedings | Annual | HTML | Datasets & Benchmarks track, paper metadata |
| PMLR | [PMLR](https://proceedings.mlr.press) | ML proceedings | Per volume | HTML/RSS | ICML, AISTATS, workshop volumes |
| Hugging Face Datasets | [HF Datasets](https://huggingface.co/datasets) | Datasets/benchmarks | Continuous | REST API | Dataset card, tags, last modified, downloads |
| Hugging Face Open LLM Leaderboard | [Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) | LLM benchmarks | Continuous | HF dataset/API | Model, score, benchmark, date |
| Stanford HELM | [HELM](https://crfm.stanford.edu/helm/) | Evaluation infrastructure | Periodic | HTML/GitHub | Scenario, metric, model, score |
| EleutherAI LM Evaluation Harness | [GitHub](https://github.com/EleutherAI/lm-evaluation-harness) | Evaluation harness | Continuous | GitHub API/RSS | New tasks, releases, task configs |
| SWE-bench | [SWE-bench](https://www.swebench.com) | Agent/code benchmark | Continuous | HTML/GitHub | Model ranking, task type, resolved rate |
| METR | [METR](https://metr.org) | Autonomy/capability eval | Per report | HTML/PDF | Time horizon, task success, eval design |
| MLCommons AILuminate | [AILuminate](https://mlcommons.org/ailuminate/) | Safety benchmark | Periodic | HTML | Hazard category, release notes, benchmark versions |
| Epoch AI | [Epoch Trends](https://epoch.ai/trends) | Compute/scaling | Rolling | HTML/CSV/RSS | Compute, cost, model metadata, benchmarks |
| NIST AI Resource Center | [AIRC](https://airc.nist.gov) | Standards/governance | Periodic | RSS/HTML | RMF updates, profiles, guidance |
| UK AI Security Institute | [AISI](https://www.aisi.gov.uk) | AI safety eval | Periodic | GOV.UK Atom/HTML | Eval reports, methods, policy updates |
| EU AI Office | [EU AI Office](https://digital-strategy.ec.europa.eu/en/policies/ai-office) | Regulation/standards | Periodic | HTML/RSS | GPAI guidance, Code of Practice, standards |
| OECD.AI | [OECD.AI](https://oecd.ai) | Policy indicators | Continuous/annual | HTML/RSS | Country indicators, capability metrics |
| Stanford HAI AI Index | [AI Index](https://hai.stanford.edu/ai-index) | Annual synthesis | Annual | PDF/HTML | AI R&D, adoption, policy, public opinion |
| Anthropic Economic Index | [Economic Index](https://www.anthropic.com/economic-index) | AI labor/task usage | Quarterly | HTML/PDF | O*NET-mapped tasks, augmentation/automation ratio |
| Census BTOS | [BTOS](https://www.census.gov/econ/btos) | Business adoption | Biweekly | Census downloads/HTML | AI adoption by firm/sector, planned adoption |
| Federal Reserve FEDS Notes | [FEDS Notes](https://www.federalreserve.gov/econres/notes/) | Economic measurement | Irregular | HTML/RSS | Survey triangulation, adoption estimates |
| DFRLab | [DFRLab](https://dfrlab.org) | OSINT/IO | Daily | RSS | Investigation topic, actor, platform, region |
| Meta Adversarial Threat Reports | [Meta Security](https://transparency.meta.com/metasecurity/) | IO/CIB | Quarterly | HTML/PDF | Actor, platform, takedown, TTPs |
| MITRE ATT&CK | [ATT&CK](https://attack.mitre.org) | Cyber ontology | Quarterly | STIX/TAXII/API | Technique IDs, tactics, mitigations |
| MITRE ATT&CK Evaluations | [ATT&CK Evaluations](https://attackevals.mitre-engenuity.org/) | EDR/XDR benchmarks | Annual | HTML/downloads | Vendor coverage, technique detection |
| Chainalysis Reports | [Chainalysis reports](https://www.chainalysis.com/reports/) | Crypto crime | Monthly/annual | RSS/HTML/PDF | Illicit volume, typologies, sanctions, ransomware |
| FATF Publications | [FATF](https://www.fatf-gafi.org/en/publications.html) | AML/CFT regulation | Irregular | HTML/RSS | Virtual-asset guidance, jurisdictional risk |

### P2 sources for breadth and early signals

| Source | URL | Domain | Cadence | Access method | Extract |
|---|---|---|---|---|---|
| DBLP | [DBLP](https://dblp.org) | Bibliography | Continuous | API/RSS | Venue, author, paper metadata |
| ICLR Proceedings | [ICLR](https://proceedings.iclr.cc) | ML proceedings | Annual | HTML | Accepted papers, eval papers, datasets |
| FAccT | [FAccT](https://facctconference.org) | Fairness/accountability | Annual | HTML | Sociotechnical measurement, audits |
| AI Incident Database | [AIID](https://incidentdatabase.ai) | Incidents | Continuous | API/HTML | Incident taxonomy, harm type, system |
| GovAI | [GovAI](https://www.governance.ai) | AI governance | Continuous | RSS | Compute, policy, safety governance |
| AI Now Institute | [AI Now](https://ainowinstitute.org) | Sociotechnical AI | Annual/quarterly | RSS | Policy, accountability, labor, power |
| Import AI | [Import AI](https://importai.substack.com) | Weekly AI synthesis | Weekly | RSS | New papers, evaluation ideas, policy |
| The Gradient | [The Gradient](https://thegradient.pub) | ML analysis | Monthly | RSS | Technical explainers, eval critiques |
| CSET Georgetown | [CSET](https://cset.georgetown.edu/publications/) | AI policy/security | Frequent | RSS | AI policy, national security, compute |
| EUvsDisinfo | [EUvsDisinfo](https://euvsdisinfo.eu) | Disinformation | Weekly | HTML/Mendeley | Cases, narrative, language, actor |
| vera.ai | [vera.ai datasets](https://www.veraai.eu/category/datasets) | Misinformation datasets | Ongoing | HTML/Zenodo/GitHub | Dataset cards, labels, media type |
| NewsGuard AI Monitor | [NewsGuard AI tracking](https://www.newsguardtech.com/special-reports/ai-tracking-center) | AI misinformation | Monthly | HTML | LLM fail rate, false-claim categories |
| OSoMe | [OSoMe](https://osome.iu.edu) | Social media/bot research | Active | Tool/API | Bot/disinfo observatory outputs |
| MISP Feeds | [MISP communities](https://www.misp-project.org/communities/) | Threat intel | Real-time | API/JSON/CSV | IoCs, events, threat actors |
| Elliptic Blog | [Elliptic](https://www.elliptic.co/blog) | Crypto AML | Ad hoc | HTML/RSS | AML typologies, dataset announcements |
| SlowMist reports | [SlowMist reports](https://www.slowmist.com/report/) | Blockchain security | Annual/ad hoc | PDF/HTML | Hacks, AML, chain incidents |

## Captured-item schema

```json
{
  "item_id": "sha256(normalized_title + canonical_url)",
  "source_id": "arxiv_cs_cl",
  "source_tier": "P1",
  "source_category": "preprint_feed",
  "title": "string",
  "url": "string",
  "doi": "string | null",
  "arxiv_id": "string | null",
  "semantic_scholar_id": "string | null",
  "authors": ["string"],
  "affiliations": ["string"],
  "abstract": "string | null",
  "published_date": "ISO8601",
  "ingested_date": "ISO8601",
  "updated_date": "ISO8601 | null",
  "venue": "string | null",
  "content_type": "preprint | proceedings | report | standard | dataset | benchmark_update | blog_post | threat_report",
  "domains": ["capability_eval", "safety_eval", "data_quality", "labor_economics", "psychometrics", "osint", "information_warfare", "cyber", "crypto_aml"],
  "constructs": ["accuracy", "calibration", "construct_validity", "trust", "adoption", "persuasion", "ttp_extraction", "bot_detection"],
  "benchmark_names": ["MMLU", "GPQA", "SWE-bench", "HELM", "ATT&CK"],
  "models_evaluated": ["string"],
  "datasets_used": ["string"],
  "code_url": "string | null",
  "dataset_url": "string | null",
  "pdf_url": "string | null",
  "citation_count": "integer | null",
  "open_access": "boolean",
  "access_method": "RSS | API | HTML_scrape | GitHub_API | bulk_download | manual_pdf",
  "verification_status": "unverified | doi_verified | arxiv_verified | s2_verified | crossref_verified",
  "dedup_status": "new | duplicate | update_of:<item_id>",
  "quality_flags": ["possible_contamination", "weak_construct_validity", "observational_only", "temporal_leakage", "adversarial_drift"],
  "notebooklm_tags": ["string"],
  "notes": "string | null"
}
```

## Extraction signals by domain

| Domain | Signals to extract | Quality filters |
|---|---|---|
| LLM benchmarks | Model, benchmark, score, prompt format, evaluation harness, number of shots, temperature, test-set version, date | Require harness/version details; flag self-reported scores without reproducibility metadata |
| Measurement validity | Construct definition, item pool, reliability, IRT model, discriminability, convergent/discriminant validity | Keep papers that specify construct-to-instrument logic; flag benchmark papers with only face validity |
| Federal data quality | Utility, objectivity, integrity, timeliness, completeness, representativeness, provenance, contamination | Map AI evidence to [FCSM data-quality dimensions](https://nces.ed.gov/fcsm/pdf/FCSM.20.04_A_Framework_for_Data_Quality.pdf) |
| Economic adoption | Survey question wording, sampling frame, weighting, sector, occupation, task type, adoption intensity | Never compare adoption rates without question wording and weighting notes |
| Productivity and labor | Task type, treatment, baseline, skill group, duration, outcome quality, time saved, wage/occupation mapping | Prioritize RCTs, field experiments, DiD, and natural experiments over self-reported productivity |
| Human-AI behavior | Reliance, overreliance, trust, distrust, confidence, accuracy, calibration, cognitive load, retention | Require validated scales or explicit psychometric rationale; flag modified trust scales |
| Persuasion and influence | Attitude shift, behavioral compliance, persistence, personalization variable, audience segment | Separate immediate Likert change from durable attitude or behavior change |
| OSINT | Entity F1, relation extraction, geolocation error, clustering score, analyst time-to-assessment | Require language, region, and source-provenance metadata |
| Information warfare | Actor, campaign, platform, narrative, coordination window, takedown date, cross-platform links | Treat platform takedowns as enforcement evidence, not perfect ground truth |
| Cyber CTI | IoC extraction precision/recall, ATT&CK technique mapping, STIX entity/relation F1, false positives | Use ATT&CK IDs as normalized ontology keys |
| Crypto AML | Wallet/subgraph labels, typology, transaction window, AUROC, precision at low FPR, temporal drift | Treat “licit” labels as absence of known illicit indicators unless confirmed |
| Synthetic media | Modality, generator family, detector, AUC/FAR/FRR, in-the-wild vs. lab source, release date | Measure detector decay across model generations and real-world media |

## Query strategy

### Daily paper triage

Use arXiv RSS and Semantic Scholar bulk search as the first-pass discovery layer. The combined arXiv categories for this project are `cs.AI`, `cs.LG`, `cs.CL`, `stat.ML`, `cs.CY`, `cs.CR`, `cs.SI`, `econ.GN`, and `q-fin` where relevant; arXiv supports category RSS feeds documented in its [RSS help page](https://info.arxiv.org/help/rss.html).

Recommended query clusters:

| Cluster | Query terms |
|---|---|
| Capability and benchmarks | `LLM benchmark`, `capability evaluation`, `MMLU`, `GPQA`, `SWE-bench`, `agent benchmark`, `tool use evaluation` |
| Measurement theory | `construct validity`, `item response theory`, `benchmark saturation`, `evaluation contamination`, `measurement error`, `psychometrics AI evaluation` |
| Safety and persuasion | `AI safety evaluation`, `jailbreak benchmark`, `deception evaluation`, `LLM persuasiveness`, `red teaming`, `refusal behavior` |
| Economic and labor | `AI adoption`, `generative AI productivity`, `occupational exposure`, `O*NET`, `labor market AI`, `firm AI survey` |
| Human behavior | `human AI decision making`, `overreliance`, `automation bias`, `trust in AI`, `cognitive offloading`, `AI feedback loop` |
| OSINT and IO | `OSINT AI`, `influence operations detection`, `coordinated inauthentic behavior`, `disinformation dataset`, `multimodal misinformation` |
| Cyber CTI | `threat intelligence extraction`, `ATT&CK mapping`, `STIX extraction`, `IoC extraction`, `LLM cybersecurity evaluation` |
| Crypto AML | `blockchain money laundering`, `crypto crime graph neural network`, `illicit transaction detection`, `AML subgraph classification` |

### GitHub and dataset monitoring

GitHub should be used for evaluation harnesses, benchmark implementations, datasets, and release notes. High-yield monitors include [EleutherAI LM Evaluation Harness](https://github.com/EleutherAI/lm-evaluation-harness), [Stanford HELM](https://github.com/stanford-crfm/helm), [OpenAI Evals](https://github.com/openai/evals), [Google BIG-bench](https://github.com/google/BIG-bench), [MGTAB](https://github.com/GraphDet/MGTAB), and [WildBench](https://github.com/allenai/WildBench).

Suggested searches:

```text
topic:llm-evaluation language:python stars:>50
topic:ai-benchmark created:>2024-01-01
topic:ai-safety-evaluation
topic:misinformation-detection
topic:cyber-threat-intelligence
topic:blockchain-analytics
```

## Deduplication and citation verification workflow

1. **Normalize metadata**: Lowercase titles, remove punctuation artifacts, resolve canonical URLs, strip arXiv version suffixes, and normalize author names.
2. **Fingerprint records**: Use DOI first, arXiv ID second, Semantic Scholar ID third, and `sha256(normalized_title + canonical_url)` as fallback.
3. **Merge exact duplicates**: Preserve `also_seen_at[]` so the same paper found via arXiv, Semantic Scholar, and a lab blog is one record with multiple discovery paths.
4. **Fuzzy-match non-DOI items**: Use title similarity and SPECTER-style embeddings; candidate duplicates above a high threshold should enter manual review rather than auto-merge.
5. **Track versions**: Link preprint, conference, journal, code, dataset, and errata records; mark the peer-reviewed version canonical when appropriate.
6. **Verify citation identity**: Check DOI metadata via Crossref, arXiv metadata via arXiv, citation graph via Semantic Scholar, and venue identity via DBLP or the official proceedings site.
7. **Flag risk conditions**: Add flags for withdrawn papers, benchmark contamination, retractions, predatory or unclear venues, inaccessible datasets, and unsupported causal claims.
8. **Export only verified sources to NotebookLM**: Use `doi_verified`, `arxiv_verified`, or `s2_verified` items for NotebookLM ingestion to keep the source corpus auditable.

## Recommended monitoring architecture

### Weekly operating cadence

| Day | Task | Tools |
|---|---|---|
| Monday | Pull all RSS/API feeds and deduplicate | arXiv RSS/API, Semantic Scholar, GitHub API, Hugging Face API |
| Tuesday | Run domain classifiers and construct tags | Keyword rules, embeddings, LLM classifier with audit log |
| Wednesday | Citation verification and metadata repair | Crossref, arXiv, Semantic Scholar, DBLP |
| Thursday | Quality triage and human review | Validity checklist, causal-design checklist, data-quality flags |
| Friday | Export curated source packs | NotebookLM source bundle, Zotero/BibTeX, Markdown digest |

### Minimal viable pipeline

1. Ingest P1 sources from arXiv, Semantic Scholar, Hugging Face, GitHub releases, NIST, OECD, HELM, Anthropic Economic Index, Census BTOS, DFRLab, Meta threat reports, MITRE ATT&CK, Chainalysis, and FATF.
2. Normalize each item into the captured-item schema.
3. Apply domain labels and construct labels.
4. Verify DOI/arXiv/Semantic Scholar identity.
5. Send only verified, high-priority items into NotebookLM or a GraphRAG corpus.
6. Produce a weekly digest with sections for “new measurement methods,” “new datasets/benchmarks,” “new domain evidence,” “standards/governance updates,” and “items requiring manual verification.”

## Methodological caveats

Benchmark scores are not comparable unless the evaluation harness, prompt format, number of shots, decoding settings, and benchmark version are documented. Standardization work such as [OLMES](https://arxiv.org/html/2406.08446v1) and independent infrastructure such as [HELM](https://crfm.stanford.edu/helm/) should be preferred over uncited vendor leaderboard claims.

AI adoption is not a single construct. Business surveys, worker surveys, usage logs, and firm-level technology inventories measure different behaviors; adoption estimates should therefore be harmonized by sampling frame, question wording, weighting, and unit of analysis before comparison. The most useful recurring sources for triangulation are [Census BTOS](https://www.census.gov/econ/btos), [Federal Reserve FEDS Notes](https://www.federalreserve.gov/econres/notes/), [Anthropic Economic Index](https://www.anthropic.com/economic-index), and nationally representative survey work such as [Rapid Adoption of Generative AI](https://www.nber.org/system/files/working_papers/w32966/w32966.pdf).

Occupational exposure is not impact. Exposure frameworks such as [GPTs are GPTs](https://www.science.org/doi/10.1126/science.adj0998) and earlier AI occupational exposure work are useful for identifying tasks susceptible to AI capability, but they do not by themselves estimate displacement, productivity, wages, or welfare.

Trust, persuasion, and overreliance require psychometric discipline. Trust-in-AI studies should distinguish cognitive trust, affective trust, behavioral reliance, distrust, and acceptance; validation work such as [Scharowski et al.](https://arxiv.org/abs/2403.00582) and scale-use reviews such as [Gutzwiller et al.](https://journals.sagepub.com/doi/10.1177/10711813251357911) are useful filters for deciding which instruments belong in a research corpus.

Security and adversarial benchmarks decay quickly. In-the-wild synthetic-media work such as [Deepfake-Eval-2024](https://arxiv.org/abs/2503.02857), platform-level reporting such as [Meta Adversarial Threat Reports](https://transparency.meta.com/metasecurity/), and operational security reporting such as [OpenAI’s influence and cyber operations update](https://cdn.openai.com/threat-intelligence-reports/influence-and-cyber-operations-an-update_October-2024.pdf) should be treated as time-stamped evidence rather than stable ground truth.

Crypto-financial crime labels are operational rather than perfect. Datasets and reports such as [Elliptic2](https://arxiv.org/html/2404.19109v3), [Chainalysis reports](https://www.chainalysis.com/reports/), and [FATF publications](https://www.fatf-gafi.org/en/publications.html) are essential, but labels often reflect heuristics, investigative intelligence, and absence of known illicit indicators rather than comprehensive truth.

## Recommended first build

The first implementation should be a P1-only monitor with about 25 sources. It should run weekly, store normalized records in a small relational database or document store, export verified sources to NotebookLM, and maintain a GraphRAG-ready citation graph using Semantic Scholar IDs, DOIs, arXiv IDs, benchmark names, datasets, models, and domains. After the weekly digest is stable, add P2 sources and domain-specific modules for OSINT/IO, cyber CTI, crypto AML, and behavioral/psychometric evidence.

