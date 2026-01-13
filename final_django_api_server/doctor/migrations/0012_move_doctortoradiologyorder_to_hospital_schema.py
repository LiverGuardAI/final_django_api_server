from django.db import migrations


FORWARD_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'hospital')
       AND EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = 'doctor_to_radiology_orders'
              AND n.nspname = 'public'
        ) THEN
        EXECUTE 'ALTER TABLE public.doctor_to_radiology_orders SET SCHEMA hospital';
    END IF;
END$$;
"""

REVERSE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'doctor_to_radiology_orders'
          AND n.nspname = 'hospital'
    ) THEN
        EXECUTE 'ALTER TABLE hospital.doctor_to_radiology_orders SET SCHEMA public';
    END IF;
END$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ('doctor', '0011_alter_encounter_options_and_more'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
