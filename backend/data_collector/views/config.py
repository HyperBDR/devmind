"""
CollectorConfig ViewSet: CRUD with atomic Beat sync. User-scoped; uuid in URLs.
"""
from typing import Optional

from django.db import transaction
from django.db.utils import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import CollectorConfig
from ..serializers import (
    CollectorConfigListSerializer,
    CollectorConfigSerializer,
)
from agentcore_task.adapters.django import TaskStatus, register_task_execution

from ..services.beat_sync import sync_config_to_beat, unsync_config_from_beat
from ..services.providers import get_provider
from ..tasks import run_collect, run_validate


HYPERBDR_PLATFORM = "hyperbdr"
HYPERBDR_DEFAULT_TIMEOUT = 30
HYPERBDR_DEFAULT_RETRY_COUNT = 3
HYPERBDR_DEFAULT_RETRY_DELAY = 2
HYPERBDR_DEFAULT_COLLECT_INTERVAL = 7200


def _is_hyperbdr_config(config: CollectorConfig) -> bool:
    return getattr(config, "platform", "") == HYPERBDR_PLATFORM


def _get_hyperbdr_data_source_model():
    from hyperbdr_dashboard.models import DataSource

    return DataSource


def _get_hyperbdr_collection_task_model():
    from hyperbdr_dashboard.models import CollectionTask

    return CollectionTask


def _get_hyperbdr_collection_runner():
    from hyperbdr_dashboard.tasks import run_collection_for_data_source

    return run_collection_for_data_source


def _get_hyperbdr_auth(config: CollectorConfig) -> dict:
    value = getattr(config, "value", None) or {}
    auth = value.get("auth") or {}
    return {
        "base_url": (value.get("base_url") or auth.get("base_url") or "").strip(),
        "username": (auth.get("username") or "").strip(),
        "password": auth.get("password") or "",
    }


def _unsync_hyperbdr_data_source(config: CollectorConfig) -> None:
    if not _is_hyperbdr_config(config):
        return
    data_source_model = _get_hyperbdr_data_source_model()
    data_source_model.objects.filter(name=config.key).delete()


def _sync_hyperbdr_data_source(
    config: CollectorConfig,
    previous_config: Optional[CollectorConfig] = None,
) -> None:
    if previous_config and _is_hyperbdr_config(previous_config):
        key_changed = previous_config.key != config.key
        platform_changed = previous_config.platform != config.platform
        if key_changed or platform_changed:
            _unsync_hyperbdr_data_source(previous_config)

    if not _is_hyperbdr_config(config):
        return

    auth = _get_hyperbdr_auth(config)
    data_source_model = _get_hyperbdr_data_source_model()
    data_source_model.objects.update_or_create(
        name=config.key,
        defaults={
            "api_url": auth["base_url"].rstrip("/"),
            "username": auth["username"],
            "password": auth["password"],
            "is_active": config.is_enabled,
            "api_timeout": HYPERBDR_DEFAULT_TIMEOUT,
            "api_retry_count": HYPERBDR_DEFAULT_RETRY_COUNT,
            "api_retry_delay": HYPERBDR_DEFAULT_RETRY_DELAY,
            "collect_interval": HYPERBDR_DEFAULT_COLLECT_INTERVAL,
        },
    )


def _queue_hyperbdr_collect(config: CollectorConfig):
    data_source_model = _get_hyperbdr_data_source_model()
    collection_task_model = _get_hyperbdr_collection_task_model()
    runner = _get_hyperbdr_collection_runner()

    data_source = data_source_model.objects.get(name=config.key)
    task = collection_task_model.objects.create(
        data_source=data_source,
        status=collection_task_model.STATUS_PENDING,
        start_time=timezone.now(),
        trigger_mode="manual",
    )
    celery_task = runner.delay(data_source.id, task.id, "manual")
    task.celery_task_id = celery_task.id
    task.save(update_fields=["celery_task_id", "updated_at"])
    return task, celery_task


def _sync_ai_pricehub_collect_config(config: CollectorConfig) -> None:
    if config.platform != "ai_pricehub":
        return
    try:
        from ai_pricehub.source_config_store import (
            list_primary_source_configs,
            set_primary_source_configs,
        )
    except Exception as exc:
        raise ValidationError(
            {
                "value": (
                    "AI PriceHub source config store is unavailable: "
                    f"{exc}"
                )
            }
        ) from exc

    value = config.value or {}
    value["project_keys"] = value.get("project_keys") or ["sync"]
    incoming_sources = value.get("primary_sources")
    if isinstance(incoming_sources, list) and incoming_sources:
        try:
            value["primary_sources"] = set_primary_source_configs(
                incoming_sources,
                owner_user=config.user,
            )
        except Exception as exc:
            raise ValidationError(
                {
                    "value": (
                        "Failed to persist AI PriceHub primary sources: "
                        f"{exc}"
                    )
                }
            ) from exc
    else:
        try:
            value["primary_sources"] = list_primary_source_configs()
        except Exception as exc:
            raise ValidationError(
                {
                    "value": (
                        "Failed to load AI PriceHub primary sources: "
                        f"{exc}"
                    )
                }
            ) from exc
    config.value = value
    config.save(update_fields=["value", "updated_at"])


