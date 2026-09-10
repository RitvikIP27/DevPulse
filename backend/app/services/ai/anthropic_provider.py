"""Anthropic implementation of AIProvider.

Uses structured outputs so the model must return the RcaResult schema. Prose
responses are not accepted: a schema is what forces the model to separate
observed facts from inferences and to populate `unknowns` explicitly.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.evidence import EvidencePackage
from app.schemas.rca import RcaResult
from app.services.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.ai.provider import AIUnavailable

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-opus-5"
MAX_TOKENS = 16000


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str | None = None):
        self.model = model or settings.anthropic_model or DEFAULT_MODEL

    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    def generate_rca(self, evidence: EvidencePackage, prompt: str) -> RcaResult:
        if not self.is_configured():
            raise AIUnavailable("ANTHROPIC_API_KEY is not set.")

        # Imported lazily because AI is an optional layer. A module-level import
        # would take the entire API down if the SDK were missing, which would
        # mean an optional feature could break the deterministic core — exactly
        # the coupling ADR-008 exists to prevent.
        try:
            import anthropic
        except ImportError as error:  # pragma: no cover - dependency is declared
            raise AIUnavailable(
                "The anthropic SDK is not installed in this environment."
            ) from error

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        try:
            response = client.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                # Adaptive thinking: this is a reasoning task over conflicting
                # signals, which is exactly what it is for.
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": build_user_prompt(prompt)}],
                output_format=RcaResult,
            )
        except anthropic.RateLimitError as error:
            raise AIUnavailable("Anthropic rate limit reached. Try again shortly.") from error
        except anthropic.AuthenticationError as error:
            raise AIUnavailable("Anthropic rejected the API key.") from error
        except anthropic.APIStatusError as error:
            raise AIUnavailable(f"Anthropic returned {error.status_code}.") from error
        except anthropic.APIConnectionError as error:
            raise AIUnavailable("Could not reach the Anthropic API.") from error

        # A safety refusal returns HTTP 200 with stop_reason "refusal", so the
        # status code alone does not tell us whether there is a usable answer.
        if getattr(response, "stop_reason", None) == "refusal":
            raise AIUnavailable("The model declined to analyse this evidence.")

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise AIUnavailable("The model did not return a valid analysis.")

        logger.info(
            "rca generated model=%s deployment=%s confidence=%s",
            self.model, evidence.deployment_id, parsed.confidence,
        )
        return parsed
