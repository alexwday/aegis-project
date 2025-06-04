#!/usr/bin/env python3
"""
RBC-specific configuration template for transcript processor.
Copy this file to 'rbc_config.py' and update with your actual values.
"""

# RBC Environment Configuration
ENVIRONMENT = "rbc"
IS_RBC_ENV = True

# SSL Configuration
SSL_CERT_FILENAME = "rbc-ca-bundle.cer"
CHECK_CERT_EXPIRY = True
CERT_EXPIRY_WARNING_DAYS = 30
USE_SSL = True

# OAuth Configuration - UPDATE THESE VALUES WITH ACTUAL CREDENTIALS
OAUTH_ENDPOINT = "your-oauth-endpoint-here"  # Replace with actual RBC OAuth endpoint
CLIENT_ID = "your-client-id-here"            # Replace with actual client ID
CLIENT_SECRET = "your-client-secret-here"    # Replace with actual client secret
OAUTH_TIMEOUT = 180
OAUTH_RETRIES = 3
OAUTH_RETRY_DELAY = 2
USE_OAUTH = True

# OpenAI Configuration
RBC_BASE_URL = "https://perf-apigw-int.saifg.rbc.com/JLCO/llm-control-stack/v1"
BASE_URL = RBC_BASE_URL

# Model Configuration
MODEL_CONFIG = {
    "name": "gpt-4o-2024-08-06",
    "max_tokens": 32768,
    "temperature": 0.1,
    "top_p": 0.95
}

# Processing Configuration
DEFAULT_INPUT_FOLDER = "input_transcripts"
DEFAULT_OUTPUT_FOLDER = "analysis_results"
DEFAULT_CONFIG_FILE = "earnings_config_template.html"