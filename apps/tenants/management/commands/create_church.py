"""Comando de gestao: provisiona um tenant (igreja) em dev.

Uso (dev):
    python manage.py create_church athos --name "Igreja Athos"

Garante o tenant publico (necessario para o TenantMiddleware funcionar), cria
o schema do tenant via `auto_create_schema`, registra o dominio primario e cria
o Pastor inicial (TECH_SPEC §2 / §4 / CLAUDE.md).
"""

from django.core.management.base import BaseCommand, CommandError

from apps.tenants.services import create_church_with_admin

DEV_DEFAULT_PASSWORD = 'changeme123'


class Command(BaseCommand):
    help = 'Provisiona uma igreja (tenant) com schema, dominio e Pastor inicial.'

    def add_arguments(self, parser):
        parser.add_argument(
            'slug',
            help='Slug da igreja (ex.: athos). Vira o subdominio e o schema.',
        )
        parser.add_argument(
            '--name',
            default=None,
            help='Nome da igreja. Padrao: slug capitalizado.',
        )
        parser.add_argument(
            '--leader-title',
            default='Pastor',
            help='Titulo do lider principal (Pastor, Padre, etc.). Padrao: Pastor.',
        )
        parser.add_argument(
            '--has-communities',
            dest='has_communities',
            action='store_true',
            default=True,
            help='Igreja em celulas/comunidades (padrao).',
        )
        parser.add_argument(
            '--no-communities',
            dest='has_communities',
            action='store_false',
            help='Igreja tradicional (sem comunidades).',
        )
        parser.add_argument(
            '--pastor-email',
            default=None,
            help='Email do Pastor inicial. Padrao: pastor@<slug>.localhost.',
        )
        parser.add_argument(
            '--pastor-password',
            default=DEV_DEFAULT_PASSWORD,
            help='Senha do Pastor inicial (descartavel em dev).',
        )
        parser.add_argument(
            '--domain',
            default=None,
            help='Dominio primario do tenant. Padrao: <slug>.localhost.',
        )

    def handle(self, *args, **options):
        slug = options['slug']
        name = options['name'] or slug.title()
        leader_title = options['leader_title']
        has_communities = options['has_communities']
        pastor_email = options['pastor_email'] or f'pastor@{slug}.localhost'
        pastor_password = options['pastor_password']
        domain = options['domain'] or f'{slug}.localhost'

        if pastor_password == DEV_DEFAULT_PASSWORD:
            self.stdout.write(
                self.style.WARNING(
                    'AVISO: usando a senha padrao de dev (descartavel). '
                    'Defina --pastor-password fora de dev.'
                )
            )

        try:
            result = create_church_with_admin(
                slug=slug,
                name=name,
                leader_title=leader_title,
                has_communities=has_communities,
                domain=domain,
                pastor_email=pastor_email,
                pastor_password=pastor_password,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if result.public_bootstrapped:
            self.stdout.write(
                self.style.SUCCESS(
                    'Tenant publico garantido (schema "public" + localhost).'
                )
            )
        else:
            self.stdout.write('Tenant publico ja existia (nenhuma acao).')

        self.stdout.write(
            self.style.SUCCESS(f'Schema do tenant criado: {result.church.schema_name}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Dominio registrado: {result.domain.domain}')
        )

        if result.pastor_created:
            self.stdout.write(
                self.style.SUCCESS(f'Pastor inicial criado: {result.pastor_email}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'Usuario com email "{result.pastor_email}" ja existia; '
                    'criacao do Pastor ignorada (email e unico globalmente).'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Igreja "{result.church.name}" provisionada com sucesso.'
            )
        )
