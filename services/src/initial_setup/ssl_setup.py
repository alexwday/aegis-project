# services/src/initial_setup/ssl_setup.py
"""
SSL Certificate Setup Module

This module handles the SSL certificate setup required for secure API communication
by configuring environment variables to use an existing certificate. It includes
functionality to validate the certificate's existence and optionally check its
expiration date.

Functions:
    check_certificate_expiry: Validates certificate expiration date
    setup_ssl: Configures SSL environment with existing CA bundle certificate

Dependencies:
    - os
    - logging
    - datetime
    - cryptography (for certificate parsing)
"""

import logging
import os
from datetime import datetime, timedelta, timezone

# Try to import certificate checking libraries
try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# Import configuration
from .env_config import config

# Get SSL settings from config
CHECK_CERT_EXPIRY = config.SSL_CHECK_CERT_EXPIRY
EXPIRY_WARNING_DAYS = config.SSL_EXPIRY_WARNING_DAYS
SSL_CERT_FILENAME = config.SSL_CERT_FILENAME

# Calculate SSL certificate directory and path based on this module's location
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SSL_CERT_DIR = _MODULE_DIR
SSL_CERT_PATH = os.path.join(SSL_CERT_DIR, SSL_CERT_FILENAME)

def _validate_certificate_path(cert_path: str) -> bool:
    """
    Validate that the certificate path is within expected boundaries.
    
    Args:
        cert_path (str): Path to validate
        
    Returns:
        bool: True if path is valid, False otherwise
    """
    try:
        # Resolve any relative paths and symbolic links
        resolved_path = os.path.realpath(cert_path)
        expected_dir = os.path.realpath(SSL_CERT_DIR)
        
        # Check if the resolved path is within the expected directory
        return resolved_path.startswith(expected_dir)
    except (OSError, ValueError):
        return False

# Get module logger (no configuration here - using centralized config)
logger = logging.getLogger(__name__)


def check_certificate_expiry(cert_path: str) -> bool:
    """
    Check if the certificate is valid and not expired or expiring soon.

    Args:
        cert_path (str): Path to the certificate file

    Returns:
        bool: True if valid and not expiring soon, False otherwise

    Raises:
        Exception: If there's an error reading or parsing the certificate
    """
    if not CRYPTO_AVAILABLE:
        logger.warning(
            "Cryptography library not available, skipping certificate expiry check"
        )
        return True

    try:
        logger.debug("Checking certificate expiry")

        # Read certificate data
        with open(cert_path, "rb") as cert_file:
            cert_data = cert_file.read()

        # Parse the certificate
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())

        # Get expiration date using the UTC method to avoid deprecation warning
        expiry_date = cert.not_valid_after_utc

        # Use timezone-aware current date to match expiry_date's timezone awareness
        current_date = datetime.now(timezone.utc)

        # Check if expired
        if current_date > expiry_date:
            logger.error("Certificate has expired")
            return False

        # Check if expiring soon
        days_until_expiry = (expiry_date - current_date).days
        if days_until_expiry <= EXPIRY_WARNING_DAYS:
            logger.warning(f"Certificate will expire in {days_until_expiry} days")
            return True

        logger.debug("Certificate is valid")
        return True

    except (OSError, IOError) as e:
        logger.error("Error reading certificate file")
        raise FileNotFoundError("Certificate file could not be read") from e
    except x509.InvalidCertificate as e:
        logger.error("Invalid certificate format")
        raise ValueError("Certificate file is not valid") from e
    except Exception as e:
        logger.error("Unexpected error during certificate validation")
        raise


def setup_ssl() -> str:
    """
    Configure SSL environment with existing CA bundle certificate.

    This function performs the following steps:
    1. Verifies the certificate file exists
    2. Optionally checks certificate expiration (if enabled in settings)
    3. Sets appropriate environment variables to use the certificate

    Returns:
        str: Path to the configured SSL certificate

    Raises:
        FileNotFoundError: If certificate file does not exist
        Exception: If certificate validation fails
    """
    logger.debug("SSL setup starting")
    
    # Validate certificate path is within expected boundaries
    if not _validate_certificate_path(SSL_CERT_PATH):
        logger.error("Certificate path validation failed")
        raise ValueError("Certificate path is not within expected directory")

    # Verify the certificate exists
    if not os.path.exists(SSL_CERT_PATH):
        logger.error("Certificate file not found")
        raise FileNotFoundError("SSL certificate file does not exist")

    logger.debug("Certificate file located successfully")

    # Check certificate expiry if enabled
    if CHECK_CERT_EXPIRY:
        try:
            check_certificate_expiry(SSL_CERT_PATH)
        except Exception as e:
            logger.warning("Certificate expiry check failed")
    else:
        logger.debug("Certificate expiry check disabled")

    # Configure SSL environment variables
    os.environ["SSL_CERT_FILE"] = SSL_CERT_PATH
    os.environ["REQUESTS_CA_BUNDLE"] = SSL_CERT_PATH

    logger.debug("SSL environment configured successfully")
    return SSL_CERT_PATH
