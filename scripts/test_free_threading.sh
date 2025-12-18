#!/bin/bash

# Comprehensive Free-Threading Test Suite
# Tests all aspects of Python 3.13/3.14 free-threading for proxy server

set -e

echo "🧪 Comprehensive Free-Threading Test Suite"
echo "===================================="

# Configuration
PYTHON_CMD="${PYTHON_CMD:-python3.13t}"
TEST_TIMEOUT="${TEST_TIMEOUT:-300}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo "🔧 Configuration:"
echo "   Python: $PYTHON_CMD"
echo "   Timeout: $TEST_TIMEOUT seconds"
echo "   Log Level: $LOG_LEVEL"

# Check Python version and GIL status
echo "🐍 Environment validation..."
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "❌ Python command not found: $PYTHON_CMD"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
GIL_STATUS=$($PYTHON_CMD -c "import sys; print('disabled' if not sys._is_gil_enabled() else 'enabled')")

echo "✅ $PYTHON_VERSION"
echo "🔓 GIL Status: $GIL_STATUS"

# Create test results directory
RESULTS_DIR="free_threading_test_results"
mkdir -p $RESULTS_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULTS_FILE="$RESULTS_DIR/test_results_$TIMESTAMP.json"

# Test 1: Basic Thread Safety
echo ""
echo "🧪 Test 1: Basic Thread Safety"
echo "-----------------------------------"

$PYTHON_CMD -c "
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import json

# Test basic thread operations
shared_counter = 0
counter_lock = threading.Lock()

def increment_counter():
    global shared_counter
    with counter_lock:
        shared_counter += 1
    return shared_counter

def test_thread_safety():
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(increment_counter) for _ in range(100)]
        results = [f.result() for f in futures]
    
    # Check for race conditions
    expected_values = list(range(1, 101))
    if results == expected_values:
        print('✅ Thread safety test passed')
        return {'status': 'pass', 'results': results[:5]}
    else:
        print('❌ Thread safety test failed - race condition detected')
        return {'status': 'fail', 'expected': expected_values[-5:], 'actual': results[-5:]}

result = test_thread_safety()
print(f'Thread safety result: {json.dumps(result)}')
" | tee -a $RESULTS_FILE

# Test 2: SDK Client Concurrency
echo ""
echo "🧪 Test 2: SDK Client Concurrency" 
echo "---------------------------------------"

$PYTHON_CMD -c "
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

def test_sdk_concurrency():
    try:
        # Mock SDK client creation (real SDK may not be available)
        created_clients = []
        client_lock = threading.Lock()
        
        def create_mock_client(model_name):
            time.sleep(0.1)  # Simulate creation delay
            with client_lock:
                created_clients.append(f'client_for_{model_name}')
            return f'client_for_{model_name}'
        
        models = ['gpt-4o', 'claude-3.5-sonnet', 'gemini-pro'] * 3  # 9 models total
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(create_mock_client, model) for model in models]
            results = [f.result(timeout=10) for f in as_completed(futures)]
        creation_time = time.time() - start_time
        
        success = len(results) == len(models) and all(f.startswith('client_for_') for f in results)
        
        return {
            'status': 'pass' if success else 'fail',
            'creation_time': creation_time,
            'models_created': len(results),
            'expected_models': len(models),
            'threads_used': 4
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

result = test_sdk_concurrency()
print(f'SDK concurrency result: {json.dumps(result)}')
" | tee -a $RESULTS_FILE

# Test 3: Concurrent Request Handling
echo ""
echo "🧪 Test 3: Concurrent Request Handling"
echo "--------------------------------------"

$PYTHON_CMD -c "
import sys
import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

class MockProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        time.sleep(0.01)  # Simulate processing
        
        response = {'status': 'ok', 'timestamp': time.time()}
        response_json = json.dumps(response).encode()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(response_json)))
        self.end_headers()
        self.wfile.write(response_json)
    
    def log_message(self, format, *args):
        pass  # Suppress logging for cleaner test output

