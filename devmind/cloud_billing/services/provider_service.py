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
        
        if provider_type == 'aws':
            api_key = (config_dict.get('AWS_ACCESS_KEY_ID') or 
                      config_dict.get('aws_access_key_id') or 
                      config_dict.get('api_key'))
            api_secret = (config_dict.get('AWS_SECRET_ACCESS_KEY') or 
                         config_dict.get('aws_secret_access_key') or 
                         config_dict.get('api_secret'))
            region = (config_dict.get('AWS_REGION') or 
                     config_dict.get('aws_region') or 
                     config_dict.get('region'))
            
            if api_key:
                normalized['api_key'] = api_key
            if api_secret:
                normalized['api_secret'] = api_secret
            if region:
                normalized['region'] = region
        elif provider_type in ('huawei', 'huawei-intl'):
            api_key = (config_dict.get('HUAWEI_ACCESS_KEY_ID') or 
                      config_dict.get('huawei_access_key_id') or 
                      config_dict.get('api_key'))
            api_secret = (config_dict.get('HUAWEI_SECRET_ACCESS_KEY') or 
                         config_dict.get('huawei_secret_access_key') or 
                         config_dict.get('api_secret'))
            region = (config_dict.get('HUAWEI_REGION') or 
                     config_dict.get('huawei_region') or 
                     config_dict.get('region'))
            
            if api_key:
                normalized['api_key'] = api_key
            if api_secret:
                normalized['api_secret'] = api_secret
            if region:
                normalized['region'] = region
            
            project_id = (
                config_dict.get('HUAWEI_PROJECT_ID') or
                config_dict.get('project_id')
            )
            if project_id:
                normalized['project_id'] = project_id
            
            is_intl = (
                provider_type == 'huawei-intl' and
                config_dict.get('HUAWEI_IS_INTERNATIONAL')
            )
            if is_intl:
                normalized['is_international'] = True
        elif provider_type == 'azure':
            tenant_id = (config_dict.get('AZURE_TENANT_ID') or 
                        config_dict.get('azure_tenant_id') or 
                        config_dict.get('tenant_id'))
            client_id = (config_dict.get('AZURE_CLIENT_ID') or 
                        config_dict.get('azure_client_id') or 
                        config_dict.get('client_id'))
            client_secret = (config_dict.get('AZURE_CLIENT_SECRET') or 
                           config_dict.get('azure_client_secret') or 
                           config_dict.get('client_secret'))
            subscription_id = (config_dict.get('AZURE_SUBSCRIPTION_ID') or 
                              config_dict.get('azure_subscription_id') or 
                              config_dict.get('subscription_id'))
            
            if tenant_id:
                normalized['tenant_id'] = tenant_id
            if client_id:
                normalized['client_id'] = client_id
            if client_secret:
                normalized['client_secret'] = client_secret
            if subscription_id:
                normalized['subscription_id'] = subscription_id
        elif provider_type == 'alibaba':
            api_key = (config_dict.get('ALIBABA_ACCESS_KEY_ID') or 
                      config_dict.get('alibaba_access_key_id') or 
                      config_dict.get('api_key'))
            api_secret = (config_dict.get('ALIBABA_SECRET_ACCESS_KEY') or 
                         config_dict.get('alibaba_secret_access_key') or 
                         config_dict.get('api_secret'))
            region = (config_dict.get('ALIBABA_REGION') or 
                     config_dict.get('alibaba_region') or 
                     config_dict.get('region'))
            
            if api_key:
                normalized['api_key'] = api_key
            if api_secret:
                normalized['api_secret'] = api_secret
            if region:
                normalized['region'] = region
        else:
            # For unknown types, pass through as-is
            normalized = config_dict.copy()
        
        # Remove None and empty string values
        result = {
            k: v for k, v in normalized.items()
            if v is not None and v != ''
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
            config_dict = self._normalize_config(
                provider_type, config_dict
            )
            
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
        period: Optional[str] = None
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
            return result
        except Exception as e:
            logger.error(
                f"ProviderService.get_billing_info: Failed to get billing "
                f"info (provider_type={provider_type}, period={period}, "
                f"error={str(e)})"
            )
            raise

    def validate_credentials(
        self,
        provider_type: str,
        config_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate provider credentials.

        Args:
            provider_type: Provider type
            config_dict: Provider configuration

        Returns:
            Dictionary with validation result:
            {valid: bool, message: str, account_id: str}
        """
        try:
            # create_provider will normalize config automatically
            provider = self.create_provider(provider_type, config_dict)

            # Try to validate credentials and capture error details
            error_code = None
            try:
                is_valid = provider.validate_credentials()
                if not is_valid:
                    error_code = self._get_error_code(provider_type, None)
            except Exception as e:
                is_valid = False
                error_code = self._get_error_code(provider_type, str(e))

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

            return {
                'valid': is_valid,
                'error_code': error_code if not is_valid else None,
                'account_id': account_id,
            }
        except Exception as e:
            error_code = self._get_error_code(provider_type, str(e))
            
            logger.warning(
                f"ProviderService.validate_credentials: "
                f"Failed to validate credentials "
                f"(provider_type={provider_type}, error={str(e)})"
            )
            return {
                'valid': False,
                'error_code': error_code,
                'account_id': '',
            }

    def _get_error_code(
        self,
        provider_type: str,
        error_msg: Optional[str]
    ) -> str:
        """
        Extract error code from technical error messages.

        Args:
            provider_type: Type of cloud provider
            error_msg: Original error message (can be None)

        Returns:
            Error code that can be used for i18n translation
        """
        if not error_msg:
            return 'validation_failed'

        error_lower = error_msg.lower()

        # AWS specific errors
        if provider_type == 'aws':
            if 'invalidclienttokenid' in error_lower:
                return 'aws_invalid_access_key_id'
            elif 'signaturedoesnotmatch' in error_lower:
                return 'aws_invalid_secret_key'
            elif 'ssl' in error_lower or 'sslerror' in error_lower:
                return 'aws_ssl_error'
            elif 'access key' in error_lower:
                return 'aws_invalid_credentials'
            elif 'region' in error_lower:
                return 'aws_invalid_region'

        # Huawei specific errors
        elif provider_type == 'huawei':
            if 'ssl' in error_lower or 'sslerror' in error_lower:
                return 'huawei_ssl_error'
            elif 'access key' in error_lower or 'api_key' in error_lower:
                return 'huawei_invalid_credentials'
            elif 'region' in error_lower:
                return 'huawei_invalid_region'

        # Azure specific errors
        elif provider_type == 'azure':
            if ('authentication' in error_lower or
                    'unauthorized' in error_lower):
                return 'azure_invalid_authentication'
            elif 'subscription' in error_lower:
                return 'azure_invalid_subscription'

        # Alibaba specific errors
        elif provider_type == 'alibaba':
            if 'access key' in error_lower:
                return 'alibaba_invalid_credentials'
            elif 'region' in error_lower:
                return 'alibaba_invalid_region'

        # Generic errors
        if 'ssl' in error_lower or 'sslerror' in error_lower:
            return 'ssl_error'
        elif 'timeout' in error_lower:
            return 'timeout_error'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'network_error'

        # Default error code
        return 'validation_failed'

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
