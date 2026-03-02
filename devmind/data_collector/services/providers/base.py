"""
Base provider interface for platform data collection.
All platform drivers must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """
    Abstract base for platform providers. Implement authenticate, collect,
    validate, fetch_attachments per platform.
    """

    @abstractmethod
    def authenticate(self, auth_config: dict) -> bool:
        """
        Verify credentials / auth config. Return True if valid.
        """
        pass

    @abstractmethod
    def collect(
        self,
        auth_config: dict,
        start_time: Any,
        end_time: Any,
        user_id: int,
        platform: str,
        **kwargs: Any,
    ) -> list[dict]:
        """
        Collect raw data from platform for the given time range.
        Return list of dicts with keys: source_unique_id, raw_data,
        filter_metadata, data_hash, source_created_at, source_updated_at.
        kwargs may contain driver-specific options (e.g. project_keys).
        """
        pass

    @abstractmethod
    def validate(
        self,
        auth_config: dict,
        start_time: Any,
        end_time: Any,
        user_id: int,
        platform: str,
        source_unique_ids: list[str],
    ) -> list[str]:
        """
        Check which source_unique_ids still exist on platform.
        Return list of ids that no longer exist (should be marked is_deleted).
        """
        pass

    @abstractmethod
    def fetch_attachments(
        self,
        auth_config: dict,
        raw_record: Any,
    ) -> list[dict]:
        """
        Fetch attachments for a raw record. Return list of dicts with
        source_file_id, file_name, file_content or file_url, file_type,
        file_size, file_md5, source_created_at, source_updated_at.
        """
        pass

    def download_attachment_content(
        self,
        auth_config: dict,
        attachment_meta: dict,
    ) -> bytes | None:
        """
        Download attachment file content. Return bytes or None.
        attachment_meta from fetch_attachments (file_url, file_name).
        """
        return None
