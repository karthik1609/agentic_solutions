"""Tests for configuration and environment setup."""

import os
import pytest
import yaml
from pathlib import Path


def test_env_template_exists():
    """Test that env.template file exists and has required fields."""
    env_template = Path("env.template")
    assert env_template.exists(), "env.template file should exist"
    
    content = env_template.read_text()
    required_vars = [
        "SERVICENOW_INSTANCE_URL",
        "SERVICENOW_USERNAME", 
        "SERVICENOW_PASSWORD",
        "SERVICENOW_VERIFY_SSL",
        "MAGENTIC_UI_PORT"
    ]
    
    for var in required_vars:
        assert var in content, f"{var} should be in env.template"


def test_magentic_config_valid_yaml():
    """Test that servicenow_final_config.yaml is valid YAML."""
    config_path = Path("servicenow_final_config.yaml")
    assert config_path.exists(), "servicenow_final_config.yaml should exist"
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    assert config is not None, "Config should be valid YAML"
    assert "mcp_agent_configs" in config, "Config should have mcp_agent_configs"


def test_openapi_specs_exist():
    """Test that OpenAPI specification files exist."""
    specs_dir = Path("openapi_specs")
    assert specs_dir.exists(), "openapi_specs directory should exist"
    
    required_specs = [
        "servicenow_table_api_final.json",
        "servicenow_knowledge_api_final.json"
    ]
    
    for spec_file in required_specs:
        spec_path = specs_dir / spec_file
        assert spec_path.exists(), f"{spec_file} should exist"


def test_port_consistency():
    """Test that port configurations are consistent."""
    config_path = Path("servicenow_final_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Extract ports from config
    table_url = None
    knowledge_url = None
    
    for agent in config.get("mcp_agent_configs", []):
        if agent["name"] == "servicenow_table_agent":
            table_url = agent["mcp_servers"][0]["server_params"]["url"]
        elif agent["name"] == "servicenow_knowledge_agent":
            knowledge_url = agent["mcp_servers"][0]["server_params"]["url"]
    
    assert "3001" in table_url, "Table API should use port 3001"
    assert "3002" in knowledge_url, "Knowledge API should use port 3002"


def test_server_names_consistent():
    """Test that server names use underscores consistently."""
    config_path = Path("servicenow_final_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    for agent in config.get("mcp_agent_configs", []):
        for server in agent.get("mcp_servers", []):
            server_name = server["server_name"]
            assert " " not in server_name, f"Server name '{server_name}' should not contain spaces"
            assert "_" in server_name, f"Server name '{server_name}' should use underscores"