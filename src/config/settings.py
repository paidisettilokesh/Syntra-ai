from dotenv import load_dotenv

load_dotenv()

from typing import List, Optional

from pydantic import AnyUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .feature_flags import FeatureFlags


class AppConfig(BaseSettings):
    environment: str = Field("development", description="dev, test, or prod")
    debug: bool = Field(False, description="Enable debug mode")
    poll_interval: int = Field(60, ge=10, le=3600, description="Polling interval in seconds")
    temp_directory: str = Field("data/temp", description="Temporary file storage")
    model_config = SettingsConfigDict(env_prefix="")


class EmailConfig(BaseSettings):
    users: str = Field(..., description="Comma separated list of emails")
    passwords: str = Field(..., description="Comma separated app passwords")
    imap_server: str = Field("imap.gmail.com")
    model_config = SettingsConfigDict(env_prefix="EMAIL_")

    @field_validator("users")
    @classmethod
    def validate_emails(cls, v):
        if not v:
            raise ValueError("Email users cannot be empty")
        for email in v.split(","):
            email = email.strip()
            if "@" not in email or "." not in email:
                raise ValueError(f"Invalid email format: {email}")
        return v

    @property
    def user_list(self) -> List[str]:
        return [x.strip() for x in self.users.split(",") if x.strip()]

    @property
    def password_list(self) -> List[str]:
        return [x.strip() for x in self.passwords.split(",") if x.strip()]


class AIConfig(BaseSettings):
    groq_api_key: Optional[SecretStr] = None
    gemini_api_key: Optional[SecretStr] = None
    openai_api_key: Optional[SecretStr] = None
    openrouter_api_key: Optional[SecretStr] = None  # OpenRouter fallback provider
    ollama_base_url: Optional[AnyUrl] = None
    model_config = SettingsConfigDict(env_prefix="")


class NotificationConfig(BaseSettings):
    # Telegram
    telegram_bot_token: Optional[SecretStr] = None
    telegram_chat_id: Optional[SecretStr] = None

    # Twilio WhatsApp (optional — requires FEATURE_ENABLE_TWILIO=true)
    twilio_account_sid: Optional[SecretStr] = None
    twilio_auth_token: Optional[SecretStr] = None
    from_whatsapp_number: Optional[str] = None
    to_whatsapp_number: Optional[str] = None

    model_config = SettingsConfigDict(env_prefix="")


class DatabaseConfig(BaseSettings):
    db_name: str = Field("data/agent_logs.db")
    model_config = SettingsConfigDict(env_prefix="DB_")


class LoggingConfig(BaseSettings):
    log_level: str = Field("INFO")
    log_file: str = Field("logs/agent.log")
    log_max_bytes: int = Field(
        10 * 1024 * 1024, description="Max log file size in bytes (default 10 MB)"
    )
    log_backup_count: int = Field(5, description="Number of rotated backup log files to keep")
    structured_logging: bool = Field(False, description="Output logs in JSON format when True")
    model_config = SettingsConfigDict(env_prefix="LOG_")


class RetentionConfig(BaseSettings):
    days_to_keep: int = Field(90, ge=1, description="Days to retain logs")
    model_config = SettingsConfigDict(env_prefix="RETENTION_")


class VerificationConfig(BaseSettings):
    enable_email_verification: bool = Field(True, validation_alias="ENABLE_EMAIL_VERIFICATION")
    enable_ai_verification: bool = Field(True, validation_alias="ENABLE_AI_VERIFICATION")
    enable_rule_verification: bool = Field(True, validation_alias="ENABLE_RULE_VERIFICATION")
    block_suspicious_emails: bool = Field(True, validation_alias="BLOCK_SUSPICIOUS_EMAILS")
    verification_confidence_threshold: float = Field(
        80.0, validation_alias="VERIFICATION_CONFIDENCE_THRESHOLD"
    )
    enable_trusted_senders: bool = Field(True, validation_alias="ENABLE_TRUSTED_SENDERS")
    enable_weighted_scoring: bool = Field(True, validation_alias="ENABLE_WEIGHTED_SCORING")
    enable_smart_ai_routing: bool = Field(True, validation_alias="ENABLE_SMART_AI_ROUTING")
    enable_detailed_logging: bool = Field(True, validation_alias="ENABLE_DETAILED_LOGGING")
    allowlist_file: str = Field("data/trusted_domains.json", validation_alias="ALLOWLIST_FILE")
    model_config = SettingsConfigDict(env_prefix="")


class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    notify: NotificationConfig = Field(default_factory=NotificationConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_nested_delimiter="__", extra="ignore"
    )


settings = Settings()
