"""Enhanced configuration management for Ultimate MCP."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    user: str = Field(default="neo4j", env="NEO4J_USER")
    password: str = Field(env="NEO4J_PASSWORD")
    database: str = Field(default="neo4j", env="NEO4J_DATABASE")
    
    # Connection pool settings
    max_connection_lifetime: int = Field(default=300, env="NEO4J_MAX_CONNECTION_LIFETIME")
    max_connection_pool_size: int = Field(default=50, env="NEO4J_MAX_POOL_SIZE")
    connection_acquisition_timeout: int = Field(default=30, env="NEO4J_ACQUISITION_TIMEOUT")

    @validator("password")
    def validate_password(cls, value: str) -> str:
        if not value or value == "password123":
            raise ValueError("NEO4J_PASSWORD must be set to a non-default value")
        return value


class SecurityConfig(BaseSettings):
    """Security configuration."""
    secret_key: str = Field(env="SECRET_KEY")
    auth_token: str = Field(env="AUTH_TOKEN")
    encryption_key: str | None = Field(default=None, env="ENCRYPTION_KEY")
    
    # JWT settings
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(default=24, env="JWT_EXPIRATION_HOURS")
    
    # Rate limiting
    rate_limit_requests_per_minute: int = Field(default=60, env="RATE_LIMIT_RPM")
    rate_limit_requests_per_hour: int = Field(default=1000, env="RATE_LIMIT_RPH")
    rate_limit_requests_per_day: int = Field(default=10000, env="RATE_LIMIT_RPD")
    
    @validator("secret_key", "auth_token")
    def validate_required_secrets(cls, v: str) -> str:
        if not v or v == "change-me":
            raise ValueError("Security keys must be set and not use default values")
        return v


class ServerConfig(BaseSettings):
    """Server configuration."""
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    debug: bool = Field(default=False, env="DEBUG")
    reload: bool = Field(default=False, env="RELOAD")
    
    # CORS settings
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000"], 
        env="ALLOWED_ORIGINS"
    )
    allowed_methods: list[str] = Field(
        default=["GET", "POST", "PUT", "DELETE"], 
        env="ALLOWED_METHODS"
    )
    allowed_headers: list[str] = Field(
        default=["*"], 
        env="ALLOWED_HEADERS"
    )
    
    @validator("allowed_origins", pre=True)
    def parse_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class ExecutionConfig(BaseSettings):
    """Code execution configuration."""
    max_execution_time: float = Field(default=30.0, env="MAX_EXECUTION_TIME")
    max_memory_mb: int = Field(default=128, env="MAX_MEMORY_MB")
    max_file_size_mb: int = Field(default=10, env="MAX_FILE_SIZE_MB")
    max_processes: int = Field(default=1, env="MAX_PROCESSES")
    
    # Supported languages
    supported_languages: list[str] = Field(
        default=["python", "javascript", "bash"],
        env="SUPPORTED_LANGUAGES"
    )
    
    # Cache settings
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_size: int = Field(default=1000, env="CACHE_SIZE")
    cache_ttl_seconds: int = Field(default=3600, env="CACHE_TTL")


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration."""
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file: str | None = Field(default=None, env="LOG_FILE")
    
    # Health checks
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    
    # Performance monitoring
    slow_query_threshold: float = Field(default=1.0, env="SLOW_QUERY_THRESHOLD")
    enable_profiling: bool = Field(default=False, env="ENABLE_PROFILING")


class RedisConfig(BaseSettings):
    """Redis configuration for caching and sessions."""
    enabled: bool = Field(default=False, env="REDIS_ENABLED")
    url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    max_connections: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    
    # Cache settings
    default_ttl: int = Field(default=3600, env="REDIS_DEFAULT_TTL")
    key_prefix: str = Field(default="ultimate_mcp:", env="REDIS_KEY_PREFIX")


class UltimateMCPConfig(BaseSettings):
    """Main configuration class combining all settings."""
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Sub-configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    def validate_production_settings(self) -> None:
        """Validate settings for production deployment."""
        if self.is_production:
            if self.server.debug:
                raise ValueError("Debug mode must be disabled in production")
            if self.security.auth_token == "change-me":
                raise ValueError("Default auth token must be changed in production")
            if not self.monitoring.metrics_enabled:
                raise ValueError("Metrics should be enabled in production")


@lru_cache()
def get_config() -> UltimateMCPConfig:
    """Get cached configuration instance."""
    config = UltimateMCPConfig()
    
    # Validate production settings
    if config.is_production:
        config.validate_production_settings()
    
    return config


# Global config instance
config = get_config()


__all__ = [
    "UltimateMCPConfig",
    "DatabaseConfig", 
    "SecurityConfig",
    "ServerConfig",
    "ExecutionConfig",
    "MonitoringConfig",
    "RedisConfig",
    "get_config",
    "config"
]
