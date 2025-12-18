#!/bin/bash

# Production Deployment Guide for Free-Threading
# Python 3.13t/3.14t with Gunicorn and Monitoring

set -e

echo "🚀 Production Free-Threading Deployment Guide"
echo "========================================="

# Configuration variables
PYTHON_VERSION="${PYTHON_VERSION:-3.14t}"
WORKERS="${WORKERS:-4}"
THREADS="${THREADS:-8}"
PORT="${PORT:-8000}"
BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0}"

echo "🔧 Configuration:"
echo "   Python Version: $PYTHON_VERSION"
echo "   Workers: $WORKERS"
echo "   Threads per Worker: $THREADS"
echo "   Bind: $BIND_ADDRESS:$PORT"

# Check Python version
echo "🐍 Checking Python installation..."
if command -v $PYTHON_VERSION &> /dev/null; then
    echo "✅ $PYTHON_VERSION found"
else
    echo "❌ $PYTHON_VERSION not found"
    echo "   Install with: uv python install $PYTHON_VERSION"
    exit 1
fi

# Verify GIL is disabled
echo "🔓 Verifying GIL status..."
GIL_STATUS=$($PYTHON_VERSION -c "import sys; print(0 if not sys._is_gil_enabled() else 1)")
if [ "$GIL_STATUS" -eq 0 ]; then
    echo "✅ GIL is disabled - free-threading active"
else
    echo "⚠️  GIL is still enabled"
    echo "   Forcing GIL disable..."
    export PYTHON_GIL=0
fi

# Create deployment directory
DEPLOY_DIR="deployment_free_threading"
mkdir -p $DEPLOY_DIR

# Create optimized Gunicorn configuration
echo "⚙️  Creating Gunicorn configuration..."
cat > $DEPLOY_DIR/gunicorn_config.py << 'EOF'
# Gunicorn configuration optimized for free-threading
import multiprocessing
import os

# Worker connections
worker_connections = 1000

# Worker class for free-threading
worker_class = "sync"

