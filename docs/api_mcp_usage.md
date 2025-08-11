## ServiceNow API and MCP SSE Usage Guide

This guide shows how to call ServiceNow Table and Knowledge APIs both directly via REST and through local MCP SSE servers.

Assumes a `.env` with:

```
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=your_username
SERVICENOW_PASSWORD=your_password
SERVICENOW_VERIFY_SSL=true
TABLE_MCP_SSE_URL=http://localhost:3001/sse
KNOWLEDGE_MCP_SSE_URL=http://localhost:3002/sse
```

### Start local MCP servers
- Table SSE server: `uv run python mcp_agents/servicenow_table_sse_server.py`  (source: `mcp_agents/servicenow_table_sse_server.py`)
- Knowledge SSE server: `uv run python mcp_agents/servicenow_knowledge_sse_server.py`  (source: `mcp_agents/servicenow_knowledge_sse_server.py`)

Related utilities:
- Quick SSE check: `scripts/check_mcp_sse.py`
- Probe via MCP and call tools: `scripts/probe_mcp_via_api.py`

OpenAPI specs used by the MCP servers:
- `openapi_specs/servicenow_table_api_final.json`
- `openapi_specs/servicenow_knowledge_api_final.json`

---

### REST setup (requests)

```python
import os, json, requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()
BASE = os.environ["SERVICENOW_INSTANCE_URL"].rstrip("/")
AUTH = HTTPBasicAuth(os.environ["SERVICENOW_USERNAME"], os.environ["SERVICENOW_PASSWORD"]) 
VERIFY = str(os.getenv("SERVICENOW_VERIFY_SSL", "true")).lower() not in {"false","0","no"}
HEADERS = {"Accept":"application/json","Content-Type":"application/json"}
```

### Table API (REST)

- List records
```python
def list_table_records(table_name, sysparm_query=None, sysparm_fields=None, limit=10, offset=0):
    params = {"sysparm_limit": limit, "sysparm_offset": offset}
    if sysparm_query: params["sysparm_query"] = sysparm_query
    if sysparm_fields: params["sysparm_fields"] = sysparm_fields
    r = requests.get(f"{BASE}/api/now/table/{table_name}", auth=AUTH, headers=HEADERS, params=params, verify=VERIFY)
    r.raise_for_status()
    return r.json()["result"]
# Example
records = list_table_records("incident", sysparm_query="active=true", limit=5)
```

- Get record
```python
def get_table_record(table_name, sys_id):
    r = requests.get(f"{BASE}/api/now/table/{table_name}/{sys_id}", auth=AUTH, headers=HEADERS, verify=VERIFY)
    r.raise_for_status()
    return r.json()["result"]
```

- Create record
```python
def create_table_record(table_name, data: dict):
    r = requests.post(f"{BASE}/api/now/table/{table_name}", auth=AUTH, headers=HEADERS, data=json.dumps(data), verify=VERIFY)
    r.raise_for_status()
    return r.json()["result"]
# Example
created = create_table_record("incident", {"short_description":"Test via REST","description":"Created by script"})
```

- Update record
```python
def update_table_record(table_name, sys_id, data: dict):
    r = requests.patch(f"{BASE}/api/now/table/{table_name}/{sys_id}", auth=AUTH, headers=HEADERS, data=json.dumps(data), verify=VERIFY)
    r.raise_for_status()
    return r.json()["result"]
```

- Delete record
```python
def delete_table_record(table_name, sys_id):
    r = requests.delete(f"{BASE}/api/now/table/{table_name}/{sys_id}", auth=AUTH, headers=HEADERS, verify=VERIFY)
    r.raise_for_status()
    return True
```

### Knowledge API (REST)

