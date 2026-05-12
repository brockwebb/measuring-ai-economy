# AI Measurement Research Across Life Domains: Papers, Frameworks & Sources to Monitor

## Executive Summary

AI measurement research has exploded across virtually every sector of human activity. The field has moved beyond simple capability benchmarks into nuanced, domain-specific quantification of AI's economic, behavioral, psychological, security, and environmental effects. This report maps the current landscape of AI measurement research across eight major life domains, with curated lists of seminal and recent papers and a directory of sites, databases, and publication feeds worth monitoring regularly for new work.

***

## 1. Economic Measurement

### Key Research

Economic measurement of AI has matured significantly, with new indices replacing traditional keyword-based indicators with LLM-driven semantic analysis.

**The AI Economy Score** (Rutgers/University of Chicago, 2025) uses generative AI to score corporate earnings call transcripts and demonstrates the resulting measure robustly predicts GDP growth, industrial production, employment, and wages for up to 14 quarters ahead — outperforming traditional survey forecasts. The Chicago Booth team showed that ChatGPT's assessment of managerial expectations "strongly predicted the following quarter's GDP, adjusted for inflation, with the effect lasting for a year after the conference call".[^1][^2]

**AI Labor Market Measurement** has become its own sub-field. Anthropic (March 2026) introduced *observed exposure*, combining O*NET occupation profiles with actual Claude usage data to weight automated vs. augmentative use — finding the ten most exposed occupations include computer programmers, customer service reps, financial analysts, and data entry keyers, but with only a 16% relative employment decline for workers ages 22–25 in the most exposed occupations and no aggregate unemployment effect. The Yale Budget Lab's parallel tracker as of April 2026 similarly finds no statistically significant relationship between AI exposure measures and changes in employment or unemployment. Brookings characterizes AI labor market research as still being in "the first inning," with strong demand outstripping rigorous supply.[^3][^4][^5][^6]

**Real-time GDP Nowcasting with AI** has shown machine learning algorithms significantly outperform simple autoregressive benchmarks and dynamic factor models; central banks using AI systems report policy response time improvements of 3–6 weeks, and advanced systems achieve reliable 2–3 quarter ahead forecasts versus 1–2 quarters for traditional methods.[^7]

**The Forecasting Research Institute / NBER** published in March 2026 the most comprehensive expert elicitation study to date, finding that economists assign only a 14% probability to an "exceptionally rapid-progress" AI scenario that would meaningfully shift GDP growth and wealth inequality before 2030, despite expecting substantial capability improvement.[^8][^9]

### Key Papers
| Paper | Institution | Focus |
|-------|-------------|-------|
| *Behavioral Economics of AI: LLM Biases and Corrections* (Jan 2026) | NBER Working Paper #34745 | Systematic behavioral biases in LLM economic decisions |
| *Harnessing Generative AI for Economic Insights* | Rutgers/Chicago | AI Economy Score predicting GDP, 14-quarter horizon |
| *Forecasting the Economic Effects of AI* (2026) | NBER #35046 | Expert elicitation on GDP, labor force, TFP projections |
| *AI, Productivity, and Labor Markets* (Feb 2026) | Law & Economics Center | Review of empirical evidence across 35.9% GenAI-using workforce |
| *Labor Market Impacts of AI: A New Measure* (Feb 2026) | Anthropic | "Observed exposure" framework |
| *Tracking the Impact of AI on the Labor Market* (Apr 2026) | Yale Budget Lab | Continuous occupational mix monitoring |

***

## 2. Behavioral Measurement

### Key Research

AI behavioral measurement sits at the intersection of cognitive science, economics, and computer science, encompassing both *how AI measures human behavior* and *how AI itself exhibits behavioral biases*.

**Synthetic Behavioral Participants**: PwC Strategy& (2025) validated that LLM-based synthetic participants can mimic human survey responses in Saudi Arabia, UAE, and the US across sustainability, financial literacy, and labor force domains, with "interview-based twins" achieving over 80% accuracy on population-level survey tasks. This raises methodological questions about the validity of AI "steerability" for behavioral policy testing.[^10][^11]

**Behavioral Biases in LLMs**: NBER WP #34745 runs the most comprehensive set of behavioral economics experiments on LLMs to date, finding systematic replication of human heuristics and biases (loss aversion, anchoring, overconfidence) across model families — with important implications for AI systems deployed in financial and policy contexts.[^12]

**Behavioral Forecasting Systems**: BBVA's behavioral economics unit reports AI-enabled "synthetic panels and archetypes" allow behavioral experiments without real participants, overcoming the perennial problem of hard-to-reach populations (e.g., C-suite executives) in traditional online panels. Behavioral forecasting predictive models incorporating contextual variables and external stimuli can now anticipate future decisions and identify friction points at scale.[^13]

**China Journal of Econometrics** (Nov 2025) identifies three emerging research directions in behavioral science × AI: AI as a new instrument for causal identification, AI-generated synthetic populations for policy simulation, and behavioral science methods applied to AI alignment.[^14]

### Key Papers
| Paper | Source | Focus |
|-------|--------|-------|
| *Behavioral Economics of AI: LLM Biases and Corrections* | NBER WP #34745 | Comprehensive bias measurement |
| *Generative AI to Augment Behavioral Research* (2025) | PwC Strategy& | Synthetic participant validation |
| *Evaluating AI-Simulated Behavior* (Aug 2025) | Nielsen Norman Group | Interview-based digital twins, 80%+ accuracy |
| *Behavioral Science in the Age of AI* (Nov 2025) | China Journal of Econometrics | Three emerging research directions |

