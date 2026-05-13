import logging
import httpx

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096


class TelegramPusher:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_base = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, text: str) -> bool:
        chunks = self._split_message(text)
        async with httpx.AsyncClient(timeout=30) as client:
            for chunk in chunks:
                try:
                    resp = await client.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": self.chat_id,
                            "text": chunk,
                            "parse_mode": "Markdown",
                            "disable_web_page_preview": True,
                        },
                    )
                    if resp.status_code != 200:
                        logger.error("Telegram send failed: %s", resp.text)
                        return False
                except Exception as e:
                    logger.error("Telegram send error: %s", e)
                    return False
        return True

    def _split_message(self, text: str) -> list[str]:
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]
        chunks = []
        while text:
            if len(text) <= MAX_MESSAGE_LENGTH:
                chunks.append(text)
                break
            split_pos = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
            if split_pos == -1:
                split_pos = MAX_MESSAGE_LENGTH
            chunks.append(text[:split_pos])
            text = text[split_pos:].lstrip("\n")
        return chunks
