#!/usr/bin/env python3
"""
ServiceNow Knowledge Management API MCP Server with SSE Transport
Provides access to ServiceNow Knowledge Management REST API operations via FastMCP with HTTP/SSE
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
    VERIFY_SSL = os.getenv('SERVICENOW_VERIFY_SSL', 'true').lower() not in ('false', '0', 'no')
    
    # Load OpenAPI spec
    spec_path = pathlib.Path('openapi_specs/servicenow_knowledge_api_final.json')
    if not spec_path.exists():
        raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")
    
    spec = json.loads(spec_path.read_text())
    
    # Update server URL in OpenAPI spec to match current instance
    if 'servers' in spec and len(spec['servers']) > 0:
        spec['servers'][0]['url'] = SN_INSTANCE
    
    async def run_server():
        async with httpx.AsyncClient(
            base_url=SN_INSTANCE,
            auth=(SN_USER, SN_PASS),
            verify=VERIFY_SSL,
            timeout=30.0
        ) as client:
            # Create FastMCP server from OpenAPI spec
            mcp = FastMCP.from_openapi(
                openapi_spec=spec,
                client=client,
                name='ServiceNow_Knowledge_API'  # Use underscores for consistency
            )
            
            print("🚀 Starting ServiceNow Knowledge Management API MCP Server (SSE)")
            print(f"📡 Port: 3002")
            print(f"🔗 ServiceNow Instance: {SN_INSTANCE}")
            print("✅ Ready for SSE requests")
            
            # FastMCP handles SSE internally with run() method
            mcp.run(transport="sse", host="localhost", port=3002)
    
    asyncio.run(run_server())

if __name__ == "__main__":
    main()