```python
# Search articles

def search_knowledge(query, kb=None, language="en", limit=10, offset=0):
    params = {"query": query, "sysparm_limit": limit, "sysparm_offset": offset, "language": language}
    if kb: params["kb"] = kb
    r = requests.get(f"{BASE}/api/sn_km_api/knowledge/articles", auth=AUTH, headers=HEADERS, params=params, verify=VERIFY)
    r.raise_for_status()
    return r.json()

# Featured

def get_featured_articles(limit=10):
    params = {"sysparm_limit": limit}
    r = requests.get(f"{BASE}/api/sn_km_api/knowledge/featured", auth=AUTH, headers=HEADERS, params=params, verify=VERIFY)
    r.raise_for_status()
    return r.json()

# Most viewed

def get_most_viewed_articles(limit=10):
    params = {"sysparm_limit": limit}
    r = requests.get(f"{BASE}/api/sn_km_api/knowledge/mostviewed", auth=AUTH, headers=HEADERS, params=params, verify=VERIFY)
    r.raise_for_status()
    return r.json()

# Get one article by sys_id

def get_knowledge_article(sys_id: str):
    r = requests.get(f"{BASE}/api/sn_km_api/knowledge/articles/{sys_id}", auth=AUTH, headers=HEADERS, verify=VERIFY)
    r.raise_for_status()
    return r.json()
```

---

### MCP SSE setup (fastmcp)

```python
import os, asyncio
from dotenv import load_dotenv
from fastmcp.client.client import Client

load_dotenv()
TABLE_MCP = os.environ["TABLE_MCP_SSE_URL"]
KNOW_MCP = os.environ["KNOWLEDGE_MCP_SSE_URL"]

async def call_mcp(url: str, tool: str, params: dict):
    client = Client(url, init_timeout=15)
    async with client:
        return await client.call_tool(tool, params)
```

### Table API (via MCP SSE)

- List records
```python
# listTableRecords(table_name, sysparm_query?, sysparm_fields?, sysparm_limit?, sysparm_offset?)
async def mcp_list_incidents():
    res = await call_mcp(TABLE_MCP, "listTableRecords", {
        "table_name": "incident",
        "sysparm_query": "active=true",
        "sysparm_limit": 5
    })
    print(res)
```

- Get record
```python
async def mcp_get_incident(sys_id: str):
    res = await call_mcp(TABLE_MCP, "getTableRecord", {
        "table_name": "incident",
        "sys_id": sys_id
    })
    print(res)
```

- Create record
```python
# createTableRecord(table_name, body)
async def mcp_create_incident():
    res = await call_mcp(TABLE_MCP, "createTableRecord", {
        "table_name": "incident",
        "body": {
            "short_description": "Test via MCP",
            "description": "Created through FastMCP SSE"
        }
    })
    print(res)
```

- Update record
```python
# updateTableRecord(table_name, sys_id, body)
async def mcp_update_incident(sys_id: str):
    res = await call_mcp(TABLE_MCP, "updateTableRecord", {
        "table_name": "incident",
        "sys_id": sys_id,
        "body": {"state": "2", "comments": "Updated via MCP"}
    })
    print(res)
```

- Delete record
```python
# deleteTableRecord(table_name, sys_id)
async def mcp_delete_incident(sys_id: str):
    res = await call_mcp(TABLE_MCP, "deleteTableRecord", {
        "table_name": "incident",
        "sys_id": sys_id
    })
    print(res)
```

### Knowledge API (via MCP SSE)

- Search articles
```python
# searchKnowledgeArticles(query, kb?, language?, sysparm_limit?, sysparm_offset?)
async def mcp_search_knowledge():
    res = await call_mcp(KNOW_MCP, "searchKnowledgeArticles", {
        "query": "windows",
        "sysparm_limit": 5
    })
    print(res)
```

- Featured
```python
# getFeaturedArticles(sysparm_limit?)
async def mcp_featured():
    res = await call_mcp(KNOW_MCP, "getFeaturedArticles", {"sysparm_limit": 5})
    print(res)
```

- Most viewed
```python
# getMostViewedArticles(sysparm_limit?)
async def mcp_most_viewed():
    res = await call_mcp(KNOW_MCP, "getMostViewedArticles", {"sysparm_limit": 5})
    print(res)
```

- Get one article
```python
# getKnowledgeArticle(sys_id)
async def mcp_get_article(sys_id: str):
    res = await call_mcp(KNOW_MCP, "getKnowledgeArticle", {"sys_id": sys_id})
    print(res)
```

---

### Example runner

```python
import asyncio

async def main():
    await mcp_list_incidents()
    await mcp_search_knowledge()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Code references in this repository
- `mcp_agents/servicenow_table_sse_server.py`
- `mcp_agents/servicenow_knowledge_sse_server.py`
- `scripts/check_mcp_sse.py`
- `scripts/probe_mcp_via_api.py`
- `openapi_specs/servicenow_table_api_final.json`
- `openapi_specs/servicenow_knowledge_api_final.json`
