#  ServiceNow MCP System

A comprehensive, production-ready ServiceNow integration system using the Model Context Protocol (MCP) with full observability, automated agent discovery, and a unified management interface.

##  Features

###  **Core Functionality**
- ** Auto-Discovery MCP Agents**: Automatically discovers and starts all MCP agents in the `mcp_agents/` folder
- ** Magentic-UI Integration**: Beautiful web interface for interacting with AI agents
- ** Full Observability**: OpenTelemetry-based monitoring with structured logging, metrics, and distributed tracing
- ** SSE-Based Communication**: Server-Sent Events for real-time, efficient communication
- ** One-Command Startup**: Single script starts the entire system

###  **Architecture**
- **ServiceNow Table API Agent**: Full CRUD operations on ServiceNow tables
- **ServiceNow Knowledge Management Agent**: Search and manage knowledge articles
- **Extensible Agent Framework**: Easy to add new MCP agents
- **Production-Ready Observability**: LGTM stack (Loki, Grafana, Tempo, Mimir) + Pyroscope

###  **Production Features**
- **Comprehensive Error Handling**: Graceful degradation and recovery
- **Health Monitoring**: Automatic health checks for all components
- **Structured Logging**: JSON logs with trace correlation
- **Signal Handling**: Proper cleanup on shutdown
- **Environment Management**: Secure credential handling

##  Quick Start

### Prerequisites
- Python 3.10-3.12
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- ServiceNow instance with API access
- OpenAI API key (optional, for AI agents)

### Installation

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd servicenow-mcp-system
   uv sync  # or pip install -e .
   ```

2. **Configure Environment**
   ```bash
   cp env.template .env
   # Edit .env with your credentials:
   # - SERVICENOW_INSTANCE_URL
   # - SERVICENOW_USERNAME  
   # - SERVICENOW_PASSWORD
   # - OPENAI_API_KEY
   ```

3. **Start the System**
   ```bash
   python start_system.py
   ```

4. **Access the Interface**
   - **Magentic-UI**: http://localhost:8081
   - **ServiceNow Table API**: http://localhost:3001/sse
   - **ServiceNow Knowledge API**: http://localhost:3002/sse

##  Project Structure

```
servicenow-mcp-system/
 start_system.py              #  Single entrypoint script
 observability.py             #  Observability configuration
 servicenow_final_config.yaml #  Magentic-UI configuration
 mcp_agents/                  #  Auto-discovered MCP agents
    servicenow_table_sse_server.py
    servicenow_knowledge_sse_server.py
 observability/               #  Observability stack configs
    otel-collector.yaml
    docker-compose.observability.yml
 openapi_specs/               #  API specifications
 tests/                       #  Comprehensive test suite
 logs/                        #  Application logs
 docs/                        #  Documentation
```

##  Usage

### Starting the System

```bash
# Start everything (recommended)
python start_system.py

# Start without observability (faster startup)
python start_system.py --no-observability

# Start without UI (agents only)
python start_system.py --no-ui

# Use custom config
python start_system.py --config my_config.yaml
```

### System Management

```bash
# Check system status
python start_system.py --status

# Stop the system
python start_system.py --stop

# Or use Ctrl+C to stop gracefully
```

### Adding New MCP Agents

1. **Create your agent script** in `mcp_agents/`:
   ```python
   # mcp_agents/my_custom_agent.py
   from fastmcp import FastMCP
   
   mcp = FastMCP("My Custom Agent")
   
   @mcp.tool()
   def my_tool(query: str) -> str:
       return f"Processed: {query}"
   
   if __name__ == "__main__":
       mcp.run(transport="sse", host="localhost", port=3003)
   ```

2. **Update Magentic-UI config** to include your agent:
   ```yaml
   # servicenow_final_config.yaml
   mcp_agent_configs:
     - name: my_custom_agent
       mcp_servers:
         - server_name: My_Custom_Agent
           server_params:
             type: SseServerParams
             url: "http://localhost:3003/sse"
   ```

3. **Restart the system** - your agent will be auto-discovered!

##  Observability

The system includes comprehensive observability out of the box:

###  **Monitoring Stack**
- **OpenTelemetry**: Distributed tracing and metrics
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization dashboards
- **Loki**: Log aggregation
- **Tempo**: Distributed tracing storage
- **Pyroscope**: Continuous profiling

###  **Logging**
- **Structured JSON logs** with trace correlation
- **Multiple log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Automatic log rotation**: 50MB main logs, 10MB error logs
- **Component-specific loggers** for all services

###  **Health Monitoring**
- **Automatic health checks** for all components
- **Endpoint monitoring** with HTTP status checks
- **Process monitoring** with PID tracking
- **Resource usage tracking**

###  **Starting Observability Stack**
```bash
# Start the full LGTM + Pyroscope stack
cd observability/
docker-compose -f docker-compose.observability.yml up -d

