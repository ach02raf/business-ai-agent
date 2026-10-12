# 🤖 Business AI Agent — Tools + MCP + LangGraph

Agent IA qui interagit avec des APIs métier (clients, commandes, tickets) via **function calling** et **MCP**,
avec **guardrails**, **fallbacks** et **validation humaine** pour les actions sensibles.

```
User ──▶ FastAPI ──▶ LangGraph agent ──▶ OpenAI (function calling)
                          │
                 ┌────────┴─────────┐
                 ▼                  ▼
              tools          sensitive_tools  ⏸ validation humaine (/approve)
                 └────────┬─────────┘
                          ▼
              Backend : local  |  MCP (stdio) ──fallback──▶ local
                          ▼
         search_customer()  get_order()  create_ticket()
```

## Fonctionnalités

| Exigence | Implémentation |
|---|---|
| Function calling | `llm.py` : `ChatOpenAI.bind_tools()` sur les tools autorisés |
| MCP | `mcp_server.py` (FastMCP) + `backends.py` (client MCP stdio) |
| Guardrails | allowlist de tools, validation Pydantic des arguments, anti prompt-injection, limite de taille, masquage des emails (PII), `MAX_STEPS` anti-boucle, audit log JSON, API key |
| Fallbacks | modèle OpenAI de secours (`with_fallbacks`), retries LLM + tools, MCP → local, message dégradé si le LLM est indisponible |
| Human validation | `interrupt_before=["sensitive_tools"]` : `create_ticket` attend un `POST /approve` |

## Démarrage rapide

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # mettez OPENAI_API_KEY, ou MOCK_LLM=true pour tester sans clé
uvicorn app.main:app --reload
```

Docker : `docker compose up --build` (API sur http://localhost:8000/docs)

## Exemples

```bash
# 1) Lecture : l'agent choisit get_order(4521)
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"message":"Find order #4521 and tell me its status."}'
# -> "Order #4521 / Status: shipped"

# 2) Écriture : l'agent veut créer un ticket -> pause
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"message":"Create a ticket for customer C-1001: package arrived damaged"}'
# -> {"status":"pending_approval","thread_id":"abc...","pending_actions":[{"tool":"create_ticket",...}]}

# 3) Un humain approuve (ou approve:false pour refuser)
curl -s localhost:8000/approve -H 'Content-Type: application/json' \
  -d '{"thread_id":"abc...","approve":true}'
```

Autres endpoints : `GET /tools`, `GET /tickets`, `GET /health`.
Si `API_KEY` est défini, ajoutez `-H 'X-API-Key: ...'`.

## Utiliser MCP

- Agent via MCP : `TOOL_BACKEND=mcp` (l'agent lance `python -m app.mcp_server` en stdio ; si MCP échoue → fallback local).
- Serveur MCP seul (ex. Claude Desktop) :
  ```json
  {"mcpServers":{"business-tools":{"command":"python","args":["-m","app.mcp_server"],"cwd":"/chemin/vers/business-ai-agent"}}}
  ```
- Inspecter : `npx @modelcontextprotocol/inspector python -m app.mcp_server`

## Contrôler l'accès aux tools

```env
ALLOWED_TOOLS=search_customer,get_order          # create_ticket désactivé
TOOLS_REQUIRING_APPROVAL=create_ticket
```

## Tests

```bash
MOCK_LLM=true pytest -q     # 15 tests : tools, guardrails, flux d'approbation, API, MCP
```

## Brancher vos vraies données

Remplacez le contenu de `app/data.py` / les fonctions de `app/tools.py` par vos appels API (CRM, ERP, Zendesk…).
Ajouter un tool = 1 modèle Pydantic + 1 fonction + 1 entrée dans `TOOLS` (il est automatiquement exposé à l'agent et au serveur MCP).
