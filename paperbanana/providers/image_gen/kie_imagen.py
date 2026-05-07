"""Kie.ai Nano Banana Pro image generation provider.

Async task-based API: createTask -> poll recordInfo -> download result image.
Pricing: ~$0.04/image (2K), ~$0.07/image (4K).
API docs: https://kie.ai/nano-banana-pro
"""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from typing import Optional

import structlog
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

from paperbanana.providers.base import ImageGenProvider

logger = structlog.get_logger()

# Task states that mean "still working"
_PENDING_STATES = {"waiting", "queuing", "generating"}

# Poll config
_POLL_INITIAL_INTERVAL = 2.0  # seconds
_POLL_MAX_INTERVAL = 10.0
_POLL_TIMEOUT = 300.0  # 5 min hard ceiling


class KieImageGen(ImageGenProvider):
    """Kie.ai Nano Banana Pro image generation.

    Uses the async task API:
      1. POST /api/v1/jobs/createTask  -> taskId
      2. GET  /api/v1/jobs/recordInfo?taskId=...  -> poll until success/fail
      3. Download the result image URL

    Requires a Kie.ai API key (https://kie.ai).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nano-banana-pro",
    ):
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def name(self) -> str:
        return "kie_imagen"

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self):
        """Lazy-init an async httpx client for the Kie.ai API."""
        if self._client is None:
            import httpx
            import os

            # 支持从环境变量读取 base URL，方便使用中转站
            base_url = os.getenv("KIE_BASE_URL", "https://api.kie.ai")

            self._client = httpx.AsyncClient(
                base_url=base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    def is_available(self) -> bool:
        return self._api_key is not None

    @staticmethod
    def _aspect_ratio(width: int, height: int) -> str:
        """Map pixel dimensions to the closest Kie.ai aspect ratio option."""
        ratio = width / height
        if ratio > 1.9:
            return "21:9"
        if ratio > 1.5:
            return "16:9"
        if ratio > 1.3:
            return "3:2"
        if ratio > 1.1:
            return "4:3"
        if ratio < 0.53:
            return "9:21"
        if ratio < 0.67:
            return "9:16"
        if ratio < 0.77:
            return "2:3"
        if ratio < 0.91:
            return "3:4"
        return "1:1"

    @staticmethod
    def _resolution(width: int, height: int) -> str:
        """Pick Kie.ai resolution tier based on requested dimensions."""
        max_dim = max(width, height)
        if max_dim <= 1024:
            return "1K"
        if max_dim <= 2048:
            return "2K"
        return "4K"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
    ) -> Image.Image:
        client = self._get_client()

        if negative_prompt:
            prompt = f"{prompt}\n\nAvoid: {negative_prompt}"

        payload = {
            "model": self._model,
            "input": {
                "prompt": prompt,
                "aspect_ratio": self._aspect_ratio(width, height),
                "resolution": self._resolution(width, height),
                "output_format": "png",
            },
        }

        # Step 1: Create task
        logger.info(
            "Kie.ai createTask",
            model=self._model,
            aspect_ratio=payload["input"]["aspect_ratio"],
            resolution=payload["input"]["resolution"],
        )
        resp = await client.post("/api/v1/jobs/createTask", json=payload)
        resp.raise_for_status()
        create_data = resp.json()

        if create_data.get("code") != 200:
            raise ValueError(
                f"Kie.ai createTask failed: {create_data.get('message', create_data)}"
            )

        task_id = create_data["data"]["taskId"]
        logger.info("Kie.ai task created", task_id=task_id)

        # Step 2: Poll until completion
        image_url = await self._poll_task(client, task_id)

        # Step 3: Download image
        logger.info("Downloading Kie.ai result image", url=image_url[:80])
        img_resp = await client.get(image_url)
        img_resp.raise_for_status()
        return Image.open(BytesIO(img_resp.content)).convert("RGB")

    async def _poll_task(self, client, task_id: str) -> str:
        """Poll task status with exponential back-off until success or failure.

        Returns the first image URL from resultJson on success.
        """
        interval = _POLL_INITIAL_INTERVAL
        elapsed = 0.0

        while elapsed < _POLL_TIMEOUT:
            await asyncio.sleep(interval)
            elapsed += interval

            resp = await client.get(
                "/api/v1/jobs/recordInfo", params={"taskId": task_id}
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 200:
                raise ValueError(
                    f"Kie.ai recordInfo error: {data.get('message', data)}"
                )

            state = data["data"].get("state", "")
            logger.debug(
                "Kie.ai poll",
                task_id=task_id,
                state=state,
                elapsed=f"{elapsed:.0f}s",
            )

            if state == "success":
                result_json = json.loads(data["data"]["resultJson"])
                urls = result_json.get("resultUrls", [])
                if not urls:
                    raise ValueError("Kie.ai task succeeded but resultUrls is empty")
                logger.info(
                    "Kie.ai task completed",
                    task_id=task_id,
                    elapsed=f"{elapsed:.0f}s",
                )
                return urls[0]

            if state == "fail":
                fail_msg = data["data"].get("failMsg", "unknown error")
                fail_code = data["data"].get("failCode", "")
                raise ValueError(
                    f"Kie.ai generation failed: [{fail_code}] {fail_msg}"
                )

            if state not in _PENDING_STATES:
                logger.warning("Kie.ai unknown state", state=state, task_id=task_id)

            # Exponential back-off, capped
            interval = min(interval * 1.5, _POLL_MAX_INTERVAL)

        raise TimeoutError(
            f"Kie.ai task {task_id} did not complete within {_POLL_TIMEOUT:.0f}s"
        )
