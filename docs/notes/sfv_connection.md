# SFV Paper — New Existence Proof: AlignedNews (Scoble/Levangie Labs)

**Found**: 2026-04-11, Session 3 of ICSP notebook project

## What It Is
AlignedNews.com is Robert Scoble's AI-native intelligence platform. It processes
100K+ X/Twitter accounts across 63 curated lists, running 3-7K posts per sweep
through a multi-pass signal detection pipeline with AI synthesis and persistent memory.

## Why It Matters for SFV
This is the SFV pattern implemented in production by people who never read the book.
Independent convergent evolution. The architecture maps directly:

| SFV Concept | AlignedNews Implementation |
|-------------|---------------------------|
| Domain expertise layer | 63 hand-curated X lists (19 years of curation) |
| State management | Weaviate vector database with seen/unseen tracking |
| Multi-pass workflow chain | Keywords -> semantic search -> cross-list amplification |
| State fidelity | AI synthesis with persistent memory across sessions |
| Provenance / structured output | RSS feed, JSON API, 30 editorial sections with citations |
| Human-in-the-loop | Robert's editorial judgment encoded in signal methodology |

## The Pattern (generalizable)
Expert-curated signal sources -> vector ingestion -> multi-pass filtering ->
cross-source amplification -> AI synthesis -> structured output

This pattern is domain-independent. Swap X lists for federal data feeds, scientific
literature, patent filings, or SEC filings and the architecture holds.

## Other Independent Convergences
- Karpathy's workflows (documented in blog posts)
- Webb Concept Mapper (6,954 survey questions through dual-model pipeline)
- [Others from book chapters]

## Key Quote Opportunity
From their about page, Scoble describes the system as finding "what Robert would miss"
through cross-list pattern amplification and context connections. This is exactly the
value proposition of SFV: maintaining fidelity to domain expert intent at scale.

## Action
- Add as case study / existence proof in SFV paper
- Reference in ai-workflow-design book (Ch 7? Ch 12? wherever production examples live)
- Do NOT get distracted building the measuring-ai-economy project before the paper ships

## Source
https://alignednews.com (the "How It Works" about page)
