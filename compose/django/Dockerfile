# =============================================================================
# compose/django/Dockerfile — imagem multi-stage do app Django (OPS-03)
# -----------------------------------------------------------------------------
# Estagio `builder`: instala dependencias com uv num venv isolado.
# Estagio `production`: runtime minimo, SEM ferramentas de build, usuario
#   nao-root, apenas o venv copiado do builder + libs de sistema de runtime.
#
# NOTA: este Dockerfile ainda nao constroi com sucesso de ponta a ponta porque
# o codigo Django (manage.py, core/, apps/) sera criado na proxima onda. A
# estrutura ja esta correta; o CMD aponta para `core.wsgi:application` (Gunicorn).
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# uv copiado da imagem oficial (resolucao/instalacao rapida e reprodutivel).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONDONTWRITEBYTECODE=1

# Dependencias de build:
#   - build-essential / python3-dev : compilar wheels quando necessario.
#   - libpq-dev                     : headers do PostgreSQL (psycopg2).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Camada de cache: instala apenas dependencias antes de copiar o codigo.
# `--frozen` exige uv.lock atualizado (mesmo contrato do CI: uv sync --frozen).
# `--no-dev` => sem ferramentas de teste/lint na imagem de runtime.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# ---------------------------------------------------------------------------
# Stage 2 — production
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv \
    DJANGO_SETTINGS_MODULE=core.settings.prod

# Libs de SISTEMA de runtime (sem toolchain de build):
#   - libpq5                                      : runtime do psycopg2.
#   - libpango / libcairo / libgdk-pixbuf / libffi: runtime do WeasyPrint
#     (RESSALVA: WeasyPrint e Fase 2 — TECH_SPEC A4; libs presentes para
#     coerencia com a dependencia declarada).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Usuario nao-root (boa pratica de runtime; nunca rodar como root).
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

# Apenas o venv pronto vem do builder (sem ferramentas de compilacao).
COPY --from=builder /opt/venv /opt/venv

# Codigo da aplicacao (sera populado na proxima onda: manage.py, core/, apps/).
COPY . .

# Gunicorn instala junto com as deps de prod (adicionar a runtime na proxima
# onda, junto com core.wsgi). Por ora o CMD documenta o contrato esperado.
USER app

EXPOSE 8000

# Entrypoint de producao esperado (ativar quando core.wsgi:application existir):
# CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
CMD ["python", "-c", "print('Imagem scaffold: core.wsgi ainda nao existe. Configure o CMD do Gunicorn na proxima onda.')"]
