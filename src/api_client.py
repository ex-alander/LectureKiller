"""OpenAI-compatible API client for vision models."""

import base64
import time
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from src.config import get_settings
from src.exceptions import APIRequestError, APIResponseEmptyError
from src.prompts import SYSTEM_PROMPT, build_user_prompt


class VisionAPIClient:
    """Client for vision-capable LLM API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = OpenAI(
            base_url=self.settings.api_base_url,
            api_key=self.settings.api_key,
            timeout=120.0,
        )

    def process_pdf_pages(
        self, image_paths: List[Path], pdf_name: str
    ) -> Optional[str]:
        """
        Send PDF pages as images to API and return markdown content.

        Args:
            image_paths: List of image file paths (one per page).
            pdf_name: Original PDF name for logging.

        Returns:
            Markdown content or None if failed.
        """
        # Prepare request content
        content = [
            {"type": "text", "text": build_user_prompt(len(image_paths))},
        ]

        for img_path in image_paths:
            b64_image = self._encode_image(img_path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_image}",
                        "detail": "high",
                    },
                }
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        # Retry logic
        for attempt in range(self.settings.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.settings.model_name,
                    messages=messages,
                    temperature=self.settings.temperature,
                    max_completion_tokens=self.settings.max_completion_tokens,
                )

                markdown = response.choices[0].message.content

                if not markdown:
                    raise APIResponseEmptyError(
                        f"Empty response from API for {pdf_name}"
                    )

                return markdown

            except Exception as e:
                if attempt == self.settings.max_retries - 1:
                    raise APIRequestError(
                        f"Failed after {self.settings.max_retries} attempts: {e}"
                    ) from e

                time.sleep(self.settings.retry_delay_seconds)

        return None  # Should never reach here

    @staticmethod
    def _encode_image(image_path: Path) -> str:
        """Encode image file to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")