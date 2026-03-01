"""Management portal views (admin-only): user list/create, group list/create.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count, Prefetch
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView

from accounts.models import Profile

User = get_user_model()


def _safe_int(value, default, min_value=1, max_value=100):
    """Parse value to int and clamp to [min_value, max_value]; else default."""
    try:
        out = int(value)
    except (TypeError, ValueError):
        return default
    if out < min_value:
        return min_value
    if out > max_value:
        return max_value
    return out


def _paginated_payload(items, total, page, page_size):
    """Build paginated response dict (count, page, page_size, results)."""
    return {
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': items,
    }


def _user_payload(u):
    """Build serializable user dict with profile, display_name, and groups."""
    try:
        profile = u.profile
    except Profile.DoesNotExist:
        profile = None
    language = profile.language if profile else 'zh-CN'
    timezone = profile.timezone if profile else 'Asia/Shanghai'
    display_name = (
        f'{u.first_name or ""} {u.last_name or ""}'.strip()
        if (getattr(u, 'first_name', None) or getattr(u, 'last_name', None))
        else (
            getattr(u, 'username', None)
            or getattr(u, 'email', None)
            or str(u.pk)
        )
    )
    ordered_groups = getattr(u, 'ordered_groups', None)
    if ordered_groups is None:
        ordered_groups = u.groups.all().order_by('name')
    groups = [{'id': g.pk, 'name': g.name} for g in ordered_groups]
    return {
        'id': u.pk,
        'username': (
            getattr(u, 'username', None)
            or getattr(u, 'email', None)
            or str(u.pk)
        ),
        'email': getattr(u, 'email', None) or '',
        'first_name': getattr(u, 'first_name', None) or '',
        'last_name': getattr(u, 'last_name', None) or '',
        'display_name': display_name,
        'is_staff': getattr(u, 'is_staff', False),
        'is_active': getattr(u, 'is_active', True),
        'date_joined': (
            u.date_joined.isoformat()
            if getattr(u, 'date_joined', None)
            else None
        ),
        'language': language,
        'timezone': timezone,
        'groups': groups,
    }


class ManagementUserListView(APIView):
    """
    GET: List all users for management console (with profile and groups).
    POST: Create user (username, email, password, is_staff, group_ids, etc).
    Admin-only.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        page = _safe_int(request.query_params.get('page'), default=1)
        page_size = _safe_int(
            request.query_params.get('page_size'),
            default=20,
        )
        groups_prefetch = Prefetch(
            'groups',
            queryset=Group.objects.order_by('name'),
            to_attr='ordered_groups',
        )
        qs = User.objects.select_related('profile').prefetch_related(
            groups_prefetch
        ).order_by('id')
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        items = [_user_payload(u) for u in qs[start:end]]
        return Response(_paginated_payload(items, total, page, page_size))

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        email = (request.data.get('email') or '').strip()
        password = request.data.get('password') or ''
        is_staff = bool(request.data.get('is_staff', False))
        group_ids = request.data.get('group_ids') or []
        if not isinstance(group_ids, list):
            group_ids = []
        language = (request.data.get('language') or '').strip() or 'zh-CN'
        timezone = (request.data.get('timezone') or '').strip() or 'Asia/Shanghai'

        if not username:
            return Response(
                {'detail': 'Username is required.', 'code': 'username_required'},
                status=HTTP_400_BAD_REQUEST
            )
        if not password:
            return Response(
                {'detail': 'Password is required.', 'code': 'password_required'},
                status=HTTP_400_BAD_REQUEST
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {
                    'detail': 'A user with that username already exists.',
                    'code': 'username_taken',
                },
                status=HTTP_400_BAD_REQUEST
            )
        if email and User.objects.filter(email=email).exists():
            return Response(
                {
                    'detail': 'A user with that email already exists.',
                    'code': 'email_taken',
                },
                status=HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=username,
            email=email or '',
            password=password,
        )
        if is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])
        if group_ids:
            valid_ids = list(
                Group.objects.filter(pk__in=group_ids).values_list(
                    'pk', flat=True
                )
            )
            if valid_ids:
                user.groups.set(valid_ids)
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            profile = None
        if profile is not None:
            profile.language = language
            profile.timezone = timezone
            profile.save(update_fields=['language', 'timezone'])
        return Response(_user_payload(user), status=HTTP_201_CREATED)


def _group_payload(g):
    return {
        'id': g.pk,
        'name': g.name,
        'user_count': getattr(g, 'user_count', g.user_set.count()),
        'permission_count': getattr(
            g,
            'permission_count',
            g.permissions.count(),
        ),
    }


class ManagementGroupListView(APIView):
    """
    GET: List all Django auth groups for management console.
    POST: Create a new group (name).
    Admin-only.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        page = _safe_int(request.query_params.get('page'), default=1)
        page_size = _safe_int(
            request.query_params.get('page_size'),
            default=20,
        )
        qs = Group.objects.annotate(
            user_count=Count('user', distinct=True),
            permission_count=Count('permissions', distinct=True),
        ).order_by('name')
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        items = [_group_payload(g) for g in qs[start:end]]
        return Response(_paginated_payload(items, total, page, page_size))

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response(
                {'detail': 'Group name is required.', 'code': 'name_required'},
                status=HTTP_400_BAD_REQUEST
            )
        if Group.objects.filter(name=name).exists():
            return Response(
                {
                    'detail': 'A group with that name already exists.',
                    'code': 'name_taken',
                },
                status=HTTP_400_BAD_REQUEST
            )
        group = Group.objects.create(name=name)
        return Response(_group_payload(group), status=HTTP_201_CREATED)
