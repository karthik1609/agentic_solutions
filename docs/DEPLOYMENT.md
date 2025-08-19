#  Deployment Guide

This guide covers different deployment scenarios for the ServiceNow MCP System, from local development to production environments.

##  Prerequisites

### System Requirements
- **Python**: 3.10-3.12
- **Memory**: 4GB+ RAM recommended
- **Storage**: 10GB+ free space
- **Network**: Access to ServiceNow instance and OpenAI API

### Required Services
- **ServiceNow Instance**: With API access enabled
- **OpenAI API Key**: For AI agent functionality (optional)
- **Docker**: For observability stack (optional)

##  Local Development

### Quick Start
```bash
# 1. Clone and setup
git clone <repository-url>
cd servicenow-mcp-system
uv sync

# 2. Configure environment
cp env.template .env
# Edit .env with your credentials

# 3. Start the system
python start_system.py

# 4. Access the interface
open http://localhost:8080
```

### Development Configuration
```bash
# Start without observability (faster)
python start_system.py --no-observability

# Start only agents (no UI)
python start_system.py --no-ui

# Custom configuration
python start_system.py --config dev_config.yaml
```

##  Docker Deployment

### Option 1: Docker Compose (Recommended)
```bash
# 1. Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  servicenow-mcp:
    build: .
    ports:
      - "8080:8080"
      - "3001:3001"
      - "3002:3002"
    environment:
      - SERVICENOW_INSTANCE_URL=${SERVICENOW_INSTANCE_URL}
      - SERVICENOW_USERNAME=${SERVICENOW_USERNAME}
      - SERVICENOW_PASSWORD=${SERVICENOW_PASSWORD}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./logs:/app/logs
      - ./.env:/app/.env
    restart: unless-stopped

  # Optional: Full observability stack
  observability:
    extends:
      file: observability/docker-compose.observability.yml
      service: otel-collector
    depends_on:
      - servicenow-mcp
EOF

# 2. Start the stack
docker-compose up -d
```

### Option 2: Standalone Docker
```bash
# 1. Build the image
docker build -t servicenow-mcp:latest .

# 2. Run the container
docker run -d \
  --name servicenow-mcp \
  -p 8080:8080 \
  -p 3001:3001 \
  -p 3002:3002 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.env:/app/.env \
  --restart unless-stopped \
  servicenow-mcp:latest
```

### Dockerfile
```dockerfile
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN uv sync --frozen

# Create logs directory
RUN mkdir -p logs

# Expose ports
EXPOSE 8080 3001 3002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080 || exit 1

# Start the system
CMD ["uv", "run", "python", "start_system.py"]
```

##  Kubernetes Deployment

### Namespace and ConfigMap
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: servicenow-mcp

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: servicenow-config
  namespace: servicenow-mcp
data:
  servicenow_final_config.yaml: |
    # Your Magentic-UI configuration
    gpt4o_client: &gpt4o_client
      provider: OpenAIChatCompletionClient
      config:
        model: gpt-4o-2024-08-06
        api_key: ${OPENAI_API_KEY}
    # ... rest of config
```

### Secrets
```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: servicenow-secrets
  namespace: servicenow-mcp
type: Opaque
stringData:
  SERVICENOW_INSTANCE_URL: "https://your-instance.service-now.com"
  SERVICENOW_USERNAME: "your_username"
  SERVICENOW_PASSWORD: "your_password"
  OPENAI_API_KEY: "your_openai_key"
```

### Deployment
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: servicenow-mcp
  namespace: servicenow-mcp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: servicenow-mcp
  template:
    metadata:
      labels:
        app: servicenow-mcp
    spec:
      containers:
      - name: servicenow-mcp
        image: servicenow-mcp:latest
        ports:
        - containerPort: 8080
        - containerPort: 3001
        - containerPort: 3002
        envFrom:
        - secretRef:
            name: servicenow-secrets
        volumeMounts:
        - name: config
          mountPath: /app/servicenow_final_config.yaml
          subPath: servicenow_final_config.yaml
        - name: logs
          mountPath: /app/logs
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
      volumes:
      - name: config
        configMap:
          name: servicenow-config
      - name: logs
        emptyDir: {}

---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: servicenow-mcp-service
  namespace: servicenow-mcp
spec:
  selector:
    app: servicenow-mcp
  ports:
  - name: ui
    port: 8080
    targetPort: 8080
  - name: table-api
    port: 3001
    targetPort: 3001
  - name: knowledge-api
    port: 3002
    targetPort: 3002
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: servicenow-mcp-ingress
  namespace: servicenow-mcp
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: servicenow-mcp.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: servicenow-mcp-service
            port:
              number: 8080
```

### Deploy to Kubernetes
```bash
# Apply all configurations
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -n servicenow-mcp
kubectl logs -f deployment/servicenow-mcp -n servicenow-mcp

# Port forward for testing
kubectl port-forward svc/servicenow-mcp-service 8080:8080 -n servicenow-mcp
```

##  Cloud Deployments

