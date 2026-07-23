# Feishu storage control-plane rollout

This rollout is additive. Legacy `DocumentAsset.feishu_file_token`, URLs, local
temporary files, and configured directory paths remain unchanged until the new
route has been verified.

## 1. Plan

Run the command without a mode to report legacy assets:

```bash
python manage.py migrate_feishu_control_plane
```

## 2. Apply mappings

```bash
python manage.py migrate_feishu_control_plane --apply
```

The command creates one legacy connection and mount, then maps existing remote
files to `DocumentReplica`. It does not delete or rewrite legacy fields.

## 3. Verify

- Run the connection health check from Django Admin.
- Compare replica counts with legacy assets that have a file token.
- Verify Excel and PDF trusted links.
- Test one upload, download, export, and replica retry.
- Confirm request and trace IDs in Audit Log and external-call logs.

## 4. Enable gradually

Enable database routing first and replica creation separately:

```text
QUOTATION_STORAGE_ROUTER_ENABLED=true
QUOTATION_DOCUMENT_REPLICA_ENABLED=false
```

After routing is stable, enable replica creation for the test environment.

## 5. Roll back

Disable both flags, then remove only rows created by the migration marker:

```bash
python manage.py migrate_feishu_control_plane --rollback
```

Legacy document fields and temporary files remain available throughout the
rollback.
