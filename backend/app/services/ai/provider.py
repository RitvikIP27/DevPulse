"""AI provider abstraction (PRD 3.3).

DevPulse must not be permanently tied to one model vendor, and the deterministic
core must not import a vendor SDK. Everything above this boundary speaks
`AIProvider`; only the concrete implementations know about a particular API.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.evidence import EvidencePackage
from app.schemas.rca import RcaResult


class AIUnavailable(Exception):
    """No usable AI provider is configured, or the provider refused."""


class AIProvider(Protocol):
    name: str
    model: str

    def is_configured(self) -> bool: ...

    def generate_rca(self, evidence: EvidencePackage, prompt: str) -> RcaResult: ...