# Worker processes
workers = int(os.environ.get("WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Threads per worker
threads = int(os.environ.get("THREADS", 8))

# Timeout settings
timeout = 600
keepalive = 2

# Free-threading specific settings
preload_app = True
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s'

# Process naming
proc_name = "proxy-worker"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

print(f"Gunicorn Config - Workers: {workers}, Threads: {threads}")
print(f"Free-threading enabled: {not os.environ.get('PYTHON_GIL', '1') == '1'}")
EOF

# Create systemd service file
echo "🔧 Creating systemd service..."
cat > $DEPLOY_DIR/sap-proxy-free-thread.service << 'EOF'
[Unit]
Description=SAP AI Core LLM Proxy - Free Threading
After=network.target

[Service]
Type=exec
User=proxy-user
Group=proxy-group
WorkingDirectory=/opt/sap-proxy
Environment=PYTHON_GIL=0
Environment=WORKERS=4
Environment=THREADS=8
Environment=PATH=/opt/sap-proxy/venv-free-thread/bin
ExecStart=/opt/sap-proxy/venv-free-thread/bin/gunicorn \
    --config python:gunicorn_config.py \
    --bind 0.0.0.0:8000 \
    --user proxy-user \
    --group proxy-group \
    proxy_server:app

# Restart policy
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

# Create nginx configuration for reverse proxy
echo "🌐 Creating nginx configuration..."
cat > $DEPLOY_DIR/nginx_proxy.conf << 'EOF'
# Nginx configuration for SAP AI Core Proxy with free-threading
upstream sap_proxy_backend {
    # Multiple backend servers for load balancing
    server 127.0.0.1:8000 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8001 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8002 weight=1 max_fails=3 fail_timeout=30s;
    
    # Load balancing method
    least_conn;
}

server {
    listen 80;
    listen [::]:80;
    server_name your-proxy-domain.com;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Client limits
    client_max_body_size 10M;
    client_body_timeout 600s;
    client_header_timeout 600s;
    
    # Proxy settings
    location / {
        proxy_pass http://sap_proxy_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
        
        # Buffering
        proxy_buffering off;
        proxy_request_buffering off;
        
        # HTTP versions
        proxy_http_version 1.1;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy";
        add_header Content-Type text/plain;
    }
    
    # Metrics endpoint
    location /metrics {
        access_log off;
        allow 127.0.0.1;
        deny all;
        return 200 "OK";
    }
    
    # Logging
    access_log /var/log/nginx/sap-proxy-access.log combined;
    error_log /var/log/nginx/sap-proxy-error.log warn;
}
EOF

# Create monitoring script
echo "📊 Creating monitoring script..."
cat > $DEPLOY_DIR/monitor_free_threading.sh << 'EOF'
#!/bin/bash

# Monitor free-threading proxy performance
METRICS_FILE="/var/log/sap-proxy-metrics.log"
PID_FILE="/var/run/sap-proxy.pid"

check_proxy_health() {
    local response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
    if [ "$response" = "200" ]; then
        echo "$(date): Health check passed" >> $METRICS_FILE
        return 0
    else
        echo "$(date): Health check failed: $response" >> $METRICS_FILE
        return 1
    fi
}

monitor_system_metrics() {
    local python_cmd="\${PYTHON_CMD:-python3.14t}"
    
    # Python-specific metrics
    $python_cmd -c "
import sys
import threading
import psutil
import time
import os

if os.path.exists('$PID_FILE'):
    with open('$PID_FILE', 'r') as f:
        pid = int(f.read().strip())
    
    try:
        p = psutil.Process(pid)
        metrics = {
            'timestamp': time.time(),
            'cpu_percent': p.cpu_percent(),
            'memory_mb': p.memory_info().rss / 1024 / 1024,
            'num_threads': p.num_threads(),
            'gil_enabled': sys._is_gil_enabled(),
            'active_python_threads': threading.active_count()
        }
        print(f'PROXY_METRICS: {metrics}')
    except:
        print('PROXY_METRICS: error_reading_process')
"
}

# Main monitoring loop
while true; do
    check_proxy_health
    monitor_system_metrics
    
    # Wait 30 seconds between checks
    sleep 30
done
EOF

chmod +x $DEPLOY_DIR/monitor_free_threading.sh

# Create deployment script
echo "🚀 Creating deployment script..."
cat > $DEPLOY_DIR/deploy.sh << 'EOF'
#!/bin/bash

set -e

echo "🚀 Deploying SAP AI Core Proxy with Free-Threading"

# Configuration
DEPLOY_USER="proxy-user"
DEPLOY_DIR="/opt/sap-proxy"
PYTHON_VERSION="\${PYTHON_VERSION:-3.14t}"
SERVICE_NAME="sap-proxy-free-thread"

# Stop existing service
echo "🛑 Stopping existing service..."
sudo systemctl stop $SERVICE_NAME || true

# Backup current deployment
if [ -d "$DEPLOY_DIR" ]; then
    echo "💾 Backing up current deployment..."
    sudo cp -r $DEPLOY_DIR $DEPLOY_DIR.backup.$(date +%Y%m%d_%H%M%S)
fi

# Create deployment directory
echo "📁 Creating deployment directory..."
sudo mkdir -p $DEPLOY_DIR
sudo chown $DEPLOY_USER:$DEPLOY_USER $DEPLOY_DIR

# Install Python version
echo "🐍 Installing Python $PYTHON_VERSION..."
sudo -u $DEPLOY_USER bash -c "
    cd $DEPLOY_DIR
    if [ ! -d 'venv-free-thread' ]; then
        $PYTHON_VERSION -m venv venv-free-thread
    fi
    source venv-free-thread/bin/activate
    pip install --quiet flask gunicorn requests ai-core-sdk sap-ai-sdk-gen openai litellm tenacity cryptography
"

# Copy application files
echo "📂 Copying application files..."
sudo -u $DEPLOY_USER cp -r /path/to/sap-ai-core-llm-proxy/* $DEPLOY_DIR/
sudo -u $DEPLOY_USER cp -r $DEPLOY_DIR/*.py $DEPLOY_DIR/
sudo -u $DEPLOY_USER chmod +x $DEPLOY_DIR/scripts/*.sh

# Install systemd service
echo "🔧 Installing systemd service..."
sudo cp $DEPLOY_DIR/sap-proxy-free-thread.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

# Configure nginx
echo "🌐 Configuring nginx..."
sudo cp $DEPLOY_DIR/nginx_proxy.conf /etc/nginx/sites-available/sap-proxy-free-thread
sudo ln -sf /etc/nginx/sites-available/sap-proxy-free-thread /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Start service
echo "🚀 Starting service..."
sudo systemctl start $SERVICE_NAME

# Verify deployment
echo "✅ Verifying deployment..."
sleep 5

if sudo systemctl is-active --quiet $SERVICE_NAME; then
    echo "✅ Service is running"
else
    echo "❌ Service failed to start"
    sudo systemctl status $SERVICE_NAME
    exit 1
fi

# Health check
echo "🏥 Health check..."
if curl -s -f http://localhost:8000/health > /dev/null; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi

echo "🎉 Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Monitor with: ./monitor_free_threading.sh"
echo "   2. Check logs: journalctl -u $SERVICE_NAME -f"
echo "   3. View metrics: tail -f /var/log/sap-proxy-metrics.log"
EOF

chmod +x $DEPLOY_DIR/deploy.sh

# Create rollback script
echo "🔙 Creating rollback script..."
cat > $DEPLOY_DIR/rollback.sh << 'EOF'
#!/bin/bash

set -e

echo "🔙 Rolling back SAP AI Core Proxy"

SERVICE_NAME="sap-proxy-free-thread"
DEPLOY_DIR="/opt/sap-proxy"
BACKUP_DIR="$DEPLOY_DIR.backup"

# Stop current service
echo "🛑 Stopping service..."
sudo systemctl stop $SERVICE_NAME

# Find latest backup
latest_backup=$(ls -t $BACKUP_DIR 2>/dev/null | head -n 1)
if [ -n "$latest_backup" ]; then
    echo "📦 Restoring from backup: $latest_backup"
    sudo rm -rf $DEPLOY_DIR
    sudo mv $latest_backup $DEPLOY_DIR
    
    # Restart with old configuration
    echo "🚀 Restarting with backup..."
    sudo systemctl start $SERVICE_NAME
    
    echo "✅ Rollback completed"
else
    echo "❌ No backup found for rollback"
    exit 1
fi
EOF

chmod +x $DEPLOY_DIR/rollback.sh

# Create testing script
echo "🧪 Creating load testing script..."
cat > $DEPLOY_DIR/load_test.sh << 'EOF'
#!/bin/bash

# Load testing for free-threading proxy
CONCURRENT_REQUESTS="\${1:-50}"
DURATION="\${2:-60}"
URL="\${3:-http://localhost:8000/v1/chat/completions}"

echo "🧪 Load Testing Free-Threading Proxy"
echo "Concurrent Requests: $CONCURRENT_REQUESTS"
echo "Duration: $DURATION seconds"
echo "URL: $URL"

# Install siege if not available
if ! command -v siege &> /dev/null; then
    echo "📦 Installing siege..."
    sudo apt-get update && sudo apt-get install -y siege
fi

# Create test payload
cat > test_payload.json << 'EOFPAYLOAD
{
  "model": "gpt-4o",
  "messages": [
    {
      "role": "user",
      "content": "Hello, this is a load test request. Please respond with a short message."
    }
  ],
  "stream": false
}
EOFPAYLOAD

# Run load test
echo "🚀 Starting load test..."
siege -c $CONCURRENT_REQUESTS -t $DURATION -H "Authorization: Bearer test-token" \
      --content-type "application/json" \
      --file "test_payload.json" \
      $URL

echo "📊 Load test completed"
echo "📋 Check metrics log for performance data"
rm -f test_payload.json
EOF

chmod +x $DEPLOY_DIR/load_test.sh

echo ""
echo "✅ Production deployment files created in: $DEPLOY_DIR"
echo ""
echo "📋 Files created:"
echo "   - gunicorn_config.py (optimized Gunicorn config)"
echo "   - sap-proxy-free-thread.service (systemd service)"
echo "   - nginx_proxy.conf (nginx reverse proxy)"
echo "   - monitor_free_threading.sh (monitoring script)"
echo "   - deploy.sh (deployment script)"
echo "   - rollback.sh (emergency rollback)"
echo "   - load_test.sh (load testing script)"
echo ""
echo "🚀 Ready for deployment!"
echo ""
echo "📋 Deployment steps:"
echo "   1. Review and customize configurations"
echo "   2. Run: $DEPLOY_DIR/deploy.sh"
echo "   3. Monitor: $DEPLOY_DIR/monitor_free_threading.sh"
echo "   4. Test: $DEPLOY_DIR/load_test.sh"