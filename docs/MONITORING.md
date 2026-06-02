# MONITORING — SaaS Igreja

> Observabilidade da Sprint 1 (healthcheck) e como monitorá-la em produção.
> Referência: `TECH_SPEC.md §12.1`, `RNF-018`. Config real de EasyPanel/Cloudflare é da **Sprint 7 (deploy)**.

## Endpoints de saúde

| Endpoint | Auth | Verifica | Retorna |
|---|---|---|---|
| `GET /health/` | Não | Processo Django vivo | **200** sempre que o processo responde (não toca no banco) |
| `GET /ready/` | Não | Postgres (`SELECT 1`) + Redis (`ping`) | **200** se ambos OK; **503** caso contrário (corpo JSON detalha qual falhou) |

Detalhes de implementação:

- Views em `apps/core/views.py` (`health`, `ready`).
- Rotas em `core/urls.py` (ROOT_URLCONF), **sem subdomínio de tenant**.
- O `TenantMiddleware` (`apps/tenants/middleware.py`) faz **bypass** de `/health/` e `/ready/`: não resolve tenant nem consulta `Domain`. Isso garante que:
  - `/health/` (liveness) responda **mesmo com o Postgres fora** — a sonda de vida não pode depender do banco;
  - as sondas respondam mesmo para um `Host` desconhecido (o monitor externo), que de outra forma cairia em `no_tenant_found → 404`.

### Liveness vs Readiness

- **Liveness (`/health/`):** "o processo está vivo?". Se falhar repetidamente, o orquestrador deve **reiniciar** o container.
- **Readiness (`/ready/`):** "consigo atender requisições agora?". Se 503 (ex.: Redis piscou), o orquestrador deve **tirar o container do balanceamento temporariamente**, sem necessariamente reiniciá-lo.

## Container (dev/build) — já configurado

O serviço `web` do `docker-compose.yml` tem `healthcheck` apontando para `/ready/` (via `urllib` do próprio Python da imagem; 503 ⇒ `unhealthy`). Ativo quando o serviço sobe sob o profile `app`.

## Produção (Sprint 7 — a aplicar no deploy)

Quando o ambiente existir (Hostinger KVM 2 + EasyPanel + Cloudflare — OD-006):

1. **EasyPanel** — configurar o healthcheck do serviço para `GET /ready/` (intervalo ~30s, timeout ~8s, 3 retries). Falha ⇒ EasyPanel não promove o deploy / sinaliza unhealthy.
2. **Cloudflare** — criar um **Health Check** (Traffic → Health Checks) para `https://<dominio>/ready/`, esperando HTTP 200, com notificação por e-mail em caso de falha. Usar para failover/alarme.
3. **Uptime externo (opcional)** — um monitor externo (ex.: UptimeRobot) batendo em `/health/` a cada 1–5 min para alarme de indisponibilidade total.
4. **Sentry** (RNF / TECH_SPEC §12.3) — alertas de 5xx e tag `tenant_id`; `before_send` sanitiza PII (configuração detalhada na Sprint 2/7).

> Nota: o monitor de produção deve usar o **domínio público** (schema `public`); as sondas não exigem subdomínio de tenant.
