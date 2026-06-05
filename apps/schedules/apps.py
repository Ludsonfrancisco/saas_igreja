from django.apps import AppConfig


class SchedulesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.schedules'

    def ready(self):
        """Conecta o signal de segurança da aprovação de exceção (P-ARQ-06).

        Import tardio + `dispatch_uid` para evitar conexão dupla no autoreload.
        """
        from django.db.models.signals import post_save

        from apps.schedules import signals
        from apps.schedules.models import ScheduleConflictApproval

        post_save.connect(
            signals.on_conflict_approval_created,
            sender=ScheduleConflictApproval,
            dispatch_uid='schedules.on_conflict_approval_created',
        )