***

## 3. Psychological Measurement

### Key Research

AI's role in psychological measurement spans two directions: AI as a more accurate *measuring tool* for mental states, and AI as a subject causing measurable psychological changes in humans.

**AI-Driven Dynamic Psychological Assessment** (PMC, Nov 2025): A WeChat mini-program study of university students found AI-driven dynamic models significantly improved accuracy of anxiety (SAS) and depression (SDS) assessments over static single-time-point measurements, and showed stronger correlation with clinician-rated gold standards. The system also appears to function as an "assessment-intervention loop," reducing clinically-rated anxiety and depression through continuous self-monitoring feedback.[^15]

**Digital Phenotyping at Scale**: The APA's *Monitor on Psychology* (Jan 2026) reports researchers using brain scans plus data from phones and wearables to determine optimal interventions before beginning treatment — bypassing trial-and-error — and AI chatbots (e.g., Therabot) have achieved 51% symptom reduction in generative AI therapy trials.[^16][^17]

**AI in Mental Health Diagnosis**: A systematic review in *Psychological Medicine* (Cambridge, Jan 2025) covers AI applications in diagnosis, monitoring, and intervention, finding diagnostic accuracy ranges from 60–98% for differentiating mild cognitive impairment from healthy controls and 68–100% for mental disorder diagnosis broadly.[^18][^19]

**AI-Induced Psychological Harm**: A *Mental Health Journal* narrative review (May 2025) is "the first dedicated examination of AI-induced psychological phenomena," identifying three major themes: psychological dependency and attachment formation, crisis incidents and harmful outcomes, and heightened vulnerability among adolescents and those with mental illness.[^17]

**Patient Values & Preferences Measurement** (*NPJ Digital Medicine*, Nature, Dec 2025): Scoping review of how AI — particularly NLP and DCEs — measures and predicts patient preferences, finding substantial potential alongside gaps in longitudinal validation.[^20]

***

## 4. OSINT and Intelligence Measurement

### Key Research

AI has fundamentally transformed OSINT from reactive human-curated scanning to proactive, automated, real-time intelligence gathering with measurable performance characteristics.

**AI-Driven Evolution of OSINT** (Academia.edu, 2025): Systematic analysis of academic literature finds that AI integration has enabled automated data collection, enhanced analytical precision, and real-time threat detection, but systems remain "vulnerable to collection and analytical errors that human cognition can readily detect," underscoring the irreplaceable role of human oversight in validation.[^21]

**OSINT CyberVision PoC** (LUISS University thesis, 2025): An LLM + RAG + ReAct-agent system demonstrated 92% factual accuracy, 4% hallucination rate, P@5 retrieval precision of 0.83, and 89% task completion for autonomous multi-step OSINT analysis — validated on vulnerability analysis, threat actor profiling, and IoC investigation.[^22]

**AI-Powered OSINT Reconnaissance Tools** (IJTSRD): Reviews the full stack — web scraping, NLP, ML, computer vision — with demonstrated improvements in automated pattern recognition, dark web monitoring, deepfake detection, and social media sentiment analysis for threat detection.[^23]

**Systematic Review of GELSI Literature** (PubMed, 2023): Analysis of 571 publications assessing AI-powered OSINT, using the GELSI framework (Geospatial, Emotional, Linguistic, Social, Imagery) to identify gaps and suggest future directions.[^24]

**Human-AI Collaborative OSINT** (ACM CI 2025): Research on "OSINT Research Studios" — flexible frameworks enabling trained novices to support expert-led investigations using AI — addresses the scalability gap between expert capacity and investigation volume.[^25]

***

## 5. Information Warfare and Disinformation Measurement

### Key Research

This is the fastest-accelerating domain in AI measurement research, with both offensive capability measurement and defensive detection measurement advancing rapidly.

**AI-GPR Index: Measuring Geopolitical Risk** (Federal Reserve Board / Matteo Iacoviello, April 2026): Replaces keyword matching with GPT-4o-mini semantic evaluation of ~5 million newspaper articles (NYT, WaPo, Chicago Tribune) from 1960–2025. The AI-GPR produces a stronger estimated negative effect of geopolitical risk on stock returns than keyword-based predecessors, assigns gradations of risk intensity rather than binary flags, and can map directed networks of geopolitical actors (initiators, respondents, spillover countries) across historical episodes.[^26][^27]

**AI Disinformation Global Intelligence Report 2025** (800+ pages, 2,347 campaigns documented): Finds AI disinformation tools have proliferated beyond state actors to non-state entities and individuals; multiple technical domains have crossed a "detection horizon" beyond which automated or human verification becomes "statistically unreliable"; semi-autonomous disinformation systems now operate with minimal human supervision.[^28][^29]

**Bot Traffic and Deepfakes** (BISI, Dec 2025): Bot traffic surpassed human web activity at 51%; deepfake incidents in Q1 2025 exceeded all of 2024; over 50% of web content is now AI-generated.[^30]

**AI-Amplified Propaganda in LLM Citations** (FDD Center for Cyber and Technology Innovation, March 2026): Study examining citation patterns across three contemporary conflicts found that when prompted on geopolitical topics, major AI platforms "respond most of the time by citing propaganda aligned with the interests of U.S. adversaries".[^31]

