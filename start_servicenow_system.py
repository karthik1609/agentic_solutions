#!/usr/bin/env python3
"""
ServiceNow MCP System - Daemon Startup Script
Starts MCP servers and Magentic-UI in detached mode
"""

import subprocess
import time
import sys
import os
import signal
import json
from pathlib import Path

# PID file locations
PID_DIR = Path(".servicenow_pids")
TABLE_PID_FILE = PID_DIR / "table_server.pid"
KNOWLEDGE_PID_FILE = PID_DIR / "knowledge_server.pid"
MAGENTIC_PID_FILE = PID_DIR / "magentic_ui.pid"

def ensure_pid_dir():
    """Ensure PID directory exists"""
    PID_DIR.mkdir(exist_ok=True)

def write_pid_file(pid_file: Path, pid: int):
    """Write PID to file"""
    with open(pid_file, 'w') as f:
        f.write(str(pid))

def read_pid_file(pid_file: Path) -> int:
    """Read PID from file"""
    try:
        with open(pid_file, 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None

def is_process_running(pid: int) -> bool:
    """Check if process is running"""
    if not pid:
        return False
    try:
        os.kill(pid, 0)  # Send signal 0 to check if process exists
        return True
    except (OSError, ProcessLookupError):
        return False

def kill_process(pid: int, name: str):
    """Kill a process by PID"""
    if not pid:
        return
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(2)
        if is_process_running(pid):
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
        print(f"✅ Stopped {name} (PID: {pid})")
    except (OSError, ProcessLookupError):
        print(f"⚠️  {name} (PID: {pid}) was not running")

def stop_existing_services():
    """Stop any existing services"""
    print("🛑 Stopping existing services...")
    
    # Stop services by PID files
    table_pid = read_pid_file(TABLE_PID_FILE)
    knowledge_pid = read_pid_file(KNOWLEDGE_PID_FILE)
    magentic_pid = read_pid_file(MAGENTIC_PID_FILE)
    
    if table_pid:
        kill_process(table_pid, "Table API Server")
    if knowledge_pid:
        kill_process(knowledge_pid, "Knowledge API Server")
    if magentic_pid:
        kill_process(magentic_pid, "Magentic-UI")
    
    # Also kill by process name (backup)
    subprocess.run(["pkill", "-f", "servicenow.*sse_server"], capture_output=True)
    subprocess.run(["pkill", "-f", "magentic-ui"], capture_output=True)
    
    # Clean up PID files
    for pid_file in [TABLE_PID_FILE, KNOWLEDGE_PID_FILE, MAGENTIC_PID_FILE]:
        if pid_file.exists():
            pid_file.unlink()
    
    time.sleep(2)

def check_prerequisites():
    """Check if all required files exist"""
    required_files = [
        "servicenow_table_sse_server.py",
        "servicenow_knowledge_sse_server.py",
        "servicenow_final_config.yaml",
        "openapi_specs/servicenow_table_api_final.json",
        "openapi_specs/servicenow_knowledge_api_final.json",
        ".env"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    
    print("✅ All required files found")
    return True

def start_mcp_server(script_name: str, server_name: str, pid_file: Path) -> bool:
    """Start an MCP server in detached mode"""
    print(f"📊 Starting {server_name}...")
    
    try:
        # Start process in detached mode
        process = subprocess.Popen([
            "uv", "run", "python", script_name
        ], 
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        preexec_fn=os.setsid  # Create new process group
        )
        
        # Write PID file
        write_pid_file(pid_file, process.pid)
        
        # Give it a moment to start
        time.sleep(30)
        
        # Check if it's still running
        if is_process_running(process.pid):
            print(f"✅ {server_name} started successfully (PID: {process.pid})")
            return True
        else:
            print(f"❌ {server_name} failed to start")
            return False
            
    except Exception as e:
        print(f"❌ Failed to start {server_name}: {e}")
        return False

def start_magentic_ui() -> bool:
    """Start Magentic-UI in detached mode"""
    print("🎭 Starting Magentic-UI...")
    
    try:
        # Start Magentic-UI in detached mode
        process = subprocess.Popen([
            ".venv/bin/magentic-ui",
            # "--host", "localhost",
            "--port", "8080", 
            "--config", "servicenow_final_config.yaml"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        preexec_fn=os.setsid  # Create new process group
        )
        
        # Write PID file
        write_pid_file(MAGENTIC_PID_FILE, process.pid)
        
        # Give it time to start
        time.sleep(5)
        
        # Check if it's running
        if is_process_running(process.pid):
            print(f"✅ Magentic-UI started successfully (PID: {process.pid})")
            return True
        else:
            print("❌ Magentic-UI failed to start")
            return False
            
    except Exception as e:
        print(f"❌ Failed to start Magentic-UI: {e}")
        return False

def check_services_status():
    """Check and display service status"""
    print("\n📊 Service Status:")
    print("=" * 40)
    
    services = [
        ("Table API Server", TABLE_PID_FILE, "http://localhost:3001/sse"),
        ("Knowledge API Server", KNOWLEDGE_PID_FILE, "http://localhost:3002/sse"),
        ("Magentic-UI", MAGENTIC_PID_FILE, "http://localhost:8080")
    ]
    
    all_running = True
    
    for name, pid_file, url in services:
        pid = read_pid_file(pid_file)
        if pid and is_process_running(pid):
            print(f"✅ {name}: Running (PID: {pid}) - {url}")
        else:
            print(f"❌ {name}: Not running")
            all_running = False
    
    return all_running

def main():
    print("🚀 ServiceNow MCP System - Daemon Startup")
    print("=" * 50)
    
    # Ensure PID directory exists
    ensure_pid_dir()
    
    # Check prerequisites
    if not check_prerequisites():
        return 1
    
    # Stop existing services (restart if already running)
    stop_existing_services()
    
    # Start MCP servers
    table_success = start_mcp_server(
        "servicenow_table_sse_server.py",
        "ServiceNow Table API Server", 
        TABLE_PID_FILE
    )
    
    knowledge_success = start_mcp_server(
        "servicenow_knowledge_sse_server.py",
        "ServiceNow Knowledge API Server",
        KNOWLEDGE_PID_FILE
    )
    
    if not (table_success and knowledge_success):
        print("❌ Failed to start MCP servers. Aborting.")
        stop_existing_services()
        return 1
    
    # Start Magentic-UI
    magentic_success = start_magentic_ui()
    
    if not magentic_success:
        print("❌ Failed to start Magentic-UI. Stopping MCP servers.")
        stop_existing_services()
        return 1
    
    # Final status check
    if check_services_status():
        print("\n🎉 All services started successfully!")
        print("\n🌐 Access your system at: http://localhost:8080")
        print("\n📋 Available agents:")
        print("   • servicenow_table_agent (Table API)")
        print("   • servicenow_knowledge_agent (Knowledge Management)")
        print("   • Plus default agents: web_surfer, coder_agent, file_surfer")
        print("\n💡 Use 'python stop_servicenow_system.py' to stop all services")
        return 0
    else:
        print("\n❌ Some services failed to start properly")
        return 1

if __name__ == "__main__":
    sys.exit(main())