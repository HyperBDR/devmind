# DevMind MCP OAuth

DevMind exposes a read-only MCP HTTP resource at `/mcp` and provides OAuth
Authorization Code with PKCE (`S256`) and Dynamic Client Registration (DCR).
Each user signs into DevMind and approves the client. MCP tools use that
DevMind user's existing permissions. OAuth clients supply their own redirect
URIs during registration; DevMind validates and stores them.

OAuth URLs come from deployment configuration, never from the incoming HTTP
`Host` header. The authorization endpoint and consent page are browser-facing.
Issuer discovery, registration, token, revocation, and MCP resource endpoints
must be reachable by the MCP client service. Those addresses may differ in a
split local Docker setup.

## Invoice responsibility searches

Invoice handler and sales owner are equivalent search aliases. Use the
`search_invoices.salesperson` argument for either name: the backend matches
the full name against `contact_person` OR `sales_owner`, ignoring case and
surrounding input whitespace. It does not match partial names. REST invoice
filters `invoice_contact`, `salesperson`, and `sales_owner` use the same rule.
Date, customer, and other filters still apply together with the user's
existing visibility scope. An invoice matching both fields is counted once.
The MCP response marks `responsibility_fields_equivalent: true`; its `total`
applies to both aliases even when an original responsibility field is empty.

## Query summaries and incomplete PDF searches

For invoice lists and monthly summaries, call `search_invoices` with
`summary=true` and `limit=20`. This returns up to 20 compact records per
page instead of full invoice details and line items. Follow the returned
`limit`, `offset`, and `has_more` for pagination, then call `get_invoice`
only when full details are needed. The default `summary=false` preserves
the existing one-record-per-page response, including line items.

Structured searches include `query_context`, which describes the applied
date filter and the authorized user's visibility scope. A successful
`result_status=complete` with `total=0` means no matching visible records;
do not retry alternate date formats or widen the date range just to confirm
that empty result. `result_status=invalid_date` is distinct from a valid
empty search.

PDF searches retain available matches and return `search_complete=false`
when some authorized documents cannot be searched. Inspect
`unavailable_document_count` and `unavailable_documents` for file-missing,
unreadable PDF, or OCR failure/timeout reasons. The document sample is
limited to 20 entries; `unavailable_documents_truncated` indicates that
more entries were omitted. Empty results from an incomplete search do not
prove the absence of matching content. Valid cached text remains searchable
when the original file is unavailable. Search does not download or restore
missing files; storage reconciliation is a separate operation.

## Read-only robot credentials

### Automatic quotation salesperson matching

Quotation ownership compares the full DevMind username with the full
quotation sales name, ignoring case, surrounding spaces and differences
between dots and spaces. For example, `evelyn.chee` matches `Evelyn Chee`.
No additional administrator configuration or database migration is needed.
Both the quotation API and MCP `salesperson` filter use this normalization.
Partial names do not establish ownership.

Before granting normalized ownership, DevMind checks all other accounts,
including inactive accounts. If another username normalizes to the same
identity, automatic ownership is disabled; existing exact ownership and
explicit administrator grants still apply. Profile display names and
self-edited real names do not grant quotation access.

This applies to quotation lists, dashboards, details, documents and MCP.
Existing creation/upload permissions, explicit grants and robot tokens
remain effective. Invoice access rules are unchanged.

MCP administrators can issue a robot credential for clients that need a
fixed, read-only identity instead of a browser OAuth login. The credential
is bound to an active DevMind account. MCP queries still apply that account's
current quotation or invoice permissions, and the credential's module scopes
further restrict which read tools it can call.

Use an active DevMind service account with only the required module access as
the robot principal. This is a service identity, not an individual user's
delegated login.

Only authenticated DevMind staff can manage credentials:

- `GET /api/v1/mcp/robots/` lists credential metadata, never token values.
- `POST /api/v1/mcp/robots/` creates a credential and returns its token once.
- `DELETE /api/v1/mcp/robots/<credential-id>/` revokes it immediately.

Create a quotation-only robot credential with:

```json
{
  "name": "Quotation reader",
  "user_id": 123,
  "scopes": ["quotation:read"],
  "expires_in_days": 90
}
```

Use `invoice:read` for an invoice-only credential, or include both module
scopes when the same robot needs both. The lifetime defaults to 90 days and
can be set from 1 to 365 days. The returned value is a bearer token; store it
in the MCP client's secret configuration and send it as
`Authorization: Bearer <token>`. DevMind stores only a SHA-256 digest, and the
raw token is never returned by list or revoke operations.

To rotate a token, create a replacement credential, update the MCP client's
secret, then revoke the old credential. MCP robot credentials are read-only;
they cannot invoke write operations.

## Endpoints

With issuer `https://devmind.example.com/` and resource
`https://devmind.example.com/mcp`:

- MCP endpoint: `https://devmind.example.com/mcp`
- Protected Resource Metadata (resource path):
  `https://devmind.example.com/.well-known/oauth-protected-resource/mcp`
- Protected Resource Metadata (origin alias):
  `https://devmind.example.com/.well-known/oauth-protected-resource`
- Authorization Server Metadata:
  `https://devmind.example.com/.well-known/oauth-authorization-server`
- DCR: `/register`
- Authorization: `/authorize`
- Token: `/token`
- Revocation: `/revoke`
- Consent page: `/oauth/mcp/authorize`

The standard metadata path is derived from the Issuer. For an Issuer with a
path, the Authorization Server Metadata route follows RFC 8414's well-known
path construction. The protected-resource path metadata remains derived from
the configured resource URI.

