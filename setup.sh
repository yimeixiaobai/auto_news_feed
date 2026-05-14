#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
step() { echo -e "\n${CYAN}${BOLD}[$1] $2${NC}"; }

prompt() {
  local var=$1 msg=$2 default=$3
  if [ -n "$default" ]; then
    read -rp "  $msg [$default]: " input
    eval "$var=\"\${input:-$default}\""
  else
    read -rp "  $msg: " input
    eval "$var=\"\$input\""
  fi
}

prompt_secret() {
  local var=$1 msg=$2
  read -rsp "  $msg: " input
  echo
  eval "$var=\"\$input\""
}

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     AI News Feed · 一键配置向导      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"

# ── Step 1: Environment ──────────────────────────────

step "1/5" "检查环境"

PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
    minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
    if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ] 2>/dev/null; then
      PYTHON="$cmd"
      ok "Python $ver"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  fail "需要 Python 3.10+，请先安装"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo -e "  创建虚拟环境..."
  $PYTHON -m venv .venv
  ok "虚拟环境已创建"
else
  ok "虚拟环境已存在"
fi

source .venv/bin/activate
pip install -q -r requirements.txt
ok "依赖安装完成"

# ── Step 2: AI Model ────────────────────────────────

step "2/5" "AI 模型配置"

echo ""
echo "  选择 AI 服务商："
echo "    1) OpenAI / OpenAI 兼容协议（适用于大多数第三方中转）"
echo "    2) Anthropic (Claude)"
echo ""
prompt PROVIDER_CHOICE "输入编号" "1"

if [ "$PROVIDER_CHOICE" = "2" ]; then
  PROVIDER="anthropic"
  DEFAULT_MODEL="claude-sonnet-4-6"
  KEY_HINT="sk-ant-..."
else
  PROVIDER="openai"
  DEFAULT_MODEL="gpt-4o"
  KEY_HINT="sk-..."
fi
ok "服务商: $PROVIDER"

echo ""
prompt_secret API_KEY "API 密钥 ($KEY_HINT)"
prompt BASE_URL "API 地址（使用官方留空，中转服务填地址）" ""
prompt MODEL "模型名称" "$DEFAULT_MODEL"
prompt TOP_N "每次推送精选条数" "15"

# ── Step 3: Push Channels ───────────────────────────

step "3/5" "推送渠道"

echo ""
echo "  可用的推送渠道："
echo "    1) 飞书"
echo "    2) 企业微信"
echo "    3) WPS 协作"
echo "    4) Telegram"
echo "    5) Bark (iOS)"
echo ""
prompt CHANNEL_CHOICES "输入要启用的编号，多个用逗号分隔（如 1,3）" ""

ENABLED_LIST=""
PUSH_LARK_URL="" PUSH_LARK_SECRET=""
PUSH_WECOM_URL=""
PUSH_WPS_URL=""
PUSH_TG_TOKEN="" PUSH_TG_CHATID=""
PUSH_BARK_KEY="" PUSH_BARK_URL=""

IFS=',' read -ra CHANNELS <<< "$CHANNEL_CHOICES"
for ch in "${CHANNELS[@]}"; do
  ch=$(echo "$ch" | tr -d ' ')
  case "$ch" in
    1)
      [ -n "$ENABLED_LIST" ] && ENABLED_LIST="$ENABLED_LIST,"
      ENABLED_LIST="${ENABLED_LIST}lark"
      echo ""
      echo -e "  ${BOLD}飞书配置：${NC}"
      prompt_secret PUSH_LARK_URL "Webhook 地址"
      prompt PUSH_LARK_SECRET "签名密钥（未开启留空）" ""
      ;;
    2)
      [ -n "$ENABLED_LIST" ] && ENABLED_LIST="$ENABLED_LIST,"
      ENABLED_LIST="${ENABLED_LIST}wecom"
      echo ""
      echo -e "  ${BOLD}企业微信配置：${NC}"
      prompt_secret PUSH_WECOM_URL "Webhook 地址"
      ;;
    3)
      [ -n "$ENABLED_LIST" ] && ENABLED_LIST="$ENABLED_LIST,"
      ENABLED_LIST="${ENABLED_LIST}wps"
      echo ""
      echo -e "  ${BOLD}WPS 协作配置：${NC}"
      prompt_secret PUSH_WPS_URL "Webhook 地址"
      ;;
    4)
      [ -n "$ENABLED_LIST" ] && ENABLED_LIST="$ENABLED_LIST,"
      ENABLED_LIST="${ENABLED_LIST}telegram"
      echo ""
      echo -e "  ${BOLD}Telegram 配置：${NC}"
      prompt_secret PUSH_TG_TOKEN "Bot Token"
      prompt PUSH_TG_CHATID "Chat ID" ""
      ;;
    5)
      [ -n "$ENABLED_LIST" ] && ENABLED_LIST="$ENABLED_LIST,"
      ENABLED_LIST="${ENABLED_LIST}bark"
      echo ""
      echo -e "  ${BOLD}Bark 配置：${NC}"
      prompt PUSH_BARK_KEY "Device Key" ""
      prompt PUSH_BARK_URL "服务器地址" "https://api.day.app"
      ;;
  esac
done

