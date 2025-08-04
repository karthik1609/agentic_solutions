#!/usr/bin/env python3
"""
ServiceNow MCP System - Daemon Shutdown Script
Stops all MCP servers and Magentic-UI services
"""

import os
import signal
import time
import subprocess
from pathlib import Path

# PID file locations
PID_DIR = Path(".servicenow_pids")
TABLE_PID_FILE = PID_DIR / "table_server.pid"
KNOWLEDGE_PID_FILE = PID_DIR / "knowledge_server.pid"
MAGENTIC_PID_FILE = PID_DIR / "magentic_ui.pid"

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

def kill_process_gracefully(pid: int, name: str, timeout: int = 10):
    """Kill a process gracefully with timeout"""
    if not pid:
        print(f"⚠️  No PID found for {name}")
        return
    
    if not is_process_running(pid):
        print(f"⚠️  {name} (PID: {pid}) is not running")
        return
    
    try:
        print(f"🛑 Stopping {name} (PID: {pid})...")
        
        # Try SIGTERM first (graceful shutdown)
        os.kill(pid, signal.SIGTERM)
        
        # Wait for graceful shutdown
        for i in range(timeout):
            if not is_process_running(pid):
                print(f"✅ {name} stopped gracefully")
                return
            time.sleep(1)
        
        # If still running, force kill
        print(f"⚠️  {name} didn't stop gracefully, forcing...")
        os.kill(pid, signal.SIGKILL)
        time.sleep(2)
        
        if is_process_running(pid):
            print(f"❌ Failed to stop {name}")
        else:
            print(f"✅ {name} force stopped")
            
    except (OSError, ProcessLookupError):
        print(f"⚠️  {name} (PID: {pid}) was already stopped")

def kill_by_process_name():
    """Kill processes by name (backup method)"""
    print("🧹 Cleaning up any remaining processes...")
    
    # Kill ServiceNow MCP servers
    result = subprocess.run(["pkill", "-f", "servicenow.*sse_server"], capture_output=True)
    if result.returncode == 0:
        print("✅ Killed remaining ServiceNow MCP servers")
    
    # Kill Magentic-UI
    result = subprocess.run(["pkill", "-f", "magentic-ui"], capture_output=True)
    if result.returncode == 0:
        print("✅ Killed remaining Magentic-UI processes")
    
    # Kill any remaining processes on our ports
    for port in [3001, 3002, 8090]:
        result = subprocess.run([
            "lsof", "-ti", f":{port}"
        ], capture_output=True, text=True)
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    subprocess.run(["kill", "-TERM", pid], capture_output=True)
                    print(f"✅ Killed process {pid} on port {port}")
                except:
                    pass

def cleanup_pid_files():
    """Remove all PID files"""
    print("🗂️  Cleaning up PID files...")
    
    pid_files = [TABLE_PID_FILE, KNOWLEDGE_PID_FILE, MAGENTIC_PID_FILE]
    
    for pid_file in pid_files:
        if pid_file.exists():
            try:
                pid_file.unlink()
                print(f"✅ Removed {pid_file.name}")
            except Exception as e:
                print(f"❌ Failed to remove {pid_file.name}: {e}")
    
    # Remove PID directory if empty
    try:
        if PID_DIR.exists() and not any(PID_DIR.iterdir()):
            PID_DIR.rmdir()
            print("✅ Removed empty PID directory")
    except:
        pass

def check_final_status():
    """Check if all services are stopped"""
    print("\n📊 Final Status Check:")
    print("=" * 30)
    
    services = [
        ("Table API Server", TABLE_PID_FILE),
        ("Knowledge API Server", KNOWLEDGE_PID_FILE), 
        ("Magentic-UI", MAGENTIC_PID_FILE)
    ]
    
    all_stopped = True
    
    for name, pid_file in services:
        pid = read_pid_file(pid_file)
        if pid and is_process_running(pid):
            print(f"❌ {name}: Still running (PID: {pid})")
            all_stopped = False
        else:
            print(f"✅ {name}: Stopped")
    
    return all_stopped

def main():
    print("🛑 ServiceNow MCP System - Daemon Shutdown")
    print("=" * 50)
    
    if not PID_DIR.exists():
        print("⚠️  No PID directory found. Services may not be running.")
        print("🧹 Attempting cleanup anyway...")
    
    # Stop services by PID
    services = [
        ("ServiceNow Table API Server", TABLE_PID_FILE),
        ("ServiceNow Knowledge API Server", KNOWLEDGE_PID_FILE),
        ("Magentic-UI", MAGENTIC_PID_FILE)
    ]
    
    for name, pid_file in services:
        pid = read_pid_file(pid_file)
        kill_process_gracefully(pid, name)
    
    # Backup cleanup by process name
    kill_by_process_name()
    
    # Wait a moment for processes to fully terminate
    time.sleep(2)
    
    # Clean up PID files
    cleanup_pid_files()
    
    # Final status check
    if check_final_status():
        print("\n🎉 All services stopped successfully!")
        print("💡 Use 'python start_servicenow_system.py' to start services again")
        return 0
    else:
        print("\n⚠️  Some services may still be running")
        print("💡 You may need to check manually with 'ps aux | grep servicenow'")
        return 1

if __name__ == "__main__":
    exit(main())