@extend_schema_view(
    list=extend_schema(
        tags=["data-collector"],
        summary="List collector configs",
        description="List configs for the current user (one per platform).",
    ),
    retrieve=extend_schema(
        tags=["data-collector"],
        summary="Get collector config",
        description="Get config by uuid.",
    ),
    create=extend_schema(
        tags=["data-collector"],
        summary="Create collector config",
        description="Create a config and register Beat tasks atomically.",
    ),
    update=extend_schema(
        tags=["data-collector"],
        summary="Update collector config",
        description="Update config and Beat; version for optimistic lock.",
    ),
    partial_update=extend_schema(
        tags=["data-collector"],
        summary="Partial update collector config",
    ),
    destroy=extend_schema(
        tags=["data-collector"],
        summary="Delete collector config",
        description="Delete config and remove Beat tasks.",
    ),
)
class CollectorConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CollectorConfig. User-scoped; uuid in URLs.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        return CollectorConfig.objects.filter(user=self.request.user).order_by(
            "platform"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CollectorConfigListSerializer
        return CollectorConfigSerializer

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user)
                config = serializer.instance
                _sync_ai_pricehub_collect_config(config)
                sync_config_to_beat(config)
                _sync_hyperbdr_data_source(config)
        except IntegrityError as e:
            err_str = str(e).lower()
            const_uniq = "data_collector_config_user_platform_uniq"
            uniq_violation = const_uniq in str(e)
            if uniq_violation or "unique" in err_str:
                raise ValidationError(
                    {
                        "platform": (
                            "A collector config already exists for this "
                            "platform; only one config per platform is allowed."
                        )
                    }
                )
            raise

    def perform_update(self, serializer):
        with transaction.atomic():
            previous_config = CollectorConfig.objects.get(pk=serializer.instance.pk)
            serializer.save()
            config = serializer.instance
            _sync_ai_pricehub_collect_config(config)
            sync_config_to_beat(config)
            _sync_hyperbdr_data_source(config, previous_config=previous_config)

    def perform_destroy(self, instance):
        with transaction.atomic():
            unsync_config_from_beat(instance)
            _unsync_hyperbdr_data_source(instance)
            instance.delete()

    @extend_schema(
        tags=["data-collector"],
        summary="Trigger collect once",
        description=(
            "Register task then queue collect. Optional: start_time, end_time "
            "(ISO8601). Range must not exceed 3 months."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Start of collect range (ISO8601).",
                    },
                    "end_time": {
                        "type": "string",
                        "format": "date-time",
                        "description": "End of collect range (ISO8601).",
                    },
                },
            }
        },
    )
    @action(detail=True, methods=["post"])
    def collect(self, request, uuid=None):
        config = get_object_or_404(
            CollectorConfig, uuid=uuid, user=request.user
        )
        config_uuid_str = str(config.uuid)
        if _is_hyperbdr_config(config):
            _sync_hyperbdr_data_source(config)
            hyperbdr_task, celery_task = _queue_hyperbdr_collect(config)
            register_task_execution(
                task_id=celery_task.id,
                task_name="hyperbdr_dashboard.tasks.run_collection_for_data_source",
                module="data_collector",
                task_kwargs={
                    "data_source_id": hyperbdr_task.data_source_id,
                    "hyperbdr_collection_task_id": hyperbdr_task.id,
                    "trigger_mode": "manual",
                },
                created_by=request.user,
                metadata={
                    "config_uuid": config_uuid_str,
                    "config_platform": config.platform,
                    "config_key": config.key,
                    "hyperbdr_collection_task_id": hyperbdr_task.id,
                },
                initial_status=TaskStatus.PENDING,
            )
            return Response(
                {"task_id": celery_task.id, "message": "Collect task queued."},
                status=status.HTTP_202_ACCEPTED,
            )
        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")
        if start_time is not None or end_time is not None:
            if not start_time or not end_time:
                raise ValidationError(
                    "start_time and end_time must be provided together."
                )
            start_dt = parse_datetime(start_time)
            end_dt = parse_datetime(end_time)
            if start_dt is None or end_dt is None:
                raise ValidationError(
                    "start_time and end_time must be valid ISO8601 datetime."
                )
            if start_dt.tzinfo is None:
                start_dt = timezone.make_aware(start_dt)
            if end_dt.tzinfo is None:
                end_dt = timezone.make_aware(end_dt)
            if start_dt >= end_dt:
                raise ValidationError("start_time must be before end_time.")
            delta = end_dt - start_dt
            max_days = 30 if config.platform == "feishu" else 90
            if delta.days > max_days:
                if config.platform == "feishu":
                    raise ValidationError(
                        "Collect range for Feishu must not exceed 30 days."
                    )
                raise ValidationError(
                    "Collect range must not exceed 3 months (90 days)."
                )
        task_kwargs = {"config_uuid": config_uuid_str}
        if start_time is not None and end_time is not None:
            task_kwargs["start_time"] = start_time
            task_kwargs["end_time"] = end_time
        task = run_collect.delay(**task_kwargs)
        register_task_execution(
            task_id=task.id,
            task_name="data_collector.tasks.run_collect",
            module="data_collector",
            task_kwargs=task_kwargs,
            created_by=request.user,
            metadata={
                "config_uuid": config_uuid_str,
                "config_platform": config.platform,
                "config_key": config.key,
            },
            initial_status=TaskStatus.PENDING,
        )
        return Response(
            {"task_id": task.id, "message": "Collect task queued."},
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        tags=["data-collector"],
        summary="Validate config payload (no save)",
        description="Validate platform + value (before create).",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "value": {"type": "object"},
                },
                "required": ["platform", "value"],
            }
        },
    )
    @action(detail=False, methods=["post"], url_path="validate-config")
    def validate_config_payload(self, request):
        platform = request.data.get("platform")
        value = request.data.get("value")
        if not platform:
            return Response(
                {"valid": False, "message": "platform is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if value is None:
            return Response(
                {"valid": False, "message": "value is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        auth_config = value.get("auth") or {}
        base_url = value.get("base_url") or auth_config.get("base_url")
        if base_url:
            auth_config = {**auth_config, "base_url": base_url}
        provider_cls = get_provider(platform)
        if not provider_cls:
            return Response(
                {"valid": False, "message": "Unknown platform."},
                status=status.HTTP_200_OK,
            )
        try:
            provider = provider_cls()
            valid = provider.authenticate(auth_config)
            msg = "Connection OK." if valid else "Authentication failed."
            return Response(
                {"valid": valid, "message": msg},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"valid": False, "message": str(e)},
                status=status.HTTP_200_OK,
            )

    @extend_schema(
        tags=["data-collector"],
        summary="Fetch projects (step 2: after auth validated)",
        description=(
            "Requires platform and value with auth. "
            "Returns list of projects to select for sync."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "value": {"type": "object"},
                },
                "required": ["platform", "value"],
            }
        },
    )
    @action(detail=False, methods=["post"], url_path="fetch-projects")
    def fetch_projects(self, request):
        platform = request.data.get("platform")
        value = request.data.get("value")
        config_uuid = request.data.get("config_uuid")
        if not platform:
            return Response(
                {"detail": "platform is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if config_uuid:
            config = get_object_or_404(
                CollectorConfig, uuid=config_uuid, user=request.user
            )
            value = config.value or {}
        if value is None:
            return Response(
                {"detail": "value is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        auth_config = value.get("auth") or {}
        base_url = value.get("base_url") or auth_config.get("base_url")
        if base_url:
            auth_config = {**auth_config, "base_url": base_url}
        provider_cls = get_provider(platform)
        if not provider_cls:
            return Response(
                {"detail": "Unknown platform."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            provider = provider_cls()
            list_projects = getattr(provider, "list_projects", None)
            if not callable(list_projects):
                return Response(
                    {"projects": []},
                    status=status.HTTP_200_OK,
                )
            projects = list_projects(auth_config)
            return Response({"projects": projects}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        tags=["data-collector"],
        summary="Validate existing config (test connection)",
        description="Test credentials for an existing config by uuid.",
    )
    @action(detail=True, methods=["post"], url_path="validate-config")
    def validate_config(self, request, uuid=None):
        config = get_object_or_404(
            CollectorConfig, uuid=uuid, user=request.user
        )
        value = config.value or {}
        auth_config = value.get("auth") or {}
        base_url = value.get("base_url") or auth_config.get("base_url")
        if base_url:
            auth_config = {**auth_config, "base_url": base_url}
        provider_cls = get_provider(config.platform)
        if not provider_cls:
            return Response(
                {"valid": False, "message": "Unknown platform."},
                status=status.HTTP_200_OK,
            )
        try:
            provider = provider_cls()
            valid = provider.authenticate(auth_config)
            msg = "Connection OK." if valid else "Authentication failed."
            return Response(
                {"valid": valid, "message": msg},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"valid": False, "message": str(e)},
                status=status.HTTP_200_OK,
            )

    @extend_schema(
        tags=["data-collector"],
        summary="Validate data",
        description=(
            "Validate records in time range; "
            "mark missing on platform as is_deleted."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "string", "format": "date-time"},
                    "end_time": {"type": "string", "format": "date-time"},
                },
                "required": ["start_time", "end_time"],
            }
        },
    )
    @action(detail=True, methods=["post"])
    def validate(self, request, uuid=None):
        config = get_object_or_404(
            CollectorConfig, uuid=uuid, user=request.user
        )
        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")
        if not start_time or not end_time:
            return Response(
                {"detail": "start_time and end_time are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        task = run_validate.delay(
            config_uuid=str(config.uuid),
            start_time=start_time,
            end_time=end_time,
        )
        return Response(
            {"task_id": task.id, "message": "Validate task queued."},
            status=status.HTTP_202_ACCEPTED,
        )