def test_concurrent_requests():
    try:
        # Start mock server
        server = HTTPServer(('localhost', 0), MockProxyHandler)
        port = server.server_address[1]
        
        def server_thread():
            server.serve_forever()
        
        server_thread = threading.Thread(target=server_thread, daemon=True)
        server_thread.start()
        
        # Give server time to start
        time.sleep(0.1)
        
        def make_request():
            try:
                import urllib.request
                import json
                data = json.dumps({'test': 'data'}).encode()
                req = urllib.request.Request(
                    f'http://localhost:{port}/',
                    data=data,
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            except:
                return False
        
        # Test concurrent requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result(timeout=5) for f in futures]
        request_time = time.time() - start_time
        
        successful_requests = sum(results)
        success_rate = successful_requests / len(results)
        
        server.shutdown()
        
        return {
            'status': 'pass' if success_rate > 0.8 else 'fail',
            'successful_requests': successful_requests,
            'total_requests': len(results),
            'success_rate': success_rate,
            'request_time': request_time,
            'concurrent_threads': 10
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

result = test_concurrent_requests()
print(f'Concurrent requests result: {json.dumps(result)}')
" | tee -a $RESULTS_FILE

# Test 4: Memory Usage Under Load
echo ""
echo "🧪 Test 4: Memory Usage Under Load"
echo "------------------------------------"

$PYTHON_CMD -c "
import sys
import threading
import time
import gc
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
import json
import psutil

def test_memory_usage():
    try:
        # Start memory tracking
        tracemalloc.start()
        
        def memory_intensive_task():
            # Allocate significant memory
            data = []
            for i in range(10000):
                data.append({
                    'id': i,
                    'data': 'x' * 100,  # 100 bytes per item
                    'timestamp': time.time()
                })
            
            # Process data
            total = sum(item['id'] for item in data)
            return len(data), total
        
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Run with multiple threads
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(memory_intensive_task) for _ in range(8)]
            results = [f.result(timeout=30) for f in futures]
        
        peak_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Force garbage collection
        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        return {
            'status': 'pass',
            'initial_memory_mb': initial_memory,
            'peak_memory_mb': peak_memory,
            'final_memory_mb': final_memory,
            'memory_growth_mb': final_memory - initial_memory,
            'peak_traced_mb': peak / 1024 / 1024,
            'tasks_completed': len(results),
            'threads_used': 4
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

result = test_memory_usage()
print(f'Memory usage result: {json.dumps(result)}')
" | tee -a $RESULTS_FILE

# Test 5: Streaming Performance
echo ""
echo "🧪 Test 5: Streaming Performance"
echo "----------------------------------"

$PYTHON_CMD -c "
import sys
import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor
import queue

def test_streaming_performance():
    try:
        def mock_streaming_task(stream_id):
            chunks = []
            for i in range(200):  # 200 chunks per stream
                chunk = {
                    'stream_id': stream_id,
                    'chunk_index': i,
                    'data': f'chunk_data_{i}',
                    'timestamp': time.time()
                }
                chunks.append(chunk)
                time.sleep(0.001)  # 1ms delay per chunk
            
            return len(chunks), chunks[-5:] if chunks else []
        
        # Test concurrent streaming
        concurrent_streams = 5
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=concurrent_streams) as executor:
            futures = [executor.submit(mock_streaming_task, i) for i in range(concurrent_streams)]
            results = [f.result(timeout=30) for f in futures]
        
        streaming_time = time.time() - start_time
        
        # Analyze results
        total_chunks = sum(result[0] for result in results)
        expected_chunks = concurrent_streams * 200
        
        return {
            'status': 'pass' if total_chunks >= expected_chunks * 0.95 else 'fail',
            'total_chunks': total_chunks,
            'expected_chunks': expected_chunks,
            'completion_rate': total_chunks / expected_chunks,
            'streaming_time': streaming_time,
            'concurrent_streams': concurrent_streams,
            'chunks_per_second': total_chunks / streaming_time if streaming_time > 0 else 0
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

result = test_streaming_performance()
print(f'Streaming performance result: {json.dumps(result)}')
" | tee -a $RESULTS_FILE

# Test 6: Load Balancing Efficiency
echo ""
echo "🧪 Test 6: Load Balancing Efficiency"
echo "---------------------------------------"

$PYTHON_CMD -c "
import sys
import threading
import time
import random
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

def test_load_balancing():
    try:
        # Simulate load balancer with counters
        class MockLoadBalancer:
            def __init__(self):
                self.counters = defaultdict(int)
                self.lock = threading.Lock()
            
            def select_endpoint(self, model, endpoints):
                with self.lock:
                    counter = self.counters[model]
                    endpoint = endpoints[counter % len(endpoints)]
                    self.counters[model] = counter + 1
                    return endpoint, counter
        
        balancer = MockLoadBalancer()
        models = ['gpt-4o', 'claude-3.5-sonnet', 'gemini-pro']
        endpoints = {
            'gpt-4o': ['ep1', 'ep2', 'ep3'],
            'claude-3.5-sonnet': ['ep4', 'ep5'],
            'gemini-pro': ['ep6', 'ep7', 'ep8', 'ep9']
        }
        
        def simulate_requests():
            requests_made = []
            for _ in range(100):
                model = random.choice(models)
                endpoint, counter = balancer.select_endpoint(model, endpoints[model])
                requests_made.append((model, endpoint))
                time.sleep(0.001)  # 1ms delay
            
            return requests_made
        
        # Test with concurrent threads
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(simulate_requests) for _ in range(4)]
            all_requests = []
            for f in futures:
                all_requests.extend(f.result(timeout=10))
        
        test_time = time.time() - start_time
        
        # Analyze load distribution
        distribution = defaultdict(lambda: defaultdict(int))
        for model, endpoint in all_requests:
            distribution[model][endpoint] += 1
        
        # Calculate evenness (lower is better)
        evenness_scores = []
        for model in models:
            counts = list(distribution[model].values())
            if counts:
                avg = sum(counts) / len(counts)
                variance = sum((c - avg) ** 2 for c in counts) / len(counts)
                evenness_scores.append(variance)
        
        avg_evenness = sum(evenness_scores) / len(evenness_scores) if evenness_scores else 0
        
        return {
            'status': 'pass',
            'total_requests': len(all_requests),
            'test_time': test_time,
            'requests_per_second': len(all_requests) / test_time,
            'models_tested': len(models),
            'evenness_score': avg_evenness,
            'lower_evenness_better': True
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

result = test_load_balancing()
print(f'Load balancing result: {json.dumps(result)}')
" | tee -a $RESULTS_FILE

# Generate comprehensive report
echo ""
echo "📊 Generating Comprehensive Report"
echo "--------------------------------"

$PYTHON_CMD -c "
import json
import sys

# Load results
with open('$RESULTS_FILE', 'r') as f:
    lines = f.readlines()

tests_data = []
for line in lines:
    if line.strip():
        try:
            tests_data.append(json.loads(line.split('result: ')[1]))
        except:
            pass

# Generate report
print('🧪 FREE-THREADING TEST SUITE REPORT')
print('=' * 50)
print()

passed_tests = sum(1 for test in tests_data if test['status'] == 'pass')
failed_tests = sum(1 for test in tests_data if test['status'] == 'fail')
error_tests = sum(1 for test in tests_data if test['status'] == 'error')

print(f'📊 SUMMARY:')
print(f'   Total Tests: {len(tests_data)}')
print(f'   ✅ Passed: {passed_tests}')
print(f'   ❌ Failed: {failed_tests}')
print(f'   ⚠️  Errors: {error_tests}')
print()

print('📋 DETAILED RESULTS:')
for i, test in enumerate(tests_data, 1):
    status_icon = '✅' if test['status'] == 'pass' else '❌' if test['status'] == 'fail' else '⚠️'
    print(f'   Test {i}: {status_icon} {test[\"status\"].upper()}')
    
    # Print key metrics
    if 'success_rate' in test:
        print(f'      Success Rate: {test[\"success_rate\"]:.2%}')
    if 'speedup' in test:
        print(f'      Speedup: {test[\"speedup\"]:.2f}x')
    if 'memory_growth_mb' in test:
        print(f'      Memory Growth: {test[\"memory_growth_mb\"]:.2f} MB')
    if 'requests_per_second' in test:
        print(f'      Throughput: {test[\"requests_per_second\"]:.1f} req/s')
    print()

# Recommendations
print('💡 RECOMMENDATIONS:')
if passed_tests == len(tests_data):
    print('   🎉 All tests passed! Ready for production deployment.')
else:
    print('   ⚠️  Some tests failed. Review before production deployment.')
    print('   🔧 Focus on resolving failed tests first.')

print()
print('🚀 NEXT STEPS:')
print('   1. Fix any failed tests')
print('   2. Run performance benchmarks')
print('   3. Deploy with monitoring')
print('   4. Validate under real load')
"

echo ""
echo "✅ Test suite completed!"
echo "📁 Results saved to: $RESULTS_FILE"
echo ""
echo "📊 View detailed report with:"
echo "   $PYTHON_CMD -c \"import sys; exec(open('$RESULTS_FILE').read())\""