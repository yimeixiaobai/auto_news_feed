import logging
import httpx

logger = logging.getLogger(__name__)

MAX_LENGTH = 4096


class WecomPusher:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, text: str) -> bool:
        content = text[:MAX_LENGTH]
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    self.webhook_url,
                    json={
                        "msgtype": "markdown",
                        "markdown": {"content": content},
                    },
                )
                data = resp.json()
                if data.get("errcode") != 0:
                    logger.error("Wecom send failed: %s", data)
                    return False
                return True
            except Exception as e:
                logger.error("Wecom send error: %s", e)
                return False
