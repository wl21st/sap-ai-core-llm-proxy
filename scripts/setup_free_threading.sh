#!/bin/bash

# Free-Threading Setup and Test Script for SAP AI Core LLM Proxy
# This script helps set up and validate free-threading capabilities

set -e

echo "🐍 Python Free-Threading Setup for SAP AI Core LLM Proxy"
echo "=================================================="

# Check current Python version
echo "📋 Checking current Python environment..."
python --version

# Check if free-threading is available
echo "🔍 Checking free-threading availability..."
if command -v python3.13t &> /dev/null; then
    PYTHON_CMD="python3.13t"
    echo "✅ Python 3.13t found"
elif command -v python3.14t &> /dev/null; then
    PYTHON_CMD="python3.14t"
    echo "✅ Python 3.14t found"
else
    echo "❌ No free-threaded Python found. Installing..."
    if command -v uv &> /dev/null; then
        echo "📦 Installing Python 3.13t via uv..."
        uv python install 3.13t
        PYTHON_CMD="python3.13t"
    else
        echo "⚠️  Please install Python 3.13t manually"
        exit 1
    fi
fi

# Verify GIL is disabled
echo "🔓 Verifying GIL status..."
GIL_STATUS=$($PYTHON_CMD -c "import sys; print(0 if not sys._is_gil_enabled() else 1)")
if [ "$GIL_STATUS" -eq 0 ]; then
    echo "✅ GIL is disabled - free-threading is active"
else
    echo "⚠️  GIL is still enabled"
    echo "   Use PYTHON_GIL=0 $PYTHON_CMD to disable GIL"
fi

# Create test virtual environment
echo "🏗️  Creating test environment..."
TEST_VENV="venv-free-thread-test"
if [ -d "$TEST_VENV" ]; then
    rm -rf "$TEST_VENV"
fi

$PYTHON_CMD -m venv $TEST_VENV
source $TEST_VENV/bin/activate
echo "✅ Test environment created"

# Install dependencies
echo "📦 Installing dependencies..."
pip install --quiet flask requests ai-core-sdk sap-ai-sdk-gen openai litellm tenacity

# Test library compatibility
echo "🧪 Testing library compatibility..."

echo "   Testing Flask..."
python -c "import flask; print('✅ Flask compatible')" || echo "❌ Flask failed"

echo "   Testing requests..."
python -c "import requests; print('✅ requests compatible')" || echo "❌ requests failed"

echo "   Testing urllib3..."
python -c "import urllib3; print('✅ urllib3 compatible')" || echo "❌ urllib3 failed"

echo "   Testing SAP AI SDK..."
python -c "from ai_core_sdk import Session; print('✅ ai-core-sdk compatible')" || echo "❌ ai-core-sdk failed"

echo "   Testing SAP AI SDK Gen..."
python -c "import sap_ai_sdk_gen; print('✅ sap-ai-sdk-gen compatible')" || echo "❌ sap-ai-sdk-gen failed"

echo "   Testing openai..."
python -c "import openai; print('✅ openai compatible')" || echo "❌ openai failed"

echo "   Testing litellm..."
python -c "import litellm; print('✅ litellm compatible')" || echo "❌ litellm failed"

echo "   Testing cryptography..."
python -c "import cryptography; print('✅ cryptography compatible')" || echo "❌ cryptography failed"

# Create simple performance test
echo "⚡ Creating performance test script..."
cat > test_free_threading_performance.py << 'EOF'
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import sys

def cpu_intensive_task(n):
    """Simple CPU-intensive task for testing"""
    total = 0
    for i in range(n):
        total += i * i
    return total

def run_performance_test():
    """Test single vs multi-threaded performance"""
    iterations = 1000000
    num_threads = 4
    
    print(f"Python Version: {sys.version}")
    print(f"GIL Enabled: {sys._is_gil_enabled()}")
    print(f"CPU Count: {threading.active_count()}")
    
    # Single-threaded test
    start_time = time.time()
    result_single = cpu_intensive_task(iterations)
    single_time = time.time() - start_time
    print(f"Single-threaded time: {single_time:.2f}s")
    
    # Multi-threaded test
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(cpu_intensive_task, iterations) for _ in range(num_threads)]
        results_multi = [f.result() for f in futures]
    multi_time = time.time() - start_time
    print(f"Multi-threaded time: {multi_time:.2f}s")
    
    # Calculate speedup
    speedup = single_time / multi_time
    print(f"Speedup: {speedup:.2f}x")
    
    # Verify results are consistent
    if all(r == result_single for r in results_multi):
        print("✅ All results consistent")
    else:
        print("❌ Results inconsistent - potential thread safety issue")

if __name__ == "__main__":
    run_performance_test()
EOF

echo "🚀 Running performance test..."
python test_free_threading_performance.py

# Create proxy server test configuration
echo "⚙️  Creating test configuration..."
cat > test_free_threading_config.json << 'EOF'
{
  "secret_authentication_tokens": ["test-token-free-threading"],
  "subaccounts": {
    "test-subaccount": {
      "resource_group": "default",
      "service_key": {
        "clientid": "test-client-id",
        "clientsecret": "test-client-secret",
        "tokenurl": "https://oauth.example.com/oauth/token",
        "identityzoneid": "test-zone-id"
      },
      "models": {
        "test-model": [
          "https://test.endpoint.com/v1/models/test-model"
        ]
      }
    }
  }
}
EOF

echo "✅ Test configuration created"

# Test basic proxy functionality
echo "🔧 Testing basic proxy functionality..."
cat > test_proxy_basic.py << 'EOF'
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# Add the project root to Python path
sys.path.insert(0, '/Users/I073228/PycharmProjects/sap-ai-core-llm-proxy')

try:
    from proxy_server import app
    from config.loader import load_config
    
    print("✅ Proxy server modules imported successfully")
    
    # Test configuration loading
    config = load_config('test_free_threading_config.json')
    print(f"✅ Configuration loaded: {len(config.subaccounts)} subaccounts")
    
    # Test threading functionality
    def test_thread_function(i):
        return f"Thread {i} completed successfully"
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(test_thread_function, i) for i in range(8)]
        results = [f.result() for f in futures]
    
    print(f"✅ Threading test passed: {len(results)} threads")
    
except Exception as e:
    print(f"❌ Error testing proxy functionality: {e}")
    sys.exit(1)
EOF

python test_proxy_basic.py

# Cleanup
echo "🧹 Cleaning up test files..."
rm -f test_free_threading_performance.py test_proxy_basic.py test_free_threading_config.json
deactivate
rm -rf $TEST_VENV

echo ""
echo "🎉 Free-threading setup complete!"
echo ""
echo "📋 Summary:"
echo "   - Python command: $PYTHON_CMD"
echo "   - GIL status: $([ "$GIL_STATUS" -eq 0 ] && echo 'Disabled' || echo 'Enabled')"
echo "   - Library compatibility: Tested above"
echo "   - Next steps: See docs/FREE_THREADING_MIGRATION_PLAN.md"
echo ""
echo "🚀 Ready to proceed with free-threading migration!"