import asyncio
import sys
import threading

from dotenv import load_dotenv

# 1. Load environment variables before settings are evaluated
load_dotenv()

from src.application.orchestrator import EmailOrchestrator
from src.config.settings import settings
from src.config.validator import StartupValidator
from src.domain.interfaces import IAIProvider, INotificationService, IRepository
from src.infrastructure.clients.ai_providers import ChainAIProvider
from src.infrastructure.clients.gmail_client import GmailClient
from src.infrastructure.clients.telegram_client import TelegramNotificationService
from src.infrastructure.clients.twilio_client import TwilioWhatsAppService
from src.infrastructure.database.sqlite_repo import SQLiteRepository
from src.infrastructure.llm.base import ILLMProvider
from src.infrastructure.llm.fallback_provider import FallbackLLMProvider
from src.infrastructure.llm.groq_provider import GroqProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider
from src.presentation.scheduler import AgentScheduler
from src.utils.di import container
from src.utils.logger import get_logger

sys.stdout.reconfigure(encoding="utf-8")
logger = get_logger("mail_agent")


def _start_dashboard(port: int = 8080) -> None:
    """
    Issue #8 & #13: Start the Flask dashboard server in a background daemon thread.
    Daemon threads are automatically killed when the main process exits.
    """
    try:
        from dashboard.server import run_server
        logger.info(f"Dashboard starting on http://localhost:{port}")
        run_server(port=port, debug=False)
    except ImportError as e:
        logger.warning(f"Dashboard server could not start (missing dependencies): {e}")
        logger.warning("Install with: pip install flask flask-cors")
    except Exception as e:
        logger.warning(f"Dashboard server error: {e}")


async def main():
    # 2. Validate configuration
    try:
        StartupValidator.validate()
        logger.info("Configuration validated successfully.")
    except Exception as e:
        logger.critical(f"Startup configuration error: {e}")
        sys.exit(1)

    # 3. Register Services in Dependency Injection Container
    try:
        container.register_singleton(IRepository, implementation=SQLiteRepository)

        # LLM Provider setup: Groq primary with OpenRouter fallback
        def llm_provider_factory():
            primary = GroqProvider()
            fallback = OpenRouterProvider()
            return FallbackLLMProvider(primary=primary, fallback=fallback)

        container.register_singleton(ILLMProvider, factory=llm_provider_factory)

        def ai_provider_factory():
            llm = container.resolve(ILLMProvider)
            return ChainAIProvider(llm_provider=llm)

        container.register_singleton(IAIProvider, factory=ai_provider_factory)

        # Register factory for EmailOrchestrator to handle list initialization
        def orchestrator_factory():
            repo = container.resolve(IRepository)
            ai = container.resolve(IAIProvider)

            # Notifications — Telegram service handles its own feature flag dynamically
            notification_services = [TelegramNotificationService()]
            if settings.features.enable_twilio:
                notification_services.append(TwilioWhatsAppService())

            # Mail Clients
            mail_clients = [
                GmailClient(user, pwd)
                for user, pwd in zip(settings.email.user_list, settings.email.password_list)
            ]

            return EmailOrchestrator(
                mail_clients=mail_clients,
                repository=repo,
                ai_provider=ai,
                notification_services=notification_services,
            )

        container.register_singleton(EmailOrchestrator, factory=orchestrator_factory)
        container.register_singleton(AgentScheduler, implementation=AgentScheduler)
        logger.info("Services registered in DI container successfully.")
    except Exception as e:
        logger.critical(f"DI registration failed: {e}")
        sys.exit(1)

    # 4. Start Dashboard Server (Issue #8 & #13)
    if settings.features.enable_dashboard:
        dashboard_port = int(__import__("os").environ.get("DASHBOARD_PORT", 8080))
        dashboard_thread = threading.Thread(
            target=_start_dashboard,
            args=(dashboard_port,),
            daemon=True,
            name="DashboardServer",
        )
        dashboard_thread.start()
        logger.info(f"Dashboard thread started. Visit http://localhost:{dashboard_port}")
    else:
        logger.info("Dashboard disabled (FEATURE_ENABLE_DASHBOARD=false). Skipping.")

    # 5. Resolve Scheduler and run
    try:
        scheduler = container.resolve(AgentScheduler)
        logger.info("Application ready. Running scheduler...")
        await scheduler.run()
    except asyncio.CancelledError:
        logger.info("Scheduler task cancelled.")
    except Exception as e:
        logger.critical(f"Application run failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent gracefully shutting down via KeyboardInterrupt.")
