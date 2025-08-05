# ServiceNow MCP Agent System

A comprehensive integration system that connects ServiceNow REST APIs with Magentic-UI through the Model Context Protocol (MCP), enabling AI agents to interact directly with ServiceNow instances.

## 🚀 Features

- **ServiceNow Table API Agent**: Full CRUD operations on any ServiceNow table (incidents, users, changes, etc.)
- **ServiceNow Knowledge Management Agent**: Search and manage knowledge articles using the Knowledge Management REST API
- **HTTP Transport**: Reliable MCP server communication using HTTP protocol
- **Daemon Management**: Production-ready start/stop/status scripts with PID management
- **Auto-discovery**: Automatically generates OpenAPI specifications from ServiceNow APIs
- **Magentic-UI Integration**: Seamless integration with Magentic-UI's agent ecosystem

## 📋 Prerequisites

- Python 3.11+
- Docker (for Magentic-UI)
- ServiceNow instance with REST API access
- UV package manager (recommended) or pip

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/karthik1609/agentic_solutions.git
   cd agentic_solutions
   ```

2. **Set up the virtual environment**:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   uv sync
   ```

4. **Configure ServiceNow credentials**:
   Create a `.env` file in the project root:
   ```env
   SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
   SERVICENOW_USERNAME=your_username
   SERVICENOW_PASSWORD=your_password
   ```

## 🎯 Quick Start

### Start with HTTP Transport (default)

```bash
# Start all services (MCP servers + Magentic-UI) using HTTP
uv run python start_servicenow_http_system.py
```

This will:
- Start ServiceNow Table API MCP server on port 3001
- Start ServiceNow Knowledge Management API MCP server on port 3002
- Launch Magentic-UI on port 8090 with ServiceNow agents configured

### Start with SSE Transport

```bash
# Start all services using SSE transport
uv run python start_servicenow_sse_system.py
```

### Access the System

Open your browser and navigate to: **http://localhost:8090**

### Available Agents

Once running, you'll have access to:

- **servicenow_table_agent**: CRUD operations on ServiceNow tables
- **servicenow_knowledge_agent**: Knowledge article search and management
- **Default agents**: web_surfer, coder_agent, file_surfer, user_proxy

### Stop the System

```bash
# Stop all services
uv run python stop_servicenow_system.py
```

### Check System Status

```bash
# HTTP mode (default after start_servicenow_http_system.py)
uv run python status_servicenow_system.py

# SSE mode
uv run python status_servicenow_system.py --transport sse
```

You can also override specific health-check endpoints:

```bash
TABLE_HEALTH_URL=http://localhost:3001/mcp/ \
KNOWLEDGE_HEALTH_URL=http://localhost:3002/mcp/ \
uv run python status_servicenow_system.py
```

## 🔧 Configuration

The system uses `servicenow_final_config.yaml` for Magentic-UI configuration. Key components:

- **HTTP MCP Servers**: ServiceNow APIs exposed as MCP tools
- **Agent Definitions**: ServiceNow-specific agents with custom system messages
- **OpenAPI Integration**: Automatic tool generation from ServiceNow API specifications

## 📁 Project Structure

```
agentic_solutions/
├── servicenow_table_http_server.py      # Table API MCP server
├── servicenow_knowledge_http_server.py  # Knowledge API MCP server
├── servicenow_final_config.yaml         # Magentic-UI configuration
├── start_servicenow_http_system.py      # System startup script
├── stop_servicenow_system.py            # System shutdown script
├── status_servicenow_system.py          # System status checker
├── create_final_servicenow_specs.py     # OpenAPI spec generator
├── cleanup_junk.py                      # Cleanup utility
├── openapi_specs/                       # Generated OpenAPI specifications
├── .pids/                              # Process ID files
└── .env                                # ServiceNow credentials (not in repo)
```

## 🔌 API Coverage

### Table API
- GET, POST, PUT, PATCH, DELETE operations
- Query with encoded queries and filters
- Aggregate operations
- Batch operations
- All ServiceNow tables (incident, sys_user, change_request, etc.)

### Knowledge Management API  
- Search articles by query terms
- Get articles by ID
- Featured and most viewed articles
- Recent articles
- Article creation and updates
- Full sn_km_api namespace support

## 🛡️ Security

- Credentials stored in `.env` file (excluded from Git)
- HTTPS verification disabled for development (configurable)
- Authentication via ServiceNow username/password
- Local-only MCP server endpoints

## 🔄 Development

### Adding New APIs

1. **Discover APIs**:
   ```bash
   uv run python create_final_servicenow_specs.py
   ```

2. **Create MCP Server**: Follow the pattern in existing server files

3. **Update Configuration**: Add agent configuration to `servicenow_final_config.yaml`

### Testing MCP Endpoints

```bash
# Test HTTP MCP endpoints directly
uv run python test_http_mcp.py
```

### Cleanup Development Files

```bash
# Remove temporary files and logs
uv run python cleanup_junk.py
```

## 📚 Dependencies

- **FastMCP**: MCP server framework with OpenAPI integration
- **Magentic-UI**: AI agent interface and orchestration
- **httpx**: Async HTTP client for ServiceNow API calls
- **uvicorn**: ASGI server for MCP HTTP transport
- **python-dotenv**: Environment variable management
- **pyyaml**: YAML configuration parsing

## 🐛 Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 3001, 3002, and 8090 are available
2. **Docker not running**: Start Docker Desktop before launching
3. **ServiceNow credentials**: Verify `.env` file configuration
4. **Agent not visible**: Try refreshing browser or starting new session

### Logs

- MCP server logs: Check terminal output
- Magentic-UI logs: Available in the web interface
- Process status: Use `status_servicenow_system.py`

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review Magentic-UI and FastMCP documentation

---

**Built with ❤️ for ServiceNow automation and AI-powered workflows**