# Access dashboards:
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
# - Pyroscope: http://localhost:4040
```

##  Testing

Comprehensive test suite with multiple test categories:

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/test_comprehensive.py::TestEnvironmentSetup -v
uv run pytest tests/test_comprehensive.py::TestMCPServers -v
uv run pytest tests/test_comprehensive.py::TestObservabilityStack -v

# Run with coverage
uv run pytest --cov=. --cov-report=html
```

### Test Categories
- **Environment Setup**: Configuration and credentials
- **MCP Servers**: Agent functionality and imports
- **Observability Stack**: Logging and monitoring
- **Service Integration**: End-to-end connectivity
- **Error Scenarios**: Failure handling and recovery

##  Configuration

### Environment Variables
```bash
# ServiceNow Configuration
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=your_username
SERVICENOW_PASSWORD=your_password
SERVICENOW_VERIFY_SSL=true

# OpenAI Configuration (Optional)
OPENAI_API_KEY=your_openai_api_key_here

# System Configuration
MAGENTIC_UI_PORT=8081
LOG_LEVEL=INFO
```

### Magentic-UI Configuration
The `servicenow_final_config.yaml` file configures:
- **Model clients** (OpenAI GPT-4o by default)
- **Agent configurations** and system messages
- **MCP server connections** (SSE endpoints)
- **Security and authentication settings**

##  Troubleshooting

### Common Issues

** "Already running asyncio in this thread"**
- **Cause**: Event loop conflicts (fixed in current version)
- **Solution**: Use the latest SSE servers in `mcp_agents/`

** "Connection refused" to MCP servers**
- **Cause**: Servers not started or port conflicts
- **Solution**: Check logs in `logs/` folder, verify ports 3001-3002 are free

** "Incorrect API key provided"**
- **Cause**: OpenAI API key not set or malformed
- **Solution**: Check `.env` file and ensure `OPENAI_API_KEY` is valid

** Magentic-UI shows "An error occurred"**
- **Cause**: MCP agents not responding or configuration mismatch
- **Solution**: Verify SSE endpoints are running: `curl http://localhost:3001/sse`

### Log Analysis
```bash
# Analyze logs for issues
python log_analyzer.py

# Check specific component logs
tail -f logs/servicenow-table-api-sse.log
tail -f logs/magentic-ui.log
```

### Health Checks
```bash
# Manual health checks
curl http://localhost:8081        # Magentic-UI
curl http://localhost:3001/sse    # Table API
curl http://localhost:3002/sse    # Knowledge API

# System status
python start_system.py --status
```

##  Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** with proper tests
4. **Run the test suite**: `uv run pytest`
5. **Submit a pull request**

### Development Setup
```bash
# Install development dependencies
uv sync --extra dev

# Run linting
ruff check .
ruff format .

# Run type checking  
mypy .

# Install pre-commit hooks
pre-commit install
```

##  License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

##  Acknowledgments

- **[FastMCP](https://github.com/jlowin/fastmcp)**: Excellent MCP framework
- **[Magentic-UI](https://github.com/magentic-ai/magentic-ui)**: Beautiful AI agent interface
- **[OpenTelemetry](https://opentelemetry.io/)**: Comprehensive observability
- **[ServiceNow](https://www.servicenow.com/)**: Enterprise service management platform

##  Roadmap

- [ ] **Multi-tenant support** for multiple ServiceNow instances
- [ ] **Custom dashboard templates** for common ServiceNow workflows  
- [ ] **Advanced agent orchestration** with workflow management
- [ ] **Real-time collaboration** features
- [ ] **Plugin marketplace** for community-contributed agents
- [ ] **Advanced security features** (RBAC, audit logging)
- [ ] **Performance optimization** and caching layers

---

** Ready to revolutionize your ServiceNow automation? Get started now!**

For questions, issues, or contributions, please visit our [GitHub repository](https://github.com/your-org/servicenow-mcp-system).