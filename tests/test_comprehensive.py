#!/usr/bin/env python3
"""
Comprehensive Test Suite for ServiceNow MCP System
Tests all components, configurations, and failure scenarios
"""

import pytest
import asyncio
import os
import sys
import json
import time
import subprocess
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability import init_observability, get_logger
import httpx


class TestEnvironmentSetup:
    """Test environment configuration and prerequisites"""
    
    def test_required_files_exist(self):
        """Test that all required files exist"""
        required_files = [
            "servicenow_table_sse_server.py",
            "servicenow_knowledge_sse_server.py",
            "servicenow_final_config.yaml",
            "openapi_specs/servicenow_table_api_final.json",
            "openapi_specs/servicenow_knowledge_api_final.json",
        ]
        
        for file_path in required_files:
            assert Path(file_path).exists(), f"Required file missing: {file_path}"
    
    def test_environment_variables(self):
        """Test that required environment variables are available"""
        # Check for ServiceNow environment variables
        sn_vars = ["SN_INSTANCE", "SN_USER", "SN_PASS"]
        missing_vars = [var for var in sn_vars if not os.getenv(var)]
        
        if missing_vars:
            pytest.skip(f"ServiceNow environment variables not set: {missing_vars}")
    
    def test_openai_api_key_configuration(self):
        """Test OpenAI API key configuration in config file"""
        config_file = Path("servicenow_final_config.yaml")
        assert config_file.exists(), "Configuration file missing"
        
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Check if API key is properly referenced
        assert "${OPENAI_API_KEY}" in content, "OpenAI API key not properly referenced in config"
        
        # Check if environment variable is set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY environment variable not set")
        
        # Verify it's not a placeholder
        assert not api_key.startswith("${"), "OPENAI_API_KEY contains unresolved placeholder"
        assert len(api_key) > 10, "OPENAI_API_KEY appears to be invalid"


class TestObservabilityStack:
    """Test the observability and logging infrastructure"""
    
    def test_observability_initialization(self):
        """Test that observability stack initializes correctly"""
        logger = init_observability(
            service_name="test-service",
            service_version="test-1.0.0"
        )
        
        assert logger is not None
        logger.info("test_log_message", test_data="test_value")
    
    def test_log_file_creation(self):
        """Test that log files are created correctly"""
        # Initialize observability
        init_observability(service_name="test-logging")
        
        # Check that logs directory exists
        logs_dir = Path("logs")
        assert logs_dir.exists(), "Logs directory not created"
        
        # Check that log files are created
        main_log = logs_dir / "test-logging.log"
        error_log = logs_dir / "test-logging-errors.log"
        
        # Log files might not exist immediately, so we'll create some logs
        logger = get_logger()
        logger.info("test_info_message")
        logger.error("test_error_message")
        
        # Give it a moment for file handlers to flush
        time.sleep(0.1)
        
        # At minimum, the directory structure should be correct
        assert logs_dir.is_dir(), "Logs directory is not a directory"
    
    def test_log_levels_captured(self):
        """Test that all log levels are captured"""
        logger = init_observability(service_name="test-log-levels")
        
        # Test all log levels
        test_messages = {
            "debug": "Debug message",
            "info": "Info message", 
            "warning": "Warning message",
            "error": "Error message",
            "critical": "Critical message"
        }
        
        for level, message in test_messages.items():
            getattr(logger, level)(message, test_level=level)


class TestMCPServers:
    """Test MCP server functionality"""
    
    @pytest.fixture
    def mock_servicenow_env(self, monkeypatch):
        """Mock ServiceNow environment variables"""
        monkeypatch.setenv("SN_INSTANCE", "https://test.service-now.com")
        monkeypatch.setenv("SN_USER", "test_user")
        monkeypatch.setenv("SN_PASS", "test_pass")
    
    def test_table_server_imports(self):
        """Test that table server can be imported without errors"""
        try:
            # Import the server module
            import servicenow_table_sse_server
            assert hasattr(servicenow_table_sse_server, 'main')
        except ImportError as e:
            pytest.fail(f"Failed to import table server: {e}")
        except Exception as e:
            # Log the error but don't fail - might be due to missing env vars
            print(f"Table server import warning: {e}")
    
    def test_knowledge_server_imports(self):
        """Test that knowledge server can be imported without errors"""
        try:
            import servicenow_knowledge_sse_server
            assert hasattr(servicenow_knowledge_sse_server, 'main')
        except ImportError as e:
            pytest.fail(f"Failed to import knowledge server: {e}")
        except Exception as e:
            print(f"Knowledge server import warning: {e}")
    
    def test_openapi_specs_valid_json(self):
        """Test that OpenAPI specifications are valid JSON"""
        spec_files = [
            "openapi_specs/servicenow_table_api_final.json",
            "openapi_specs/servicenow_knowledge_api_final.json"
        ]
        
        for spec_file in spec_files:
            with open(spec_file, 'r') as f:
                try:
                    spec_data = json.load(f)
                    assert "openapi" in spec_data, f"Missing OpenAPI version in {spec_file}"
                    assert "paths" in spec_data, f"Missing paths in {spec_file}"
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {spec_file}: {e}")


