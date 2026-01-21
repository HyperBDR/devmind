"""
Provider service for cloud billing.
"""
import logging
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ProviderService:
    """
    Service for managing cloud provider operations.
    """

    def __init__(self):
        """
        Initialize provider service.
        """
        self._setup_provider_imports()

    def _setup_provider_imports(self):
        """
        Setup imports for cloud_billings providers.
        Add cloud_billings to Python path if needed.
        """
        cloud_billings_path = '/home/ubuntu/workspace/devmind_workspace/cloud_billings'
        if cloud_billings_path not in sys.path:
            sys.path.insert(0, cloud_billings_path)

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
            from cloud_billings.clouds.service import ProviderFactory

            provider = ProviderFactory.create_provider(provider_type, config_dict)
            return provider
        except ImportError as e:
            logger.error(
                f"ProviderService.create_provider: Failed to import provider "
                f"factory (provider_type={provider_type}, error={str(e)})"
            )
            raise ValueError(f"Unsupported provider type: {provider_type}")
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
            from cloud_billings.clouds.service import BillingService

            billing_service = BillingService(provider_type, config_dict)
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
            Dictionary with validation result: {valid: bool, message: str, account_id: str}
        """
        try:
            provider = self.create_provider(provider_type, config_dict)

            is_valid = provider.validate_credentials()
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

            message = (
                'Credentials are valid' if is_valid
                else 'Invalid credentials'
            )
            return {
                'valid': is_valid,
                'message': message,
                'account_id': account_id,
            }
        except Exception as e:
            logger.error(
                f"ProviderService.validate_credentials: Failed to validate "
                f"credentials (provider_type={provider_type}, error={str(e)})"
            )
            return {
                'valid': False,
                'message': str(e),
                'account_id': '',
            }

    def get_account_id(self, provider_type: str, config_dict: Dict[str, Any]) -> str:
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