**Fake News Detection**: Keele University researchers (Jan 2025) developed an ensemble-voting ML model achieving 99% accuracy in detecting fake news. FactFlow AI (Newtral/JournalismAI, 2025), using open-source Qwen trained on 1M+ messages, reduced fact-checker monitoring time from hours to seconds on Telegram.[^32][^33]

**AI and Information Warfare in Major Powers** (*Defense and Security Analysis*, 2024): Comparative analysis of how US, China, and Russia deploy AI in their information warfare/influence operations (IWIO) strategies, identifying divergent approaches driven by each state's broader IW doctrine.[^34]

**Measuring Propaganda with Deep Learning** (CEUR 2025): BERT-based transformer models achieve 80%+ accuracy detecting propaganda techniques; GPT-3.5-turbo-based pipeline achieves classification for propaganda targets using SemEval-2020 Task 11 dataset.[^35]

**Misinformation Receptivity Measurement at Scale** (Stanford HAI, Sept 2024): Developed a method combining survey data with observational Twitter/X data to probabilistically estimate users both *exposed to* and *likely to believe* specific misinformation — providing more precise impact estimates than raw view/share counts.[^36]

***

## 6. Cryptocurrency and Financial Markets Measurement

### Key Research

AI measurement in crypto spans trading behavior, sentiment analysis, fraud detection, and market structure analysis.

**AI's Role in Crypto Markets**: AI-powered trading bots accounted for approximately 40% of daily cryptocurrency trading volume in 2023; around 62% of cryptocurrency hedge funds had integrated AI for asset management by 2024; AI was the best-performing sector in crypto in 2024 with an 84% average log return, with AI agents leading at 186%. The global Crypto Making AI market is projected to grow from $5.1B in 2025 to $55.2B by 2035 at a 26.8% CAGR.[^37]

**Social Media vs. AI Search Divergence in Crypto** (CryptoRank, 2025): A comprehensive 2025 analysis finds Bitcoin dominates social media conversation while Ethereum leads AI search volume — divergence reflecting distinct market positions and investor psychology.[^38]

**Financial Fraud Detection**: More than 50% of fraud in 2025 involves AI; 90% of financial institutions now use AI to detect fraud; AI applications span scam detection (50%), transaction fraud (39%), and anti-money laundering (30%). The AI fraud detection market is projected to grow from $15.6B in 2025 to $119.9B by 2034 at a 25.4% CAGR.[^39][^40][^41]

**Stablecoin and Adoption Measurement** (TRM Labs, 2025): US crypto transaction volume grew ~50% YoY in both 2024 and 2025 to over $1 trillion, with India retaining the #1 position and the US at #2 in the Chainalysis Global Crypto Adoption Index.[^42]

***

## 7. Governance, Law Enforcement, and Military Measurement

### Key Research

**Predictive Policing**: A 2025 RIT thesis applying an integrated empirical-literature approach to AI crime prediction found Random Forest models achieved a balanced F1-Score of 0.402 and ROC AUC of 0.586 for identifying crime hotspots — representing a "moderate, non-random ability" with significant improvement over traditional baselines for place-based forecasting. A ScienceDirect systematic review of 120 papers (2008–2021) spans 34 crime categories researched using AI approaches.[^43][^44]

**DOJ Final Report on AI and Criminal Justice** (Dec 2024): Maps eight AI application areas in criminal justice — including crime forecasting, pretrial risk assessment, prison management, and forensic analysis — with recommendations balancing efficiency gains against privacy, civil rights, and bias protections.[^45]

**Military AI Measurement**: A May 2025 arXiv paper argues that AI-powered Lethal Autonomous Weapons Systems (AI-LAWS) introduce novel risks — unanticipated escalation, poor reliability in unfamiliar environments, erosion of human oversight — that existing V&V frameworks are "not designed to address" and proposes technically-informed regulation. The Belfer Center (Dec 2025) identifies development of AI-specific Verification and Validation (V&V) frameworks as an urgent priority, including "rigorous stress-testing under simulated combat conditions".[^46][^47]

**NIST AI 800-3** (Feb 2026): New NIST publication introduces Generalized Linear Mixed Models (GLMMs) for AI benchmark evaluation — formalizing how uncertainty is measured across 22 frontier LLMs on GPQA-Diamond, BIG-Bench Hard, and Global-MMLU Lite — to enable more rigorous statistical inference from benchmark results.[^48][^49]

**NIST AI RMF Measurement Function** (updated 2025): Framework now requires continuous monitoring metrics including fairness indicators (demographic parity), robustness measures, drift detection, privacy leakage testing, and explainability scoring — operationalized across sectoral profiles covering healthcare, finance, hiring, and critical infrastructure.[^50][^51]

***

## 8. Environmental and Societal Measurement

### Key Research

**AI Carbon Footprint**: The carbon footprint of AI systems in 2025 may be between 32.6–79.7 million metric tons of CO₂ — equivalent to New York City's annual footprint — while water consumption could reach 312.5–764.6 billion liters (rivaling global bottled water production). Training GPT-3 emitted roughly 500 metric tons of CO₂; per-query costs vary widely depending on model size.[^52][^53][^54]

**AI and Inequality**: A *Behaviour & Information Technology* paper (May 2025) introduces the "AI divide" concept — the gap between those who can and cannot generate sustainable outcomes with AI — identifying social, technical, and sociotechnical inequalities as the key drivers. Research on AI in education finds compounding disadvantages for marginalized populations as AI reshapes both societal structures and service delivery.[^55][^56]

