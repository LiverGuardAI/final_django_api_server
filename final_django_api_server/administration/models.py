from django.db import models


class Administration(models.Model):
    """원무과 직원"""
    
    staff_id = models.AutoField(primary_key=True)
    employee_no = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Foreign Keys
    user = models.OneToOneField('accounts.CustomUser', on_delete=models.CASCADE, db_column='user_id')
    department = models.ForeignKey('accounts.Department', on_delete=models.RESTRICT, db_column='department_id')
    
    class Meta:
        db_table = 'hospital"."administration'
        verbose_name = '원무과'
        verbose_name_plural = '원무과'
    
    def __str__(self):
        return f"{self.name} ({self.employee_no})"