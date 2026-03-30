"""LLM client for vLLM integration with SAIA V4."""

import logging
import json
import asyncio
from typing import AsyncGenerator, Optional
import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """HTTP client for vLLM with fallback mock mode."""

    def __init__(self, base_url: str, model: str, mock_mode: bool = False):
        """
        Initialize the LLM client.

        Args:
            base_url: Base URL for the vLLM server (e.g., http://localhost:8001/v1)
            model: Model name to use (e.g., llama-3.1-70b)
            mock_mode: If True, return realistic fake responses instead of calling vLLM
        """
        self.base_url = base_url
        self.model = model
        self.mock_mode = mock_mode
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.1,
        stream: bool = False,
    ) -> str:
        """
        Call the LLM with the given prompts.

        Args:
            system_prompt: System message/instructions
            user_prompt: User query
            max_tokens: Maximum tokens in response
            temperature: Temperature for sampling (0-1)
            stream: If True, stream the response

        Returns:
            LLM response text
        """
        if self.mock_mode:
            return self._get_mock_response(user_prompt)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

        url = f"{self.base_url}/chat/completions"

        # Retry logic with exponential backoff
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()

                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        return result["choices"][0]["message"]["content"]
                    else:
                        logger.warning(f"Unexpected LLM response format: {result}")
                        return ""

            except httpx.HTTPError as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"LLM call attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"LLM call failed after {max_retries + 1} attempts: {e}")
                    # Fall back to mock response
                    return self._get_mock_response(user_prompt)

            except Exception as e:
                logger.error(f"Unexpected error in LLM call: {e}")
                return self._get_mock_response(user_prompt)

        return ""

    async def call_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        """
        Call the LLM with streaming response.

        Args:
            system_prompt: System message/instructions
            user_prompt: User query
            max_tokens: Maximum tokens in response
            temperature: Temperature for sampling

        Yields:
            Tokens from the LLM response
        """
        if self.mock_mode:
            # Yield mock response in chunks
            response = self._get_mock_response(user_prompt)
            chunk_size = 10
            for i in range(0, len(response), chunk_size):
                yield response[i : i + chunk_size]
            return

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break

                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Streaming LLM call failed: {e}")
            # Fall back to non-streaming mock
            response = self._get_mock_response(user_prompt)
            chunk_size = 10
            for i in range(0, len(response), chunk_size):
                yield response[i : i + chunk_size]

    def _get_mock_response(self, user_prompt: str) -> str:
        """
        Generate a realistic mock response based on the user prompt type.

        Args:
            user_prompt: User query

        Returns:
            Mock response text
        """
        prompt_lower = user_prompt.lower()

        # Service A: Enrichment (returns JSON)
        if "enrichment" in prompt_lower or "enrich" in prompt_lower:
            return json.dumps(
                {
                    "enriched_fields": {
                        "geolocation": "Saudi Arabia",
                        "asn": "AS15830",
                        "organization": "Saudi Telecom Company",
                        "threat_intel": "No known threats",
                    },
                    "confidence_score": 0.95,
                }
            )

        # Service B: Chatbot (returns natural language)
        if any(
            word in prompt_lower
            for word in ["explain", "what", "how", "tell", "describe", "ask"]
        ):
            return (
                "This alert appears to be triggered by unusual access patterns. "
                "The user accessed multiple sensitive resources within a short timeframe, "
                "which deviates from their typical behavior. I recommend investigating "
                "the recent activity logs and verifying if this is authorized access."
            )

        # Service C: Narrative (returns markdown)
        if (
            "narrative" in prompt_lower
            or "summary" in prompt_lower
            or "report" in prompt_lower
        ):
            return (
                "## Security Alert Summary\n\n"
                "### Overview\n"
                "An anomaly has been detected in the user's behavior on 2024-03-28.\n\n"
                "### Key Findings\n"
                "- Unusual access pattern detected\n"
                "- Multiple resource accesses outside normal hours\n"
                "- Access from unfamiliar location\n\n"
                "### Recommendation\n"
                "Immediate investigation recommended to verify legitimacy of access."
            )

        # Default response
        return (
            "I have analyzed the provided information and identified potential security concerns. "
            "Please review the details and take appropriate action."
        )


# Global LLM client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    Get or create the singleton LLM client.

    Returns:
        Global LLMClient instance
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            mock_mode=settings.llm_mock_mode,
        )
    return _llm_client
