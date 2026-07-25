from types import SimpleNamespace

from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from quotation.models import (
    DocumentAsset,
    EXPORT_ARCHIVE_SYNC_STAGE,
    ExportJobStatus,
    Quotation,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.services.storage import delete_documents_after_commit
from quotation.services.storage_control import (
    delete_owned_replicas_after_commit,
)


ACTIVE_EXPORT_STATUSES = {
    ExportJobStatus.QUEUED,
    ExportJobStatus.RENDERING_EXCEL,
    ExportJobStatus.CONVERTING_PDF,
    ExportJobStatus.RENDERED,
    ExportJobStatus.UPLOAD_QUEUED,
    ExportJobStatus.UPLOADING,
}
ACTIVE_UPLOAD_STATUSES = {
    SyncJobStatus.QUEUED,
    SyncJobStatus.RUNNING,
    SyncJobStatus.RETRYING,
}


@receiver(pre_delete, sender=Quotation)
def prepare_quotation_artifact_cleanup(
    sender,
    instance: Quotation,
    using,
    **kwargs,
) -> None:
    """Block active exports and clean artifacts for every deletion path."""
    locked = (
        sender.objects.using(using)
        .select_for_update()
        .filter(pk=instance.pk)
        .first()
    )
    if locked is None:
        return
    active_jobs = list(
        locked.export_jobs.filter(status__in=ACTIVE_EXPORT_STATUSES)
    )
    active_uploads = list(
        SyncJob.objects.using(using).filter(
            quotation=locked,
            job_type=SyncJobType.UPLOAD,
            stage=EXPORT_ARCHIVE_SYNC_STAGE,
            status__in=ACTIVE_UPLOAD_STATUSES,
        )
    )
    protected_objects = [*active_jobs, *active_uploads]
    if protected_objects:
        raise ProtectedError(
            "Quotation has active export jobs",
            protected_objects,
        )


@receiver(pre_delete, sender=DocumentAsset)
def prepare_document_artifact_cleanup(
    sender,
    instance: DocumentAsset,
    using,
    **kwargs,
) -> None:
    """Clean local and remote artifacts for every document deletion path."""
    references = list(instance.replicas.all())
    if instance.feishu_file_token:
        references.append(
            SimpleNamespace(
                connection_id=None,
                remote_file_token=instance.feishu_file_token,
                metadata={"remote_file_owned": False},
            )
        )
    delete_owned_replicas_after_commit(references)
    delete_documents_after_commit([instance.storage_key])