**Stanford 2026 AI Index**: The 9th annual report (April 2026, 423 pages) documents: AI system accuracy on real-world computer tasks rose from 12% (18 months ago) to 66% (March 2026); organizational adoption at 88%; generative AI reached 53% population adoption faster than the PC or internet; documented AI incidents rose from 233 in 2024 to 362 in 2025 with a January 2026 peak of 435. Estimated value of generative AI tools to US consumers reached $172B annually by early 2026.[^57][^58][^59][^60]

***

## Sites and Databases to Monitor Regularly

### Preprint & Academic Search Platforms

| Platform | URL | Best For |
|----------|-----|----------|
| **arXiv** (cs.AI, cs.LG, econ.GN) | arxiv.org | Real-time preprints across all technical domains |
| **Semantic Scholar** | semanticscholar.org | 200M+ papers, free API, citation graph analysis[^61][^62] |
| **SSRN** | ssrn.com | Economics, law, social science working papers |
| **OpenAlex** | openalex.org | 250M+ papers, open bibliometrics, institution data[^62] |
| **PubMed Central** | ncbi.nlm.nih.gov/pmc | AI in health, psychology, neuroscience |
| **NBER Working Papers** | nber.org/papers | Frontier economics & labor market research[^12][^9] |
| **arXiv Sanity (Karpathy)** | arxiv-sanity-lite.com | Personalized recommendations from arXiv[^63] |

### Government and Policy Organizations

| Organization | URL | Focus |
|--------------|-----|-------|
| **Stanford HAI AI Index** | hai.stanford.edu/ai-index | Annual comprehensive AI measurement barometer[^59][^64] |
| **CSET Georgetown** | cset.georgetown.edu | AI × national security, US-China tech competition[^65][^66] |
| **NIST AI** | nist.gov/artificial-intelligence | Official US AI measurement standards, AI RMF, AI 800-3[^48] |
| **Federal Reserve Board** | federalreserve.gov | AI-GPR Index, AI macro measurement[^26] |
| **Brookings AI Initiative** | brookings.edu | AI labor, policy, governance research[^5] |
| **Yale Budget Lab** | budgetlab.yale.edu | AI labor market tracking[^6] |
| **RAND AI** | rand.org/topics/artificial-intelligence | Defense, social, economic AI implications |
| **European Parliament EPRS** | europarl.europa.eu | EU AI Act, autonomous weapons, digital governance[^67] |

### Security, OSINT, and Disinformation

| Organization | URL | Focus |
|--------------|-----|-------|
| **FDD CCTI** | fdd.org | AI propaganda measurement, cyber threats[^31] |
| **BISI (British Institute for Security)** | bisi.org.uk | AI-driven information warfare reports[^30] |
| **World Economic Forum** | weforum.org | Geopolitical risk, cognitive manipulation[^68] |
| **TRM Labs** | trmlabs.com | Crypto crime, AI fraud measurement[^42] |
| **Belfer Center (Harvard)** | belfercenter.org | Military AI, autonomous weapons governance[^47] |
| **SemEval / PAN Shared Tasks** | pan.webis.de | Annual disinformation & propaganda detection benchmarks |
| **AI Incident Database** | incidentdatabase.ai | Real-world AI failures and incidents tracking |

### Health, Psychology, and Behavioral Research

| Organization | URL | Focus |
|--------------|-----|-------|
| **APA Monitor on Psychology** | apa.org/monitor | AI in mental health care[^16] |
| **NPJ Digital Medicine (Nature)** | nature.com/npjdigitalmed | AI clinical outcomes, digital phenotyping[^20] |
| **JMIR AI** | jmir.org/journals/ai | AI in digital health, systematic reviews[^69] |
| **NBER Behavioral Economics** | nber.org | LLM bias, behavioral measurement papers[^12] |
| **Frontiers in Digital Health** | frontiersin.org | Open access AI health research |

### Finance, Crypto, and Economics

| Organization | URL | Focus |
|--------------|-----|-------|
| **Chainalysis** | chainalysis.com | Global Crypto Adoption Index, illicit finance[^42] |
| **Feedzai Research** | feedzai.com | AI fraud detection benchmarks[^39] |
| **CryptoRank** | cryptorank.io | AI crypto market analytics[^38] |
| **Chicago Booth Review** | chicagobooth.edu/review | Applied economics + AI research[^1] |
| **Forecasting Research Institute** | forecastingresearch.org | Expert elicitation on AI economic effects[^8] |

### Newsletters and Feeds to Subscribe

For continuous monitoring of new measurement research, the following are the highest-signal feeds across technical, policy, and applied domains:

| Newsletter | Frequency | Best For |
|-----------|-----------|---------|
| **Import AI** (Jack Clark, Anthropic co-founder) | Weekly | Frontier AI research + policy analysis[^70][^71] |
| **TLDR AI** | Daily | Engineers, ML researchers, paper summaries[^72] |
| **AlphaSignal** | Weekly | Top ML research papers + GitHub repos[^72] |
| **Turing Post** | Weekly | Policy, R&D, academic AI research[^72] |
| **The Batch** (Andrew Ng) | Weekly | Research-to-practice bridge[^73] |
| **CSET Dispatch** | Irregular | AI national security, China tech competition[^65] |
| **Stanford HAI Weekly** | Weekly | Societal AI measurement updates[^64] |
| **The Rundown AI** | Daily | Broad AI news, 2M+ subscribers[^70] |

***

## Cross-Domain Measurement Frameworks

Several umbrella frameworks organize measurement across the domains above and are worth tracking as evolving standards:

