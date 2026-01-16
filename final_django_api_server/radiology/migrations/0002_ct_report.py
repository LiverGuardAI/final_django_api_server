from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('radiology', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CTReport',
            fields=[
                ('report_id', models.AutoField(primary_key=True, serialize=False)),
                ('series_instance_uid', models.CharField(db_index=True, max_length=64)),
                ('report_text', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'hospital"."ct_reports',
            },
        ),
    ]
