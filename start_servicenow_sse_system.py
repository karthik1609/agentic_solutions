#!/usr/bin/env python3
"""
Start ServiceNow MCP System with SSE Transport
Starts SSE MCP servers first, then magentic-ui
"""

import subprocess
import time
import sys
import signal
import os
from pathlib import Path

# Store process references for cleanup
processes = []

def cleanup_processes():
    """Clean up all started processes"""
    print("\n🧹 Cleaning up processes...")
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass
    processes.clear()

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    cleanup_processes()
    sys.exit(0)

def main():
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🚀 Starting ServiceNow MCP System with SSE Transport")
    print("=" * 60)
    
    # Check required files
    required_files = [
        "servicenow_table_sse_server.py",
        "servicenow_knowledge_sse_server.py", 
        "servicenow_final_config.yaml",
        "openapi_specs/servicenow_table_api_final.json",
        "openapi_specs/servicenow_knowledge_api_final.json"
    ]
    
    missing_files = [f for f in required_files if not Path(f).exists()]
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return 1
        
    print("✅ All required files found")
    
    # Kill any existing processes on our ports
    print("🔧 Cleaning up existing processes...")
    subprocess.run(["pkill", "-f", "magentic-ui"], capture_output=True)
    subprocess.run(["pkill", "-f", "servicenow.*sse_server"], capture_output=True)
    time.sleep(2)
    
    try:
        # Start ServiceNow Table API SSE server
        print("📊 Starting ServiceNow Table API SSE server on port 3001...")
        table_log = "table_sse_server.log"
        with open(table_log, "w") as log_file:
            table_proc = subprocess.Popen([
                "uv", "run", "python", "servicenow_table_sse_server.py"
            ], stdout=log_file, stderr=subprocess.STDOUT)
        processes.append(table_proc)

        # Start ServiceNow Knowledge API SSE server
        print("📚 Starting ServiceNow Knowledge API SSE server on port 3002...")
        knowledge_log = "knowledge_sse_server.log"
        with open(knowledge_log, "w") as log_file:
            knowledge_proc = subprocess.Popen([
                "uv", "run", "python", "servicenow_knowledge_sse_server.py"
            ], stdout=log_file, stderr=subprocess.STDOUT)
        processes.append(knowledge_proc)
        
        # Wait for servers to start
        print("⏳ Waiting for MCP servers to initialize...")
        time.sleep(5)
        
        # Check if servers are running
        if table_proc.poll() is not None:
            print("❌ Table API server failed to start")
            with open(table_log, "r", encoding="utf-8", errors="replace") as f:
                print(f"Error:\n{f.read()}")
            return 1

        if knowledge_proc.poll() is not None:
            print("❌ Knowledge API server failed to start")
            with open(knowledge_log, "r", encoding="utf-8", errors="replace") as f:
                print(f"Error:\n{f.read()}")
            return 1
            
        print("✅ MCP servers started successfully")
        
        # Start magentic-ui
        print("🎭 Starting magentic-ui...")
        magentic_proc = subprocess.Popen([
            ".venv/bin/magentic-ui", 
            "--host", "localhost", 
            "--port", "8080",
            "--config", "servicenow_final_config.yaml"
        ])
        processes.append(magentic_proc)
        
        print("🌐 System started! Access at: http://localhost:8080")
        print("📋 Available agents:")
        print("   • servicenow_table_agent (Table API)")
        print("   • servicenow_knowledge_agent (Knowledge Management)")
        print("   • Plus default agents: web_surfer, coder_agent, file_surfer")
        print("\nPress Ctrl+C to stop all services")
        
        # Wait for magentic-ui to finish
        magentic_proc.wait()
        
    except KeyboardInterrupt:
        print("\n⏹️ Received shutdown signal")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        cleanup_processes()
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
