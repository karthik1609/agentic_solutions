#!/usr/bin/env python3
"""
ServiceNow Table API MCP Server - HTTP Transport
HTTP-based MCP server for ServiceNow Table API
"""

import pathlib
import json
import httpx
import os
from dotenv import load_dotenv, find_dotenv
from fastmcp import FastMCP

def main():
    load_dotenv(find_dotenv())
    
    SN_INSTANCE = os.environ['SERVICENOW_INSTANCE_URL'].rstrip('/')
    SN_USER = os.environ['SERVICENOW_USERNAME']
    SN_PASS = os.environ['SERVICENOW_PASSWORD']
    
    spec_path = pathlib.Path('openapi_specs/servicenow_table_api_final.json')
    if not spec_path.exists():
        raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")
    
    spec = json.loads(spec_path.read_text())
    
    client = httpx.AsyncClient(
        base_url=SN_INSTANCE,
        auth=(SN_USER, SN_PASS),
        verify=False,
        timeout=30.0
    )
    
    mcp = FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name='ServiceNow Table API'
    )
    
    print("🚀 Starting ServiceNow Table API MCP Server (HTTP)")
    print(f"📡 Port: 3001")
    print(f"🔗 ServiceNow Instance: {SN_INSTANCE}")
    print("✅ Ready for HTTP requests")
    
    # FastMCP HTTP transport for Magentic-UI integration
    mcp.run(transport="http", host="localhost", port=3001)

if __name__ == "__main__":
    main()