## Production configuration

MCP configuration is generated automatically at startup, including during
normal image-based upgrades. Existing deployments do not need to add MCP
variables to `.env`, and startup does not rewrite the file.

With `DJANGO_DEBUG=false`, the default origin is derived from `SITE_DOMAIN`,
then `FRONTEND_URL`. Localhost and example domains are skipped. If neither
provides a usable host, the hosted DevMind default is
`https://tower.oneprocloud.com`. Inferred origins always use HTTPS, and all
endpoint paths and allowed hosts are generated from them. Existing explicit
MCP values take precedence; empty values use the generated defaults.

Other installations can reuse their existing site configuration or set
`MCP_OAUTH_CLIENT_BASE_URL` and `MCP_OAUTH_BROWSER_BASE_URL`. For deployments
with separate public endpoints, individual overrides remain supported:

```env
MCP_OAUTH_ISSUER_URL=https://devmind.example.com/
MCP_OAUTH_RESOURCE_URL=https://devmind.example.com/mcp
MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL=https://devmind.example.com/authorize
MCP_OAUTH_TOKEN_ENDPOINT_URL=https://devmind.example.com/token
MCP_OAUTH_REGISTRATION_ENDPOINT_URL=https://devmind.example.com/register
MCP_OAUTH_REVOCATION_ENDPOINT_URL=https://devmind.example.com/revoke
MCP_OAUTH_CONSENT_URL=https://devmind.example.com/oauth/mcp/authorize
MCP_OAUTH_SCOPES=mcp:read
```

Production startup rejects HTTP OAuth URLs. Nginx must proxy `/mcp`, OAuth
endpoints, and `/.well-known/` to the backend. It must route the consent page
to the frontend. Allowed hosts are derived from the effective endpoint URLs
unless `MCP_ALLOWED_HOSTS` is explicitly set; custom lists must include the API
host. Generated allowlists include both the bare hostname and its `:*`
port pattern: production Nginx forwards a bare Host, while direct clients may
include a port. IPv6 addresses retain square brackets in both forms.

## Local Docker configuration

The browser uses `localhost`; a client running in another Docker container
uses the host-published DevMind port through `host.docker.internal`. Do not
put the container-only hostname in `MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL` or
`MCP_OAUTH_CONSENT_URL`.

```env
MCP_OAUTH_ISSUER_URL=http://host.docker.internal:18000/
MCP_OAUTH_RESOURCE_URL=http://host.docker.internal:18000/mcp
MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL=http://localhost:18000/authorize
MCP_OAUTH_TOKEN_ENDPOINT_URL=http://host.docker.internal:18000/token
MCP_OAUTH_REGISTRATION_ENDPOINT_URL=http://host.docker.internal:18000/register
MCP_OAUTH_REVOCATION_ENDPOINT_URL=http://host.docker.internal:18000/revoke
MCP_OAUTH_CONSENT_URL=http://localhost:18000/oauth/mcp/authorize
MCP_OAUTH_SCOPES=mcp:read
```

These HTTP URLs are accepted only with `DJANGO_DEBUG=true`. From the host
browser, open the OAuth metadata and authorization URLs using `localhost`.
From the MCP client container, open the Issuer metadata, registration, token,
and MCP resource URLs using `host.docker.internal`. If the client shares the
DevMind Docker network, its service name and container port can be used for
the client-facing URLs instead.

## Metadata examples

Authorization Server Metadata:

```json
{
  "issuer": "https://devmind.example.com/",
  "authorization_endpoint": "https://devmind.example.com/authorize",
  "token_endpoint": "https://devmind.example.com/token",
  "registration_endpoint": "https://devmind.example.com/register",
  "revocation_endpoint": "https://devmind.example.com/revoke",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256"],
  "token_endpoint_auth_methods_supported": [
    "client_secret_basic",
    "client_secret_post",
    "none"
  ],
  "scopes_supported": ["mcp:read"]
}
```

Protected Resource Metadata for `/mcp`:

```json
{
  "resource": "https://devmind.example.com/mcp",
  "authorization_servers": ["https://devmind.example.com/"],
  "scopes_supported": ["mcp:read"],
  "resource_name": "DevMind MCP"
}
```

Currently `mcp:read` is the implemented scope. Startup rejects unsupported
scope configuration instead of advertising permissions that tools do not
enforce. Tokens are opaque, stored by digest, issuer-bound, resource-bound,
short-lived, and authorized against the user's DevMind permissions on each
request. Refresh tokens rotate on use. No OAuth signing key or per-client
account mapping is required.

Run the normal Django migrations during deployment. MCP has one initial
replacement migration that creates the six final models directly, without
creating obsolete external-identity mapping tables.

The replacement declares the previous MCP migrations `0001` through `0008`
in `replaces`. Environments that already applied all eight keep their tables,
OAuth clients, and robot credentials; Django recognizes the completed chain
without recreating tables. Do not delete migration records, drop tables, or
use `--fake` for this upgrade.

Before upgrading an existing development environment, inspect
`python manage.py showmigrations mcp_server` using its previous checkout.
Only a fresh environment or a fully completed `0001`–`0008` chain is supported
by this replacement. If only part of the old chain was applied, stop and
complete that chain on the previous version first; its `0005` must remove the
redundant `RemoveField(user)` operation before the whole mapping table is
deleted. Back up the database before that repair. Do not deploy this
replacement over a partially applied chain.
