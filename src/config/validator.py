import os
from pathlib import Path

from src.config.settings import settings
from src.domain.exceptions import InvalidConfiguration
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StartupValidator:
    @staticmethod
    def validate():
        # 1. Validate directories
        dirs_to_check = ["logs", "data", settings.app.temp_directory]
        for d in dirs_to_check:
            path = Path(d)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created missing directory: {d}")
            if not os.access(path, os.W_OK):
                raise InvalidConfiguration(f"Directory '{d}' is not writable. Check filesystem permissions.")

        # 2. Validate Email config
        if len(settings.email.user_list) != len(settings.email.password_list):
            raise InvalidConfiguration(
                f"Number of EMAIL_USERS ({len(settings.email.user_list)}) must match "
                f"EMAIL_PASSWORDS ({len(settings.email.password_list)}). "
                "Ensure both are comma-separated lists of equal length."
            )

        # 3. AI Provider check & Self-Test
        from src.utils.sanitizer import is_valid_api_key, mask_secret

        def _get_key(setting_val, env_name):
            if setting_val:
                v = setting_val.get_secret_value()
                if is_valid_api_key(v):
                    return v.strip()
            v_env = os.getenv(env_name)
            if is_valid_api_key(v_env):
                return v_env.strip()
            return None

        groq_key = _get_key(settings.ai.groq_api_key, "GROQ_API_KEY")
        openrouter_key = _get_key(settings.ai.openrouter_api_key, "OPENROUTER_API_KEY")
        gemini_key = _get_key(settings.ai.gemini_api_key, "GEMINI_API_KEY")
        openai_key = _get_key(settings.ai.openai_api_key, "OPENAI_API_KEY")

        if groq_key:
            logger.info(f"[SELF-TEST] Groq Provider valid. Key: {mask_secret(groq_key)}")
        else:
            logger.warning("[SELF-TEST] Groq API Key missing or placeholder.")

        if openrouter_key:
            logger.info(f"[SELF-TEST] OpenRouter Provider valid. Key: {mask_secret(openrouter_key)}")
        else:
            logger.warning("[SELF-TEST] OpenRouter API Key missing or placeholder.")

        if not any([groq_key, openrouter_key, gemini_key, openai_key]):
            logger.warning(
                "No valid AI provider API keys configured (GROQ_API_KEY, OPENROUTER_API_KEY, etc.). "
                "AI-based email classification and verification will be unavailable. "
                "Set at least one valid AI provider key in .env."
            )

        # 4. Telegram credential check
        if settings.features.enable_telegram:
            if not settings.notify.telegram_bot_token or not settings.notify.telegram_chat_id:
                raise InvalidConfiguration(
                    "Telegram notifications are enabled (FEATURE_ENABLE_TELEGRAM=true) but "
                    "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing. "
                    "Set both in .env or disable Telegram with FEATURE_ENABLE_TELEGRAM=false."
                )

        # 5. Twilio credential check
        if settings.features.enable_twilio:
            missing = []
            if not settings.notify.twilio_account_sid:
                missing.append("TWILIO_ACCOUNT_SID")
            if not settings.notify.twilio_auth_token:
                missing.append("TWILIO_AUTH_TOKEN")
            if not settings.notify.from_whatsapp_number:
                missing.append("FROM_WHATSAPP_NUMBER")
            if not settings.notify.to_whatsapp_number:
                missing.append("TO_WHATSAPP_NUMBER")
            if missing:
                raise InvalidConfiguration(
                    f"Twilio WhatsApp is enabled (FEATURE_ENABLE_TWILIO=true) but the following "
                    f"required settings are missing: {', '.join(missing)}. "
                    "Set them in .env or disable Twilio with FEATURE_ENABLE_TWILIO=false."
                )

        logger.info(
            f"Startup validation passed. "
            f"Accounts: {len(settings.email.user_list)}, "
            f"Telegram: {'enabled' if settings.features.enable_telegram else 'disabled'}, "
            f"Twilio: {'enabled' if settings.features.enable_twilio else 'disabled'}, "
            f"Circuit Breaker: {'enabled' if settings.features.enable_circuit_breaker else 'disabled'}."
        )
