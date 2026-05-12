# Ontology Stack for Measuring AI, IT, and Crypto in the Economy

## Executive summary

The best ontology stack for measuring AI in the economy should start with the U.S. Federal Statistical System and then add international, technical, and crypto-financial ontologies where official economic classifications are too coarse. The canonical U.S. backbone is **NAICS for industries**, **NAPCS for products**, **SOC and O*NET for occupations and tasks**, **BEA national accounts and input-output tables for value added and supply chains**, **HTS/Schedule B/HS for traded goods**, **EBOPS-style services categories through BEA international accounts**, **CPC/IPC patent classifications for innovation**, **NCSES/CIP/HERD/Frascati-compatible fields for R&D**, and **FCSM for data quality** ([Census NAICS](https://www.census.gov/naics/), [Census NAPCS](https://www.census.gov/naics/napcs/), [BLS SOC](https://www.bls.gov/soc/2018/home.htm), [O*NET](https://www.onetonline.org/), [BEA input-output accounts](https://www.bea.gov/data/industries/input-output-accounts-data), [USITC HTS](https://hts.usitc.gov/), [Census Schedule B](https://www.census.gov/foreign-trade/schedules/b/), [USPTO CPC](https://www.uspto.gov/web/patents/classification/cpc/html/cpc.html), [NCSES Earned Doctorates](https://ncses.nsf.gov/surveys/earned-doctorates), [FCSM data quality](https://statspolicy.gov/FCSM/groups/data-quality/)).

The global comparison layer should use **ISIC, CPC, COICOP, HS, EBOPS, SNA/BPM, ISCO, Frascati, Oslo, OECD ICT-sector definitions, OECD digital trade definitions, OECD AI system and capability taxonomies, and Eurostat digital economy indicators**. These systems make it possible to ask whether the United States is leading, lagging, or merely classifying differently when compared with the EU, UK, Canada, Australia, Japan, Korea, and other high-data-capacity economies ([UNSD ISIC](https://unstats.un.org/unsd/classifications/Econ/isic), [UNSD CPC](https://unstats.un.org/unsd/classifications/Econ/cpc), [WCO HS](https://www.wcoomd.org/en/topics/nomenclature/instrument-and-tools/hs-nomenclature-2022-edition/hs-nomenclature-2022-edition.aspx), [EBOPS](https://unstats.un.org/unsd/classifications/Family/Detail/101), [SNA 2025](https://unstats.un.org/unsd/nationalaccount/sna2025.asp), [ILO ISCO](https://ilostat.ilo.org/methods/concepts-and-definitions/classification-occupation/), [OECD Frascati Manual](https://www.oecd.org/en/publications/frascati-manual-2015_9789264239012-en.html), [OECD measuring digital trade handbook](https://www.oecd.org/content/dam/oecd/en/publications/reports/2023/07/handbook-on-measuring-digital-trade-second-edition_099afd2f/ac99e6d3-en.pdf), [Eurostat digital economy and society](https://ec.europa.eu/eurostat/web/digital-economy-and-society)).

The technical layer should fill gaps that official statistics cannot yet see. **NIST AI RMF, NIST CSF, NIST NICE, MITRE ATT&CK, CVE/CWE/CPE/CVSS, SPDX, CycloneDX, DCAT, Dublin Core, PROV-O, RDF/OWL/SKOS, Schema.org, model cards, datasheets, Hugging Face metadata, and AI incident taxonomies** provide machine-readable vocabularies for AI systems, software supply chains, cyber risk, data provenance, model documentation, and real-time AI ecosystem tracking ([NIST AI RMF](https://www.nist.gov/artificial-intelligence/ai-risk-management-framework), [NIST CSF](https://www.nist.gov/cyberframework), [NICE Framework](https://niccs.cisa.gov/workforce-development/nice-framework), [MITRE ATT&CK](https://attack.mitre.org), [NVD API](https://nvd.nist.gov/developers), [SPDX](https://spdx.dev), [CycloneDX](https://cyclonedx.org), [DCAT 3](https://www.w3.org/TR/vocab-dcat-3/), [PROV-O](https://www.w3.org/TR/prov-o/), [SKOS](https://www.w3.org/TR/skos-reference/), [Hugging Face model cards](https://huggingface.co/docs/hub/models-cards), [AI Incident Database](https://incidentdatabase.ai/)).

The crypto and digital-asset layer should not be treated as one ontology. A usable measurement system needs **IMF/SNA/BPM classifications for macroeconomic recording**, **FSB/BCBS/FATF/IOSCO for global regulatory and risk categories**, **SEC/CFTC/FinCEN/IRS for U.S. legal and reporting categories**, **ISO 20022/4217/10962/17442/24165 for messages, currencies, instruments, entities, and tokens**, **FIBO for formal financial semantics**, and **XBRL for public-company disclosure** ([IMF BPM7 chapters](https://www.imf.org/en/data/statistics/bpm/bpm7-chapters), [SNA 2025](https://unstats.un.org/unsd/nationalaccount/sna2025.asp), [FSB crypto-assets hub](https://www.fsb.org/work-of-the-fsb/financial-innovation-and-structural-change/crypto-assets-and-global-stablecoins/), [BCBS cryptoasset exposures](https://www.bis.org/bcbs/publ/d545.pdf), [FATF virtual assets](https://www.fatf-gafi.org/en/topics/virtual-assets.html), [ISO 20022](https://www.iso20022.org/iso-20022), [GLEIF LEI](https://www.gleif.org/en/about-lei/introducing-the-legal-entity-identifier-lei), [DTIF DTI](https://dtif.org), [FIBO](https://spec.edmcouncil.org/fibo/), [SEC XBRL taxonomies](https://www.sec.gov/newsroom/whats-new/2403-2024-xbrl-taxonomies-update)).

## Priority architecture

### Tier 0: Use as the official statistical spine

| Measurement need | Preferred ontology or classification | Why it is primary | AI/IT/crypto caveat |
|---|---|---|---|
| Industry output, employment, establishments | [NAICS](https://www.census.gov/naics/) | Backbone of U.S. industry statistics and aligned trilaterally with Canada and Mexico | No dedicated AI or crypto code; AI is split across cloud, software, search, R&D, and consulting |
| Products and services | [NAPCS](https://www.census.gov/naics/napcs/) | Better than NAICS for cross-sector AI products because it classifies outputs regardless of producer | AI inference, model APIs, and crypto services need finer product detail |
| Occupations | [SOC](https://www.bls.gov/soc/2018/home.htm) | Official U.S. occupation classification used by BLS surveys | No dedicated ML engineer or AI engineer code in SOC 2018 |
| Tasks and skills | [O*NET](https://www.onetonline.org/) | Best federal-adjacent task-level system for AI exposure and skill analysis | AI exposure measures depend heavily on task interpretation and capability vintage |
| National accounts and supply chains | [BEA input-output accounts](https://www.bea.gov/data/industries/input-output-accounts-data) | Enables value-added, intermediate-input, and multiplier analysis | AI usually appears as software, cloud, data processing, R&D, or own-account software |
| Digital economy GDP | [BEA Digital Economy](https://www.bea.gov/data/special-topics/digital-economy) | U.S. satellite account framework for digital economy measurement | Formal satellite account was discontinued after the December 2023 update, leaving a major gap |
| Goods trade | [HTS](https://hts.usitc.gov/), [Schedule B](https://www.census.gov/foreign-trade/schedules/b/), [HS](https://www.wcoomd.org/en/topics/nomenclature/instrument-and-tools/hs-nomenclature-2022-edition/hs-nomenclature-2022-edition.aspx) | Captures semiconductors, computers, telecom equipment, and AI hardware trade | AI chips are classified by physical/function characteristics, not AI capability |
| Advanced technology trade | [Census Advanced Technology Products](https://www.census.gov/foreign-trade/reference/codes/atp/index.html) | Useful U.S. flag for high-technology goods trade | Captures embodied technology, not services or AI software |
| Patents and innovation | [CPC G06N](https://www.uspto.gov/web/patents/classification/cpc/html/cpc-G06N.html), [IPC](https://www.wipo.int/en/web/classification-ipc) | Best structured signal for AI inventive activity | Patent classifications lead economic data but do not measure deployment |
| R&D fields | [NCSES SED/CIP](https://ncses.nsf.gov/surveys/earned-doctorates), [HERD](https://ncses.nsf.gov/surveys/higher-education-research-development/2024), [Frascati](https://www.oecd.org/en/publications/frascati-manual-2015_9789264239012-en.html) | Measures AI-relevant research labor and spending | Field definitions lag emerging AI subfields |
| Statistical quality | [FCSM Framework for Data Quality](https://statspolicy.gov/FCSM/groups/data-quality/) | U.S. federal quality vocabulary for utility, objectivity, and integrity | Needs operational mapping to AI training data, model outputs, and benchmark evidence |

### Tier 1: Add for global comparison

| Global question | Ontology or standard | U.S. linkage |
|---|---|---|
| How large is the U.S. AI/digital sector relative to other economies? | [ISIC](https://unstats.un.org/unsd/classifications/Econ/isic), [OECD ICT sector definitions](https://www.oecd.org/en/publications/oecd-definitions-of-the-ict-sector-the-content-and-media-sector-and-information-industries-based-on-isic-rev-5_b9576889-en.html), [NACE](https://ec.europa.eu/eurostat/web/nace) | NAICS-to-ISIC and NAICS-to-NACE crosswalks |
| What products and digital services are being produced? | [CPC](https://unstats.un.org/unsd/classifications/Econ/cpc), [NAPCS](https://www.census.gov/naics/napcs/) | NAPCS-to-CPC alignment |
| What digital goods are traded? | [HS](https://www.wcoomd.org/en/topics/nomenclature/instrument-and-tools/hs-nomenclature-2022-edition/hs-nomenclature-2022-edition.aspx), WTO ITA product lists | HTS and Schedule B extend HS to U.S. import/export reporting |
| What digital services are traded? | [EBOPS](https://unstats.un.org/unsd/classifications/Family/Detail/101), [OECD/WTO/IMF digital trade handbook](https://www.oecd.org/content/dam/oecd/en/publications/reports/2023/07/handbook-on-measuring-digital-trade-second-edition_099afd2f/ac99e6d3-en.pdf) | BEA services trade statistics |
| How should AI and crypto enter macro accounts? | [SNA 2025](https://unstats.un.org/unsd/nationalaccount/sna2025.asp), [BPM7](https://www.imf.org/en/data/statistics/bpm/bpm7-chapters) | Future BEA/BLS/Federal Reserve implementation and international comparability |
| How should AI labor be compared internationally? | [ISCO-08](https://ilostat.ilo.org/methods/concepts-and-definitions/classification-occupation/), [ESCO](https://esco.ec.europa.eu/) | SOC-to-ISCO and O*NET/ESCO skill crosswalks |
| How should AI adoption be compared? | [Eurostat digital economy indicators](https://ec.europa.eu/eurostat/web/digital-economy-and-society), [OECD AI indicators](https://oecd.ai/) | Compare against Census BTOS, NSF business innovation surveys, and BEA/BLS measures |
| How should AI capability be compared to human skills? | [OECD AI Capability Indicators](https://www.oecd.org/en/publications/2025/06/introducing-the-oecd-ai-capability-indicators_7c0731f0.html) | Link to O*NET tasks, SOC occupations, and federal workforce analyses |

### Tier 2: Add technical ontologies for what official statistics miss

| Measurement gap | Technical ontology | Why it matters |
|---|---|---|
| AI system risk and trustworthiness | [NIST AI RMF](https://www.nist.gov/artificial-intelligence/ai-risk-management-framework) | Provides federal AI risk functions, trustworthiness characteristics, and MEASURE vocabulary |
| Cybersecurity posture | [NIST CSF 2.0](https://www.nist.gov/cyberframework) | Provides organization-level cyber outcome categories and subcategories |
| Cyber workforce skills | [NICE Framework](https://niccs.cisa.gov/workforce-development/nice-framework) | Provides tasks, knowledge, and skills below SOC granularity |
| Adversary behavior | [MITRE ATT&CK](https://attack.mitre.org) | Provides tactics, techniques, procedures, groups, software, mitigations, and detections |
| Software vulnerability measurement | [CVE](https://cve.mitre.org), [CWE](https://cwe.mitre.org), [CPE](https://nvd.nist.gov/products/cpe), [CVSS](https://www.first.org/cvss/) | Links weaknesses, affected products, vulnerabilities, and severity |
| Software and AI supply chains | [SPDX](https://spdx.dev), [CycloneDX](https://cyclonedx.org) | Provides SBOM and ML-BOM structures for components, dependencies, provenance, and vulnerabilities |
| Data cataloging | [DCAT 3](https://www.w3.org/TR/vocab-dcat-3/), [Dublin Core](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/) | Provides dataset, data service, catalog, resource, and metadata structures |
| Provenance and lineage | [PROV-O](https://www.w3.org/TR/prov-o/) | Provides entity-activity-agent provenance graph for AI pipelines |
| Crosswalk publication | [SKOS](https://www.w3.org/TR/skos-reference/) | Provides exact, close, broad, narrow, and related matches across classification systems |
| Formal knowledge graphs | [RDF](https://www.w3.org/TR/rdf11-concepts/), [OWL 2](https://www.w3.org/TR/owl2-overview/), [SPARQL](https://www.w3.org/TR/sparql11-overview/) | Provides the graph substrate for ontology integration and GraphRAG |
| AI model ecosystem | [Hugging Face model metadata](https://huggingface.co/docs/hub/models-cards), [model cards](https://arxiv.org/abs/1810.03993), [datasheets](https://www.microsoft.com/en-us/research/publication/datasheets-for-datasets/) | Provides real-time task, license, model lineage, dataset, and evaluation metadata |
| AI harms and incidents | [AI Incident Database](https://incidentdatabase.ai/) | Provides applied harm, failure, sector, and incident taxonomies not present in economic statistics |

### Tier 3: Add crypto and digital-asset ontologies

| Measurement need | Ontology or standard | Preferred role |
|---|---|---|
| National accounts and balance of payments | [SNA 2025](https://unstats.un.org/unsd/nationalaccount/sna2025.asp), [BPM7](https://www.imf.org/en/data/statistics/bpm/bpm7-chapters), [IMF crypto guidance](https://www.imf.org/-/media/files/data/statistics/bpm6/approved-guidance-notes/f18-the-recording-of-fungible-crypto-assets-in-macroeconomic-statisticsapproved-final-version.pdf) | Classify crypto assets for GDP, balance sheets, BOP, and IIP |
| Global regulatory risk | [FSB crypto framework](https://www.fsb.org/work-of-the-fsb/financial-innovation-and-structural-change/crypto-assets-and-global-stablecoins/) | Functional global regulatory vocabulary |
| Bank prudential exposure | [BCBS cryptoasset exposures](https://www.bis.org/bcbs/publ/d545.pdf) | Group 1/2 cryptoasset exposure classification |
| AML/CFT obligations | [FATF virtual assets guidance](https://www.fatf-gafi.org/en/topics/virtual-assets.html), [FinCEN CVC guidance](https://www.fincen.gov/system/files/2019-05/FinCEN%20Guidance%20CVC%20FINAL%20508.pdf) | VASP/MSB roles, Travel Rule data, suspicious activity classification |
| U.S. tax reporting | [IRS digital assets](https://www.irs.gov/filing/digital-assets), [IRS virtual currency FAQ](https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions) | Property treatment and broker-reporting data |
| Financial messaging | [ISO 20022](https://www.iso20022.org/iso-20022) | Structured payment, securities, FX, and treasury messages |
| Entity identity | [GLEIF LEI](https://www.gleif.org/en/about-lei/introducing-the-legal-entity-identifier-lei) | Global legal entity identifier and ownership graph |
| Token identity | [DTIF Digital Token Identifier](https://dtif.org) | ISO-standard token identifier for fungible digital tokens |
| Instrument classification | [ISO 10962 CFI](https://www.iso.org/standard/81140.html) | Instrument type and attributes, especially tokenized securities |
| Formal financial ontology | [FIBO](https://spec.edmcouncil.org/fibo/) | OWL-based semantic backbone for financial entities, instruments, contracts, and processes |
| Public-company crypto disclosures | [SEC XBRL taxonomies](https://www.sec.gov/newsroom/whats-new/2403-2024-xbrl-taxonomies-update) | Machine-readable disclosures and accounting data |

## Crosswalk strategy

### Core entity model

The central graph should treat **industry**, **product**, **occupation**, **task**, **firm**, **establishment**, **asset**, **technology**, **dataset**, **model**, **software component**, **patent**, **transaction**, **payment message**, and **incident** as distinct entity types. This avoids the common error of forcing AI into one industry or one technology label when it actually appears as a product, capital asset, occupational task, software dependency, patent class, risk control, and service-delivery mechanism.

| Entity type | Primary identifier | Secondary mappings |
|---|---|---|
| Establishment/industry | NAICS | ISIC, NACE, BEA I-O industry, SIC legacy |
| Product/service | NAPCS | CPC, EBOPS, BEA PCE/NIPA categories |
| Occupation | SOC | O*NET-SOC, ISCO, ESCO, NICE |
| Task/skill | O*NET task and technology skill | ESCO skill, NICE task/knowledge/skill |
| Goods trade item | HTS/Schedule B | HS, ATP, end-use category |
| Patent | CPC/IPC symbol | NAICS patent-to-industry mappings, WIPO AI search strategies |
| R&D field | NCSES/CIP/HERD field | Frascati FOS |
| AI system | NIST AI RMF category | OECD AI system dimensions, model card metadata |
| Dataset | DCAT/Dublin Core identifier | Datasheet, PROV-O lineage, Hugging Face dataset card |
| Model | Model card or HF model ID | SPDX/CycloneDX AI component, benchmark metadata |
| Software component | SPDX/CycloneDX package ID | CPE, CVE, CWE, license, PURL |
| Cyber technique | ATT&CK technique ID | CWE, CVE, NIST CSF, incident taxonomy |
| Legal entity | LEI | SEC CIK, IRS EIN where available, GLEIF parent hierarchy |
| Digital token | DTI | Contract address, chain ID, ticker, CFI if financial instrument |
| Financial instrument | CFI/ISIN where applicable | DTI, FIBO class, SEC/CFTC category |
| Payment/transaction | ISO 20022 message element | FATF Travel Rule fields, FinCEN/IRS reporting fields |

### GraphRAG-ready relationship types

| Relationship | Example |
|---|---|
| `classified_as` | Firm establishment `classified_as` NAICS 518 or 5415 |
| `produces` | Establishment `produces` NAPCS cloud, software, or AI-related service |
| `maps_to` | NAICS `maps_to` ISIC or NACE class |
| `requires_skill` | SOC occupation `requires_skill` O*NET technology skill or NICE task |
| `performs_task` | Occupation `performs_task` O*NET task |
| `uses_model` | AI service `uses_model` model card/HF model ID |
| `trained_on` | Model `trained_on` dataset described by datasheet/DCAT |
| `derived_from` | Dataset/model/output `derived_from` prior entity via PROV-O |
| `contains_component` | AI system `contains_component` SPDX/CycloneDX package |
| `affected_by` | Software component `affected_by` CVE |
| `implements_control` | Organization `implements_control` NIST CSF or AI RMF subcategory |
| `observed_in_incident` | AI system or component `observed_in_incident` AIID event |
| `has_token_identifier` | Cryptoasset `has_token_identifier` DTI |
| `issued_by` | Token/stablecoin `issued_by` LEI-identified entity |
| `reported_in` | Public company crypto holding `reported_in` XBRL filing |
| `settled_via` | Transaction `settled_via` ISO 20022 or blockchain rail |

## Best sources by measurement objective

| Objective | Start here | Add for depth |
|---|---|---|
| Measure AI industry size in the U.S. | NAICS, NAPCS, BEA I-O, BEA digital economy | OECD ICT sector, ISIC, NACE, CPC |
| Measure AI workforce and skill exposure | SOC, O*NET | ISCO, ESCO, NICE, OECD AI capability indicators |
| Measure AI adoption by firms | Census BTOS, NSF innovation/R&D surveys, NAICS | Eurostat ICT Business Survey, OECD sectoral AI intensity |
| Measure AI R&D and innovation | NCSES HERD/SED/CIP, CPC/IPC patents | Frascati, WIPO PATENTSCOPE, OECD R&D indicators |
| Measure AI infrastructure and cloud | NAICS 518, NIST cloud taxonomy, BEA I-O | ISIC Rev. 5, OECD ICT product definitions, CPC |
| Measure AI software supply chain | SPDX, CycloneDX, CPE/CVE/CWE | NIST CSF, NTIA/CISA SBOM guidance |
| Measure AI data and provenance | DCAT, Dublin Core, PROV-O, datasheets | FCSM, Model Cards, SPDX Dataset/AI profiles |
| Measure AI cyber risk | NIST CSF, ATT&CK, CVE/CWE/CVSS | NICE, CISA NCF, AI RMF adversarial ML taxonomy |
| Measure crypto in macro accounts | SNA 2025, BPM7, IMF crypto guidance | FSB framework, ISO 20022, DTI, LEI |
| Measure crypto regulation and compliance | FATF, FinCEN, IRS, SEC/CFTC, BCBS | Chainalysis/Elliptic typologies, IOSCO, FIBO |
| Measure U.S. versus global digital economy | OECD ICT definitions, ISIC, CPC, EBOPS, Eurostat | BEA, Census, BLS, OECD digital trade handbook |

## Key gaps and watch points

The most important U.S. measurement gap is the absence of AI-specific NAICS and SOC categories. AI firms, products, and workers are currently scattered across cloud, search, software, R&D, consulting, data science, computer research, and software-development categories, which makes direct official measurement difficult ([Census NAICS](https://www.census.gov/naics/), [BLS SOC](https://www.bls.gov/soc/2018/home.htm), [O*NET](https://www.onetonline.org/)).

The second major gap is the discontinuation of the BEA Digital Economy Satellite Account after its December 2023 release. That satellite account was the closest U.S. analog to an official digital-economy measurement system, and its absence makes OECD and Eurostat comparisons more important for benchmarking U.S. performance ([BEA digital economy](https://www.bea.gov/data/special-topics/digital-economy), [OECD ICT definitions](https://www.oecd.org/en/publications/oecd-definitions-of-the-ict-sector-the-content-and-media-sector-and-information-industries-based-on-isic-rev-5_b9576889-en.html), [Eurostat digital economy and society](https://ec.europa.eu/eurostat/web/digital-economy-and-society)).

The third gap is that crypto has better regulatory identifiers than economic classifications. DTI, LEI, ISO 20022, XBRL, FATF, and BCBS are strong for transaction, entity, disclosure, and risk analysis, but NAICS/NAPCS and national accounts still struggle to isolate crypto production, DeFi activity, and tokenized services ([DTIF](https://dtif.org), [GLEIF](https://www.gleif.org/en/about-lei/introducing-the-legal-entity-identifier-lei), [ISO 20022](https://www.iso20022.org/iso-20022), [FATF virtual assets](https://www.fatf-gafi.org/en/topics/virtual-assets.html), [BCBS cryptoasset exposures](https://www.bis.org/bcbs/publ/d545.pdf)).

The fourth gap is machine-readability. Technical standards such as ATT&CK, CVE/NVD, SPDX, CycloneDX, DCAT, PROV-O, SKOS, FIBO, DTI, LEI, and XBRL are machine-readable, while many statistical and regulatory frameworks remain PDF/prose-first, requiring human-coded crosswalks or LLM-assisted extraction with verification ([MITRE ATT&CK STIX data](https://github.com/mitre-attack/attack-stix-data), [NVD developers](https://nvd.nist.gov/developers), [SPDX](https://spdx.dev), [CycloneDX](https://cyclonedx.org), [DCAT 3](https://www.w3.org/TR/vocab-dcat-3/), [PROV-O](https://www.w3.org/TR/prov-o/), [SKOS](https://www.w3.org/TR/skos-reference/), [FIBO](https://spec.edmcouncil.org/fibo/), [SEC XBRL taxonomies](https://www.sec.gov/newsroom/whats-new/2403-2024-xbrl-taxonomies-update)).

The fifth gap is time-series breakage. ISIC Rev. 5, CPC 3.0, SNA 2025, BPM7, NACE Rev. 2.1, and future SOC/ISCO revisions are likely to improve AI/digital/crypto measurement, but they will also introduce discontinuities that must be explicitly modeled in longitudinal analyses ([UNSD ISIC](https://unstats.un.org/unsd/classifications/Econ/isic), [UNSD CPC](https://unstats.un.org/unsd/classifications/Econ/cpc), [SNA 2025](https://unstats.un.org/unsd/nationalaccount/sna2025.asp), [IMF BPM7](https://www.imf.org/en/data/statistics/bpm/bpm7-chapters), [Eurostat NACE](https://ec.europa.eu/eurostat/web/nace), [ILO ISCO](https://ilostat.ilo.org/methods/concepts-and-definitions/classification-occupation/)).

## Recommended implementation

Build the first ontology graph around the federal spine: NAICS, NAPCS, SOC/O*NET, BEA I-O, HTS/Schedule B/ATP, CPC/IPC, NCSES fields, and FCSM dimensions. Then add international bridge nodes for ISIC, CPC, ISCO, SNA/BPM, EBOPS, OECD ICT definitions, and Eurostat digital indicators. Finally, add machine-readable technical and crypto layers: NIST AI RMF, CSF, NICE, ATT&CK, CVE/CWE/CPE/CVSS, SPDX, CycloneDX, DCAT, PROV-O, SKOS, FIBO, LEI, DTI, ISO 20022, and XBRL.

For the first operational release, prioritize six crosswalks: NAICS-to-ISIC/NACE, NAPCS-to-CPC, SOC-to-O*NET-to-ISCO/ESCO, CPC/IPC-to-NAICS innovation mappings, DTI/LEI/ISO 20022-to-crypto transaction entities, and NIST AI RMF-to-FCSM data-quality dimensions. These crosswalks will support the highest-value questions: how much AI activity exists, where it is produced, who performs it, how it is traded, how it affects productivity and risk, and how the United States compares with the global economy.

