"""
Logging utilities for cloud billing module.
"""


def mask_sensitive_config(config_dict):
    """
    Mask sensitive information in configuration dictionary.

    Masks sensitive values like API keys, secrets, passwords, etc.
    by showing only first 4 characters followed by ***.

    Args:
        config_dict: Configuration dictionary to mask

    Returns:
        Configuration dictionary with sensitive values masked
    """
    if not config_dict or not isinstance(config_dict, dict):
        return config_dict

    # Sensitive keys to mask (case-insensitive)
    sensitive_keys = {
        'api_key', 'api_secret', 'secret_key', 'secret_access_key',
        'access_key_id', 'access_key', 'api_secret_key',
        'client_secret', 'client_id', 'tenant_id',
        'password', 'passwd', 'pwd',
        'token', 'access_token', 'refresh_token',
        'private_key', 'private_key_id',
        'aws_access_key_id', 'aws_secret_access_key',
        'huawei_access_key_id', 'huawei_secret_access_key',
        'azure_client_secret', 'azure_subscription_key',
        'alibaba_access_key_id', 'alibaba_access_key_secret',
    }

    sanitized = {}
    for key, value in config_dict.items():
        # Check if key contains any sensitive keyword
        key_lower = key.lower()
        is_sensitive = any(
            sensitive_key in key_lower
            for sensitive_key in sensitive_keys
        )

        if is_sensitive and value:
            # Mask sensitive values
            if isinstance(value, str) and len(value) > 4:
                sanitized[key] = f"{value[:4]}***"
            else:
                sanitized[key] = "***"
        else:
            sanitized[key] = value

    return sanitized


def mask_sensitive_config_object(config_obj):
    """
    Mask sensitive information in configuration object.

    Converts configuration object to dictionary and masks sensitive
    values like API keys, secrets, passwords, etc.

    Args:
        config_obj: Configuration object (dataclass or similar)

    Returns:
        Dictionary representation with sensitive fields masked
    """
    if config_obj is None:
        return None

    # Convert object to dict if it's a dataclass or has __dict__
    if hasattr(config_obj, '__dict__'):
        config_dict = config_obj.__dict__
    elif hasattr(config_obj, '__dataclass_fields__'):
        # It's a dataclass
        config_dict = {
            field: getattr(config_obj, field, None)
            for field in config_obj.__dataclass_fields__
        }
    else:
        return str(config_obj)

    return mask_sensitive_config(config_dict)
