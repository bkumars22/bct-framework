"""
Per-project integration adapters — each wraps a real system's own API
endpoint as the AI-under-test, with adversarial cases specific to that
system's actual failure modes (not BCT's generic 6-category grammar),
and pushes results to AIPQ for prompt-version quality tracking.

Not imported by bct/__init__.py — these are project-specific, opt-in
integrations, not part of the core framework's public API.
"""
