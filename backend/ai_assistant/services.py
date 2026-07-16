"""Application services for assistant capabilities and authorization."""

from accounts.access import get_effective_feature_keys

from ai_assistant.registry import capability_registry
from ai_assistant.skills import skill_catalog


def user_can_access_capability(user, capability) -> bool:
    """Return whether the user can use one registered capability."""

    return capability.required_feature in set(
        get_effective_feature_keys(user)
    )


def list_capabilities_for_user(user) -> list[dict]:
    """Serialize enabled capabilities visible to the current user."""

    payload = []
    for capability in capability_registry.all():
        if not user_can_access_capability(user, capability):
            continue
        skills = skill_catalog.for_app(capability.app_key)
        profile = (
            capability.profile_loader()
            if capability.profile_loader is not None
            else {}
        )
        payload.append(
            {
                "app_key": capability.app_key,
                "display_name": capability.display_name,
                "description": capability.description,
                "icon": capability.icon,
                "version": capability.version,
                "skill_count": len(skills),
                "profile": profile,
            }
        )
    return payload


def authorized_app_keys(user) -> tuple[str, ...]:
    """Return registered app keys the current user may access."""

    return tuple(
        capability.app_key
        for capability in capability_registry.all()
        if user_can_access_capability(user, capability)
    )
