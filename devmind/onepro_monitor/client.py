import base64
import io
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from requests.exceptions import HTTPError

import requests
from PIL import Image, ImageFilter, ImageOps

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

try:
    import ddddocr
except Exception:  # pragma: no cover
    ddddocr = None


logger = logging.getLogger(__name__)
TESSERACT_CONFIG = "--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _response_detail(response):
    if response is None:
        return ""
    try:
        payload = response.json()
        return payload.get("title") or payload.get("message") or payload.get("detail") or ""
    except Exception:
        return (response.text or "").strip()[:500]


class OneProClient:
    def __init__(
        self,
        api_url,
        username,
        password,
        timeout=30,
        retry_count=3,
        retry_delay=2,
    ):
        self.api_url = api_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.token = None
        self.token_expires_at = 0
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "X-LANG": "zh",
                "X-SCENE": "system",
            }
        )

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _request(self, method, url, **kwargs):
        last_error = None
        for attempt in range(1, self.retry_count + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )
                response.raise_for_status()
                return response
            except HTTPError as exc:  # pragma: no cover - network failure
                detail = _response_detail(exc.response)
                message = str(exc)
                if detail:
                    message = f"{message} | detail: {detail}"
                last_error = HTTPError(message, response=exc.response)
                logger.warning(
                    "OnePro request failed %s/%s for %s: status=%s detail=%s",
                    attempt,
                    self.retry_count,
                    url,
                    getattr(exc.response, "status_code", "unknown"),
                    detail or "n/a",
                )
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
            except Exception as exc:  # pragma: no cover - network failure
                last_error = exc
                logger.warning("OnePro request failed %s/%s for %s: %s", attempt, self.retry_count, url, exc)
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
        raise last_error

    def _get_captcha(self):
        response = self._request("GET", f"{self.api_url}/api/v2/getImageCaptcha")
        payload = response.json()
        if payload.get("code") != "00000000":
            raise ValueError(payload.get("title") or "Failed to fetch captcha")
        data = payload.get("data") or {}
        return data.get("id") or "", data.get("data") or ""

    def _ocr_captcha(self, captcha_image):
        if not captcha_image:
            return ""
        if captcha_image.startswith("data:image/"):
            _, encoded = captcha_image.split(",", 1)
        else:
            encoded = captcha_image
        image_data = base64.b64decode(encoded)
        if not pytesseract and not ddddocr:  # pragma: no cover
            return ""
        image = Image.open(io.BytesIO(image_data))
        candidates = []

        candidates.extend(self._ddddocr_candidates(image_data, image))
        candidates.extend(self._tesseract_candidates(image))

        valid_codes = [code for code in candidates if 3 <= len(code) <= 4]
        if not valid_codes:
            logger.warning("Captcha OCR produced no valid candidates")
            return ""

        preferred_codes = [code for code in valid_codes if len(code) == 4] or valid_codes
        best_code = Counter(preferred_codes).most_common(1)[0][0]
        logger.info("Captcha OCR candidates=%s selected=%s", preferred_codes, best_code)
        return best_code

    def _ddddocr_candidates(self, image_data, image):
        if not ddddocr:  # pragma: no cover
            return []

        candidates = []
        try:
            ocr = ddddocr.DdddOcr(show_ad=False)
            variants = [image_data]

            gray_image = ImageOps.grayscale(image)
            gray_buffer = io.BytesIO()
            gray_image.save(gray_buffer, format="PNG")
            variants.append(gray_buffer.getvalue())

            resized_image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
            resized_buffer = io.BytesIO()
            resized_image.save(resized_buffer, format="PNG")
            variants.append(resized_buffer.getvalue())

            for threshold in (100, 120, 150, 180):
                binary_image = gray_image.point(lambda x: 255 if x > threshold else 0, "1")
                binary_buffer = io.BytesIO()
                binary_image.save(binary_buffer, format="PNG")
                variants.append(binary_buffer.getvalue())

            for variant in variants:
                code = self._clean_code(ocr.classification(variant))
                if code:
                    candidates.append(code)
        except Exception as exc:  # pragma: no cover - optional dependency/runtime behavior
            logger.warning("ddddocr captcha recognition failed: %s", exc)
        return candidates

    def _tesseract_candidates(self, image):
        if not pytesseract:  # pragma: no cover
            return []

        candidates = []
        variants = [image]
        gray_image = ImageOps.grayscale(image)
        variants.append(gray_image)
        variants.append(ImageOps.autocontrast(gray_image))
        variants.append(ImageOps.invert(gray_image))
        variants.append(gray_image.filter(ImageFilter.MedianFilter()))
        variants.append(image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS))

        base_gray = ImageOps.autocontrast(gray_image)
        for threshold in (100, 120, 150, 180):
            variants.append(base_gray.point(lambda x: 255 if x > threshold else 0, "1"))

        for variant in variants:
            try:
                code = self._clean_code(pytesseract.image_to_string(variant, config=TESSERACT_CONFIG))
                if code:
                    candidates.append(code)
            except OSError as exc:  # pragma: no cover - depends on runtime image
                raise RuntimeError(
                    "OnePro captcha OCR requires the 'tesseract-ocr' system package in the backend image."
                ) from exc
        return candidates

    def _clean_code(self, code):
        return "".join(ch for ch in str(code).upper().strip() if ch.isalnum())[:4]

    def login(self):
        last_error = None
        for attempt in range(1, self.retry_count + 1):
            try:
                captcha_id, captcha_image = self._get_captcha()
                captcha_code = self._ocr_captcha(captcha_image)
                if len(captcha_code) < 3:
                    raise ValueError("Captcha OCR failed")
                login_url = f"{self.api_url}/admin/api/v2/admin-login"
                response = self.session.post(
                    login_url,
                    timeout=self.timeout,
                    json={
                        "username": self.username,
                        "password": self.password,
                        "id": captcha_id,
                        "code": captcha_code,
                    },
                )
                payload = response.json()
                if response.status_code >= 400:
                    detail = payload.get("title") or payload.get("message") or response.text
                    raise HTTPError(
                        f"{response.status_code} Client Error for url: {login_url} | detail: {detail}",
                        response=response,
                    )
                if payload.get("code") != "00000000":
                    raise ValueError(payload.get("title") or "Login failed")
                token = (payload.get("data") or {}).get("token")
                if not token:
                    raise ValueError("Missing token in login response")
                self.token = token
                self.token_expires_at = time.time() + 3600
                self.session.headers["X-AUTH-TOKEN"] = token
                return token
            except Exception as exc:  # pragma: no cover - dependent on external service
                last_error = exc
                logger.warning("OnePro login failed %s/%s: %s", attempt, self.retry_count, exc)
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
        raise last_error

    def ensure_authenticated(self):
        if not self.token or time.time() >= self.token_expires_at:
            self.login()

    def _fetch(self, path, params=None):
        self.ensure_authenticated()
        response = self._request("GET", f"{self.api_url}{path}", params=params)
        payload = response.json()
        if payload.get("code") != "00000000":
            raise ValueError(payload.get("title") or f"Request failed for {path}")
        return payload

    def get_tenants(self, page=1, page_size=1000):
        return self._fetch(
            "/admin/api/v2/admin-getTenants",
            params={"page": page, "page_size": page_size},
        )

    def get_tenant_detail(self, enterprise_id):
        return self._fetch(
            "/admin/api/v2/admin-getTenantDetail",
            params={"enterprise_id": enterprise_id},
        )

    def get_tenant_licenses_statistics(self, enterprise_id, scene="dr", page=1, page_size=100):
        return self._fetch(
            "/admin/api/v2/admin-getTenantsLicensesStatistics",
            params={
                "enterprise_id": enterprise_id,
                "scene": scene,
                "page": page,
                "page_size": page_size,
            },
        )

    def get_tenant_licenses_details(self, enterprise_id, scene="dr", page=1, page_size=100):
        try:
            return self._fetch(
                "/admin/api/v2/admin-getLicenses",
                params={
                    "enterprise_id": enterprise_id,
                    "scene": scene,
                    "page": page,
                    "page_size": page_size,
                },
            )
        except Exception:
            return self.get_tenant_licenses_statistics(
                enterprise_id=enterprise_id,
                scene=scene,
                page=page,
                page_size=page_size,
            )

    def get_tenant_hosts(self, project_id, user_id, scene="dr", page=1, page_size=100):
        return self._fetch(
            "/admin/api/v2/admin-getTenantHosts",
            params={
                "project_id": project_id,
                "user_id": user_id,
                "scene": scene,
                "page": page,
                "page_size": page_size,
            },
        )


def parse_remote_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None
