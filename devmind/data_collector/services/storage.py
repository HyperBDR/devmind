"""
Attachment storage under DATA_COLLECTOR_ROOT/raw_data/{raw_record_uuid}/.
Disk path uses UUIDs only; original name/type in DB.
"""
import os

from ..conf import get_data_collector_root
from ..models import RawDataRecord


def get_raw_data_attachment_dir(raw_record: RawDataRecord) -> str:
    """
    Return absolute directory path for a raw record's attachments.
    """
    root = get_data_collector_root()
    sub = os.path.join(root, "raw_data")
    uid = str(raw_record.uuid)
    return os.path.join(sub, uid)


def attachment_file_path(
    raw_record: RawDataRecord, attachment_uuid: str
) -> str:
    """
    Return absolute file path for an attachment. UUID only, no original name.
    Path: {root}/raw_data/{rec_uuid}/{att_uuid}.
    """
    dir_path = get_raw_data_attachment_dir(raw_record)
    uid = str(attachment_uuid)
    return os.path.join(dir_path, uid)


def attachment_file_url(
    raw_record: RawDataRecord, attachment_uuid: str
) -> str:
    """
    Return HTTP URL path for an attachment (/media/storage/data_collector/...).
    UUID only; download API sends file_name from DB as Content-Disposition.
    """
    base = "/media/storage/data_collector/raw_data"
    return f"{base}/{raw_record.uuid}/{attachment_uuid}"


def ensure_attachment_dir(raw_record: RawDataRecord) -> str:
    """
    Ensure directory for raw record's attachments exists; return dir path.
    """
    dir_path = get_raw_data_attachment_dir(raw_record)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path
