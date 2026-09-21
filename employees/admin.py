from django.contrib import admin
from .models import Attendance, ChecklistItem, Employee, EmployeeChecklistEntry, Leave
from .models import SalaryRecord

admin.site.register(Employee)
admin.site.register(Attendance)
admin.site.register(Leave)


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "order", "is_active")
    list_filter = ("organization", "is_active")
    list_editable = ("order", "is_active")


@admin.register(EmployeeChecklistEntry)
class EmployeeChecklistEntryAdmin(admin.ModelAdmin):
    list_display = ("employee", "item", "status", "completed_on", "marked_by", "updated_at")
    list_filter = ("status", "item")

@admin.register(SalaryRecord)
class SalaryRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "month_display",
        "base_salary",
        "payable_days",
        "total_days",
        "gross_earned",
        "net_salary",
        "confirmed",
        "confirmed_by",
    )
    list_filter = ("organization", "year", "month", "confirmed")
    search_fields = ("employee__first_name", "employee__last_name", "employee__employee_id")
    readonly_fields = ("generated_at", "updated_at")

    def month_display(self, obj):
        return f"{obj.month:02d}/{obj.year}"
    month_display.short_description = "Period"
    