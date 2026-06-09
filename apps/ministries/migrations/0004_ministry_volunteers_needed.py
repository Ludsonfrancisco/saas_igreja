# Generated for Sprint 6.6 / Bloco 2 (OD-029 — meta de voluntários do ministério).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ministries', '0003_remove_ministry_coordinator_ministry_coordinators'),
    ]

    operations = [
        migrations.AddField(
            model_name='ministry',
            name='volunteers_needed',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
