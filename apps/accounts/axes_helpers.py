"""Resolucao de username para o django-axes (SEC-02).

Por que um callable proprio? O axes, por padrao, tenta extrair o username de
`credentials[AXES_USERNAME_FORM_FIELD]` e so depois de `request.POST`. No nosso
fluxo:

- O formulario de login do allauth posta o campo como `login`.
- O `user_login_failed` do Django chega com `credentials` cujo nome de chave
  varia (`email`/`username`, conforme o backend), e NAO contem `login`.

Sem este callable, o axes registra `username=None` e o lockout degrada para
"apenas por IP". Com ele, o lockout fica corretamente por (usuario+IP): tentamos
varias chaves conhecidas tanto em `credentials` quanto em `request.POST`,
normalizando para minusculas (login por email e case-insensitive — casa com o
EmailBackend).

Importante: o valor retornado e usado como CHAVE de lockout do axes (vai para a
tabela AccessAttempt no schema public). Nunca passamos esse valor para o
SecurityLog/Sentry — la nao registramos PII (TENANT-07).
"""

_USERNAME_KEYS = ('login', 'email', 'username')


def get_username(request, credentials=None):
    """Extrai o identificador de login (email) de credentials ou request.POST."""
    for source in (credentials or {}, getattr(request, 'POST', {}) or {}):
        for key in _USERNAME_KEYS:
            value = source.get(key)
            if value:
                return value.strip().lower()
    return ''
