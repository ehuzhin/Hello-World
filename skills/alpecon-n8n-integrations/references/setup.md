# Setup and continuation

## Account boundary

The user authorized configuring n8n Cloud, OpenAI, Claude, Dropbox and YouGile and saving a skill to GitHub. This does not provide accounts, balances, OAuth consent, API keys or an instance. Finish preparation before asking for the actual missing step. Never put credentials in chat or git.

Register at https://app.n8n.cloud/register using a corporate email selected by the user. Hand off final account creation/acceptance of terms. Set timezone Asia/Almaty. Cloud trial requires UI import; paid plans offer Settings > n8n API. Follow secure account/credential handoffs and applicable approval rules.

OpenAI: https://platform.openai.com; create ALPECON project, enable API billing and create a project key. n8n credential `openAiApi`, name `ALPECON OpenAI`.

Claude: https://console.anthropic.com; enable API billing and create a key. n8n credential `anthropicApi`, name `ALPECON Claude`.

Dropbox: n8n Cloud credential `dropboxOAuth2Api`, name `ALPECON Dropbox`; OAuth2 > Connect my account. Full Dropbox is needed for existing folders. Verify the actual shared-folder path. A ChatGPT connector is independent of n8n authorization. Create the destination folder through the UI or authorized Dropbox connector. The workflow expects it to exist.

YouGile: https://ru.yougile.com/api-v2. POST `https://yougile.com/api-v2/auth/companies` with login/password for company ID, then POST `/auth/keys` with login/password/companyId for a key. Use secure entry, never chat. n8n credential `httpHeaderAuth`, name `ALPECON YouGile`, name `Authorization`, value `Bearer <key>`. Test GET `/projects`, resolve a task UUID with GET `/tasks?title=...`, then read GET `/tasks/{id}`. Rate limit: 50 requests/minute/company. Reuse keys rather than regenerate them.

## Private runtime

- `ALPECON_N8N_BASE_URL`: HTTPS instance root without `/api/v1` suffix.
- `ALPECON_N8N_API_KEY`: management key, sent as `X-N8N-API-KEY` only to that instance.
- `ALPECON_OPENAI_API_KEY`, `ALPECON_ANTHROPIC_API_KEY`, `ALPECON_YOUGILE_API_KEY`: optional keys for `connect-keys`.
- `ALPECON_WEBHOOK_TOKEN`: optional external execution secret. Header: `X-ALPECON-TOKEN`.

`connect-keys` checks credential schemas, skips absent environment keys and reuses IDs from private state. It saves each successful ID to a mode-0600 file, never secret values. Dropbox OAuth remains interactive. Creating credentials does not verify provider connectivity.

Config accepts only a task UUID, model IDs, Dropbox folder path and credential IDs. Placeholders intentionally fail before live work. Copy IDs from n8n UI; names alone do not identify accounts uniquely. API deployment requires all four IDs (and webhook ID for external automation).

## Deploy and run

`deploy` reuses recorded workflow ID or resolves an exact name across all workflow pages. Ambiguous names stop deployment. Repeated identical deployments do not update the graph. Changed active workflows require deactivation before update. Private state must belong to the same instance. Manual and webhook variants share a managed name and therefore update the same workflow.

`--webhook --activate` activates the authenticated webhook after complete configuration. POST `{"task_id":"<uuid>"}`. It waits for Dropbox metadata. Timeout is 180 seconds; inspect Executions before repeating an ambiguous failure. No schedules, chat access or employee messages are created.

`build` checks graph/config, not live n8n import compatibility. `check` verifies management API reachability only. Final acceptance requires successful execution AND the expected file in Dropbox. Keep logs private.

## Sources checked 2026-10-11

- https://docs.n8n.io/api/authentication/
- https://docs.n8n.io/integrations/builtin/credentials/openai/
- https://docs.n8n.io/integrations/builtin/credentials/anthropic/
- https://docs.n8n.io/integrations/builtin/credentials/dropbox/
- https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.chainllm/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.converttofile/
- https://ru.yougile.com/api-v2 and linked schema https://ru.yougile.com/api-json
- Official source at https://github.com/n8n-io/n8n for the model, Dropbox and ConvertToFile nodes.

Recheck schemas when deployment versions change. Template uses OpenAI model 1.2, Anthropic model 1.3, Basic LLM Chain 1.7, Dropbox 1 and ConvertToFile 1.1. The conversion node discards input JSON, so Dropbox's path references the Report node explicitly.
