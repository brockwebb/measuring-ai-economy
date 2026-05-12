"""Harvester self-improvement subsystems.

Phase 3.1 modules:
- co_occurrence: cross-source dedup → harvest.co_sources ledger
- failure_patterns: per-source error clustering → harvest.failure_patterns
- saturation: deposit-ratio computation + email alerts → harvest.saturation view
- notify: shared SMTP-or-stderr alert helper
"""
