import logging

logger = logging.getLogger(__name__)

DIGEST_PROMPT = """你是一位AI领域的资深新闻编辑。下面是今日从多个信息源抓取的全部文章（共 {total} 篇）。
请从中筛选出最重要、最有价值的 {top_n} 条，生成一份结构化的「AI 日报」。

筛选标准（按优先级）：
- 重大发布、突破性进展、有广泛影响的事件优先
- 去重：同一事件多个来源只保留一条，优先选信息量最大的来源
- 覆盖多样性：尽量覆盖不同类别，避免同一话题占据过多条目
{keywords}{already_pushed}
严格按以下 Markdown 模板输出，不要偏离格式：

---模板开始---
# 📰 AI 日报｜今日最值得关注的 {top_n} 条

**1. 🔥 热门｜标题文字**
摘要内容，1-2 句中文。
原文链接：[来源名称](URL)

**2. 💼 行业动态｜标题文字**
摘要内容，1-2 句中文。
原文链接：[来源名称](URL)

...（共 {top_n} 条，每条之间空一行）

> 一句话总结：总结文字。
---模板结束---

分类图标只用这四种：🔥 热门、📊 论文/观点、🛠 工具/开源、💼 行业动态

文章列表：
{articles}"""


class _AnthropicBackend:
    def __init__(self, api_key: str, base_url: str, model: str):
        import anthropic
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**kwargs)
        self.model = model

    def chat(self, prompt: str, max_tokens: int = 300) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()


class _OpenAIBackend:
    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def chat(self, prompt: str, max_tokens: int = 300) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()


class Summarizer:
    def __init__(
        self,
        provider: str = "anthropic",
        model: str = "claude-sonnet-4-6",
        api_key: str = "",
        base_url: str = "",
    ):
        if provider == "openai":
            self.backend = _OpenAIBackend(api_key, base_url, model)
        else:
            self.backend = _AnthropicBackend(api_key, base_url, model)

    def generate_digest(self, articles: list[dict], top_n: int = 10, already_pushed: list[dict] | None = None, keywords: list[str] | None = None) -> str:
        article_text = ""
        for i, a in enumerate(articles, 1):
            article_text += (
                f"\n---\n{i}. 【{a['source']}】{a['title']}\n"
                f"摘要：{a.get('summary', '无')}\n"
                f"链接：{a['url']}\n"
            )

        pushed_section = ""
        if already_pushed:
            pushed_lines = "\n".join(
                f"  - 【{a['source']}】{a['title']}" for a in already_pushed
            )
            pushed_section = (
                f"\n⚠️ 以下是最近已推送过的文章（共 {len(already_pushed)} 条），"
                f"请跳过与这些内容相同或高度相似的新闻事件（即使来自不同信息源）：\n"
                f"{pushed_lines}\n"
            )

        keywords_section = ""
        if keywords:
            keywords_section = (
                f"\n⭐ 用户特别关注以下话题/关键词，涉及这些关键词的文章请优先选入：\n"
                f"  {', '.join(keywords)}\n"
            )

        try:
            return self.backend.chat(
                DIGEST_PROMPT.format(
                    total=len(articles),
                    top_n=top_n,
                    articles=article_text,
                    already_pushed=pushed_section,
                    keywords=keywords_section,
                ),
                max_tokens=8000,
            )
        except Exception as e:
            logger.error("Digest generation failed: %s", e)
            return self._fallback_digest(articles, top_n)

    def _fallback_digest(self, articles: list[dict], top_n: int) -> str:
        lines = ["📰 AI 日报\n"]
        for i, a in enumerate(articles[:top_n], 1):
            summary = a.get("summary", "")
            lines.append(f"{i}. 【{a['source']}】{a['title']}")
            if summary:
                lines.append(f"   {summary}")
            lines.append(f"   [🔗 原文链接]({a['url']})\n")
        return "\n".join(lines)