### AWS ECS
```json
{
  "family": "servicenow-mcp",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "servicenow-mcp",
      "image": "your-registry/servicenow-mcp:latest",
      "portMappings": [
        {"containerPort": 8080, "protocol": "tcp"},
        {"containerPort": 3001, "protocol": "tcp"},
        {"containerPort": 3002, "protocol": "tcp"}
      ],
      "environment": [
        {"name": "SERVICENOW_INSTANCE_URL", "value": "${SERVICENOW_INSTANCE_URL}"},
        {"name": "SERVICENOW_USERNAME", "value": "${SERVICENOW_USERNAME}"},
        {"name": "SERVICENOW_PASSWORD", "value": "${SERVICENOW_PASSWORD}"},
        {"name": "OPENAI_API_KEY", "value": "${OPENAI_API_KEY}"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/servicenow-mcp",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Google Cloud Run
```yaml
# cloud-run.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: servicenow-mcp
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/memory: "2Gi"
        run.googleapis.com/cpu: "1000m"
    spec:
      containers:
      - image: gcr.io/your-project/servicenow-mcp:latest
        ports:
        - containerPort: 8080
        env:
        - name: SERVICENOW_INSTANCE_URL
          value: "https://your-instance.service-now.com"
        - name: SERVICENOW_USERNAME
          valueFrom:
            secretKeyRef:
              name: servicenow-secrets
              key: username
        - name: SERVICENOW_PASSWORD
          valueFrom:
            secretKeyRef:
              name: servicenow-secrets
              key: password
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secrets
              key: api-key
```

### Azure Container Instances
```bash
# Create resource group
az group create --name servicenow-mcp-rg --location eastus

# Create container instance
az container create \
  --resource-group servicenow-mcp-rg \
  --name servicenow-mcp \
  --image your-registry/servicenow-mcp:latest \
  --cpu 2 \
  --memory 4 \
  --ports 8080 3001 3002 \
  --environment-variables \
    SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com" \
  --secure-environment-variables \
    SERVICENOW_USERNAME="your_username" \
    SERVICENOW_PASSWORD="your_password" \
    OPENAI_API_KEY="your_key" \
  --restart-policy Always
```

##  Production Configuration

### Environment Variables
```bash
# Production .env
SERVICENOW_INSTANCE_URL=https://prod-instance.service-now.com
SERVICENOW_USERNAME=service_account
SERVICENOW_PASSWORD=secure_password
SERVICENOW_VERIFY_SSL=true

OPENAI_API_KEY=sk-prod-key-here

# Production settings
LOG_LEVEL=INFO
MAGENTIC_UI_PORT=8080
DATABASE_URL=postgresql://user:pass@db:5432/magentic_ui

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
PROMETHEUS_ENDPOINT=http://prometheus:9090
```

### Production Checklist
- [ ] **Secrets Management**: Use proper secret stores (AWS Secrets Manager, Azure Key Vault, etc.)
- [ ] **SSL/TLS**: Enable HTTPS with valid certificates
- [ ] **Database**: Use external database for Magentic-UI
- [ ] **Logging**: Centralized logging with retention policies
- [ ] **Monitoring**: Full observability stack with alerting
- [ ] **Backup**: Regular backups of configuration and data
- [ ] **Security**: Network policies, firewall rules, access controls
- [ ] **Scaling**: Auto-scaling policies for high availability
- [ ] **Updates**: CI/CD pipeline for automated deployments

### Load Balancer Configuration
```nginx
# nginx.conf for load balancing
upstream servicenow_mcp_backend {
    server servicenow-mcp-1:8080;
    server servicenow-mcp-2:8080;
    server servicenow-mcp-3:8080;
}

server {
    listen 80;
    server_name servicenow-mcp.your-domain.com;
    
    location / {
        proxy_pass http://servicenow_mcp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
    }
}
```

##  Monitoring Setup

### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'servicenow-mcp'
    static_configs:
      - targets: ['servicenow-mcp:8080']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'mcp-agents'
    static_configs:
      - targets: ['servicenow-mcp:3001', 'servicenow-mcp:3002']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Grafana Dashboards
```json
{
  "dashboard": {
    "title": "ServiceNow MCP System",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{service}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "P95"
          }
        ]
      }
    ]
  }
}
```

##  Troubleshooting

### Common Issues

**Container Won't Start**
```bash
# Check container logs
docker logs servicenow-mcp
kubectl logs -f deployment/servicenow-mcp -n servicenow-mcp

# Check environment variables
docker exec servicenow-mcp env | grep SERVICENOW
```

**Health Check Failures**
```bash
# Manual health check
curl -f http://localhost:8080/health
kubectl get pods -n servicenow-mcp

# Check resource usage
docker stats servicenow-mcp
kubectl top pods -n servicenow-mcp
```

**Network Connectivity Issues**
```bash
# Test ServiceNow connectivity from container
docker exec servicenow-mcp curl -I https://your-instance.service-now.com

# Test MCP agent endpoints
curl http://localhost:3001/sse
curl http://localhost:3002/sse
```

### Performance Tuning

**Memory Optimization**
```python
# In start_system.py, add memory limits
import resource

# Set memory limit (2GB)
resource.setrlimit(resource.RLIMIT_AS, (2*1024*1024*1024, -1))
```

**Connection Pool Tuning**
```python
# In MCP agents, optimize HTTP client
import httpx

client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=20,
        max_connections=100,
        keepalive_expiry=30.0
    ),
    timeout=httpx.Timeout(30.0)
)
```

This deployment guide provides comprehensive coverage for various deployment scenarios, ensuring the ServiceNow MCP System can be reliably deployed in any environment.