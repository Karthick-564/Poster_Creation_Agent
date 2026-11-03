"""Agentic poster design pipeline package.

Decomposes poster composition into an autonomous LLM designer loop
operating against VectorCraft MCP tools with locked brand zones,
continuous physics measurement, and multimodal vision critique.
"""
from .critic import CriticStage
from .llm_backend import LLMBackend, get_backend
from .router import Router, RouterDecision, RerouteAction
from .structure import lock_all_zones, lock_header_logo, lock_footer_bar, lock_qr_code

__all__ = [
    "CriticStage",
    "LLMBackend",
    "get_backend",
    "Router",
    "RouterDecision",
    "RerouteAction",
    "lock_all_zones",
    "lock_header_logo",
    "lock_footer_bar",
    "lock_qr_code",
]

