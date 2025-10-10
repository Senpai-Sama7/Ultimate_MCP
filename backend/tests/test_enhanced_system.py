"""Comprehensive tests for enhanced Ultimate MCP system."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from mcp_server.config import UltimateMCPConfig
from mcp_server.monitoring import HealthChecker, MetricsCollector
from mcp_server.utils.enhanced_security import (
    EnhancedSecurityManager,
    SecurityLevel,
    SecurityViolationError,
    ensure_safe_python,
)


class TestEnhancedSecurity:
    """Test enhanced security features."""
    
    def test_security_manager_initialization(self):
        """Test security manager initialization."""
        manager = EnhancedSecurityManager("test-secret-key")
        assert manager.secret_key == "test-secret-key"
        assert manager.cipher is not None
    
    def test_token_generation_and_verification(self):
        """Test JWT token generation and verification."""
        manager = EnhancedSecurityManager("test-secret-key")
        
        payload = {"user_id": "test-user", "roles": ["user"]}
        token = manager.generate_secure_token(payload)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token
        decoded = manager.verify_token(token)
        assert decoded["user_id"] == "test-user"
        assert decoded["roles"] == ["user"]
    
    def test_data_encryption_decryption(self):
        """Test data encryption and decryption."""
        manager = EnhancedSecurityManager("test-secret-key")
        
        original_data = "sensitive information"
        encrypted = manager.encrypt_sensitive_data(original_data)
        decrypted = manager.decrypt_sensitive_data(encrypted)
        
        assert encrypted != original_data
        assert decrypted == original_data
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        from backend.mcp_server.utils.enhanced_security import RateLimitConfig
        
        manager = EnhancedSecurityManager("test-secret-key")
        config = RateLimitConfig(requests_per_minute=2)
        
        # First two requests should pass
        assert manager.check_rate_limit("test-ip", config) is True
        assert manager.check_rate_limit("test-ip", config) is True
        
        # Third request should fail
        assert manager.check_rate_limit("test-ip", config) is False
    
    def test_security_context_creation(self):
        """Test security context creation."""
        manager = EnhancedSecurityManager("test-secret-key")
        
        # Public context
        context = manager.create_security_context()
        assert context.security_level == SecurityLevel.PUBLIC
        assert context.user_id is None
        
        # Authenticated context
        token = manager.generate_secure_token({
            "user_id": "test-user",
            "security_level": "authenticated"
        })
        
        context = manager.create_security_context(token=token)
        assert context.security_level == SecurityLevel.AUTHENTICATED
        assert context.user_id == "test-user"


class TestCodeSecurity:
    """Test enhanced code security validation."""
    
    def test_safe_python_code(self):
        """Test validation of safe Python code."""
        safe_code = """
def hello_world():
    return "Hello, World!"

