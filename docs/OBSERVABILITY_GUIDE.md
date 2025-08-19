#  Observability & Telemetry Guide

Welcome to the **ServiceNow MCP System** observability guide.  
This document shows you **where to look** and **what to do** to understand _everything_ happening in the stack  logs, metrics, traces, and profiles.

> **TL;DR**  Start Docker (`Docker Desktop` / `colima` / `dockerd`) and run:
> ```bash
> python start_system.py           # starts MCP agents, Magentic-UI, LGTM + Pyroscope
> open http://localhost:3000       # Grafana  one-stop observability portal
> ```

---
##   Stack Topology

| Layer | Component | URL | Notes |
|-------|-----------|-----|-------|
| **UI** | **Grafana** | <http://localhost:3000> | Dashboards for logs  metrics  traces  profiles. Login: `admin / admin` |
| | Magentic-UI | <http://localhost:8080> | Interact with MCP agents |
| **Logs** | **Loki** | n/a (queried via Grafana) | Stores JSON logs from every process |
| **Metrics** | **Prometheus** | <http://localhost:9090> | Scrapes MCP + system metrics |
| **Traces** | **Tempo** | n/a (queried via Grafana) | OTLP traces visualised in Grafana |
| **Profiles** | **Pyroscope** | <http://localhost:4040> | CPU/Wall-time flame-graphs |
| **Glue** | **OTel-Collector** | :4317 / :4318 | Receives OTLP, fan-out to back-ends |

---
##  1. Starting the Stack

```bash
# 1. Ensure Docker is ON (Docker Desktop / colima / docker-desktop)
# 2. Start entire system  agents + observability + UI
python start_system.py

# Optional flags
python start_system.py --no-ui            # agents + observability only
python start_system.py --no-observability # agents + UI, no LGTM stack
python start_system.py --status           # show live component/endpoint status
```
The first run automatically pulls all required Docker images ( 600 MB). Subsequent runs start in seconds.

> Old `.log` files are **purged on every start** (see `clear_old_logs()`), so you only see fresh telemetry.

Once the script prints  _System started successfully!_ visit the endpoints above.

---
##  2. Grafana  The Single Pane of Glass

### 2.1 Login & Data-sources
1. Open **Grafana**  <http://localhost:3000>  
2. Credentials  `admin / admin` (you will be prompted to change).
3. Pre-provisioned data-sources (see `observability/grafana/provisioning/`):
   * **Prometheus**  metrics
   * **Loki**  logs
   * **Tempo**  traces (with log-exemplar correlation)
   * **Pyroscope**  continuous profiles

### 2.2 Dashboards
Grafana ships with sample dashboards  import or build your own.

* _Home  +  Import_ and paste a dashboard ID from <https://grafana.com/grafana/dashboards> e.g.:
  * **15172**  Prometheus / ETL System
  * **13659**  Loki / Log volume & rate
  * **17476**  Pyroscope / CPU Flame-graph

> **TIP**: when Tempo + Loki are configured, click **``** on a trace span  **_Logs_** to jump straight to correlated log lines.

---
##  3. Exploring Logs (Loki)

1. Grafana  _Loki Explorer_ (left menu **_Explore_**).
2. Select **Loki** data-source.
3. Sample queries:
   ```logql
   {app="servicenow-mcp-system"}          # all system logs
   {level="error"}                         # errors only
   {event="mcp_agent_started"}            # agent startup events
   {app="servicenow_table_api_sse"} | json | status="500"
   ```
4. Click a log row  **Show context** for adjacent lines.

> All application logs are JSON (structlog) so you can `| json` then filter on keys.

---
##  4. Metrics (Prometheus)

* **Prometheus UI** (<http://localhost:9090>) for raw queries.
* In Grafana  _Explore  Prometheus_.

> The Python services expose metrics on **port 8010** by default
> (`PROMETHEUS_METRICS_PORT`). Ensure Prometheus and the OTel
> Collector scrape configs target this port.

Example PromQL snippets:
```promql
# MCP request throughput (replace job label if needed)
rate(http_requests_total{job="mcp-table-agent"}[1m])

# CPU usage of MCP agent containers (cAdvisor metrics via node-exporter if configured)
process_cpu_seconds_total{service="servicenow_table_api_sse"}

# 95th percentile request latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

---
##  5. Traces (Tempo)

1. Grafana  _Loki Explore_  choose **Tracing** or Dashboards  _Tempo Search_.
2. Query by **service.name** (set via `OTEL_SERVICE_NAME`), e.g.:
   ```
   {service.name="servicenow-table-api-sse"}
   ```
3. Click a trace  view spans timeline.  Click a span  **_Logs_** to see its logs.

> **Generate a trace**  open Magentic-UI, run any ServiceNow agent command.  Each request becomes a trace flowing from UI  MCP  ServiceNow.

---
##  6. Continuous Profiling (Pyroscope)

1. Pyroscope UI  <http://localhost:4040>
2. **Select application** (e.g. `servicenow_table_api_sse`) and timeframe.
3. View CPU flame-graph or Diff comparisons.

> Profiles are automatically tagged with `trace_id` when possible  click a flame-graph frame  _View Trace_ to jump to Tempo.

---
##  7. Useful CLI Commands

```bash
# Tail live structlog
stern servicenow-mcp-system          #  if you use stern/k9s (k8s)

# Loki query via logcli (alternative to Grafana)
logcli query --addr=http://localhost:3100 \
  '{level="error"}' --limit=50

# Prometheus instant query
curl "http://localhost:9090/api/v1/query?query=up"

# Tempo trace search (requires tempo-cli)
tempo-cli query --service servicenow-table-api-sse --limit 5
```

---
##  8. Alerting Templates

Create alert rules in **Prometheus** or use **Grafana Alerting**.  Example High Error-Rate rule:
```yaml
group: mcp.rules
name: HighErrorRate
rules:
  - alert: MCPHighErrorRate
    expr: |
      rate(http_requests_total{status=~"5.."}[5m])
        / rate(http_requests_total[5m]) > 0.05
    for: 5m
    labels:
      severity: page
    annotations:
      summary: "{{ $labels.job }} high error rate"
      description: "More than 5% requests are failing on {{ $labels.job }}"
```
Reload Prometheus or use Grafana Notification Channels.

---
##  9. Cleaning Up

```bash
# Stop everything
python start_system.py --stop

# Remove Docker containers / volumes completely
docker compose -f observability/docker-compose.observability.yml down -v

# Delete all logs (done automatically on each start)
rm -rf logs/*.log
```

---
##  FAQ

**Q : Grafana says _Loki data-source is down_**  
A : Wait ~15 s after stack start; Loki may still be initialising.

**Q : Traces dont show logs**  
A : Ensure `trace_id` is injected into logs (structlog + `opentelemetry-instrumentation-logging` already configured).  Also verify _Tempo  Loki_ correlation is enabled in the datasource settings.

**Q : Prometheus cant scrape endpoints (connection refused)**  
A : Check that you used `host.docker.internal` for host-network targets on macOS/Windows.  On Linux use the host IP or run everything inside Docker.

**Q : Pyroscope shows _No data_**  
A : Profiles start after the first minute; ensure the app is under load.  Also verify `pyroscope-io` SDK is enabled in `observability.py`.

---
###  Need help?
Open an issue or ping the maintainers  happy graphing!