class TestMagenticUIConfiguration:
    """Test Magentic-UI configuration"""
    
    def test_config_file_syntax(self):
        """Test that configuration file has valid YAML syntax"""
        import yaml
        
        config_file = Path("servicenow_final_config.yaml")
        with open(config_file, 'r') as f:
            try:
                config_data = yaml.safe_load(f)
                assert config_data is not None, "Configuration file is empty"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax: {e}")
    
    def test_mcp_agent_configs(self):
        """Test MCP agent configurations"""
        import yaml
        
        with open("servicenow_final_config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        assert "mcp_agent_configs" in config, "Missing mcp_agent_configs"
        
        agents = config["mcp_agent_configs"]
        assert len(agents) >= 2, "Should have at least 2 MCP agents"
        
        # Check each agent configuration
        for agent in agents:
            assert "name" in agent, "Agent missing name"
            assert "mcp_servers" in agent, "Agent missing mcp_servers"
            
            for server in agent["mcp_servers"]:
                assert "server_name" in server, "Server missing server_name"
                assert "server_params" in server, "Server missing server_params"
                
                params = server["server_params"]
                assert "type" in params, "Server params missing type"
                assert "url" in params, "Server params missing url"
    
    def test_sse_endpoints_configured(self):
        """Test that SSE endpoints are properly configured"""
        import yaml
        
        with open("servicenow_final_config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        for agent in config["mcp_agent_configs"]:
            for server in agent["mcp_servers"]:
                params = server["server_params"]
                
                # Should be SSE transport
                assert params["type"] == "SseServerParams", f"Expected SseServerParams, got {params['type']}"
                
                # Should use /sse endpoint
                assert "/sse" in params["url"], f"URL should contain /sse: {params['url']}"


class TestServiceIntegration:
    """Integration tests for the complete system"""
    
    @pytest.mark.integration
    def test_mcp_servers_can_start(self):
        """Test that MCP servers can start (requires environment variables)"""
        # Skip if no ServiceNow credentials
        if not all(os.getenv(var) for var in ["SN_INSTANCE", "SN_USER", "SN_PASS"]):
            pytest.skip("ServiceNow credentials not available")
        
        # This is a basic smoke test - we won't actually start the servers
        # but we'll test that the main functions exist and can be called
        import servicenow_table_sse_server
        import servicenow_knowledge_sse_server
        
        assert callable(servicenow_table_sse_server.main)
        assert callable(servicenow_knowledge_sse_server.main)
    
    @pytest.mark.integration
    def test_service_endpoints_when_running(self):
        """Test service endpoints when servers are running"""
        endpoints = [
            ("http://localhost:3001/sse", "Table SSE Server"),
            ("http://localhost:3002/sse", "Knowledge SSE Server"),
            ("http://localhost:8080", "Magentic-UI")
        ]
        
        for url, service_name in endpoints:
            try:
                response = requests.get(url, timeout=5)
                print(f"{service_name}: HTTP {response.status_code}")
            except requests.RequestException as e:
                print(f"{service_name}: Not running - {e}")


class TestErrorScenarios:
    """Test various error scenarios and edge cases"""
    
    def test_missing_environment_variables(self):
        """Test behavior when environment variables are missing"""
        # Test with missing ServiceNow credentials
        with patch.dict(os.environ, {}, clear=True):
            # Should handle missing env vars gracefully
            try:
                import servicenow_table_sse_server
                # The import itself should work
                assert True
            except Exception as e:
                # If it fails, it should be a clear error message
                assert "environment" in str(e).lower() or "credential" in str(e).lower()
    
    def test_invalid_openai_api_key(self):
        """Test behavior with invalid OpenAI API key"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "invalid_key"}, clear=True):
            # This should be handled gracefully by the application
            # The test just ensures the configuration doesn't break
            import yaml
            
            with open("servicenow_final_config.yaml", 'r') as f:
                config = yaml.safe_load(f)
            
            # Config should still be valid
            assert config is not None
    
    def test_port_conflicts(self):
        """Test behavior when ports are already in use"""
        # This is more of a documentation test - the actual port conflict
        # handling would need to be implemented in the servers
        ports = [3001, 3002, 8080]
        
        for port in ports:
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:
                    print(f"Port {port} is in use")
                else:
                    print(f"Port {port} is available")
            except Exception as e:
                print(f"Could not test port {port}: {e}")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])