result = hello_world()
print(result)
"""
        # Should not raise exception
        ensure_safe_python(safe_code)
    
    def test_dangerous_imports_blocked(self):
        """Test that dangerous imports are blocked."""
        dangerous_codes = [
            "import os",
            "import subprocess",
            "from os import system",
            "import socket",
        ]
        
        for code in dangerous_codes:
            with pytest.raises(SecurityViolationError):
                ensure_safe_python(code)
    
    def test_dangerous_functions_blocked(self):
        """Test that dangerous functions are blocked."""
        dangerous_codes = [
            "eval('print(1)')",
            "exec('print(1)')",
            "open('file.txt')",
            "__import__('os')",
        ]
        
        for code in dangerous_codes:
            with pytest.raises(SecurityViolationError):
                ensure_safe_python(code)
    
    def test_complexity_limit(self):
        """Test code complexity limits."""
        # Generate complex code that exceeds limit
        complex_code = "\n".join([f"x{i} = {i}" for i in range(200)])
        
        with pytest.raises(SecurityViolationError):
            ensure_safe_python(complex_code, max_complexity=100)
    
    def test_dangerous_patterns_blocked(self):
        """Test that dangerous patterns are blocked."""
        dangerous_codes = [
            "getattr(obj, 'dangerous_attr')",
            "__builtins__.eval('code')",
            "with open('file.txt') as f: pass",
        ]
        
        for code in dangerous_codes:
            with pytest.raises(SecurityViolationError):
                ensure_safe_python(code)


class TestMetricsCollector:
    """Test metrics collection functionality."""
    
    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector for testing."""
        return MetricsCollector(max_history=10)
    
    @pytest.mark.asyncio
    async def test_request_recording(self, metrics_collector):
        """Test HTTP request metrics recording."""
        await metrics_collector.record_request(
            method="GET",
            path="/api/test",
            status_code=200,
            duration=0.5,
            user_id="test-user",
            authenticated=True
        )
        
        metrics = metrics_collector.get_application_metrics()
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.authenticated_requests == 1
        assert metrics.unique_users == 1
    
    @pytest.mark.asyncio
    async def test_execution_recording(self, metrics_collector):
        """Test code execution metrics recording."""
        await metrics_collector.record_execution(
            language="python",
            duration=1.2,
            success=True,
            user_id="test-user"
        )
        
        metrics = metrics_collector.get_application_metrics()
        assert metrics.total_executions == 1
        assert metrics.successful_executions == 1
        assert metrics.failed_executions == 0
        assert metrics.executions_by_language["python"] == 1
    
    def test_system_metrics_collection(self, metrics_collector):
        """Test system metrics collection."""
        system_metrics = metrics_collector.get_system_metrics()
        
        assert system_metrics.cpu_percent >= 0
        assert system_metrics.memory_percent >= 0
        assert system_metrics.memory_used_mb >= 0
        assert system_metrics.disk_usage_percent >= 0
    
    @pytest.mark.asyncio
    async def test_comprehensive_metrics(self, metrics_collector):
        """Test comprehensive metrics aggregation."""
        # Record some sample data
        await metrics_collector.record_request("GET", "/test", 200, 0.1)
        await metrics_collector.record_request("POST", "/test", 500, 0.2)
        await metrics_collector.record_execution("python", 1.0, True)
        await metrics_collector.record_execution("javascript", 0.5, False)
        
        metrics = await metrics_collector.get_metrics()
        
        assert "timestamp" in metrics
        assert "uptime_seconds" in metrics
        assert "system" in metrics
        assert "application" in metrics
        
        app_metrics = metrics["application"]
        assert app_metrics["requests"]["total"] == 2
        assert app_metrics["requests"]["successful"] == 1
        assert app_metrics["requests"]["failed"] == 1
        assert app_metrics["executions"]["total"] == 2


class TestHealthChecker:
    """Test health checking functionality."""
    
    @pytest.fixture
    def mock_neo4j_client(self):
        """Create mock Neo4j client."""
        client = AsyncMock()
        client.health_check.return_value = True
        return client
    
    @pytest.fixture
    def health_checker(self, mock_neo4j_client):
        """Create health checker for testing."""
        return HealthChecker(mock_neo4j_client)
    
    @pytest.mark.asyncio
    async def test_database_health_check_success(self, health_checker, mock_neo4j_client):
        """Test successful database health check."""
        mock_neo4j_client.health_check.return_value = True
        
        result = await health_checker.check_database_health()
        
        assert result["status"] == "healthy"
        assert result["response_time"] > 0
        assert result["error"] is None
    
    @pytest.mark.asyncio
    async def test_database_health_check_failure(self, health_checker, mock_neo4j_client):
        """Test failed database health check."""
        mock_neo4j_client.health_check.side_effect = Exception("Connection failed")
        
        result = await health_checker.check_database_health()
        
        assert result["status"] == "unhealthy"
        assert result["error"] == "Connection failed"
    
    @pytest.mark.asyncio
    async def test_system_health_check(self, health_checker):
        """Test system health check."""
        result = await health_checker.check_system_health()
        
        assert "status" in result
        assert result["status"] in ["healthy", "degraded", "unhealthy"]
        
        if result["status"] != "unhealthy":
            assert "cpu" in result
            assert "memory" in result
            assert "disk" in result
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_status(self, health_checker):
        """Test comprehensive health status."""
        status = await health_checker.get_health_status()
        
        assert "status" in status
        assert "timestamp" in status
        assert "components" in status
        assert "database" in status["components"]
        assert "system" in status["components"]
    
    @pytest.mark.asyncio
    async def test_health_monitoring_lifecycle(self, health_checker):
        """Test health monitoring start and stop."""
        # Start monitoring
        await health_checker.start_monitoring(interval=0.1)
        assert health_checker.is_monitoring is True
        
        # Let it run briefly
        await asyncio.sleep(0.2)
        
        # Stop monitoring
        await health_checker.stop_monitoring()
        assert health_checker.is_monitoring is False


