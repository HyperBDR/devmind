from django.contrib import admin

from .models import Company, User, Incident


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["sys_id", "name", "created_at", "updated_at"]
    search_fields = ["sys_id", "name"]
    ordering = ["name", "sys_id"]


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["sys_id", "name", "email", "department", "active", "created_at"]
    search_fields = ["sys_id", "name", "email", "user_name"]
    list_filter = ["active", "department"]
    ordering = ["name", "sys_id"]


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = [
        "number", "priority", "state", "company",
        "assignment_group", "assigned_to", "created_at",
    ]
    search_fields = ["number", "short_description", "company", "caller"]
    list_filter = ["priority", "state", "assignment_group", "month"]
    ordering = ["-created_at", "-id"]
    date_hierarchy = "created_at"
