"""Harvester triage subsystem.

LLM-driven per-axis scoring against the research_axes.yaml rubric.
Writes structured TriageResult rows into harvest.triage_results with
stochastic provenance recorded in harvest.stochastic_provenance.
"""
