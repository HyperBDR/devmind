"""Bound snapshot storage batches and authenticate each batch on read."""

import re
from contextlib import closing
from itertools import islice

from django.core.exceptions import ValidationError

from agione_ops.native_analytics import parse_time
from agione_ops.native_sync_models import NativeSnapshotChunk


BATCH_SIZE = 1000


def valid_chunk_reference(entry):
    """Accept a checksum, optionally followed by indexed time bounds."""
    if isinstance(entry, list):
        if len(entry) != 3:
            return False
        checksum, first, last = entry
        if parse_time(first) > parse_time(last):
            return False
    else:
        checksum = entry
    return isinstance(checksum, str) and bool(
        re.fullmatch(r"[0-9a-f]{64}", checksum)
    )


def write_chunks(version, metadata, rows):
    from agione_ops.native_sync import digest

    manifest = dict(metadata, rows=[], chunkDigests=[])
    with closing(rows):
        while batch := list(islice(rows, BATCH_SIZE)):
            index = len(manifest["chunkDigests"])
            NativeSnapshotChunk.objects.create(
                version=version, position=index, rows=batch,
            )
            times = [parse_time(row["occurred_at"]) for row in batch]
            manifest["chunkDigests"].append([
                digest(batch), min(times).isoformat(), max(times).isoformat(),
            ])
    return manifest


def snapshot_rows(snapshot, start=None, end=None):
    if "chunkDigests" not in snapshot.data:
        return snapshot.data["rows"]
    return _chunk_rows(snapshot, start, end)


def _chunk_rows(snapshot, start, end):
    from agione_ops.native_sync import digest

    data = snapshot.data
    hashes = data["chunkDigests"]
    if digest(data) != snapshot.content_digest:
        raise ValidationError("Invalid snapshot manifest.")
    positions = [
        i for i, entry in enumerate(hashes)
        if isinstance(entry, str) or (
            (start is None or parse_time(entry[2]) >= start)
            and (end is None or parse_time(entry[1]) < end)
        )
    ]
    chunks = NativeSnapshotChunk.objects.filter(
        version_id=snapshot.pk, position__in=positions,
    ).order_by("position").values_list("position", "rows")
    expected = iter(positions)
    for pos, batch in chunks.iterator(chunk_size=1):
        entry = hashes[pos]
        checksum = entry if isinstance(entry, str) else entry[0]
        if pos != next(expected, None) or digest(batch) != checksum:
            raise ValidationError("Invalid snapshot chunk.")
        times = [parse_time(row["occurred_at"]) for row in batch]
        if not isinstance(entry, str) and (
            not times or min(times) != parse_time(entry[1])
            or max(times) != parse_time(entry[2])
        ):
            raise ValidationError("Invalid snapshot chunk interval.")
        yield from batch
    if next(expected, None) is not None:
        raise ValidationError("Incomplete snapshot chunks.")


def validate_manifest(snapshot, run, version):
    from agione_ops.native_sync import digest, validate_snapshot_data

    validate_snapshot_data(snapshot.data, snapshot.content_digest)
    header = dict(snapshot.data)
    header.pop("chunkDigests")
    if (header["metadata"]["configVersion"] != run.config_version
            or header["metadata"]["credentialVersion"] != run.credential_version
            or not run.native_state.directory_complete
            or run.native_shards.exclude(status__in=["succeeded", "split"]).exists()):
        raise ValidationError("Invalid publication state.")

    rows = snapshot_rows(snapshot)
    staged = run.native_staging.order_by(
        "occurred_at", "record_id",
    ).values_list("record_id", "content_digest").iterator(chunk_size=BATCH_SIZE)
    count = 0
    while batch := list(islice(rows, BATCH_SIZE)):
        if any(next(staged, None) != (row["record_id"], digest(row))
               for row in batch):
            raise ValidationError("Snapshot differs from collected records.")
        sample = dict(header, rows=batch)
        validate_snapshot_data(sample, digest(sample))
        if any(not version.window_start <= parse_time(x["occurred_at"])
               < version.window_end for x in batch):
            raise ValidationError("Snapshot row outside version window.")
        count += len(batch)
    if count != run.native_staging.count():
        raise ValidationError("Incomplete snapshot.")
