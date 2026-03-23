import logging
import sys
import re
import os
from datetime import datetime
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings

settings = get_settings()

# Log Directory
LOG_DIR = "/var/log/rag-chatbot"
os.makedirs(LOG_DIR, exist_ok=True)


class PIIMasker:
    """Simple PII masking utility."""

    @staticmethod
    def mask_email(text: str) -> str:
        """Mask email addresses."""
        return re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***EMAIL***', text)

    @staticmethod
    def mask_phone(text: str) -> str:
        """Mask phone numbers."""
        # Korean phone numbers
        text = re.sub(r'\b\d{2,3}-\d{3,4}-\d{4}\b', '***PHONE***', text)
        # International format
        text = re.sub(r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b', '***PHONE***', text)
        return text

    @staticmethod
    def mask_ssn(text: str) -> str:
        """Mask Korean SSN (주민등록번호)."""
        return re.sub(r'\b\d{6}-\d{7}\b', '***SSN***', text)

    @classmethod
    def mask_pii(cls, text: str) -> str:
        """Apply all PII masking."""
        if not text:
            return text
        text = cls.mask_email(text)
        text = cls.mask_phone(text)
        text = cls.mask_ssn(text)
        return text


class ServiceTypeFilter(logging.Filter):
    """Inject service_type into log records for structured logging."""
    def __init__(self, service_type: Optional[str] = None):
        super().__init__()
        self.service_type = service_type or "GENERAL"

    def filter(self, record):
        record.service_type = self.service_type
        return True


# 아래의 설정을 통해 logger.info를 한번만 호출해도 메시지는 자동으로 콘솔과 CloudWatch 두 곳 모두로 전송됨
def setup_logger(name: str, service_type: Optional[str] = None) -> logging.Logger:
    """Set up logger with CloudWatch handler if available."""
    logger = logging.getLogger(name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO if not settings.debug else logging.DEBUG)

    # Add service type filter
    service_filter = ServiceTypeFilter(service_type)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout) #StreamHandler - 로그를 터미널로 보냄
    console_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    console_handler.addFilter(service_filter)
    formatter = logging.Formatter(
        '%(asctime)s - [%(service_type)s] - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler - File Log Save (Date)
    log_filename = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(
        filename=log_filename,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.addFilter(service_filter)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # CloudWatch handler (only if AWS credentials are configured)
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        try:
            import watchtower
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group=settings.cloudwatch_log_group,
                stream_name=settings.cloudwatch_log_stream,
                boto3_client=boto3.client(
                    'logs',
                    region_name=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key
                )
            )
            cloudwatch_handler.addFilter(service_filter)
            cloudwatch_handler.setFormatter(formatter)
            logger.addHandler(cloudwatch_handler) # 로거는 두 곳으로 로그를 보내게 된다
            logger.info("CloudWatch logging enabled")
        except (ClientError, Exception) as e:
            logger.warning(f"CloudWatch logging not available: {e}")

    return logger


def log_api_call(
    logger: logging.Logger,
    user_id: Optional[str],
    session_id: Optional[str],
    endpoint: str,
    request_data: Optional[str] = None,
    response_data: Optional[str] = None,
    status_code: int = 200
):
    """Log API call with PII masking."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "endpoint": endpoint,
        "status_code": status_code,
    }

    if request_data:
        log_entry["request"] = PIIMasker.mask_pii(request_data)

    if response_data:
        log_entry["response"] = PIIMasker.mask_pii(response_data)

    logger.info(f"API_CALL: {log_entry}")
