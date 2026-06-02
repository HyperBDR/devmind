"""
Custom middleware for the core application.
"""
from django.conf import settings


class LanguageCodeMappingMiddleware:
    """
    Middleware to map browser language codes to Django language codes.

    Uses LANGUAGE_CODE_MAPPING from settings to dynamically map
    browser language codes (e.g., zh-CN) to Django language codes
    (e.g., zh-hans). This allows browsers to send various language
    code formats while Django uses standardized language codes.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.language_mapping = getattr(
            settings,
            "LANGUAGE_CODE_MAPPING",
            {},
        )

    def __call__(self, request):
        accept_language = request.META.get("HTTP_ACCEPT_LANGUAGE", "")

        if accept_language and self.language_mapping:
            parts = accept_language.split(",")
            first_part = parts[0].strip()
            first_lang = first_part.lower()
            first_lang = first_lang.split(";")[0].strip()

            mapped_lang = self.language_mapping.get(first_lang)
            if mapped_lang:
                quality_part = first_part.split(";", 1)
                if len(quality_part) > 1:
                    new_first_part = f"{mapped_lang};{quality_part[1]}"
                else:
                    new_first_part = mapped_lang

                remaining_parts = ",".join(parts[1:]) if len(parts) > 1 else ""
                new_accept_language = (
                    f"{new_first_part},{remaining_parts}".rstrip(",")
                )
                request.META["HTTP_ACCEPT_LANGUAGE"] = new_accept_language

        response = self.get_response(request)
        return response