class TestConfiguration:
    """Test configuration management."""
    
    def test_config_initialization(self):
        """Test configuration initialization."""
        config = UltimateMCPConfig()
        
        assert config.environment == "development"
        assert config.database is not None
        assert config.security is not None
        assert config.server is not None
        assert config.execution is not None
        assert config.monitoring is not None
    
    def test_environment_detection(self):
        """Test environment detection methods."""
        config = UltimateMCPConfig(environment="development")
        assert config.is_development is True
        assert config.is_production is False
        
        config = UltimateMCPConfig(environment="production")
        assert config.is_development is False
        assert config.is_production is True
    
    def test_production_validation(self):
        """Test production settings validation."""
        config = UltimateMCPConfig(
            environment="production",
            security={"secret_key": "test-key", "auth_token": "test-token"},
            server={"debug": False},
            monitoring={"metrics_enabled": True}
        )
        
        # Should not raise exception
        config.validate_production_settings()
        
        # Test with invalid production settings
        config.server.debug = True
        with pytest.raises(ValueError):
            config.validate_production_settings()


class TestIntegration:
    """Integration tests for enhanced system."""
    
    @pytest.mark.asyncio
    async def test_security_and_metrics_integration(self):
        """Test integration between security and metrics."""
        security_manager = EnhancedSecurityManager("test-secret")
        metrics_collector = MetricsCollector()
        
        # Create authenticated context
        token = security_manager.generate_secure_token({
            "user_id": "test-user",
            "security_level": "authenticated"
        })
        
        context = security_manager.create_security_context(token=token)
        
        # Record metrics with security context
        await metrics_collector.record_request(
            method="POST",
            path="/api/execute",
            status_code=200,
            duration=1.5,
            user_id=context.user_id,
            authenticated=True
        )
        
        metrics = await metrics_collector.get_metrics()
        assert metrics["application"]["users"]["unique_users"] == 1
        assert metrics["application"]["requests"]["authenticated_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_end_to_end_request_flow(self):
        """Test complete request processing flow."""
        # This would test the full request pipeline:
        # Security -> Rate limiting -> Execution -> Metrics -> Response
        
        # Mock components
        security_manager = EnhancedSecurityManager("test-secret")
        metrics_collector = MetricsCollector()
        
        # Simulate request processing
        start_time = asyncio.get_event_loop().time()
        
        # 1. Security validation
        context = security_manager.create_security_context()
        assert context.security_level == SecurityLevel.PUBLIC
        
        # 2. Rate limiting check
        # Verify rate limits are configured
        assert security_manager.rate_limits is not None
        
        # 3. Code execution (mocked)
        execution_result = {
            "id": "test-execution",
            "return_code": 0,
            "stdout": "Hello, World!",
            "stderr": "",
            "duration_seconds": 0.1
        }
        
        # 4. Metrics recording
        end_time = asyncio.get_event_loop().time()
        await metrics_collector.record_request(
            method="POST",
            path="/api/execute",
            status_code=200,
            duration=end_time - start_time,
            authenticated=False
        )
        
        await metrics_collector.record_execution(
            language="python",
            duration=execution_result["duration_seconds"],
            success=execution_result["return_code"] == 0
        )
        
        # Verify metrics
        metrics = await metrics_collector.get_metrics()
        assert metrics["application"]["requests"]["total"] == 1
        assert metrics["application"]["executions"]["total"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
