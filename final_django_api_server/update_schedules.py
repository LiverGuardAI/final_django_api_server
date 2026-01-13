import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liverguard_api_server.settings')
django.setup()

from accounts.models import DutySchedule

print("--- Updating Duty Schedules ---")
pending_schedules = DutySchedule.objects.filter(schedule_status='PENDING')
count = pending_schedules.count()

if count > 0:
    print(f"Found {count} PENDING schedules. Updating to CONFIRMED...")
    pending_schedules.update(schedule_status='CONFIRMED')
    print("Update complete.")
else:
    print("No PENDING schedules found.")

# Verify
all_schedules = DutySchedule.objects.all()
for s in all_schedules:
    print(f"ID: {s.schedule_id}, User: {s.user.username}, Status: {s.schedule_status}")
