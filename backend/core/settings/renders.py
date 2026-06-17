"""
This module provides custom renderers for standardizing API response formats.
It includes a CustomJSONRenderer that ensures all API responses follow a
consistent structure with code, message and data fields.

The renderer also extends the standard JSON encoder so common non-native
types (``Decimal``, ``datetime``, ``date``, ``UUID``, ``bytes``) are
serialized automatically. Without this, DRF raises
``TypeError: Object of type Decimal is not JSON serializable`` whenever a
view returns ORM data containing money columns (see Sentry TOWER-39).
"""

import datetime
import decimal
import uuid
from json import JSONEncoder

from rest_framework.renderers import JSONRenderer
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.utils import json

from .constants import SUCCESS_MESSAGE, FAILED_MESSAGE, SUCCESS_CODE


class StandardJSONEncoder(JSONEncoder):
    """
    JSON encoder that gracefully handles common non-native scalar types
    produced by Django/DRF views (Decimal prices, UUID PKs, date/datetime
    fields, raw bytes from binary fields).
    """

    def default(self, obj):  # noqa: D401 - JSONEncoder API
        if isinstance(obj, decimal.Decimal):
            # Quantize-less str() preserves precision; callers that need
            # numeric output can pre-cast in their serializer.
            return str(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (bytes, bytearray)):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return obj.hex()
        return super().default(obj)


class CustomJSONRenderer(JSONRenderer):
    """
    A custom JSON renderer that standardizes API response format.

    This renderer is primarily used for JWT authentication-related responses
    (login, refresh token, etc.) since custom views already handle the
    response format internally.

    The standardized format is:
    {
        # 0 for success, HTTP status code for errors
        "code": int,
        # "success" or "failed"
        "message": str,
        # Original response data
        "data": dict
    }

    The renderer handles three cases:
    1. Response already has correct format (code, message, data)
    2. Response has code/message but no data (will restructure other fields)
    3. Response has none of the required fields (will create standard format)

    Example success response:
    {
        "code": 0,
        "message": "success",
        "data": {
            "access": "jwt_token_here",
            "refresh": "refresh_token_here"
        }
    }

    Example error response:
    {
        "code": 401,
        "message": "failed",
        "data": {
            "detail": "Invalid credentials"
        }
    }
    """
    def render(
        self,
        data,
        accepted_media_type=None,
        renderer_context=None
    ):
        if renderer_context is None:
            return super().render(data, accepted_media_type,
                                  renderer_context)

        response = renderer_context.get('response')
        is_success = (status.HTTP_200_OK <= response.status_code <
                     status.HTTP_300_MULTIPLE_CHOICES)

        # Ensure data is a dictionary
        if not isinstance(data, dict):
            data = {'data': data}

        # Extract code and message from the response
        code = data.get('code', SUCCESS_CODE if is_success else
                        response.status_code)
        message = data.get('message',
                           SUCCESS_MESSAGE if is_success else
                           FAILED_MESSAGE)

        formatted_data = {
            'code': code,
            'message': message,
            'data': data.get('data', data)
        }

        return json.dumps(
            formatted_data,
            cls=StandardJSONEncoder,
            ensure_ascii=not api_settings.UNICODE_JSON,
            allow_nan=not api_settings.STRICT_JSON,
        ).encode()