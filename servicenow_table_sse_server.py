#!/usr/bin/env python3
"""
ServiceNow Table API MCP Server with SSE Transport
Provides access to ServiceNow Table API operations via FastMCP with HTTP/SSE
"""

import asyncio
import pathlib
import json
import httpx
import os
from dotenv import load_dotenv, find_dotenv
from fastmcp import FastMCP

def main():
    # Load environment variables
    load_dotenv(find_dotenv())
    
    SN_INSTANCE = os.environ['SERVICENOW_INSTANCE_URL'].rstrip('/')
    SN_USER = os.environ['SERVICENOW_USERNAME']
    SN_PASS = os.environ['SERVICENOW_PASSWORD']
    
    # Load OpenAPI spec
    spec_path = pathlib.Path('openapi_specs/servicenow_table_api_final.json')
    if not spec_path.exists():
        raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")
    
    spec = json.loads(spec_path.read_text())
    
    # Create HTTP client with ServiceNow authentication
    client = httpx.AsyncClient(
        base_url=SN_INSTANCE,
        auth=(SN_USER, SN_PASS),
        verify=False,
        timeout=30.0
    )
    
    # Create FastMCP server from OpenAPI spec
    mcp = FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name='ServiceNow Table API'
    )
    
    # FastMCP handles SSE internally with run() method
    mcp.run(transport="sse", host="localhost", port=3001)

if __name__ == "__main__":
    main()