**NIST AI RMF (Govern/Map/Measure/Manage)**: The de facto US federal standard for AI risk measurement; 2025 updates added AI-specific profiles for healthcare, finance, hiring, and generative AI systems. NIST AI 800-3 (Feb 2026) advances the statistical methodology underlying benchmark evaluations.[^51][^74][^50][^48]

**Stanford AI Index**: Annual 400+ page data-driven snapshot covering capability benchmarks, R&D investment, adoption, responsible AI incidents, education, policy, and public trust — referenced by governments, companies, and academic researchers globally.[^75][^59][^76]

**EU AI Act Conformity Assessments**: Risk-tiered regulatory measurement requirements now in enforcement, covering prohibited AI practices, high-risk system testing, and transparency obligations — generating significant compliance measurement literature.[^50]

**Clarivate Societal Impact Framework** (ISI/Web of Science, 2024): Structured categorization system combining academic publications, patents, clinical trial data, and policy documents to assess AI research's societal impact, now embedded in Web of Science Research Intelligence.[^77]

**AI Energy Score Benchmark**: Open-source benchmark measuring per-query energy consumption across open LLMs — providing a standardized comparison for the carbon footprint measurement gap, where closed-source models remain opaque.[^54]

***

## Identified Research Gaps

Despite significant activity, several measurement gaps remain:

1. **Long-term behavioral effects of AI companions** on attachment formation, loneliness, and social skill atrophy — methodologically challenging to measure with existing longitudinal study designs[^17]
2. **AI's labor supply effects** — most research focuses on demand-side displacement; supply-side responses (job search, career switching, retraining) are understudied[^5]
3. **Cross-platform information warfare attribution** — measuring coordinated inauthentic behavior across fragmented platforms with inconsistent API access[^28]
4. **AI divide quantification** — no consensus metric for measuring who benefits vs. is harmed by AI adoption across socioeconomic strata globally[^56]
5. **Military AI performance under adversarial conditions** — existing V&V methodologies designed for conventional systems are inadequate; AI-specific frameworks remain in early development[^47][^46]

---

## References

