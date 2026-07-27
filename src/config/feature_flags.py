from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureFlags(BaseSettings):
    enable_ai: bool = True
    enable_ocr: bool = True
    enable_telegram: bool = True
    enable_twilio: bool = False          # WhatsApp alerts via Twilio (opt-in)
    enable_dashboard: bool = True        # Issue #8: Web dashboard — default ON
    enable_analytics: bool = True
    enable_health_monitoring: bool = True
    enable_prompt_compression: bool = False
    enable_circuit_breaker: bool = True
    enable_gmail_labels: bool = True
    enable_scheduler: bool = True

    model_config = SettingsConfigDict(env_prefix="FEATURE_")
