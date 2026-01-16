import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liverguard_api_server.settings')
django.setup()

from patients.models import Appointment
from doctor.models import Encounter

# Find appointments with COMPLETED encounters but still showing '예약완료'
appointments = Appointment.objects.filter(status='예약완료')
updated = 0

for apt in appointments:
    encounter = Encounter.objects.filter(appointment=apt, workflow_state='COMPLETED').first()
    if encounter:
        apt.status = '진료완료'
        apt.save()
        print(f'Updated Apt {apt.id}')
        updated += 1

print(f'Total updated: {updated}')
