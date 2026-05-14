# AI News Feed

自动化 AI 新闻聚合工具 —— 抓取 RSS 订阅源、AI 智能筛选摘要、推送到聊天工具。

## 功能特性

- **多源抓取** — 支持 RSS / Atom 订阅，内置 13 个 AI 领域信息源，可自由增减
- **AI 智能摘要** — 使用大语言模型从海量文章中精选 Top N，生成结构化中文日报
- **多渠道推送** — 支持飞书、企业微信、WPS 协作、Telegram、Bark
- **Web 控制台** — 浏览器内完成所有配置，无需手动编辑文件
- **定时运行** — 支持 GitHub Actions 云端定时 或 本地 crontab
- **自动去重** — 基于 SQLite 存储，同一文章不会重复推送

## 快速开始

### 方式一：一键配置（推荐）

```bash
git clone https://github.com/yimeixiaobai/auto_news_feed.git
cd auto_news_feed
bash setup.sh
```

脚本会引导你完成：环境安装 → AI 模型配置 → 推送渠道配置 → 测试运行。如果本地安装了 `gh` (GitHub CLI)，还能一键同步 Secrets 到 GitHub Actions。

### 方式二：手动配置

**1. 安装依赖**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. 启动 Web 控制台**

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 ，按照首页的配置向导完成设置：

1. **添加信息源** — 默认已内置多个 AI 领域 RSS 源
2. **配置 AI 模型** — 填入 API 密钥（支持 Anthropic / OpenAI 协议）
3. **设置推送渠道** — 选择飞书、企业微信等接收方式
4. **手动运行** — 点击「立即运行」验证全流程

**3. 命令行运行**

```bash
# 预览模式：抓取 + 摘要，输出到终端，不推送
python main.py --dry-run

# 正式运行：抓取 + 摘要 + 推送
python main.py

# 跳过 AI 摘要（省 API 费用，仅抓取推送标题列表）
python main.py --no-summary
```

## 定时运行

### 方式一：GitHub Actions（推荐）

项目已包含 `.github/workflows/daily_news.yml`，默认每天北京时间 8:00 和 18:00 自动运行。

Fork 本仓库后，在 **Settings → Secrets and variables → Actions** 中添加所需的环境变量（见下方[环境变量](#环境变量)章节），即可自动运行。

### 方式二：本地 crontab

```bash
# 编辑 crontab
crontab -e

# 每天 8:00 和 18:00 运行（示例）
0 8,18 * * * cd /path/to/auto_news_feed && .venv/bin/python main.py >> logs/cron.log 2>&1
```

## 配置说明

所有配置通过 Web 控制台修改，保存在 `config/` 目录下：

| 文件 | 说明 |
|------|------|
| `config/feeds.yaml` | 信息源列表 |
| `config/settings.yaml` | 默认配置（会提交到 Git） |
| `config/settings.local.yaml` | 本地配置覆盖（已 gitignore，存放密钥等敏感信息） |

配置优先级：环境变量 > `settings.local.yaml` > `settings.yaml`

## 环境变量

所有敏感配置均可通过环境变量设置，适用于 GitHub Actions 或 Docker 部署：

| 变量名 | 说明 |
|--------|------|
| `SUMMARIZER_PROVIDER` | AI 服务商：`anthropic` 或 `openai` |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `ANTHROPIC_BASE_URL` | Anthropic API 地址（可选，留空用官方） |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `OPENAI_BASE_URL` | OpenAI API 地址（可选，留空用官方） |
| `PUSH_ENABLED` | 启用的推送渠道，逗号分隔，如 `lark,wps` |
| `WPS_WEBHOOK_URL` | WPS 协作 Webhook 地址 |
| `LARK_WEBHOOK_URL` | 飞书 Webhook 地址 |
| `LARK_SECRET` | 飞书签名密钥（可选） |
| `WECOM_WEBHOOK_URL` | 企业微信 Webhook 地址 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID |
| `BARK_DEVICE_KEY` | Bark 设备 Key |
| `BARK_SERVER_URL` | Bark 服务器地址（可选） |

## 项目结构

```
auto_news_feed/
├── main.py                  # CLI 入口：抓取 → 摘要 → 推送
├── server.py                # Web 控制台（FastAPI）
├── config/
│   ├── feeds.yaml           # 信息源配置
│   ├── settings.yaml        # 默认设置
│   └── settings.local.yaml  # 本地覆盖（gitignore）
├── src/
│   ├── config.py            # 配置读取（YAML + 环境变量）
│   ├── fetcher.py           # RSS 抓取与解析
│   ├── summarizer.py        # AI 摘要生成（Anthropic / OpenAI）
│   ├── db.py                # SQLite 存储与去重
│   └── pusher/              # 推送渠道实现
│       ├── lark.py          #   飞书
│       ├── wecom.py         #   企业微信
│       ├── wps.py           #   WPS 协作
│       ├── telegram.py      #   Telegram
│       └── bark.py          #   Bark（iOS）
├── static/
│   └── index.html           # Web 控制台前端
└── .github/
    └── workflows/
        └── daily_news.yml   # GitHub Actions 定时任务
```

## License

[MIT](LICENSE)
