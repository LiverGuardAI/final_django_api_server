# Generated manually on 2026-01-05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0003_patient_phone_alter_encounter_encounter_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='patient',
            name='doctor',
            field=models.ForeignKey(
                blank=True,
                db_column='doctor_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='doctor.doctor'
            ),
        ),
    ]
