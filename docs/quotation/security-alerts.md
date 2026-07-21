# Quote Desk security alert runbooks

These runbooks apply to the low-cardinality security rules emitted by Quote
Desk. Never paste credentials, tokens, full third-party responses, or document
content into an alert resolution note.

## repeated_access_denials

Confirm the actor and request IDs, review the requested resource types, and
revoke active sessions if the activity was not expected.

## unusual_bulk_downloads

Confirm the business reason for the downloads and review the affected document
IDs through the Audit Log. Escalate unexplained activity to the security owner.

## object_id_enumeration

Review distinct missing object IDs and source IP evidence. Revoke the session
when the pattern is not an approved integration.

## configuration_change

Confirm that the connection, mount, or catalog change was approved. For a mount
change, run a health check before allowing new synchronization jobs.

## credential_refresh_failure

Check the managed connection status. Rotate credentials through the backend
configuration and verify the configured root folder before re-enabling jobs.

## sync_failure_backlog

Inspect the linked SyncJob and DocumentReplica records, verify connection
health, and retry only after the stable error code has been addressed.

## repeated_feishu_access_failures

Verify the connection and configured folder permissions. Use request and trace
IDs to locate sanitized external-call logs.

## new_device_sensitive_action

Confirm the device with the affected user and review the related activity
before resolving the alert.
