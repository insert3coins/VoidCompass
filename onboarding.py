"""Presentation-neutral first-commissioning state helpers."""

from __future__ import annotations


def should_show(config):
    """Return whether the HTML First Commissioning deck must be presented."""
    return not bool((config or {}).get("onboarding_complete", False))
