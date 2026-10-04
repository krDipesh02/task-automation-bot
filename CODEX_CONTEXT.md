# Codex Context — Task Automation Bot

Internal implementation handoff, specific to this repository. README is only the human-facing purpose/role summary. Read this before editing; inspect git status and source; current code is authoritative. Preserve user edits and don't commit unless asked.

## Scope and runtime

Python FastAPI service for Telegram/webhook automation, workflow adapters and agent orchestration. SpendWise-specific responsibility: Telegram webhook verification, extracting trusted Telegram identity/context, command handling, backend authorization check, response delivery, conversation memory, selecting/invoking default/n8n/SpendWise agents. It must never access backend database.

Startup initializes n8n, default and SpendWise agents; missing agent credentials may fail app startup. Local webhook path is POST /webhook/telegram in app/main.py, service normally port 8000. Config template is configs/env.example.

## Request path and source files

- app/main.py: FastAPI lifespan, Telegram route, webhook secret check, /start and /setup branches, authorization gate and orchestration dispatch.
- app/adapters/telegram/parser.py: maps Telegram message/chat/from fields into TelegramRequestContext; sender/parser format Telegram HTML.
- app/services/spendwise_service.py: synchronous requests to internal backend for status lookup, invite claim, credential setup URL and conversation memory get/put/delete. Reads SPENDWISE_BASE_URL and SPENDWISE_TELEGRAM_SERVICE_TOKEN at import time.
- app/core/models.py: immutable TelegramRequestContext / ConversationTurn and ContextVars for current request and history.
- app/core/orchestrator.py: read memory → route agent → invoke → persist memory. Exceptions are logged and returned as an Error string; consider safe user messaging if changing.
- app/core/router.py and extractor.py: agent/workflow classification.
- app/agents/agent_registry.py: builds agents at startup and invokes them with request/history ContextVars. Prepends temporal context to each invocation.
- app/agents/spendwise_agent.py and app/tools/mcp_tools.py: MCP connection, tools and trusted identity propagation/interception.
- app/prompts/agent_prompts.py: agent-specific system prompts.
- app/executor and app/workflows: n8n orchestration.
- app/config/settings.py, configs/env.example: some settings; note app/main.py and service modules also capture environment values at import time.
- tests/test_telegram_enrollment.py, test_orchestrator.py, test_context_flow.py and test_workflows.py are relevant.

Path should be: verified webhook → parsed context → /start,/setup and authorization branches → orchestrator only for ACTIVE → agent → MCP → backend. Authorization and onboarding commands must bypass LLM/MCP.

## Telegram webhook and credential boundaries

TELEGRAM_WEBHOOK_SECRET must equal the secret_token supplied to Telegram setWebhook; Telegram sends X-Telegram-Bot-Api-Secret-Token on webhook updates. Bot uses constant-time compare. It validates Telegram delivery configuration and is not backend auth.

Keep credentials separate:
- TELEGRAM_BOT_TOKEN: bot calls Telegram API.
- TELEGRAM_WEBHOOK_SECRET: Telegram request verification.
- SPENDWISE_TELEGRAM_SERVICE_TOKEN: bot calls backend internal Telegram routes.
- SPENDWISE_MCP_AUTH_TOKEN: bot calls MCP.
- SPENDWISE_AUTOMATION_SERVICE_TOKEN: MCP calls backend business routes.
Do not put any of these in logs/source control.

Telegram user ID comes from verified update message.from.id, not username. /start <token> calls backend claim endpoint and never reaches agent; claim is pending until admin verifies out of band and approves. Plain /start explains invite process. /setup requests a one-time credential setup URL for active linked user. Normal message first calls backend lookup; unknown/pending user gets unauthorized response, blocked receives denial, only active invokes orchestrator.

## Enrollment and user data

Bot submits invite token and Telegram ID/profile metadata to backend internal claim endpoint. Backend owns token hashing, expiration/revocation, single-claim atomicity, pending/active state and user mapping. Admin frontend/backend handles review. On approval, backend creates SpendWise profile and ACTIVE Telegram mapping. /setup adds browser username/password to this same profile via one-time setup token; bot must not send temporary password.

Conversation memory is stored through backend internal Telegram memory endpoints, keyed by Telegram user identity. This is not MCP. Existing authorization gate must precede memory/orchestrator for unauthorized users; check app/main.py if modifying ordering.

## Agent context, MCP identity

TelegramRequestContext and memory are carried with Python ContextVars around invoke_agent. MCP calls must inherit trusted Telegram context from the Telegram update; ignore model-requested identity. Backend independently verifies automation service credential and maps Telegram ID to canonical SpendWise user UUID.

Agent startup is in app/agents/agent_registry.py. Native n8n MCP tools receive Telegram context via _build_n8n_execution_context. SpendWise tools are in spendwise_agent.py; inspect interceptors and MCP client args before changing identity propagation.

## Date incident and current mitigation

The earlier bot answered “Today's date is October 4, 2023” on actual October 4, 2026 in Asia/Kolkata; Telegram expense spentAt was old while DB createdAt was correct.

Mitigation is already present locally:
- app/utils/date_context.py reads APP_TIMEZONE (default Asia/Kolkata), uses zoneinfo to calculate current timestamp/date, relative dates, and explicit date rules.
- app/agents/agent_registry.py calls build_temporal_context() and puts it in system messages for each agent invocation.
- configs/env.example has APP_TIMEZONE=Asia/Kolkata.
- MCP expense_create still requires spent_at and passes as spentAt; backend persists it. User-explicit past dates must remain valid.

If issue repeats, verify deployed bot container/process has this code and APP_TIMEZONE, then inspect system message placement, conversation history, MCP arguments and backend request JSON. Don't change backend to silently replace dates without investigation.

## Config and debugging notes

Key vars: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, APP_TIMEZONE, OPENAI_API_KEY/GEMINI_API_KEY, N8N_MCP_URL, N8N_AUTH_TOKEN, SPENDWISE_BASE_URL, SPENDWISE_TELEGRAM_SERVICE_TOKEN, SPENDWISE_MCP_URL, SPENDWISE_MCP_AUTH_TOKEN, optional LangSmith. Docker/container calls require service DNS rather than localhost.

Historical problems:
- /auth/automation/api-key-exchange was not a valid backend route; 302 Google OAuth redirect caused misleading auth symptoms.
- Credential setup for inactive Telegram user correctly raised 403; servlet ERROR dispatch formerly made caller see 401, fixed in backend SecurityConfig and confirmed by user.
- Backend X-Request-Id correlates server request log and response header.
- Avoid exposing exception trace, invite token, or service detail in Telegram responses.

Relevant tests exist; historical suite had 20 passing before latest context edit. README is intentionally role-only; runtime instructions/config belong in this file and env examples.
