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

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI

# Add parent directory to path for imports
import sys

from pydantic import BaseModel

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Observability imports
from observability import init_observability, get_logger

CHROMA_PATH = r"chroma_db"

def query_validator(query: str) -> bool:
    logger = init_observability(
        service_name="service-now-table-rag-validator",
        service_version="1.0.0"
    )

    # Initialize OpenAI and embeddings
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY")
    )

    logger.info("openai client initialized")

    # Load an existing vector store
    vectorstore = Chroma(
        collection_name="validation_policy",
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH
    )

    logger.info("Vector store initialized")

    # Ask user
    user_query = query

    # Retrieve top relevant chunks
    docs = vectorstore.similarity_search(user_query, k=4)

    logger.info("Similarity search done")

    # Format context
    context = "\n\n".join([doc.page_content for doc in docs])

    # Debug retrieved content
    # print("\n🔍 Retrieved Context:\n")
    # for i, doc in enumerate(docs, start=1):
    #     print(f"--- Chunk {i} ---")
    #     print(doc.page_content[:300] + "...")
    #     print()

    # Build system prompt
    system_prompt = f"""
    You are a helpful assistant that validates a user's API call requests
    Use ONLY the following context to answer the question.
    If the answer is not contained in the context, say you don't know.
    Whenever using a tool, ALWAYS include the user's original query in the users_original_query

    CONTEXT:
    {context}
    """
    logger.info("System prompt built")
    logger.info("Context built: {}".format(context))

    class Approval(BaseModel):
        approval: bool = False
        reason: str = ""

    # Query OpenAI
    response = openai_client.responses.parse(
        model="gpt-5-nano",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        text_format=Approval
    )

    logger.info("openai response built")

    logger.info(response.output_parsed.reason)

    return response.output_parsed.approval

class GuardedAsyncClient(httpx.AsyncClient):
    async def request(self, method, url, *args, **kwargs):
        logger = init_observability(
            service_name="service-now-table-api-guardedClient",
            service_version="1.0.0"
        )


        body = kwargs.get("json")
        if not body:
            body = {}

        # Get only the relevant part of the api call
        # url = url.split(".com")[1]

        # Convert to text for RAG
        user_query = f"""
        I want to send an API request to the Table API with the following method:
        {str(method)}
        the following url:
        {str(url)}
        and the following body:
        {str(body)}
        Based on the TableAPI policy, am I allowed to do so?
        """

        logger.info(f"Body of validation check : {body}")

        if not query_validator(user_query):
            raise RuntimeError("Invalid User Query")

        return await super().request(method, url, *args, **kwargs)

def main():
    # Initialize observability stack
    logger = init_observability(
        service_name="servicenow-table-api-sse",
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
    spec_path = pathlib.Path('openapi_specs/servicenow_table_api_final.json')
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
        client = GuardedAsyncClient(
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
            name='ServiceNow_Table_API'
        )
        
        logger.info("server_starting", 
                   service="ServiceNow Table API MCP Server",
                   transport="SSE",
                   port=3001,
                   instance=SN_INSTANCE)
        
        print(" Starting ServiceNow Table API MCP Server (SSE)")
        print(f" Port: 3001")
        print(f" ServiceNow Instance: {SN_INSTANCE}")
        print(" Ready for SSE requests")
        
        # Let FastMCP handle the event loop
        logger.info("mcp_server_running", host="localhost", port=3001)
        mcp.run(transport="sse", host="localhost", port=3001)
        
    except KeyboardInterrupt:
        logger.info("server_shutdown_requested")
    except Exception as e:
        logger.error("server_startup_failed", error=str(e), exc_info=True)
        return 1
    finally:
        logger.info("server_shutdown_complete")

if __name__ == "__main__":
    main()