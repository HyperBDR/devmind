"""
Langfuse observability configuration.

Doc: https://langfuse.com/docs
"""

import os

# ============================
# Langfuse Configuration
# ============================

# Enable Langfuse tracing for agent runs
# Default: disabled (empty string or "false" disables it)
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "").lower() in ("1", "true", "yes")

# Langfuse public key (safe to expose to frontend)
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")

# Langfuse secret key (keep server-side only)
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# Langfuse host URL
# Default: http://localhost:3000 (local dev); replace with your deployment
LANGFUSE_HOST = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000")

# Sampling rate: 0.0 to 1.0 (1.0 = 100% of traces captured)
# Default: 1.0 (capture all)
LANGFUSE_SAMPLE_RATE = float(os.getenv("LANGFUSE_SAMPLE_RATE", "1.0"))

# Request timeout in seconds for Langfuse API calls
LANGFUSE_TIMEOUT = int(os.getenv("LANGFUSE_TIMEOUT", "10"))
