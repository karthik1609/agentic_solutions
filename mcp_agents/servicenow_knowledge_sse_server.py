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

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Observability imports
from observability import init_observability, get_logger

def main():
    # Initialize observability stack
    logger = init_observability(
        service_name="servicenow-knowledge-api-sse",
        service_version="1.0.0"
    )
    
    # Load environment variables
    load_dotenv(find_dotenv())
    
    SN_INSTANCE = os.environ['SERVICENOW_INSTANCE_URL'].rstrip('/')
    SN_USER = os.environ['SERVICENOW_USERNAME']
    SN_PASS = os.environ['SERVICENOW_PASSWORD']
    VERIFY_SSL = os.getenv('SERVICENOW_VERIFY_SSL', 'true').lower() not in ('false', '0', 'no')
    
    logger.info("server_config_loaded", 
               instance=SN_INSTANCE,
               ssl_verification=VERIFY_SSL,
               username=SN_USER)
    
    # Load OpenAPI spec
    spec_path = pathlib.Path('openapi_specs/servicenow_knowledge_api_final.json')
    if not spec_path.exists():
        logger.error("openapi_spec_not_found", spec_path=str(spec_path))
        raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")
    
    spec = json.loads(spec_path.read_text())
    logger.info("openapi_spec_loaded", 
               spec_path=str(spec_path),
               endpoints_count=len(spec.get('paths', {})))
    
    # Update server URL in OpenAPI spec to match current instance
    if 'servers' in spec and len(spec['servers']) > 0:
        spec['servers'][0]['url'] = SN_INSTANCE
        logger.debug("openapi_server_url_updated", new_url=SN_INSTANCE)
    
    
    try:
        # Create the server synchronously and let FastMCP handle the event loop
        with open(spec_path) as f:
            spec = json.load(f)
        
        # Update server URL in OpenAPI spec to match current instance
        if 'servers' in spec and len(spec['servers']) > 0:
            spec['servers'][0]['url'] = SN_INSTANCE
            logger.debug("openapi_server_url_updated", new_url=SN_INSTANCE)
        
        logger.info("http_client_starting", 
                   base_url=SN_INSTANCE, 
                   timeout=30.0)
        
        # Create HTTP client
        client = httpx.AsyncClient(
            base_url=SN_INSTANCE,
            auth=(SN_USER, SN_PASS),
            verify=VERIFY_SSL,
            timeout=30.0
        )
        
        logger.info("fastmcp_server_creating")
        
        # Create FastMCP server from OpenAPI spec
        mcp = FastMCP.from_openapi(
            openapi_spec=spec,
            client=client,
            name='ServiceNow_Knowledge_API'
        )
        
        logger.info("server_starting", 
                   service="ServiceNow Knowledge API MCP Server",
                   transport="SSE",
                   port=3002,
                   instance=SN_INSTANCE)
        
        print(" Starting ServiceNow Knowledge API MCP Server (SSE)")
        print(f" Port: 3002")
        print(f" ServiceNow Instance: {SN_INSTANCE}")
        print(" Ready for SSE requests")
        
        # Let FastMCP handle the event loop
        logger.info("mcp_server_running", host="localhost", port=3002)
        mcp.run(transport="sse", host="localhost", port=3002)
        
    except KeyboardInterrupt:
        logger.info("server_shutdown_requested")
    except Exception as e:
        logger.error("server_startup_failed", error=str(e), exc_info=True)
        return 1
    finally:
        logger.info("server_shutdown_complete")

if __name__ == "__main__":
    main()