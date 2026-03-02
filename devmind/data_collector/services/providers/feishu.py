"""
Feishu (Lark) approval provider. Placeholder implementation; collect/validate
will call Feishu API when implemented.
"""
from .base import BaseProvider


class FeishuProvider(BaseProvider):
    """
    Feishu approval data collection provider.
    """

    def authenticate(self, auth_config: dict) -> bool:
        """
        Verify Feishu app credentials (app_id, app_secret, etc.).
        """
        if not auth_config:
            return False
        return True

    def collect(
        self,
        auth_config: dict,
        start_time,
        end_time,
        user_id: int,
        platform: str,
        **kwargs,
    ) -> list[dict]:
        """
        Fetch Feishu approval instances in time range. Placeholder returns [].
        """
        return []

    def validate(
        self,
        auth_config: dict,
        start_time,
        end_time,
        user_id: int,
        platform: str,
        source_unique_ids: list[str],
    ) -> list[str]:
        """
        Return approval instance ids that no longer exist. Placeholder: [].
        """
        return []

    def fetch_attachments(self, auth_config: dict, raw_record) -> list[dict]:
        """
        Fetch attachments for a Feishu approval. Placeholder returns [].
        """
        return []
