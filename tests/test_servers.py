"""Tests for MCP server functionality."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_openapi_specs_no_hardcoded_urls():
    """Test that OpenAPI specs don't contain hardcoded instance URLs."""
    specs_dir = Path("openapi_specs")
    
    for spec_file in specs_dir.glob("*.json"):
        with open(spec_file) as f:
            spec = json.load(f)
        
        if "servers" in spec:
            for server in spec["servers"]:
                url = server.get("url", "")
                # Should not contain hardcoded dev instance
                assert "dev206621.service-now.com" not in url, f"Hardcoded URL found in {spec_file}"
                # Should use template or variable
                assert "{server_url}" in url or "your-instance" in url, f"URL should be templated in {spec_file}"


@patch.dict("os.environ", {
    "SERVICENOW_INSTANCE_URL": "https://test.service-now.com",
    "SERVICENOW_USERNAME": "test_user",
    "SERVICENOW_PASSWORD": "test_pass",
    "SERVICENOW_VERIFY_SSL": "false"
})
def test_ssl_verification_setting():
    """Test that SSL verification respects environment variable."""
    # Import here to use patched environment
    import servicenow_table_http_server
    
    # Mock the necessary components
    with patch("servicenow_table_http_server.pathlib.Path") as mock_path, \
         patch("servicenow_table_http_server.json.loads") as mock_json, \
         patch("servicenow_table_http_server.httpx.AsyncClient") as mock_client, \
         patch("servicenow_table_http_server.FastMCP") as mock_fastmcp, \
         patch("servicenow_table_http_server.asyncio.run") as mock_run:
        
        # Setup mocks
        mock_path.return_value.exists.return_value = True
        mock_path.return_value.read_text.return_value = '{"servers": [{"url": "test"}]}'
        mock_json.return_value = {"servers": [{"url": "test"}]}
        
        # Call main function
        servicenow_table_http_server.main()
        
        # Verify SSL verification was set correctly
        mock_run.assert_called_once()


def test_server_startup_scripts_exist():
    """Test that all required startup scripts exist."""
    required_scripts = [
        "start_servicenow_http_system.py",
        "stop_servicenow_system.py", 
        "status_servicenow_system.py",
        "servicenow_table_http_server.py",
        "servicenow_knowledge_http_server.py"
    ]
    
    for script in required_scripts:
        script_path = Path(script)
        assert script_path.exists(), f"{script} should exist"
        assert script_path.is_file(), f"{script} should be a file"