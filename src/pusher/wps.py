import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

MAX_LENGTH = 4800


class WpsPusher:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, text: str) -> bool:
        chunks = _split_message(text)
        async with httpx.AsyncClient(timeout=30) as client:
            for i, chunk in enumerate(chunks):
                try:
                    resp = await client.post(
                        self.webhook_url,
                        json={
                            "msgtype": "markdown",
                            "markdown": {"text": chunk},
                        },
                    )
                    if resp.status_code != 200:
                        logger.error("WPS send failed (part %d/%d): %s", i + 1, len(chunks), resp.text)
                        return False
                    if i < len(chunks) - 1:
                        await asyncio.sleep(3)
                except Exception as e:
                    logger.error("WPS send error (part %d/%d): %s", i + 1, len(chunks), e)
                    return False
        return True


def _split_message(text: str) -> list[str]:
    if len(text) <= MAX_LENGTH:
        return [text]

    chunks = []
    while text:
        if len(text) <= MAX_LENGTH:
            chunks.append(text)
            break
        split_pos = text.rfind("\n\n", 0, MAX_LENGTH)
        if split_pos == -1:
            split_pos = text.rfind("\n", 0, MAX_LENGTH)
        if split_pos == -1:
            split_pos = MAX_LENGTH
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")
    return chunks
