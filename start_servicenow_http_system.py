#!/usr/bin/env python3
"""
ServiceNow MCP System - HTTP Transport Startup
Daemon-style startup script for HTTP-based MCP servers and Magentic-UI
"""

import subprocess
import os
import time
import pathlib
import requests
from dotenv import load_dotenv, find_dotenv

PID_DIR = pathlib.Path(".servicenow_pids")
TABLE_SERVER_PID_FILE = PID_DIR / "table_server.pid"
KNOWLEDGE_SERVER_PID_FILE = PID_DIR / "knowledge_server.pid"
MAGENTIC_UI_PID_FILE = PID_DIR / "magentic_ui.pid"


def get_pid(pid_file):
    if pid_file.exists():
        try:
            return int(pid_file.read_text().strip())
        except ValueError:
            return None
    return None


def is_process_running(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)  # Check if process exists
        return True
    except OSError:
        return False


def stop_service(name, pid_file, process_name_grep):
    print(f"🛑 Stopping {name}...")
    pid = get_pid(pid_file)
    if pid and is_process_running(pid):
        try:
            os.kill(pid, 15)  # SIGTERM
            time.sleep(2)  # Give it time to shut down
            if is_process_running(pid):
                os.kill(pid, 9)  # SIGKILL if still running
                print(f"   Force-killed {name} (PID: {pid})")
            else:
                print(f"✅ {name} stopped gracefully")
        except OSError as e:
            print(f"❌ Error stopping {name} (PID: {pid}): {e}")
    else:
        print(f"   {name} not running or PID file missing.")

    # Also kill any lingering processes by name
    try:
        subprocess.run(
            ["pkill", "-f", process_name_grep],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
    except subprocess.CalledProcessError:
        pass  # Process not found, no big deal

    if pid_file.exists():
        pid_file.unlink()


def start_service(name, cmd, pid_file, env=None):
    print(f"📊 Starting {name}...")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
            env=env,
        )
        pid_file.write_text(str(process.pid))
        print(f"✅ {name} started successfully (PID: {process.pid})")
        return process.pid
    except Exception as e:
        print(f"❌ Failed to start {name}: {e}")
        return None


def check_health(url):
    """Check if MCP HTTP endpoint is responding properly."""
    try:
        # Test with a simple MCP initialize request
        payload = {
            "jsonrpc": "2.0",
            "id": "health-check",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "HealthCheck", "version": "1.0.0"}
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        # MCP server should respond with JSON-RPC, even if it's an error about session
        return response.status_code in [200, 400] and response.headers.get('content-type', '').startswith('application/json')
    except requests.exceptions.RequestException:
        return False


def main():
    # Load environment variables
    load_dotenv(find_dotenv())
    
    # Get ports from environment with defaults
    MAGENTIC_UI_PORT = os.getenv("MAGENTIC_UI_PORT", "8090")
    TABLE_API_PORT = os.getenv("SERVICENOW_TABLE_API_PORT", "3001")
    KNOWLEDGE_API_PORT = os.getenv("SERVICENOW_KNOWLEDGE_API_PORT", "3002")
    
    print("🚀 ServiceNow MCP System - HTTP Transport Startup")
    print("=" * 55)
    print(f"📡 Ports: Magentic-UI={MAGENTIC_UI_PORT}, Table={TABLE_API_PORT}, Knowledge={KNOWLEDGE_API_PORT}")

    # Ensure PID directory exists
    PID_DIR.mkdir(exist_ok=True)

    # Check for required files
    required_files = [
        "servicenow_table_http_server.py",
        "servicenow_knowledge_http_server.py",
        "servicenow_final_config.yaml",
        "openapi_specs/servicenow_table_api_final.json",
        "openapi_specs/servicenow_knowledge_api_final.json",
    ]
    for f in required_files:
        if not pathlib.Path(f).exists():
            print(f"❌ Missing required file: {f}")
            return

    print("✅ All required files found")

    # Stop existing services
    stop_service("Magentic-UI", MAGENTIC_UI_PID_FILE, "magentic-ui")
    stop_service(
        "ServiceNow Table API Server",
        TABLE_SERVER_PID_FILE,
        "servicenow_table_http_server.py",
    )
    stop_service(
        "ServiceNow Knowledge API Server",
        KNOWLEDGE_SERVER_PID_FILE,
        "servicenow_knowledge_http_server.py",
    )

    # Start HTTP MCP servers as separate processes
    table_env = os.environ.copy()
    table_env["SERVICENOW_TABLE_API_PORT"] = TABLE_API_PORT
    
    knowledge_env = os.environ.copy()
    knowledge_env["SERVICENOW_KNOWLEDGE_API_PORT"] = KNOWLEDGE_API_PORT
    
    table_pid = start_service(
        "ServiceNow Table API Server",
        [".venv/bin/python", "servicenow_table_http_server.py"],
        TABLE_SERVER_PID_FILE,
        env=table_env,
    )
    knowledge_pid = start_service(
        "ServiceNow Knowledge API Server",
        [".venv/bin/python", "servicenow_knowledge_http_server.py"],
        KNOWLEDGE_SERVER_PID_FILE,
        env=knowledge_env,
    )

    print("⏳ Waiting for MCP servers to initialize...")
    time.sleep(5)

    magentic_ui_pid = start_service(
        "Magentic-UI",
        [
            ".venv/bin/magentic-ui",
            "--host",
            "localhost",
            "--port",
            MAGENTIC_UI_PORT,
            "--config",
            "servicenow_final_config.yaml",
        ],
        MAGENTIC_UI_PID_FILE,
    )

    print("\n📊 Service Status:")
    print("========================================")

    table_running = is_process_running(table_pid)
    knowledge_running = is_process_running(knowledge_pid)
    magentic_ui_running = is_process_running(magentic_ui_pid)

    print(
        f"✅ Table API Server: {'Running' if table_running else 'Stopped'} (PID: {table_pid}) - http://localhost:{TABLE_API_PORT}"
    )
    print(
        f"✅ Knowledge API Server: {'Running' if knowledge_running else 'Stopped'} (PID: {knowledge_pid}) - http://localhost:{KNOWLEDGE_API_PORT}"
    )
    print(
        f"✅ Magentic-UI: {'Running' if magentic_ui_running else 'Stopped'} (PID: {magentic_ui_pid}) - http://localhost:{MAGENTIC_UI_PORT}"
    )

    if table_running and knowledge_running and magentic_ui_running:
        print("\n🎉 All services started successfully!")
        print(f"\n🌐 Access your system at: http://localhost:{MAGENTIC_UI_PORT}")
        print("\n📋 Available agents:")
        print("   • servicenow_table_agent (Table API)")
        print("   • servicenow_knowledge_agent (Knowledge Management)")
        print("   • Plus default agents: web_surfer, coder_agent, file_surfer")
        print(
            "\n💡 Use '.venv/bin/python stop_servicenow_system.py' to stop all services"
        )
        print("💡 HTTP MCP servers running independently - more reliable!")
    else:
        print("\n⚠️  Some services failed to start. Check logs for details.")


if __name__ == "__main__":
    main()
