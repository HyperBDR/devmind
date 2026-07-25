from types import SimpleNamespace
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase

from quotation.services.feishu_client import (
    FeishuClient,
    FeishuDownloadTooLargeError,
)


class FeishuClientDownloadTests(SimpleTestCase):
    def test_download_stops_when_content_exceeds_limit(self):
        settings = SimpleNamespace(feishu_base_url="https://feishu.test")
        client = FeishuClient(settings=settings)
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"oversized")
        )
        http_client = httpx.Client(transport=transport)

        with patch(
            "quotation.services.feishu_client.httpx.Client",
            return_value=http_client,
        ):
            with self.assertRaises(FeishuDownloadTooLargeError):
                client.download_file(
                    "access-token",
                    "file-token",
                    max_bytes=3,
                )
