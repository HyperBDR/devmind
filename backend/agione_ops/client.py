"""Built-in synthetic source with no transport or credential support."""

from datetime import timedelta

from django.conf import settings
from rest_framework.exceptions import APIException

SYNTHETIC_TENANT_ID = "synthetic-basic-tenant"
CUSTOMER_IDS = ("90071992547409931", "90071992547409932")
MODEL_IDS = ("synthetic-model-a", "synthetic-model-b")
PAGE_SIZE = 2
MAX_PAGES = 100


class AgioneOpsError(APIException):
    """Expose only stable domain codes and safe diagnostic messages."""

    def __init__(self, code, message=None, status_code=400, retryable=False):
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message or code, code=code)


def require_synthetic_enabled(connection=None):
    """Fail closed unless this process explicitly enables synthetic mode."""

    if connection is not None and connection.source_kind == "demo_snapshot":
        raise AgioneOpsError("DEMO_SNAPSHOT_READ_ONLY", status_code=403)
    if getattr(settings, "AGIONE_OPS_SYNTHETIC_ENABLED", False) is not True:
        raise AgioneOpsError("SYNTHETIC_DISABLED", status_code=403)
    if connection is not None:
        if connection.source_kind != "synthetic":
            raise AgioneOpsError("SOURCE_KIND_FORBIDDEN", status_code=403)
        if connection.endpoint:
            raise AgioneOpsError("REAL_SOURCE_FORBIDDEN", status_code=403)
        if connection.credential_ciphertext:
            raise AgioneOpsError("REAL_CREDENTIALS_FORBIDDEN", status_code=403)


def get_client(connection):
    """Return an allowlisted in-process fixture, never an HTTP client."""

    require_synthetic_enabled(connection)
    if connection.synthetic_fixture != "basic":
        raise AgioneOpsError("FIXTURE_NOT_SUPPORTED")
    return SyntheticClient(connection)


class SyntheticClient:
    """Generate a tiny deterministic source for one explicit query window."""

    def __init__(self, connection):
        self.platform = connection.platform
        self.principal_kind = connection.principal_kind

    def identity(self):
        """Return fixture identity independently of configured expectations."""

        return {
            "tenant_id": SYNTHETIC_TENANT_ID,
            "platform": self.platform,
            "principal_kind": self.principal_kind,
        }

    def customers(self):
        """Return the complete synthetic authorized customer directory."""

        return [{"id": value} for value in CUSTOMER_IDS]

    def models(self):
        """Return the complete synthetic model directory."""

        return [{"id": value} for value in MODEL_IDS]

    def page_calls(self, window_start, window_end, page):
        """Return bounded pages including one quarantined unknown customer."""

        duration = int((window_end - window_start).total_seconds())
        template = [
            (CUSTOMER_IDS[0], MODEL_IDS[0], "success", 100, 40),
            (CUSTOMER_IDS[0], MODEL_IDS[0], "failure", 0, 0),
            (CUSTOMER_IDS[1], MODEL_IDS[1], "unknown", None, 3),
            (CUSTOMER_IDS[1], MODEL_IDS[1], "success", 30, None),
            ("synthetic-unauthorized", MODEL_IDS[0], "success", 999, 999),
        ]
        rows = []
        for index, (customer, model, status, input_, output) in enumerate(
            template
        ):
            rows.append(
                {
                    "upstream_record_id": str(90071992547410000 + index),
                    "occurred_at": window_start
                    + timedelta(seconds=(duration * index) // len(template)),
                    "customer_id": customer,
                    "model_id": model,
                    "status": status,
                    "input_tokens": input_,
                    "output_tokens": output,
                }
            )
        offset = (page - 1) * PAGE_SIZE
        items = rows[offset : offset + PAGE_SIZE]
        return {
            "identity": self.identity(),
            "page": page,
            "items": items,
            "total": len(rows),
            "next_page": page + 1 if offset + len(items) < len(rows) else None,
        }