1. [A New Tool for Predicting Economic Growth | Chicago Booth Review](https://www.chicagobooth.edu/review/a-new-tool-predicting-economic-growth) - A new tool for predicting economic growth. Generative AI can gauge managers' expectations to forecas...

2. [[PDF] Harnessing Generative AI for Economic Insights*](https://www.business.rutgers.edu/sites/default/files/documents/harnessing-generative-ai-economic-insights.pdf) - The overall measure, AI Economy Score, robustly predicts future economic indicators such as GDP grow...

3. [Labor market impacts of AI: A new measure and early evidence](https://www.anthropic.com/research/labor-market-impacts) - In this paper, we present a new framework for understanding AI's labor market impacts, and test it a...

4. [New Measures for Examining AI's Impact on Labor Markets](https://cottrillresearch.com/new-measures-for-examining-ais-impact-on-labor-markets/) - In AI-exposed occupations, younger workers (ages 22-25) experienced 16% relative employment declines...

5. [Research on AI and the labor market is still in the first inning](https://www.brookings.edu/articles/research-on-ai-and-the-labor-market-is-still-in-the-first-inning/) - They found employment fell more for young workers in occupations with higher AI exposure but not in ...

6. [Tracking the Impact of AI on the Labor Market - Yale Budget Lab](https://budgetlab.yale.edu/research/tracking-impact-ai-labor-market) - The proportion of employment in occupations with high levels of task AI usage, whether automation or...

7. [Real-time AI GDP Modeling: Transforming Economic Analysis in the ...](https://www.linkedin.com/pulse/real-time-ai-gdp-modeling-transforming-economic-age-andre-rvcue) - This comprehensive analysis explores the multifaceted landscape of real-time AI GDP modeling, examin...

8. [Forecasting the Economic Effects of AI](https://forecastingresearch.substack.com/p/forecasting-the-economic-effects-of-ai) - We completed the most comprehensive study of how economists and AI experts think AI will affect the ...

9. [[PDF] NBER WORKING PAPER SERIES FORECASTING THE ECONOMIC ...](https://www.nber.org/system/files/working_papers/w35046/w35046.pdf) - We elicit forecasts of how AI will affect the U.S. economy, comparing the beliefs of five groups: ac...

10. [Generative AI to augment behavioral research - Strategyand.pwc.com](https://www.strategyand.pwc.com/m1/en/ideation-center/ic-research/2025/gen-ai-behavioral-research.html) - Behavioral researchers are exploring if LLMs like GPT can serve as synthetic participants by answeri...

11. [Evaluating AI-Simulated Behavior: Insights from Three Studies on ...](https://www.nngroup.com/articles/ai-simulations-studies/) - Summary: AI-simulated users can fill in missing data and predict population-level trends. They perfo...

12. [Behavioral Economics of AI: LLM Biases and Corrections - NBER](https://www.nber.org/papers/w34745) - Do generative AI models, particularly large language models (LLMs), exhibit systematic behavioral bi...

13. [How AI can (also) empower the behavioral sciences - BBVA](https://www.bbva.com/en/innovation/how-ai-can-also-empower-the-behavioral-sciences/) - AI has a profound impact on how we understand human behavior, and second, behavioral sciences can he...

14. [Behavioral Science in the Age of Artificial Intelligence - 计量经济学报](https://cjoe.cjoe.ac.cn/EN/10.12012/CJoE2025-0610) - The rapid development of artificial intelligence has profoundly reshaped both the substantive focus ...

15. [AI-driven dynamic psychological measurement: correcting university ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC12698557/) - This study aimed to evaluate an Artificial Intelligence (AI)-driven dynamic psychological measuremen...

16. [AI, neuroscience, and data are fueling personalized mental health ...](https://www.apa.org/monitor/2026/01-02/trends-personalized-mental-health-care) - Psychologists are using a patient's brain scans plus data from phones and wearables to determine the...

17. [Minds in Crisis: How the AI Revolution is Impacting Mental Health](https://www.mentalhealthjournal.org/articles/minds-in-crisis-how-the-ai-revolution-is-impacting-mental-health.html) - Recent studies of Generative AI Chatbots for mental health treatment have found generative AI therap...

18. [Use of Artificial Intelligence in Mental Healthcare, Health Psychology ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC12665507/) - Through several studies regarding AI in neuropsychology, it was found that AI can diagnose mental di...

19. [Artificial intelligence in mental health care: a systematic review of ...](https://www.cambridge.org/core/journals/psychological-medicine/article/artificial-intelligence-in-mental-health-care-a-systematic-review-of-diagnosis-monitoring-and-intervention-applications/04DBD2D05976C9B1873B475018695418) - This systematic review presents the application of AI in mental health in the domains of diagnosis, ...

20. [Application of artificial intelligence to measure and predict patient ...](https://www.nature.com/articles/s41746-025-02156-2) - This scoping review examines how artificial intelligence (AI) has been applied to measure and predic...

21. [(PDF) Beyond Human Analysis: The AI-Driven Evolution of OSINT ...](https://www.academia.edu/144129033/Beyond_Human_Analysis_The_AI_Driven_Evolution_of_OSINT_Capabilities) - This paper examines the evolutionary trajectory of Open Source Intelligence (OSINT) from its traditi...

22. [[PDF] The Impact of Artificial Intelligence on OSINT Technologies](https://tesi.luiss.it/44191/1/289791_ALLAM_ELIYA.pdf) - This includes metrics on retrieval quality, response quality, and agent performance, alongside case ...

23. [[PDF] AI Powered OSINT (Open-Source Intelligence) Reconnaissance Tool](https://www.ijtsrd.com/papers/ijtsrd81146.pdf) - This research paper explores the evolution, methodologies, applications, challenges, and future tren...

24. [Open source intelligence and AI: a systematic review of the GELSI ...](https://pubmed.ncbi.nlm.nih.gov/36741972/) - It analyzes 571 publications to assess the current state of the literature on the use of AI-powered ...

25. [[PDF] Scaling Open Source Intelligence Investigations Through Human-AI ...](https://ci.acm.org/2025/wp-content/uploads/Anirban-Mukhopadhyay.pdf) - My dissertation explores how to scale OSINT investigations through sociotechnical systems with a foc...

26. [The AI-GPR Index: Measuring Geopolitical Risk using Artificial ...](https://www.frbsf.org/research-and-insights/publications/board-of-governors/2026/03/the-ai-gpr-index-measuring-geopolitical-risk-using-artificial-intelligence/) - We introduce an improved measure of geopolitical risk that builds on Caldara and Iacoviello (2022) a...

27. [[PDF] The AI-GPR Index: Measuring Geopolitical Risk using Artificial ...](https://www.matteoiacoviello.com/research_files/AI_GPR_PAPER.pdf) - The daily AI-GPR index scores about 5 million articles from the New York Times, Washington Post, and...

28. [AI Disinformation Global Intelligence Report 2025 with Threats ...](https://www.businesswire.com/news/home/20251014039793/en/AI-Disinformation-Global-Intelligence-Report-2025-with-Threats-Worldwide-Through-2035---ResearchAndMarkets.com) - This comprehensive 800+ page global intelligence report provides a detailed assessment of artificial...

29. [AI Disinformation Global Intelligence Package - Research and Markets](https://www.researchandmarkets.com/reports/6174097/ai-disinformation-global-intelligence-package) - By 2026-2027, AI-powered disinformation capabilities will achieve a decisive advantage over detectio...

30. [AI-Driven Information Warfare: Disinformation and Psychological ...](https://bisi.org.uk/reports/ai-driven-information-warfare-disinformation-and-psychological-manipulation) - Bot traffic at 51% and deepfakes surging: How AI is weaponising disinformation and psychological man...

31. [AI-Amplified Narratives: Measuring Propaganda in LLM Citations](https://www.fdd.org/analysis/2026/03/03/ai-amplified-narratives-measuring-propaganda-in-llm-citations/) - This study examined citation patterns across three contemporary conflicts by prompting three LLMs wi...

32. [AI-powered tool developed by Keele scientists can detect fake news ...](https://www.keele.ac.uk/research/researchnews/2025/january/artificial-intelligence/fake-news-detector.php) - “The risk posed by misinformation, disinformation, or fake news to the credibility of online news pl...

33. [Five tools to detect, analyze and counter disinformation](https://latamjournalismreview.org/articles/five-tools-to-detect-analyze-and-counter-disinformation/) - Five tools to detect, analyze and counter disinformation · Google Fact Check Tools · Archive.org · O...

34. [Artificial intelligence and information warfare in major power states](https://augusta.elsevierpure.com/en/publications/artificial-intelligence-and-information-warfare-in-major-power-st/) - We find that the US, China, and Russia are utilizing AI in their IWIO approaches in significant ways...

35. [[PDF] Method for Detecting Propaganda Objects Using Deep Learning ...](https://ceur-ws.org/Vol-3933/Paper_4.pdf) - Detecting propaganda in text using natural language processing (NLP) presents considerable challenge...

36. [Measuring receptivity to misinformation at scale on a social media ...](https://hai.stanford.edu/research/measuring-receptivity-to-misinformation-at-scale-on-a-social-media-platform) - Our paper provides a more precise estimate of misinformation's impact by focusing on the exposure of...

37. [Crypto Making AI Market Size, Share | CAGR of 26.8%](https://market.us/report/crypto-making-ai-market/) - AI was the best-performing sector in crypto in 2024, achieving an 84% average log return. AI agents ...

38. [Cryptocurrencies Trending: The 2025 Social Media and AI Search ...](https://cryptorank.io/news/feed/9981e-cryptocurrencies-trending-social-media-ai-search-2) - Global cryptocurrency markets in 2025 demonstrate fascinating divergence between social media conver...

39. [AI Fraud Trends 2025: Banks Fight Back | Feedzai](https://www.feedzai.com/pressrelease/ai-fraud-trends-2025/) - AI fraud in 2025: Over 50% involves AI & deepfakes. Learn how banks use GenAI to combat fraud and fi...

40. [Artificial Intelligence in Fraud Detection Market](https://dimensionmarketresearch.com/report/artificial-intelligence-in-fraud-detection-market/) - Artificial Intelligence (AI) in Fraud Detection Market is expected to be valued at USD 15.6 bn in 20...

41. [AI in Fraud Detection Market: Growth, Trends, and Forecast - LinkedIn](https://www.linkedin.com/pulse/artificial-intelligence-ai-fraud-detection-market-ydewf) - Artificial Intelligence (AI) in fraud detection Market is projected to grow from USD 15.6 bn in 2025...

42. [2025 Crypto Adoption and Stablecoin Usage Report - TRM Labs](https://www.trmlabs.com/reports-and-whitepapers/2025-crypto-adoption-and-stablecoin-usage-report) - Our research shows that between January and July 2025, crypto transaction volume in the US rose by r...

43. [The Role of AI and Predictive Policing in Crime Prevention](https://repository.rit.edu/theses/12399/) - The current thesis examines the application of Artificial Intelligence (AI) in the arena of predicti...

44. [Artificial intelligence & crime prediction: A systematic literature review](https://www.sciencedirect.com/science/article/pii/S2590291122000961) - We review 120 research papers published between 2008 and 2021 that cover AI approaches for crime pre...

45. [[PDF] Artificial Intelligence and Criminal Justice, Final Report](https://www.justice.gov/olp/media/1381796/dl) - Law enforcement agencies use historical data to forecast the places where crime is likely to cluster...

46. [Military AI Needs Technically-Informed Regulation to Safeguard AI ...](https://arxiv.org/html/2505.18371v1) - We focus on a specific subset of lethal autonomous weapon systems (LAWS) that use AI for targeting o...

47. [Code, Command, and Conflict: Charting the Future of Military AI](https://www.belfercenter.org/research-analysis/code-command-and-conflict-charting-future-military-ai) - Legal guardrails around autonomous weapons systems and AI-based decision support systems are a work ...

48. [New Report: Expanding the AI Evaluation Toolbox with Statistical ...](https://www.nist.gov/news-events/news/2026/02/new-report-expanding-ai-evaluation-toolbox-statistical-models) - In NIST AI 800-3, we develop a statistical model for AI evaluations which formalizes evaluation assu...

49. [NIST Publishes Guidance to Enhance AI Benchmark Evaluations](https://www.executivegov.com/articles/nist-guidance-ai-benchmark-evaluations) - The NIST AI 800-3 publication introduces a formal modeling framework to clarify how AI benchmark res...

50. [NIST AI Risk Management Framework (AI RMF 1.0) - Nemko Digital](https://digital.nemko.com/regulations/nist-rmf) - Master the NIST AI Risk Management Framework to safeguard AI systems in 2025. Learn proven strategie...

51. [NIST AI RMF 2025 Updates: What You Need to Know About the ...](https://www.ispartnersllc.com/blog/nist-ai-rmf-2025-updates-what-you-need-to-know-about-the-latest-framework-changes/) - Discover what's new for 2025 in the NIST AI Risk Management Framework and how organizations can impr...

52. [The Carbon Footprint of AI | Climate Impact Partners](https://www.climateimpact.com/news-insights/insights/carbon-footprint-of-ai/) - AI is transforming our world - but understanding its hidden carbon footprint is key to building a sm...

53. [AI's 2025 carbon footprint may match New York City, report estimates](https://techxplore.com/news/2025-12-ai-carbon-footprint-york-city.html) - By the end of the year, the carbon footprint of global AI systems for the whole of 2025 could equal ...

54. [AI's Environmental Impact: Making an Informed Choice - Marmelab](https://marmelab.com/blog/2025/03/19/ai-carbon-footprint.html) - A Nature paper demonstrated that the carbon emissions of writing and illustrating are lower for AI t...

55. [Ahn explores AI, social work and inequality - Brown School](https://brownschool.washu.edu/2025/10/ahn-explores-ai-social-work-and-inequality/) - She studies how AI affects inequality, governance, and fairness, and how social workers should respo...

56. [Bridging the gap: inequalities that divide those who can and cannot ...](https://www.tandfonline.com/doi/full/10.1080/0144929X.2025.2500451) - ABSTRACT. The widespread use of AI technologies impacts individuals, organisations, and societies in...

57. [Stanford's AI Report Card: Agents Are Ready. Companies Are Not](https://www.forbes.com/sites/stevenwolfepereira/2026/04/14/stanfords-ai-report-card-agents-are-ready-companies-are-not/) - AI system accuracy is rapidly approaching human-level performance, rising to 66.3% in 2025 against a...

58. [The 2026 AI Index Report from Stanford and what it says about AI ...](https://www.i-scoop.eu/the-2026-ai-index-report-from-stanford-and-what-it-says-about-ai-right-now/) - The report estimates the value of generative AI tools to U.S. consumers at $172 billion annually by ...

59. [The 2026 AI Index Report | Stanford HAI](https://hai.stanford.edu/ai-index/2026-ai-index-report) - The AI Index offers one of the most comprehensive, data-driven views of artificial intelligence. Rec...

60. [Stanford's 2026 AI Index: 10 Numbers Every Business Leader ...](https://www.linkedin.com/pulse/stanfords-2026-ai-index-10-numbers-every-business-see-steven-8ejjc) - Documented AI incidents rose to 362 in 2025, up from 233 in 2024. The six-month moving average hit 3...

61. [Semantic Scholar Scraper — Academic Papers and Data - Apify](https://apify.com/automation-lab/semantic-scholar-scraper) - Scrape Semantic Scholar papers, author profiles, citation data, and abstracts. Bulk research data ex...

62. [Semantic Scholar Has a Free API — Search 200M+ Papers With AI ...](https://dev.to/0012303/semantic-scholar-has-a-free-api-search-200m-papers-with-ai-powered-relevance-no-key-2pjj) - Semantic Scholar Has a Free API — Search 200M+ Papers With AI-Powered Relevance (No Key) · What make...

63. [Where To Find The Latest AI Research? Top 7 Sources to Stay ...](https://learnprompting.org/blog/resources_latest_research_papers) - Platforms such as ArXiv.org have gained popularity in the AI community because they provide immediat...

64. [AI Index | Stanford HAI](https://hai.stanford.edu/ai-index) - The mission of the AI Index is to provide unbiased, rigorously vetted, and globally sourced data for...

65. [CSET | Center for Security and Emerging Technology](https://cset.georgetown.edu) - CSET produces data-driven research at the intersection of security and technology, providing nonpart...

66. [Our Research | Center for Security and Emerging Technology - CSET](https://cset.georgetown.edu/our-research/) - As AI dominates news headlines day after day, CSET has kept pace by providing rigorous analysis on t...

67. [[PDF] Defence and artificial intelligence - European Parliament](https://www.europarl.europa.eu/RegData/etudes/BRIE/2025/769580/EPRS_BRI(2025)769580_EN.pdf) - AI is viewed as a force multiplier that can improve command and control, intelligence gathering, dec...

68. [How cognitive manipulation and AI will shape disinformation in 2026](https://www.weforum.org/stories/2026/03/how-cognitive-manipulation-and-ai-will-shape-disinformation-in-2026/) - Advanced AI and synthetic media are spreading disinformation, creating a global crisis that threaten...

69. [AI in Health Care Service Quality: Systematic Review - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12594439/) - AI adoption has the potential to elevate care quality, improve patient outcomes, reduce costs, and e...

70. [10 Best Free AI Newsletters in 2026 (No Paywall Required) - Readless](https://www.readless.app/blog/best-free-ai-newsletters-2026) - The Rundown AI, TLDR AI, and Superhuman AI are the three best free AI newsletters in 2026, together ...

71. [10 best AI newsletters to stay updated in 2026 | The Jotform Blog](https://www.jotform.com/ai/best-ai-newsletters/) - The 10 best AI newsletters · 1. The Rundown · 2. Ben's Bites · 3. The Neuron · 4. Import AI · 5. AI ...

72. [Top 12 AI Newsletters to Follow in 2026 | GenAI.Works](https://genai.works/insights/top-12-ai-newsletters-to-follow-in-2026) - Top 12 AI Newsletters to Follow in 2026 ; The Atlas, 3,151,421, Biweekly ; AI Frontier, 847,137, Wee...

73. [11 Top AI Newsletters for 2026 Insights | Crossover posted on the topic](https://www.linkedin.com/posts/crossover_11-must-read-newsletters-to-dominate-the-activity-7412762577987883008-1l-9) - 11 must-read newsletters to dominate the AI landscape in 2026: The Power Players (Quick Daily Briefi...

74. [Framing the Risk Management Framework: Actionable Instructions ...](https://epic.org/framing-the-risk-management-framework-actionable-instructions-by-nist-in-the-measure-section-of-the-ai-rmf/) - Identify and document testing procedures and metrics to measure both A.I. trustworthiness and signif...

75. [Stanford HAI AI Index Report 2024 | VerifyWise AI Governance Library](https://verifywise.ai/ai-governance-library/research-and-academic/stanford-hai-ai-index-report) - The comprehensive annual report tracking AI progress across research, development, technical perform...

76. [[PDF] Artificial Intelligence Index Report | Stanford HAI](https://hai.stanford.edu/assets/files/ai_index_report_2026.pdf) - “The AI Index 2026 Annual Report,” AI Index Steering Committee, Institute for. Human-Centered AI, St...

77. [Understanding how to measure the societal impact of research](https://clarivate.com/academia-government/blog/understanding-the-societal-impact-of-research/) - Measuring the societal impact of research is increasingly important. This article explains how the C...

