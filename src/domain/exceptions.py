class AgentException(Exception):
    """Base exception for all agent-related errors."""

    pass


class ConfigurationError(AgentException):
    """Raised when environment variables or configurations are missing/invalid."""

    pass


class ValidationError(AgentException):
    """Raised during manual validation checks."""

    pass


class MissingEnvironmentVariable(ConfigurationError):
    """Raised when a required env var is missing."""

    pass


class InvalidConfiguration(ConfigurationError):
    """Raised when configuration values are conflicting or out of bounds."""

    pass


class ServiceRegistrationError(AgentException):
    """Raised when DI container fails to register a service."""

    pass


class DependencyResolutionError(AgentException):
    """Raised when DI container cannot resolve a dependency."""

    pass


class EmailProcessingError(AgentException):
    """Raised when parsing or extracting an email fails."""

    pass


class AIProviderError(AgentException):
    """Raised when an AI provider fails (rate limits, timeouts, etc.)."""

    pass


class NotificationError(AgentException):
    """Raised when sending a notification fails."""

    pass


class RepositoryError(AgentException):
    """Raised when a repository operation fails."""

    pass


class DatabaseError(RepositoryError):
    """Raised when database connection or execution fails."""

    pass


class SchedulerError(AgentException):
    """Raised when scheduler operations fail."""

    pass
