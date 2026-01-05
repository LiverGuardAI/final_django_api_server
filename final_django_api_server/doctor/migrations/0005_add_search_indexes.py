# Generated manually on 2026-01-05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0004_patient_doctor'),
    ]

    operations = [
        # patient_id 인덱스 추가
        migrations.AlterField(
            model_name='patient',
            name='patient_id',
            field=models.CharField(max_length=50, unique=True, primary_key=True, db_index=True),
        ),
        # name 필드에 인덱스 추가 (검색 성능 향상)
        migrations.RunSQL(
            sql='CREATE INDEX IF NOT EXISTS idx_patient_name ON "hospital"."patient" ("name");',
            reverse_sql='DROP INDEX IF EXISTS idx_patient_name;',
        ),
        # sample_id 필드에 인덱스 추가
        migrations.RunSQL(
            sql='CREATE INDEX IF NOT EXISTS idx_patient_sample_id ON "hospital"."patient" ("sample_id");',
            reverse_sql='DROP INDEX IF EXISTS idx_patient_sample_id;',
        ),
        # created_at 인덱스 (정렬 성능 향상)
        migrations.RunSQL(
            sql='CREATE INDEX IF NOT EXISTS idx_patient_created_at ON "hospital"."patient" ("created_at" DESC);',
            reverse_sql='DROP INDEX IF EXISTS idx_patient_created_at;',
        ),
    ]
