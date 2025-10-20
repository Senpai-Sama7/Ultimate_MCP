"""Enhanced configuration management for Ultimate MCP."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _coerce_str_list(value: object) -> list[str]:
    """Normalize comma-separated environment variables to string lists."""
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise TypeError(f"Unsupported value for list coercion: {value!r}")


def _secret_value(secret: SecretStr | None) -> str:
    """Safely unwrap optional SecretStr values."""
    return "" if secret is None else secret.get_secret_value()


class SettingsBase(BaseSettings):
    """Base class that applies shared Settings configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class DatabaseConfig(SettingsBase):
    """Database configuration."""

    uri: str = Field(
        default="bolt://localhost:7687",
        validation_alias=AliasChoices("NEO4J_URI", "uri"),
    )
    user: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("NEO4J_USER", "user"),
    )
    password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("NEO4J_PASSWORD", "password"),
    )
    database: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("NEO4J_DATABASE", "database"),
    )
    max_connection_lifetime: int = Field(
        default=300,
        validation_alias=AliasChoices("NEO4J_MAX_CONNECTION_LIFETIME", "max_connection_lifetime"),
    )
    max_connection_pool_size: int = Field(
        default=50,
        validation_alias=AliasChoices("NEO4J_MAX_POOL_SIZE", "max_connection_pool_size"),
    )
    connection_acquisition_timeout: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "NEO4J_ACQUISITION_TIMEOUT",
            "connection_acquisition_timeout",
        ),
    )


class SecurityConfig(SettingsBase):
    """Security configuration."""

    secret_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("SECRET_KEY", "secret_key"),
    )
    auth_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_TOKEN", "auth_token"),
    )
    encryption_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ENCRYPTION_KEY", "encryption_key"),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "jwt_algorithm"),
    )
    jwt_expiration_hours: int = Field(
        default=24,
        validation_alias=AliasChoices("JWT_EXPIRATION_HOURS", "jwt_expiration_hours"),
    )
    rate_limit_requests_per_minute: int = Field(
        default=60,
        validation_alias=AliasChoices("RATE_LIMIT_RPM", "rate_limit_requests_per_minute"),
    )
    rate_limit_requests_per_hour: int = Field(
        default=1_000,
        validation_alias=AliasChoices("RATE_LIMIT_RPH", "rate_limit_requests_per_hour"),
    )
    rate_limit_requests_per_day: int = Field(
        default=10_000,
        validation_alias=AliasChoices("RATE_LIMIT_RPD", "rate_limit_requests_per_day"),
    )


class ServerConfig(SettingsBase):
    """Server configuration."""

    host: str = Field(
        default="0.0.0.0",  # noqa: S104
        validation_alias=AliasChoices("HOST", "host"),
    )
    port: int = Field(default=8000, validation_alias=AliasChoices("PORT", "port"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("DEBUG", "debug"))
    reload: bool = Field(default=False, validation_alias=AliasChoices("RELOAD", "reload"))
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "allowed_origins"),
    )
    allowed_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"],
        validation_alias=AliasChoices("ALLOWED_METHODS", "allowed_methods"),
    )
    allowed_headers: list[str] = Field(
        default_factory=lambda: ["*"],
        validation_alias=AliasChoices("ALLOWED_HEADERS", "allowed_headers"),
    )

    @field_validator("allowed_origins", "allowed_methods", "allowed_headers", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _coerce_str_list(value)


class ExecutionConfig(SettingsBase):
    """Code execution configuration."""

    max_execution_time: float = Field(
        default=30.0,
        validation_alias=AliasChoices("MAX_EXECUTION_TIME", "max_execution_time"),
    )
    max_memory_mb: int = Field(
        default=128,
        validation_alias=AliasChoices("MAX_MEMORY_MB", "max_memory_mb"),
    )
    max_file_size_mb: int = Field(
        default=10,
        validation_alias=AliasChoices("MAX_FILE_SIZE_MB", "max_file_size_mb"),
    )
    max_processes: int = Field(
        default=1,
        validation_alias=AliasChoices("MAX_PROCESSES", "max_processes"),
    )
    supported_languages: list[str] = Field(
        default_factory=lambda: ["python", "javascript", "bash"],
        validation_alias=AliasChoices("SUPPORTED_LANGUAGES", "supported_languages"),
    )
    cache_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("CACHE_ENABLED", "cache_enabled"),
    )
    cache_size: int = Field(
        default=1_000,
        validation_alias=AliasChoices("CACHE_SIZE", "cache_size"),
    )
    cache_ttl_seconds: int = Field(
        default=3_600,
        validation_alias=AliasChoices("CACHE_TTL", "cache_ttl_seconds"),
    )

    @field_validator("supported_languages", mode="before")
    @classmethod
    def _normalize_languages(cls, value: object) -> list[str]:
        return _coerce_str_list(value)


