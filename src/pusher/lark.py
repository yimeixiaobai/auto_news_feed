import logging
import hashlib
import hmac
import base64
import time

import httpx

logger = logging.getLogger(__name__)

MAX_LENGTH = 20000


class LarkPusher:
    def __init__(self, webhook_url: str, secret: str = ""):
        self.webhook_url = webhook_url
        self.secret = secret

    def _sign(self) -> tuple[str, str]:
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode(), digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode()
        return timestamp, sign

    async def send(self, text: str, title: str = "AI 日报") -> bool:
        content_lines = _markdown_to_lark_post(text, MAX_LENGTH)
        payload: dict = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": content_lines,
                    }
                }
            },
        }

        if self.secret:
            ts, sign = self._sign()
            payload["timestamp"] = ts
            payload["sign"] = sign

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(self.webhook_url, json=payload)
                data = resp.json()
                if data.get("code") != 0:
                    logger.error("Lark send failed: %s", data)
                    return False
                return True
            except Exception as e:
                logger.error("Lark send error: %s", e)
                return False


def _markdown_to_lark_post(text: str, max_len: int) -> list[list[dict]]:
    text = text[:max_len]
    paragraphs = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        paragraphs.append([{"tag": "text", "text": line}])
    return paragraphs
