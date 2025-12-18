#!/bin/bash

# Free-Threading Performance Benchmark Script
# Tests single-threaded vs multi-threaded performance for the proxy server

set -e

echo "🚀 Python Free-Threading Performance Benchmark"
echo "======================================="

# Check for free-threaded Python
if command -v python3.13t &> /dev/null; then
    PYTHON_CMD="python3.13t"
    PYTHON_VERSION="3.13t"
elif command -v python3.14t &> /dev/null; then
    PYTHON_CMD="python3.14t"
    PYTHON_VERSION="3.14t"
else
    echo "❌ No free-threaded Python found. Please install python3.13t or python3.14t"
    exit 1
fi

echo "🐍 Using Python: $PYTHON_VERSION"
echo "🔓 GIL Status: $($PYTHON_CMD -c "import sys; print('Disabled' if not sys._is_gil_enabled() else 'Enabled')")"

# Create benchmark directory
BENCH_DIR="benchmark_results"
mkdir -p $BENCH_DIR

# Create comprehensive benchmark script
cat > benchmark_comprehensive.py << 'EOF'
import sys
import time
import json
import threading
import asyncio
import aiohttp
import statistics
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Dict, Any
import requests

class ProxyBenchmarkSuite:
    """Comprehensive benchmark suite for free-threading evaluation"""
    
    def __init__(self):
        self.results = {}
        self.python_version = sys.version
        self.gil_enabled = sys._is_gil_enabled()
        self.cpu_count = threading.active_count()
    
    def run_all_benchmarks(self):
        """Run complete benchmark suite"""
        print(f"Python: {self.python_version}")
        print(f"GIL Enabled: {self.gil_enabled}")
        print(f"CPU Count: {self.cpu_count}")
        print()
        
        # 1. CPU-intensive benchmark
        self.results['cpu_intensive'] = self.benchmark_cpu_intensive()
        
        # 2. I/O-bound benchmark (HTTP requests)
        self.results['io_bound'] = self.benchmark_io_bound()
        
        # 3. Mixed workload benchmark
        self.results['mixed_workload'] = self.benchmark_mixed_workload()
        
        # 4. Concurrent streaming simulation
        self.results['streaming_simulation'] = self.benchmark_streaming_simulation()
        
        # 5. Memory allocation test
        self.results['memory_allocation'] = self.benchmark_memory_allocation()
        
        return self.results
    
    def benchmark_cpu_intensive(self):
        """Test pure CPU computation"""
        print("🧮 CPU-Intensive Benchmark...")
        
        def compute_fibonacci(n):
            """Compute Fibonacci number recursively"""
            if n <= 1:
                return n
            return compute_fibonacci(n-1) + compute_fibonacci(n-2)
        
        def cpu_task():
            return compute_fibonacci(35)  # Takes ~0.1 seconds
        
        # Single-threaded
        start = time.time()
        for _ in range(20):
            cpu_task()
        single_time = time.time() - start
        
        # Multi-threaded
        start = time.time()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(cpu_task) for _ in range(20)]
            results = [f.result() for f in futures]
        multi_time = time.time() - start
        
        speedup = single_time / multi_time
        efficiency = speedup / 4 * 100  # Perfect scaling would be 4x
        
        return {
            'single_time': single_time,
            'multi_time': multi_time,
            'speedup': speedup,
            'efficiency_percent': efficiency,
            'threads_used': 4
        }
    
    def benchmark_io_bound(self):
        """Test I/O-bound operations (simulated HTTP requests)"""
        print("🌐 I/O-Bound Benchmark...")
        
        def io_task():
            # Simulate HTTP request with delay
            time.sleep(0.1)  # 100ms delay
            return "response_data"
        
        # Single-threaded
        start = time.time()
        results = []
        for _ in range(50):
            results.append(io_task())
        single_time = time.time() - start
        
        # Multi-threaded
        start = time.time()
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(io_task) for _ in range(50)]
            results = [f.result() for f in futures]
        multi_time = time.time() - start
        
        speedup = single_time / multi_time
        efficiency = speedup / 8 * 100
        
        return {
            'single_time': single_time,
            'multi_time': multi_time,
            'speedup': speedup,
            'efficiency_percent': efficiency,
            'requests_processed': len(results),
            'threads_used': 8
        }
    
    def benchmark_mixed_workload(self):
        """Test mixed CPU and I/O operations"""
        print("⚖️  Mixed Workload Benchmark...")
        
        def mixed_task():
            # Mix of CPU and I/O
            total = 0
            for i in range(1000):  # CPU work
                total += i * i
            time.sleep(0.01)  # I/O work
            return total
        
        iterations = 30
        
        # Single-threaded
        start = time.time()
        single_results = []
        for _ in range(iterations):
            single_results.append(mixed_task())
        single_time = time.time() - start
        
        # Multi-threaded
        start = time.time()
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(mixed_task) for _ in range(iterations)]
            multi_results = [f.result() for f in futures]
        multi_time = time.time() - start
        
        speedup = single_time / multi_time
        efficiency = speedup / 6 * 100
        
        return {
            'single_time': single_time,
            'multi_time': multi_time,
            'speedup': speedup,
            'efficiency_percent': efficiency,
            'iterations': iterations,
            'threads_used': 6
        }
    
    def benchmark_streaming_simulation(self):
        """Simulate concurrent streaming responses"""
        print("📡 Streaming Simulation Benchmark...")
        
        def streaming_task():
            """Simulate processing streaming response"""
            chunks = []
            for i in range(100):  # 100 chunks
                chunk_data = f"chunk_{i}_data_{i*10}"
                chunks.append(chunk_data)
                time.sleep(0.001)  # Small delay to simulate I/O
            return len(chunks)
        
        concurrent_streams = 10
        
        # Single-threaded (sequential)
        start = time.time()
        single_results = []
        for _ in range(concurrent_streams):
            single_results.append(streaming_task())
        single_time = time.time() - start
        
        # Multi-threaded (concurrent)
        start = time.time()
        with ThreadPoolExecutor(max_workers=concurrent_streams) as executor:
            futures = [executor.submit(streaming_task) for _ in range(concurrent_streams)]
            multi_results = [f.result() for f in futures]
        multi_time = time.time() - start
        
        speedup = single_time / multi_time
        efficiency = speedup / concurrent_streams * 100
        
        return {
            'single_time': single_time,
            'multi_time': multi_time,
            'speedup': speedup,
            'efficiency_percent': efficiency,
            'concurrent_streams': concurrent_streams,
            'threads_used': concurrent_streams
        }
    
    def benchmark_memory_allocation(self):
        """Test memory allocation patterns"""
        print("💾 Memory Allocation Benchmark...")
        
        def memory_task():
            # Allocate and process data
            data = []
            for i in range(10000):
                data.append({
                    'id': i,
                    'data': f'item_{i}',
                    'metadata': {'timestamp': time.time()}
                })
            # Process data
            processed = sum(item['id'] for item in data)
            return processed
        
        iterations = 20
        
        # Single-threaded
        start = time.time()
        for _ in range(iterations):
            memory_task()
        single_time = time.time() - start
        
        # Multi-threaded
        start = time.time()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(memory_task) for _ in range(iterations)]
            results = [f.result() for f in futures]
        multi_time = time.time() - start
        
        speedup = single_time / multi_time
        efficiency = speedup / 4 * 100
        
        return {
            'single_time': single_time,
            'multi_time': multi_time,
            'speedup': speedup,
            'efficiency_percent': efficiency,
            'iterations': iterations,
            'threads_used': 4
        }
    
    def format_results(self):
        """Format benchmark results for display"""
        print()
        print("📊 BENCHMARK RESULTS")
        print("=" * 50)
        
        for test_name, result in self.results.items():
            print(f"\n🧪 {test_name.replace('_', ' ').title()}:")
            print(f"   Single-threaded: {result['single_time']:.3f}s")
            print(f"   Multi-threaded:   {result['multi_time']:.3f}s")
            print(f"   Speedup:         {result['speedup']:.2f}x")
            print(f"   Efficiency:       {result['efficiency_percent']:.1f}%")
            if 'threads_used' in result:
                print(f"   Threads used:     {result['threads_used']}")
        
        # Summary
        speedups = [r['speedup'] for r in self.results.values()]
        avg_speedup = statistics.mean(speedups)
        print(f"\n🎯 Average Speedup: {avg_speedup:.2f}x")
        print(f"🎯 Best Speedup: {max(speedups):.2f}x")
        print(f"🎯 Worst Speedup: {min(speedups):.2f}x")
        
        return self.results

