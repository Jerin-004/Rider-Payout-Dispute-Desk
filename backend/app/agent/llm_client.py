"""LLM provider abstraction — swap Groq/Gemini via LLM_PROVIDER env var."""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import get_settings
from app.core.exceptions import LLMError

log = logging.getLogger(__name__)
settings = get_settings()


class BaseLLMClient(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        """Send a prompt and return the raw text response."""

    async def complete_json(self, system: str, user: str, temperature: float = 0.1) -> dict:
        """Complete and parse JSON from the response."""
        raw = await self.complete(system, user, temperature)
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last fence lines
            inner = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            text = inner
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            # Try extracting JSON object/array from the text
            import re
            m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
            log.error("LLM returned non-JSON: %s", text[:500])
            raise LLMError(f"LLM did not return valid JSON: {exc}") from exc


class GroqClient(BaseLLMClient):
    def __init__(self):
        try:
            from groq import AsyncGroq
        except ImportError as e:
            raise LLMError("groq package not installed") from e
        if not settings.groq_api_key:
            raise LLMError("GROQ_API_KEY is not set")
        # 15s timeout — prevents indefinite hangs on network issues
        self._client = AsyncGroq(api_key=settings.groq_api_key, timeout=15.0)
        self.model = settings.groq_model

    async def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=512,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            log.error("Groq API error: %s", exc)
            raise LLMError(f"Groq API error: {exc}") from exc


class GeminiClient(BaseLLMClient):
    def __init__(self):
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise LLMError("google-generativeai package not installed") from e
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        genai.configure(api_key=settings.gemini_api_key)
        self._genai = genai
        self.model_name = settings.gemini_model

    async def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        import asyncio
        try:
            model = self._genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system,
            )
            response = await asyncio.to_thread(
                model.generate_content,
                user,
                generation_config={"temperature": temperature, "max_output_tokens": 1024},
            )
            return response.text or ""
        except Exception as exc:
            log.error("Gemini API error: %s", exc)
            raise LLMError(f"Gemini API error: {exc}") from exc


class MockLLMClient(BaseLLMClient):
    """
    Deterministic mock for tests.

    complete_json() — returns structured intent JSON (for orchestrator._classify_intent).
    complete()      — returns a short natural-language reply string (for _generate_reply).
    """

    async def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        """Return a short, plausible rider-facing reply based on keywords in the situation."""
        text = user.lower()
        if "no discrepancy" in text or "sahi hai" in text or "correct" in text:
            return "Maine check kiya — aapka payout records ke hisaab se sahi hai."
        if "payment processed" in text or "successfully" in text or "pout_" in text:
            return "Aapka missing payout process ho gaya hai. Please 24 ghante mein check karein."
        if "approval" in text or "ops" in text or "requires" in text:
            return "Aapka case ops team ke paas review ke liye bhej diya gaya hai. Jald update milega."
        if "not found" in text or "nahi mili" in text:
            return "Ye order ID hamare records mein nahi mili. Please order ID dobara check karein."
        if "escalat" in text:
            return "Aapka case ops team ko refer kar diya gaya hai. Jald update milega."
        if "order id" in text or "date" in text or "tarikh" in text or "missing" in text:
            return "Bhai, mujhe order ID ya delivery date chahiye. Please share karein."
        if "7-day" in text or "window" in text or "outside" in text:
            return "Sorry, ye dispute 7-day window se bahar hai."
        return "Main aapka issue check kar raha hoon. Thodi der mein update milega."

    async def complete_json(self, system: str, user: str, temperature: float = 0.1) -> dict:
        """Return structured intent JSON derived deterministically from the user message."""
        text = user.lower()

        # Intent detection
        if any(w in text for w in ["surge", "multiplier"]):
            intent = "MISSING_SURGE"
        elif any(w in text for w in ["incentive", "bonus"]):
            intent = "MISSING_INCENTIVE"
        elif any(w in text for w in ["penalty", "cancel"]):
            intent = "DUPLICATE_PENALTY"
        elif any(w in text for w in ["nahi mila", "nahi aaya", "missing", "kam aaya", "nahi aya"]):
            intent = "MISSING_PAYOUT"
        elif any(w in text for w in ["galat", "incorrect", "wrong", "check"]):
            intent = "MISSING_PAYOUT"
        else:
            intent = "GENERAL_QUERY"

        # Extract trip IDs — match T followed by 4-8 alphanumeric chars (covers TTEST1, T926334)
        import re
        trip_ids = re.findall(r"\bT[A-Z0-9]{4,8}\b", user, re.IGNORECASE)
        # Uppercase them so they match DB records
        trip_ids = [t.upper() for t in trip_ids]

        # Extract dates
        delivery_date = None
        date_match = re.search(r"(1[2-9]|2[0-1])\s*(?:sep|tarikh|ko|wala|sept)", text)
        if date_match:
            delivery_date = f"2026-09-{date_match.group(1).zfill(2)}"

        # Determine missing info
        missing = []
        if not trip_ids and not delivery_date:
            if intent not in ("GENERAL_QUERY",):
                missing = ["delivery_date"]

        return {
            "intent": intent,
            "trip_ids": trip_ids,
            "delivery_date": delivery_date,
            "claimed_amount": None,
            "missing_information": missing,
            "confidence": 0.85,
            "rider_message_language": "hinglish",
            "multiple_disputes": len(trip_ids) > 1,
        }


def get_llm_client() -> BaseLLMClient:
    """Factory: return appropriate LLM client based on LLM_PROVIDER env."""
    provider = settings.llm_provider.lower()
    if provider == "groq" and settings.groq_api_key:
        return GroqClient()
    elif provider == "gemini" and settings.gemini_api_key:
        return GeminiClient()
    else:
        log.warning("No LLM API key configured — using MockLLMClient")
        return MockLLMClient()
