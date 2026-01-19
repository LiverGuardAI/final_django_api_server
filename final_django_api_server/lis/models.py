from django.db import models

class LisStaff(models.Model):
    """진단검사의학과 직원"""

    staff_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    employee_no = models.CharField(max_length=50, unique=True)
    date_of_birth = models.DateField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    user = models.OneToOneField('accounts.CustomUser', on_delete=models.CASCADE, db_column='user_id')
    department = models.ForeignKey('accounts.Department', on_delete=models.RESTRICT, db_column='department_id')
    
    class Meta:
        db_table = 'hospital"."lis_staff'
        verbose_name = '진단검사의학과'
        verbose_name_plural = '진단검사의학과'

    def __str__(self):
        return f"{self.name} ({self.employee_no})"