def run_benchmark():
    """Main benchmark execution"""
    suite = ProxyBenchmarkSuite()
    results = suite.run_all_benchmarks()
    return suite.format_results()

if __name__ == "__main__":
    # Run benchmark and capture results
    results = run_benchmark()
    
    # Save results to JSON file
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = f"benchmark_results/free_threading_benchmark_{timestamp}.json"
    
    benchmark_data = {
        'timestamp': timestamp,
        'python_version': sys.version,
        'gil_enabled': sys._is_gil_enabled(),
        'results': results
    }
    
    with open(output_file, 'w') as f:
        json.dump(benchmark_data, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
EOF

echo "🧪 Running comprehensive benchmark..."
$PYTHON_CMD benchmark_comprehensive.py

# Create comparison script (if both standard and free-threaded available)
echo "📊 Creating comparison tool..."
cat > compare_results.py << 'EOF'
import json
import sys
import glob
from statistics import mean

def load_benchmark_files():
    """Load all benchmark result files"""
    files = glob.glob("benchmark_results/*.json")
    results = {}
    
    for file in files:
        with open(file, 'r') as f:
            data = json.load(f)
            version = data['python_version'].split()[0]
            gil_status = "GIL" if data['gil_enabled'] else "No-GIL"
            key = f"{version} ({gil_status})"
            results[key] = data
    
    return results

def compare_performance(results):
    """Compare performance between different Python versions"""
    if len(results) < 2:
        print("Need at least 2 benchmark results to compare")
        return
    
    print("📊 PERFORMANCE COMPARISON")
    print("=" * 50)
    
    test_names = list(list(results.values())[0]['results'].keys())
    
    for test_name in test_names:
        print(f"\n🧪 {test_name.replace('_', ' ').title()}:")
        
        for version, data in results.items():
            result = data['results'][test_name]
            print(f"   {version}: {result['speedup']:.2f}x speedup")
    
    # Calculate overall performance improvement
    if len(results) == 2:
        versions = list(results.keys())
        gil_speedups = [results[v]['results'][t]['speedup'] for t in results[versions[0]]['results']]
        no_gil_speedups = [results[v]['results'][t]['speedup'] for t in results[versions[1]]['results']]
        
        if mean(no_gil_speedups) > mean(gil_speedups):
            improvement = mean(no_gil_speedups) / mean(gil_speedups)
            print(f"\n🚀 Free-threading improvement: {improvement:.2f}x average speedup")

if __name__ == "__main__":
    results = load_benchmark_files()
    compare_performance(results)
EOF

echo ""
echo "✅ Benchmark complete!"
echo ""
echo "📋 Files created:"
echo "   - benchmark_comprehensive.py (comprehensive performance test)"
echo "   - compare_results.py (comparison tool)"
echo "   - benchmark_results/ (result directory)"
echo ""
echo "🚀 Run benchmarks with different Python versions to compare:"
echo "   Standard: python benchmark_comprehensive.py"
echo "   Free-threading: $PYTHON_CMD benchmark_comprehensive.py"
echo "   Compare: python compare_results.py"