"""DeepSeek VLM provider — OpenAI-compatible API."""

from __future__ import annotations

from typing import Optional

import structlog
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

from paperbanana.core.utils import image_to_base64
from paperbanana.providers.base import VLMProvider

logger = structlog.get_logger()


class DeepSeekVLM(VLMProvider):
    """VLM provider using DeepSeek's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-v4-flash",
    ):
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def name(self) -> str:
        return "deepseek"

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self):
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                base_url="https://api.deepseek.com",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    def is_available(self) -> bool:
        return self._api_key is not None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def generate(
        self,
        prompt: str,
        images: Optional[list[Image.Image]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> str:
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        content = []
        if images:
            for img in images:
                b64 = image_to_base64(img)
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
        content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": content})

        payload = {
            "messages": messages,
            "model": self._model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "reasoning_effort": "high",  # Use high for better quality
        }

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        response = await client.post("/chat/completions", json=payload)

        if response.is_error:
            detail = response.text.strip()
            raise RuntimeError(
                f"DeepSeek VLM HTTP {response.status_code}: {detail or 'empty response body'}"
            )

        data = response.json()
        text = data["choices"][0]["message"]["content"]
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))

        logger.debug("DeepSeek VLM response", model=self._model, usage=data.get("usage"))
        return text
