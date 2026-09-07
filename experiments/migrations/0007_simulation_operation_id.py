# Generated for Step 33 - Production Simulation Orchestration

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0006_simulation_simulationagent_agentstate_activityevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='simulation',
            name='operation_id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