class MonitoringConfig(SettingsBase):
    """Monitoring and observability configuration."""

    metrics_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("METRICS_ENABLED", "metrics_enabled"),
    )
    metrics_port: int = Field(
        default=9090,
        validation_alias=AliasChoices("METRICS_PORT", "metrics_port"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL", "log_level"),
    )
    log_format: str = Field(
        default="json",
        validation_alias=AliasChoices("LOG_FORMAT", "log_format"),
    )
    log_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOG_FILE", "log_file"),
    )
    health_check_interval: int = Field(
        default=30,
        validation_alias=AliasChoices("HEALTH_CHECK_INTERVAL", "health_check_interval"),
    )
    slow_query_threshold: float = Field(
        default=1.0,
        validation_alias=AliasChoices("SLOW_QUERY_THRESHOLD", "slow_query_threshold"),
    )
    enable_profiling: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_PROFILING", "enable_profiling"),
    )


class RedisConfig(SettingsBase):
    """Redis configuration for caching and sessions."""

    enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("REDIS_ENABLED", "enabled"),
    )
    url: str = Field(
        default="redis://localhost:6379",
        validation_alias=AliasChoices("REDIS_URL", "url"),
    )
    max_connections: int = Field(
        default=20,
        validation_alias=AliasChoices("REDIS_MAX_CONNECTIONS", "max_connections"),
    )
    default_ttl: int = Field(
        default=3_600,
        validation_alias=AliasChoices("REDIS_DEFAULT_TTL", "default_ttl"),
    )
    key_prefix: str = Field(
        default="ultimate_mcp:",
        validation_alias=AliasChoices("REDIS_KEY_PREFIX", "key_prefix"),
    )


class UltimateMCPConfig(SettingsBase):
    """Main configuration combining all sub-sections."""

    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "environment"),
    )
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)

    @property
    def is_production(self) -> bool:
        """Return True when running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Return True when running in development environment."""
        return self.environment.lower() == "development"

    def validate_production_settings(self) -> None:
        """Validate security-sensitive settings for production deployments."""
        if not self.is_production:
            return

        auth_token = _secret_value(self.security.auth_token)
        secret_key = _secret_value(self.security.secret_key)
        password = _secret_value(self.database.password)

        if self.server.debug:
            raise ValueError("Debug mode must be disabled in production")
        if auth_token in {"", "change-me"}:
            raise ValueError("Default auth token must be changed in production")
        if secret_key in {"", "change-me"}:
            raise ValueError("Default secret key must be changed in production")
        if password in {"", "password123"}:
            raise ValueError("Neo4j password must be changed in production")
        if not self.monitoring.metrics_enabled:
            raise ValueError("Metrics should be enabled in production")


@lru_cache
def get_config() -> UltimateMCPConfig:
    """Return a cached configuration instance."""
    config = UltimateMCPConfig()

    if config.is_production:
        config.validate_production_settings()

    return config


__all__ = [
    "UltimateMCPConfig",
    "DatabaseConfig",
    "SecurityConfig",
    "ServerConfig",
    "ExecutionConfig",
    "MonitoringConfig",
    "RedisConfig",
    "get_config",
    "config",
]

config = get_config()
