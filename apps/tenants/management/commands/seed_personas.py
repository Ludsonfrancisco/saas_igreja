"""Seed de PERSONAS de dev — cria uma conta de cada papel num tenant, com escopo e
conteúdo visíveis, para o dono verificar manualmente "o que cada visão enxerga".

NÃO é para produção (senha de dev descartável). Idempotente: re-rodar não duplica.

Personas criadas (todas com a mesma senha de dev):
- Secretário        → admin-like (vê tudo, mas não aprova exceção nem tesouraria)
- Líder             → líder de UMA comunidade (vê só a célula dele + pessoas dela)
- Coordenador       → coordenador de UM ministério (vê só os voluntários/escalas dele)
- Líder+Coordenador → os dois ao mesmo tempo (vê a UNIÃO: célula X + ministério Y)
- Tesoureiro        → só Financeiro

Uso: python manage.py seed_personas [--slug athos]
"""

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.tenants.models import Church

DEV_PASSWORD = 'Athos@2026'  # noqa: S105 — senha de dev descartável (não-prod)


class Command(BaseCommand):
    help = 'Cria contas de cada papel (com escopo) num tenant para verificação manual.'

    def add_arguments(self, parser):
        parser.add_argument('--slug', default='athos', help='Slug do tenant (dev).')

    def handle(self, *args, **options):
        slug = options['slug']
        church = Church.objects.filter(slug=slug).first()
        if not church:
            raise CommandError(f'Tenant "{slug}" nao encontrado.')

        def make_user(email, roles):
            user = User.objects.filter(email=email).first()
            if user:
                return user, False
            return (
                User.objects.create_user(
                    email=email,
                    password=DEV_PASSWORD,
                    roles=roles,
                    church=church,
                ),
                True,
            )

        secretary, _ = make_user(f'secretario@{slug}.localhost', ['secretary'])
        leader, _ = make_user(f'lider@{slug}.localhost', ['leader'])
        coordinator, _ = make_user(f'coordenador@{slug}.localhost', ['leader'])
        leadcoord, _ = make_user(f'lidercoord@{slug}.localhost', ['leader'])
        treasurer, _ = make_user(f'tesoureiro@{slug}.localhost', ['treasurer'])

        with schema_context(church.schema_name):
            from apps.communities.models import Community
            from apps.ministries.models import Ministry
            from apps.people.models import Person

            def staff_person(name, user_id):
                person, _ = Person.objects.get_or_create(
                    name=name,
                    defaults={'status': Person.Status.LEADER, 'user_id': user_id},
                )
                if person.user_id != user_id:
                    person.user_id = user_id
                    person.save(update_fields=['user_id', 'updated_at'])
                return person

            def cell(name):
                return Community.objects.get_or_create(name=name)[0]

            def ministry(name):
                return Ministry.objects.get_or_create(name=name)[0]

            def members(community, prefix, n=3):
                for i in range(1, n + 1):
                    Person.objects.get_or_create(
                        name=f'{prefix} {i}',
                        defaults={
                            'status': Person.Status.MEMBER,
                            'community': community,
                        },
                    )

            def volunteers(min_obj, prefix, n=3):
                for i in range(1, n + 1):
                    person, _ = Person.objects.get_or_create(
                        name=f'{prefix} {i}',
                        defaults={'status': Person.Status.MEMBER},
                    )
                    person.ministries.add(min_obj)

            # Líder → comunidade "Alfa" (+ membros visíveis); fora do escopo: as demais.
            alfa = cell('Alfa')
            alfa.leaders.add(staff_person('Líder Demo', leader.id))
            members(alfa, 'Membro Alfa')

            # Coordenador → ministério "Louvor" (+ voluntários).
            louvor = ministry('Louvor')
            louvor.coordinators.add(staff_person('Coordenador Demo', coordinator.id))
            volunteers(louvor, 'Voluntário Louvor')

            # Líder+Coordenador → comunidade "Semente" + ministério "Acolhida".
            lc_person = staff_person('Líder e Coordenador Demo', leadcoord.id)
            semente = cell('Semente')
            semente.leaders.add(lc_person)
            members(semente, 'Membro Semente')
            acolhida = ministry('Acolhida')
            acolhida.coordinators.add(lc_person)
            volunteers(acolhida, 'Voluntário Acolhida')

        self.stdout.write(self.style.SUCCESS(f'Personas de dev em "{slug}" prontas:'))
        for email in (
            secretary.email,
            leader.email,
            coordinator.email,
            leadcoord.email,
            treasurer.email,
        ):
            self.stdout.write(f'  {email}  /  {DEV_PASSWORD}')
        self.stdout.write(
            'Líder→célula Alfa · Coordenador→ministério Louvor · '
            'Líder+Coord→Semente + Acolhida.'
        )
