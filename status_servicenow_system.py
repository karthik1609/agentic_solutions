#!/usr/bin/env python3
"""
ServiceNow MCP System - Status Checker
Check the status of all running services
"""

import os
import subprocess
import requests
import time
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
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def check_url_health(url: str, timeout: int = 5) -> bool:
    """Check if URL is responding"""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except:
        return False

def get_process_info(pid: int) -> dict:
    """Get process information"""
    if not pid or not is_process_running(pid):
        return None
    
    try:
        # Get process info using ps
        result = subprocess.run([
            "ps", "-p", str(pid), "-o", "pid,ppid,pcpu,pmem,etime,cmd"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                fields = lines[1].split()
                return {
                    'pid': fields[0],
                    'ppid': fields[1], 
                    'cpu': fields[2],
                    'memory': fields[3],
                    'runtime': fields[4],
                    'command': ' '.join(fields[5:])
                }
    except:
        pass
    
    return {'pid': str(pid), 'status': 'running'}

def check_port_usage():
    """Check which processes are using our ports"""
    ports = [3001, 3002, 8090]
    port_info = {}
    
    for port in ports:
        try:
            result = subprocess.run([
                "lsof", "-ti", f":{port}"
            ], capture_output=True, text=True)
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                port_info[port] = pids
            else:
                port_info[port] = []
        except:
            port_info[port] = []
    
    return port_info

def main():
    print("📊 ServiceNow MCP System - Status Check")
    print("=" * 50)
    
    # Check if PID directory exists
    if not PID_DIR.exists():
        print("⚠️  PID directory not found. Services may not be running via daemon.")
        print("🔍 Checking for processes anyway...\n")
    
    # Service definitions
    services = [
        {
            'name': 'ServiceNow Table API Server',
            'pid_file': TABLE_PID_FILE,
            'url': 'http://localhost:3001/sse',
            'port': 3001
        },
        {
            'name': 'ServiceNow Knowledge API Server', 
            'pid_file': KNOWLEDGE_PID_FILE,
            'url': 'http://localhost:3002/sse',
            'port': 3002
        },
        {
            'name': 'Magentic-UI',
            'pid_file': MAGENTIC_PID_FILE,
            'url': 'http://localhost:8090/api/health',
            'port': 8090
        }
    ]
    
    # Check port usage
    port_info = check_port_usage()
    
    all_healthy = True
    
    # Check each service
    for service in services:
        print(f"🔍 {service['name']}:")
        print("-" * 30)
        
        # Check PID file
        pid = read_pid_file(service['pid_file'])
        if pid:
            print(f"📄 PID File: {pid}")
            
            # Check if process is running
            if is_process_running(pid):
                print(f"✅ Process: Running")
                
                # Get detailed process info
                proc_info = get_process_info(pid)
                if proc_info:
                    print(f"💾 Memory: {proc_info.get('memory', 'N/A')}%")
                    print(f"⚡ CPU: {proc_info.get('cpu', 'N/A')}%")
                    print(f"⏱️  Runtime: {proc_info.get('runtime', 'N/A')}")
                
            else:
                print(f"❌ Process: Not running (stale PID file)")
                all_healthy = False
        else:
            print(f"⚠️  PID File: Not found")
            
            # Check if something else is using the port
            port_pids = port_info.get(service['port'], [])
            if port_pids:
                print(f"🔌 Port {service['port']}: Used by PIDs {port_pids}")
            else:
                print(f"🔌 Port {service['port']}: Available")
                all_healthy = False
        
        # Check URL health
        print(f"🌐 Testing: {service['url']}")
        if check_url_health(service['url']):
            print(f"✅ Health: Responding")
        else:
            print(f"❌ Health: Not responding")
            all_healthy = False
        
        print()
    
    # Overall status
    print("=" * 50)
    if all_healthy:
        print("🎉 System Status: All services are healthy!")
        print("🌐 Access your system at: http://localhost:8090")
    else:
        print("⚠️  System Status: Some issues detected")
        print("💡 Try: python stop_servicenow_system.py && python start_servicenow_system.py")
    
    # Additional info
    print("\n📋 Quick Commands:")
    print("   Start:  python start_servicenow_system.py")
    print("   Stop:   python stop_servicenow_system.py") 
    print("   Status: python status_servicenow_system.py")
    print("   Clean:  python cleanup_junk.py")
    
    return 0 if all_healthy else 1

if __name__ == "__main__":
    exit(main())