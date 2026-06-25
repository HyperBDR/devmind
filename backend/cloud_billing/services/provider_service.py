"""
Provider service for cloud billing.
"""

import logging
from typing import Any, Dict, Optional

from ..clouds.service import ProviderFactory, BillingService
from ..utils.logging import mask_sensitive_config

logger = logging.getLogger(__name__)


class ProviderService:
    """
    Service for managing cloud provider operations.
    """

    def _normalize_config(
        self, provider_type: str, config_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalize configuration dictionary to match backend config class
        field names.

        Args:
            provider_type: Provider type
            config_dict: Provider configuration with frontend field names

        Returns:
            Normalized configuration dictionary
        """
        sanitized_config = mask_sensitive_config(config_dict)
        logger.debug(
            f"Normalizing config for {provider_type}: {sanitized_config}"
        )
        normalized = {}

        if provider_type == "aws":
            api_key = (
                config_dict.get("AWS_ACCESS_KEY_ID")
                or config_dict.get("aws_access_key_id")
                or config_dict.get("api_key")
            )
            api_secret = (
                config_dict.get("AWS_SECRET_ACCESS_KEY")
                or config_dict.get("aws_secret_access_key")
                or config_dict.get("api_secret")
            )
            region = (
                config_dict.get("AWS_REGION")
                or config_dict.get("aws_region")
                or config_dict.get("region")
            )

            if api_key:
                normalized["api_key"] = api_key
            if api_secret:
                normalized["api_secret"] = api_secret
            if region:
                normalized["region"] = region
        elif provider_type in ("huawei", "huawei-intl"):
            api_key = (
                config_dict.get("HUAWEI_ACCESS_KEY_ID")
                or config_dict.get("huawei_access_key_id")
                or config_dict.get("api_key")
            )
            api_secret = (
                config_dict.get("HUAWEI_SECRET_ACCESS_KEY")
                or config_dict.get("huawei_secret_access_key")
                or config_dict.get("api_secret")
            )
            region = (
                config_dict.get("HUAWEI_REGION")
                or config_dict.get("huawei_region")
                or config_dict.get("region")
            )

            if api_key:
                normalized["api_key"] = api_key
            if api_secret:
                normalized["api_secret"] = api_secret
            if region:
                normalized["region"] = region

            project_id = config_dict.get(
                "HUAWEI_PROJECT_ID"
            ) or config_dict.get("project_id")
            if project_id:
                normalized["project_id"] = project_id

            is_intl = provider_type == "huawei-intl" and config_dict.get(
                "HUAWEI_IS_INTERNATIONAL"
            )
            if is_intl:
                normalized["is_international"] = True
        elif provider_type == "azure":
            tenant_id = (
                config_dict.get("AZURE_TENANT_ID")
                or config_dict.get("azure_tenant_id")
                or config_dict.get("tenant_id")
            )
            client_id = (
                config_dict.get("AZURE_CLIENT_ID")
                or config_dict.get("azure_client_id")
                or config_dict.get("client_id")
            )
            client_secret = (
                config_dict.get("AZURE_CLIENT_SECRET")
                or config_dict.get("azure_client_secret")
                or config_dict.get("client_secret")
            )
            subscription_id = (
                config_dict.get("AZURE_SUBSCRIPTION_ID")
                or config_dict.get("azure_subscription_id")
                or config_dict.get("subscription_id")
            )
            billing_account_id = (
                config_dict.get("AZURE_BILLING_ACCOUNT_ID")
                or config_dict.get("azure_billing_account_id")
                or config_dict.get("billing_account_id")
            )

            if tenant_id:
                normalized["tenant_id"] = tenant_id
            if client_id:
                normalized["client_id"] = client_id
            if client_secret:
                normalized["client_secret"] = client_secret
            if subscription_id:
                normalized["subscription_id"] = subscription_id
            if billing_account_id:
                normalized["billing_account_id"] = billing_account_id
        elif provider_type == "alibaba":
            api_key = (
                config_dict.get("ALIBABA_ACCESS_KEY_ID")
                or config_dict.get("alibaba_access_key_id")
                or config_dict.get("api_key")
            )
            api_secret = (
                config_dict.get("ALIBABA_SECRET_ACCESS_KEY")
                or config_dict.get("alibaba_secret_access_key")
                or config_dict.get("api_secret")
            )
            region = (
                config_dict.get("ALIBABA_REGION")
                or config_dict.get("alibaba_region")
                or config_dict.get("region")
            )

            if api_key:
                normalized["api_key"] = api_key
            if api_secret:
                normalized["api_secret"] = api_secret
            if region:
                normalized["region"] = region
        elif provider_type == "tencentcloud":
            access_key_id = config_dict.get(
                "TENCENT_ACCESS_KEY_ID"
            ) or config_dict.get("access_key_id")
            access_key_secret = config_dict.get(
                "TENCENT_ACCESS_KEY_SECRET"
            ) or config_dict.get("access_key_secret")
            app_id = config_dict.get("TENCENT_APP_ID") or config_dict.get(
                "app_id"
            )
            region = config_dict.get("TENCENT_REGION") or config_dict.get(
                "region"
            )
            endpoint = config_dict.get("TENCENT_ENDPOINT") or config_dict.get(
                "endpoint"
            )
            timeout = config_dict.get("TENCENT_TIMEOUT") or config_dict.get(
                "timeout"
            )
            max_retries = (
                config_dict.get("TENCENT_MAX_RETRIES")
                or config_dict.get("max_retries")
            )
            if access_key_id:
                normalized["access_key_id"] = access_key_id
            if access_key_secret:
                normalized["access_key_secret"] = access_key_secret
            if app_id:
                normalized["app_id"] = app_id
            if region:
                normalized["region"] = region
            if endpoint:
                normalized["endpoint"] = endpoint
            if timeout is not None and timeout != "":
                normalized["timeout"] = int(timeout)
            if max_retries is not None and max_retries != "":
                normalized["max_retries"] = int(max_retries)
        elif provider_type == "volcengine":
            access_key_id = (
                config_dict.get("VOLCENGINE_ACCESS_KEY_ID")
                or config_dict.get("volcengine_access_key_id")
                or config_dict.get("access_key_id")
                or config_dict.get("api_key")
            )
            access_key_secret = (
                config_dict.get("VOLCENGINE_SECRET_ACCESS_KEY")
                or config_dict.get("VOLCENGINE_ACCESS_KEY_SECRET")
                or config_dict.get("volcengine_secret_access_key")
                or config_dict.get("volcengine_access_key_secret")
                or config_dict.get("access_key_secret")
                or config_dict.get("api_secret")
            )
            region = (
                config_dict.get("VOLCENGINE_REGION")
                or config_dict.get("volcengine_region")
                or config_dict.get("region")
            )
            endpoint = config_dict.get(
                "VOLCENGINE_ENDPOINT"
            ) or config_dict.get("volcengine_endpoint")
            payer_id = (
                config_dict.get("VOLCENGINE_PAYER_ID")
                or config_dict.get("volcengine_payer_id")
                or config_dict.get("payer_id")
            )
            service = config_dict.get("VOLCENGINE_SERVICE") or config_dict.get(
                "volcengine_service"
            )
            version = config_dict.get("VOLCENGINE_VERSION") or config_dict.get(
                "volcengine_version"
            )
            if access_key_id:
                normalized["api_key"] = access_key_id
            if access_key_secret:
                normalized["api_secret"] = access_key_secret
            if region:
                normalized["region"] = region
            if endpoint:
                normalized["endpoint"] = endpoint
            if payer_id:
                normalized["payer_id"] = payer_id
            if service:
                normalized["service"] = service
            if version:
                normalized["version"] = version
        elif provider_type == "baidu":
            api_key = (
                config_dict.get("BAIDU_ACCESS_KEY_ID")
                or config_dict.get("baidu_access_key_id")
                or config_dict.get("api_key")
            )
            api_secret = (
                config_dict.get("BAIDU_SECRET_ACCESS_KEY")
                or config_dict.get("baidu_secret_access_key")
                or config_dict.get("api_secret")
            )
            timeout = (
                config_dict.get("BAIDU_TIMEOUT")
                or config_dict.get("timeout")
            )
            max_retries = (
                config_dict.get("BAIDU_MAX_RETRIES")
                or config_dict.get("max_retries")
            )

            if api_key:
                normalized["api_key"] = api_key
            if api_secret:
                normalized["api_secret"] = api_secret
            if timeout is not None and timeout != "":
                normalized["timeout"] = int(timeout)
            if max_retries is not None and max_retries != "":
                normalized["max_retries"] = int(max_retries)
        elif provider_type == "zhipu":
            username = (
                config_dict.get("ZHIPU_USERNAME")
                or config_dict.get("zhipu_username")
                or config_dict.get("username")
            )
            password = (
                config_dict.get("ZHIPU_PASSWORD")
                or config_dict.get("zhipu_password")
                or config_dict.get("password")
            )
            user_type = (
                config_dict.get("ZHIPU_USER_TYPE")
                or config_dict.get("zhipu_user_type")
                or config_dict.get("user_type")
            )
            timeout = (
                config_dict.get("ZHIPU_TIMEOUT")
                or config_dict.get("timeout")
            )
            max_retries = (
                config_dict.get("ZHIPU_MAX_RETRIES")
                or config_dict.get("max_retries")
            )
            if username:
                normalized["username"] = username
            if password:
                normalized["password"] = password
            if user_type:
                normalized["user_type"] = user_type
            if timeout is not None and timeout != "":
                normalized["timeout"] = int(timeout)
            if max_retries is not None and max_retries != "":
                normalized["max_retries"] = int(max_retries)
        else:
            # For unknown types, pass through as-is
            normalized = config_dict.copy()

        # Remove None and empty string values
        result = {
            k: v for k, v in normalized.items() if v is not None and v != ""
        }
        sanitized_result = mask_sensitive_config(result)
        logger.debug(
            f"Normalized config for {provider_type}: {sanitized_result}"
        )
        return result

    def create_provider(self, provider_type: str, config_dict: Dict[str, Any]):
        """
        Create a cloud provider instance.

        Args:
            provider_type: Provider type (aws, huawei, alibaba, azure)
            config_dict: Provider configuration dictionary

        Returns:
            Provider instance
        """
        try:
            # Always normalize config field names to ensure consistency
            # This handles both frontend field names (AWS_ACCESS_KEY_ID)
            # and backend field names (api_key)
            config_dict = self._normalize_config(provider_type, config_dict)

            provider = ProviderFactory.create_provider(
                provider_type, config_dict
            )
            return provider
        except Exception as e:
            logger.error(
                f"ProviderService.create_provider: Failed to create provider "
                f"(provider_type={provider_type}, error={str(e)})"
            )
            raise

    def get_billing_info(
        self,
        provider_type: str,
        config_dict: Dict[str, Any],
        period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get billing information for a provider.

        Args:
            provider_type: Provider type
            config_dict: Provider configuration
            period: Billing period in YYYY-MM format

        Returns:
            Dictionary with billing information
        """
        try:
            # Normalize config field names if needed
            normalized_config = self._normalize_config(
                provider_type, config_dict
            )
            billing_service = BillingService(provider_type, normalized_config)
            result = billing_service.get_billing_info(period=period)
            error_msg = result.get("error")
            if result.get("status") == "error" and error_msg:
                classification = self._classify_error(
                    provider_type, str(error_msg)
                )
                error_type = classification.get("error_type")
                result["error_code"] = classification.get("error_code")
                result["required_permissions"] = classification.get(
                    "required_permissions", []
                )
                if error_type == "permission_error":
                    result["is_permission_error"] = True
                elif error_type == "service_error":
                    result["is_api_error"] = True
            return result
        except ValueError as e:
            # Configuration errors should not be reported as system errors
            # to Sentry - they indicate missing/invalid configuration
            error_msg = str(e)
            logger.warning(
                f"ProviderService.get_billing_info: Configuration error "
                f"(provider_type={provider_type}, period={period}, "
                f"error={error_msg})"
            )
            return {
                "status": "config_error",
                "data": None,
                "error": error_msg,
                "is_config_error": True,
            }
        except Exception as e:
            logger.error(
                f"ProviderService.get_billing_info: Failed to get billing "
                f"info (provider_type={provider_type}, period={period}, "
                f"error={str(e)})"
            )
            raise

    def validate_credentials(
        self, provider_type: str, config_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate provider credentials and permissions.

        Args:
            provider_type: Provider type
            config_dict: Provider configuration

        Returns:
            Dictionary with validation result:
            {
                valid: bool,
                message: str,
                account_id: str,
                error_type: str,
                required_permissions: List[str]
            }
        """
        try:
            # create_provider will normalize config automatically
            provider = self.create_provider(provider_type, config_dict)

            # Try to validate credentials and capture error details
            error_message = None
            error_classification = None
            try:
                is_valid = provider.validate_credentials()
                if not is_valid:
                    error_classification = self._classify_error(provider_type, None)
            except Exception as e:
                is_valid = False
                error_message = str(e)
                error_classification = self._classify_error(
                    provider_type, error_message
                )

            account_id = ""

            if is_valid:
                try:
                    account_id = provider.get_account_id()
                    logger.info(
                        f"ProviderService.validate_credentials: "
                        f"Credentials validated successfully "
                        f"(provider_type={provider_type}, "
                        f"account_id={account_id})"
                    )
                except Exception as e:
                    logger.warning(
                        f"ProviderService.validate_credentials: Failed to "
                        f"get account ID (provider_type={provider_type}, "
                        f"error={str(e)})"
                    )

            if not is_valid and error_classification is None:
                error_classification = self._classify_error(
                    provider_type, error_message
                )

            classification = error_classification if not is_valid else None
            result = {
                "valid": is_valid,
                "error_code": (
                    classification["error_code"] if classification else None
                ),
                "account_id": account_id,
                "error_type": (
                    classification["error_type"] if classification else None
                ),
                "required_permissions": (
                    classification["required_permissions"]
                    if classification
                    else []
                ),
            }
            if error_message and not is_valid:
                result["message"] = error_message
            return result
        except Exception as e:
            error_message = str(e)
            error_classification = self._classify_error(provider_type, error_message)

            logger.warning(
                f"ProviderService.validate_credentials: "
                f"Failed to validate credentials "
                f"(provider_type={provider_type}, error={error_message})"
            )
            return {
                "valid": False,
                "error_code": error_classification["error_code"],
                "account_id": "",
                "message": error_message,
                "error_type": error_classification["error_type"],
                "required_permissions": error_classification["required_permissions"],
            }

    def _classify_error(
        self, provider_type: str, error_msg: Optional[str]
    ) -> Dict[str, Any]:
        """
        Classify error into credential, permission, or service error.

        Args:
            provider_type: Type of cloud provider
            error_msg: Original error message (can be None)

        Returns:
            Dictionary with error classification:
            {error_code: str, error_type: str, required_permissions: List[str]}
        """
        if not error_msg:
            return {
                "error_code": "validation_failed",
                "error_type": "service_error",
                "required_permissions": [],
            }

        error_lower = error_msg.lower()

        # AWS specific errors
        if provider_type == "aws":
            if "invalidclienttokenid" in error_lower:
                return {
                    "error_code": "aws_invalid_access_key_id",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "signaturedoesnotmatch" in error_lower:
                return {
                    "error_code": "aws_invalid_secret_key",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "ssl" in error_lower or "sslerror" in error_lower:
                return {
                    "error_code": "aws_ssl_error",
                    "error_type": "service_error",
                    "required_permissions": [],
                }
            elif "access key" in error_lower:
                return {
                    "error_code": "aws_invalid_credentials",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "region" in error_lower:
                return {
                    "error_code": "aws_invalid_region",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "accessdenied" in error_lower:
                return {
                    "error_code": "aws_cost_explorer_permission_denied",
                    "error_type": "permission_error",
                    "required_permissions": ["ce:GetCostAndUsage"],
                }

        # Huawei specific errors
        elif provider_type == "huawei":
            if "ssl" in error_lower or "sslerror" in error_lower:
                return {
                    "error_code": "huawei_ssl_error",
                    "error_type": "service_error",
                    "required_permissions": [],
                }
            elif "access key" in error_lower or "api_key" in error_lower:
                return {
                    "error_code": "huawei_invalid_credentials",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "region" in error_lower:
                return {
                    "error_code": "huawei_invalid_region",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif (
                "cbc.0151" in error_lower
                or "access denied" in error_lower
                or (
                    "permission" in error_lower
                    and ("denied" in error_lower or "required" in error_lower)
                )
            ):
                return {
                    "error_code": "huawei_bss_permission_denied",
                    "error_type": "permission_error",
                    "required_permissions": ["bss:bill:read", "bss:account:read"],
                }

        # Huawei International specific errors
        elif provider_type == "huawei-intl":
            if "ssl" in error_lower or "sslerror" in error_lower:
                return {
                    "error_code": "huawei_intl_ssl_error",
                    "error_type": "service_error",
                    "required_permissions": [],
                }
            elif "access key" in error_lower or "api_key" in error_lower:
                return {
                    "error_code": "huawei_intl_invalid_credentials",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif (
                "cbc.0151" in error_lower
                or "access denied" in error_lower
                or (
                    "permission" in error_lower
                    and ("denied" in error_lower or "required" in error_lower)
                )
            ):
                return {
                    "error_code": "huawei_intl_bss_permission_denied",
                    "error_type": "permission_error",
                    "required_permissions": [
                        "BSS Intl Billing Service access"
                    ],
                }

        # Azure specific errors
        elif provider_type == "azure":
            if "authentication" in error_lower or "unauthorized" in error_lower:
                return {
                    "error_code": "azure_invalid_authentication",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "subscription" in error_lower:
                return {
                    "error_code": "azure_invalid_subscription",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "permission" in error_lower or "forbidden" in error_lower:
                return {
                    "error_code": "azure_consumption_permission_denied",
                    "error_type": "permission_error",
                    "required_permissions": [
                        "Microsoft.Consumption/read",
                        "Microsoft.Billing/billingAccounts/read",
                    ],
                }

        # Alibaba specific errors
        elif provider_type == "alibaba":
            if "getcalleridentity" in error_lower or "sts:getcalleridentity" in error_lower:
                return {
                    "error_code": "alibaba_need_sts_get_caller_identity",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if "access key" in error_lower:
                return {
                    "error_code": "alibaba_invalid_credentials",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "region" in error_lower:
                return {
                    "error_code": "alibaba_invalid_region",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            elif "permission" in error_lower or "forbidden" in error_lower:
                return {
                    "error_code": "alibaba_bss_permission_denied",
                    "error_type": "permission_error",
                    "required_permissions": ["bss:ReadOnlyAccess"],
                }

        # Tencent Cloud specific errors
        elif provider_type == "tencentcloud":
            # Check more specific patterns first (unauthorizedoperation vs unauthorized)
            if (
                "unauthorizedoperation" in error_lower
                or ("cam" in error_lower and "permission" in error_lower)
                or ("no permission" in error_lower)
            ):
                return {
                    "error_code": "tencentcloud_billing_permission_denied",
                    "error_type": "permission_error",
                    "required_permissions": ["QcloudBillingReadOnlyAccess"],
                }
            if "auth" in error_lower or "signatureexpire" in error_lower:
                return {
                    "error_code": "tencentcloud_invalid_credentials",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if "secret" in error_lower or "signature" in error_lower:
                return {
                    "error_code": "tencentcloud_invalid_secret",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if "permission" in error_lower or "forbidden" in error_lower:
                return {
                    "error_code": "tencentcloud_no_permission",
                    "error_type": "permission_error",
                    "required_permissions": [],
                }

        # Volcengine specific errors
        elif provider_type == "volcengine":
            if "unauthorized" in error_lower or "access denied" in error_lower:
                return {
                    "error_code": "volcengine_invalid_credentials",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if "signature" in error_lower or "authorization" in error_lower:
                return {
                    "error_code": "volcengine_invalid_secret",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if (
                "rate limit" in error_lower
                or "throttl" in error_lower
                or "429" in error_lower
            ):
                return {
                    "error_code": "volcengine_rate_limit",
                    "error_type": "service_error",
                    "required_permissions": [],
                }
            if "timeout" in error_lower:
                return {
                    "error_code": "volcengine_timeout",
                    "error_type": "service_error",
                    "required_permissions": [],
                }
            if "permission" in error_lower or "forbidden" in error_lower:
                return {
                    "error_code": "volcengine_billing_permission_denied",
                    "error_type": "permission_error",
                    "required_permissions": ["费用中心访问权限"],
                }

        # Baidu specific errors
        elif provider_type == "baidu":
            if "signature" in error_lower or "authorization" in error_lower:
                return {
                    "error_code": "baidu_invalid_secret",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if "access key" in error_lower or "ak" in error_lower:
                return {
                    "error_code": "baidu_invalid_credentials",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if "permission" in error_lower or "forbidden" in error_lower:
                return {
                    "error_code": "baidu_billing_permission_denied",
                    "error_type": "permission_error",
                    "required_permissions": ["财务服务访问权限"],
                }
        elif provider_type == "zhipu":
            if "password" in error_lower or "username" in error_lower:
                return {
                    "error_code": "zhipu_invalid_credentials",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if "token" in error_lower or "authorization" in error_lower:
                return {
                    "error_code": "zhipu_invalid_token",
                    "error_type": "credential_error",
                    "required_permissions": [],
                }
            if "permission" in error_lower or "forbidden" in error_lower:
                return {
                    "error_code": "zhipu_no_permission",
                    "error_type": "permission_error",
                    "required_permissions": [],
                }

        # Generic errors
        if "ssl" in error_lower or "sslerror" in error_lower:
            return {
                "error_code": "ssl_error",
                "error_type": "service_error",
                "required_permissions": [],
            }
        elif "timeout" in error_lower:
            return {
                "error_code": "timeout_error",
                "error_type": "service_error",
                "required_permissions": [],
            }
        elif "connection" in error_lower or "network" in error_lower:
            return {
                "error_code": "network_error",
                "error_type": "service_error",
                "required_permissions": [],
            }

        # Default error code
        return {
            "error_code": "validation_failed",
            "error_type": "service_error",
            "required_permissions": [],
        }

    def _get_error_code(
        self, provider_type: str, error_msg: Optional[str]
    ) -> str:
        """
        Extract error code from technical error messages.

        Args:
            provider_type: Type of cloud provider
            error_msg: Original error message (can be None)

        Returns:
            Error code that can be used for i18n translation
        """
        classification = self._classify_error(provider_type, error_msg)
        return classification["error_code"]

    def get_account_id(
        self, provider_type: str, config_dict: Dict[str, Any]
    ) -> str:
        """
        Get account ID for a provider.

        Args:
            provider_type: Provider type
            config_dict: Provider configuration

        Returns:
            Account ID string
        """
        try:
            provider = self.create_provider(provider_type, config_dict)
            return provider.get_account_id()
        except Exception as e:
            logger.error(
                f"ProviderService.get_account_id: Failed to get account ID "
                f"(provider_type={provider_type}, error={str(e)})"
            )
            raise
