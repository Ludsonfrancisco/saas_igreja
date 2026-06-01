"""Project package.

Importa o app Celery no carregamento do pacote para que tasks com o decorator
`@shared_task` sejam registradas corretamente (padrao oficial do Celery + Django).
"""

from .celery import app as celery_app

__all__ = ('celery_app',)
