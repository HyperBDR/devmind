from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for Profile model.
    """
    list_display = [
        'user',
        'registration_completed',
        'language',
        'timezone',
        'nickname',
    ]
    list_filter = [
        'registration_completed',
        'language',
        'timezone',
    ]
    search_fields = [
        'user__username',
        'user__email',
        'nickname'
    ]
    readonly_fields = [
        'registration_token',
        'registration_token_expires'
    ]
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Registration', {
            'fields': (
                'registration_completed',
                'registration_token',
                'registration_token_expires'
            )
        }),
        ('Profile Information', {
            'fields': (
                'nickname',
                'avatar_url',
                'bio',
                'language',
                'timezone'
            )
        }),
    )


class ProfileInline(admin.StackedInline):
    """
    Inline admin for Profile in User admin.
    """
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'


class UserAdmin(BaseUserAdmin):
    """
    Custom User admin that includes Profile inline.
    """
    inlines = (ProfileInline,)

    def get_inline_instances(self, request, obj=None):
        """
        Only show Profile inline when editing existing user.
        """
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