if [ -z "$ENABLED_LIST" ]; then
  warn "未选择任何推送渠道，可稍后在 Web 控制台中配置"
fi

# ── Step 4: Save config ─────────────────────────────

step "4/5" "保存配置"

# Build enabled list YAML
ENABLED_YAML=""
IFS=',' read -ra EN_ARR <<< "$ENABLED_LIST"
for e in "${EN_ARR[@]}"; do
  ENABLED_YAML="$ENABLED_YAML\n  - $e"
done
[ -z "$ENABLED_YAML" ] && ENABLED_YAML=" []"

cat > config/settings.local.yaml << YAML
summarizer:
  provider: ${PROVIDER}
  top_n: ${TOP_N}
  ${PROVIDER}:
    api_key: '${API_KEY}'
    base_url: '${BASE_URL}'
    model: '${MODEL}'
push:
  enabled:$(echo -e "$ENABLED_YAML")
  lark:
    webhook_url: '${PUSH_LARK_URL}'
    secret: '${PUSH_LARK_SECRET}'
  wecom:
    webhook_url: '${PUSH_WECOM_URL}'
  wps:
    webhook_url: '${PUSH_WPS_URL}'
  telegram:
    bot_token: '${PUSH_TG_TOKEN}'
    chat_id: '${PUSH_TG_CHATID}'
  bark:
    device_key: '${PUSH_BARK_KEY}'
    server_url: '${PUSH_BARK_URL}'
YAML

ok "配置已保存到 config/settings.local.yaml"

# ── Step 5: Test run ─────────────────────────────────

step "5/5" "测试运行"

echo ""
prompt DO_TEST "是否运行一次测试？（仅预览，不实际推送）[Y/n]" "Y"

if [[ "$DO_TEST" =~ ^[Yy]$ ]] || [ -z "$DO_TEST" ]; then
  echo ""
  echo "  运行中，请稍候..."
  echo ""
  .venv/bin/python main.py --dry-run -v 2>&1 | sed 's/^/  /'
  RET=${PIPESTATUS[0]}
  echo ""
  if [ "$RET" -eq 0 ]; then
    ok "测试运行成功！"
  else
    fail "运行出错，请检查上方日志"
  fi
fi

# ── Optional: GitHub Actions ─────────────────────────

echo ""
if command -v gh &>/dev/null && gh auth status &>/dev/null 2>&1; then
  prompt DO_GH "检测到 gh 已登录，是否同步配置到 GitHub Secrets？[y/N]" "N"

  if [[ "$DO_GH" =~ ^[Yy]$ ]]; then
    REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || true)
    if [ -z "$REPO" ]; then
      prompt REPO "输入 GitHub 仓库（格式 owner/repo）" ""
    fi

    if [ -n "$REPO" ]; then
      echo "  同步 Secrets 到 $REPO ..."
      gh secret set SUMMARIZER_PROVIDER --body "$PROVIDER" --repo "$REPO"
      [ -n "$API_KEY" ]          && gh secret set "${PROVIDER^^}_API_KEY"  --body "$API_KEY"  --repo "$REPO"
      [ -n "$BASE_URL" ]         && gh secret set "${PROVIDER^^}_BASE_URL" --body "$BASE_URL" --repo "$REPO"
      [ -n "$MODEL" ]            && gh secret set "${PROVIDER^^}_MODEL"    --body "$MODEL"    --repo "$REPO"
      [ -n "$ENABLED_LIST" ]     && gh secret set PUSH_ENABLED             --body "$ENABLED_LIST" --repo "$REPO"
      [ -n "$PUSH_LARK_URL" ]    && gh secret set LARK_WEBHOOK_URL         --body "$PUSH_LARK_URL" --repo "$REPO"
      [ -n "$PUSH_LARK_SECRET" ] && gh secret set LARK_SECRET              --body "$PUSH_LARK_SECRET" --repo "$REPO"
      [ -n "$PUSH_WECOM_URL" ]   && gh secret set WECOM_WEBHOOK_URL        --body "$PUSH_WECOM_URL" --repo "$REPO"
      [ -n "$PUSH_WPS_URL" ]     && gh secret set WPS_WEBHOOK_URL          --body "$PUSH_WPS_URL" --repo "$REPO"
      [ -n "$PUSH_TG_TOKEN" ]    && gh secret set TELEGRAM_BOT_TOKEN       --body "$PUSH_TG_TOKEN" --repo "$REPO"
      [ -n "$PUSH_TG_CHATID" ]   && gh secret set TELEGRAM_CHAT_ID         --body "$PUSH_TG_CHATID" --repo "$REPO"
      [ -n "$PUSH_BARK_KEY" ]    && gh secret set BARK_DEVICE_KEY           --body "$PUSH_BARK_KEY" --repo "$REPO"
      [ -n "$PUSH_BARK_URL" ]    && gh secret set BARK_SERVER_URL           --body "$PUSH_BARK_URL" --repo "$REPO"
      ok "GitHub Secrets 已同步"
    fi
  fi
fi

# ── Done ──────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}══════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  配置完成！${NC}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════${NC}"
echo ""
echo "  后续操作："
echo "    启动 Web 控制台:  python -m uvicorn server:app --port 8000"
echo "    手动运行一次:     python main.py"
echo "    预览模式:         python main.py --dry-run"
echo ""
