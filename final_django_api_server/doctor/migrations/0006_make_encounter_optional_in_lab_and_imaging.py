# Generated manually on 2026-01-06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0005_add_search_indexes'),
    ]

    operations = [
        # LabResult의 encounter FK를 optional로 변경
        migrations.AlterField(
            model_name='labresult',
            name='encounter',
            field=models.ForeignKey(
                blank=True,
                db_column='encounter_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='doctor.encounter'
            ),
        ),
        # ImagingOrder의 encounter FK를 optional로 변경
        migrations.AlterField(
            model_name='imagingorder',
            name='encounter',
            field=models.ForeignKey(
                blank=True,
                db_column='encounter_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='doctor.encounter'
            ),
        ),
    ]
