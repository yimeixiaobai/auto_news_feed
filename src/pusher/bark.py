import logging
import httpx

logger = logging.getLogger(__name__)


class BarkPusher:
    def __init__(self, server_url: str, device_key: str):
        self.base_url = f"{server_url.rstrip('/')}/{device_key}"

    async def send(self, text: str, title: str = "AI 日报") -> bool:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    self.base_url,
                    json={
                        "title": title,
                        "body": text,
                        "group": "AI News",
                        "sound": "default",
                    },
                )
                if resp.status_code != 200:
                    logger.error("Bark send failed: %s", resp.text)
                    return False
                return True
            except Exception as e:
                logger.error("Bark send error: %s", e)
                return False
