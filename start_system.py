#!/usr/bin/env python3
"""
 ServiceNow MCP System - Consolidated Starter

This script starts the complete ServiceNow MCP system:
- Observability stack (OpenTelemetry, Prometheus, etc.)
- All MCP agents (auto-discovered from mcp_agents/ folder)
- Magentic-UI with proper configuration

Usage:
    python start_system.py [--no-observability] [--no-ui] [--config CONFIG_FILE]
"""

import os
import sys
import time
import signal
import subprocess
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional
import json

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from observability import init_observability, get_logger, shutdown_observability
except ImportError:
    print("  Observability module not found, continuing without observability...")
    def init_observability(*args, **kwargs):
        return logging.getLogger(__name__)
    def get_logger():
        return logging.getLogger(__name__)
    def shutdown_observability():
        pass

class SystemManager:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.pid_files: List[Path] = []
        self.logger = None
        self.project_root = Path(__file__).parent
        self.mcp_agents_dir = self.project_root / "mcp_agents"
        
    def _safe_log(self, level: str, message: str, **kwargs):
        """Safe logging method that handles both structured and standard logging"""
        if not self.logger:
            return
            
        log_method = getattr(self.logger, level.lower(), None)
        if not log_method:
            return
            
        try:
            # Try structured logging first (structlog)
            log_method(message, **kwargs)
        except TypeError:
            # Fallback to standard logging
            if kwargs:
                formatted_kwargs = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
                log_method(f"{message}: {formatted_kwargs}")
            else:
                log_method(message)
    
    def log_info(self, message: str, **kwargs):
        """Log info message"""
        self._safe_log("info", message, **kwargs)
    
    def log_error(self, message: str, **kwargs):
        """Log error message"""
        self._safe_log("error", message, **kwargs)
    
    def log_warning(self, message: str, **kwargs):
        """Log warning message"""
        self._safe_log("warning", message, **kwargs)
    
    def check_docker(self) -> bool:
        """Check if Docker is running"""
        try:
            result = subprocess.run(
                ["docker", "info"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def start_observability_stack(self) -> bool:
        """Start the observability stack using Docker Compose"""
        observability_dir = self.project_root / "observability"
        compose_file = observability_dir / "docker-compose.observability.yml"
        
        if not compose_file.exists():
            self.log_error("observability_compose_not_found", file=str(compose_file))
            return False
        
        if not self.check_docker():
            self.log_error("docker_not_running")
            print(" Docker is not running. Please start Docker and try again.")
            return False
        
        self.log_info("starting_observability_stack")
        print(" Starting observability stack (LGTM + Pyroscope)...")
        
        try:
            # Start the observability stack
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "up", "-d"],
                cwd=str(observability_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.log_info("observability_stack_started")
                print("    Observability stack started")
                
                # Mark that observability was started
                self._observability_started = True
                
                # Wait for services to be ready
                print("    Waiting for services to be ready...")
                time.sleep(15)
                return True
            else:
                self.log_error("observability_stack_failed", 
                             stdout=result.stdout, 
                             stderr=result.stderr)
                print(f"    Failed to start observability stack")
                print(f"   Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_error("observability_stack_timeout")
            print("    Timeout starting observability stack")
            return False
        except Exception as e:
            self.log_error("observability_stack_error", error=str(e))
            print(f"    Error starting observability stack: {e}")
            return False
    
    def stop_observability_stack(self) -> bool:
        """Stop the observability stack"""
        observability_dir = self.project_root / "observability"
        compose_file = observability_dir / "docker-compose.observability.yml"
        
        if not compose_file.exists():
            return True  # Nothing to stop
        
        self.log_info("stopping_observability_stack")
        print(" Stopping observability stack...")
        
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "down"],
                cwd=str(observability_dir),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.log_info("observability_stack_stopped")
                print("    Observability stack stopped")
                return True
            else:
                self.log_warning("observability_stack_stop_failed",
                               stdout=result.stdout,
                               stderr=result.stderr)
                return False
                
        except Exception as e:
            self.log_error("observability_stack_stop_error", error=str(e))
            return False
        
    def clear_old_logs(self):
        """Delete old .log files to avoid confusion with previous runs"""
        log_dir = self.project_root / "logs"
        if log_dir.exists():
            for f in log_dir.glob("*.log"):
                try:
                    f.unlink()
                except Exception as e:
                    self.log_warning("log_cleanup_error", file=str(f), error=str(e))
        else:
            log_dir.mkdir(parents=True, exist_ok=True)
        # Create an initial system log
        (log_dir / "servicenow-mcp-system.log").touch(exist_ok=True)
        self.log_info("old_logs_cleared")

    def setup_logging(self, enable_observability: bool = True):
        """Initialize logging and observability"""
        if enable_observability:
            try:
                self.logger = init_observability(
                    service_name="servicenow-mcp-system",
                    service_version="1.0.0"
                )
                self.log_info("observability_initialized", system="servicenow-mcp")
            except Exception as e:
                print(f"  Failed to initialize observability: {e}")
                self.logger = logging.getLogger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            logging.basicConfig(level=logging.INFO)
        
    def discover_mcp_agents(self) -> List[Path]:
        """Auto-discover MCP agent scripts in mcp_agents/ folder"""
        if not self.mcp_agents_dir.exists():
            self.log_warning("mcp_agents_directory_not_found", path=str(self.mcp_agents_dir))
            return []
        
        agents = []
        for file_path in self.mcp_agents_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
            agents.append(file_path)
            
        self.log_info("mcp_agents_discovered", count=len(agents), agents=[a.name for a in agents])
        return agents
    
    def start_mcp_agent(self, agent_path: Path) -> bool:
        """Start a single MCP agent"""
        agent_name = agent_path.stem
        log_file = self.project_root / "logs" / f"{agent_name}.log"
        
        # Ensure logs directory exists
        log_file.parent.mkdir(exist_ok=True)
        
        try:
            # Start the MCP agent process
            cmd = ["uv", "run", "python", str(agent_path)]
            process = subprocess.Popen(
                cmd,
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                cwd=str(self.project_root)
            )
            
            self.processes[agent_name] = process
            
            # Give it a moment to start
            time.sleep(2)
            
            # Check if it's still running
            if process.poll() is None:
                self.log_info("mcp_agent_started", 
                               agent=agent_name, 
                               pid=process.pid,
                               log_file=str(log_file))
                return True
            else:
                self.log_error("mcp_agent_failed_to_start", 
                                agent=agent_name,
                                return_code=process.poll())
                return False
                
        except Exception as e:
            self.log_error("mcp_agent_start_error", 
                            agent=agent_name, 
                            error=str(e))
            return False
    
    def start_magentic_ui(self, config_file: str = "servicenow_final_config.yaml") -> bool:
        """Start Magentic-UI"""
        config_path = self.project_root / config_file
        
        if not config_path.exists():
            self.log_error("magentic_ui_config_not_found", config_file=str(config_path))
            return False
        
        log_file = self.project_root / "logs" / "magentic-ui.log"
        log_file.parent.mkdir(exist_ok=True)
        
        try:
            # Start Magentic-UI in detached mode
            cmd = ["uv", "run", "magentic-ui", "--port", "8080", "--config", str(config_path)]
            
            # Use nohup equivalent for cross-platform compatibility
            process = subprocess.Popen(
                cmd,
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                cwd=str(self.project_root)
            )
            
            self.processes["magentic-ui"] = process
            
            # Give it time to start
            time.sleep(5)
            
            if process.poll() is None:
                self.log_info("magentic_ui_started", 
                               pid=process.pid,
                               config=config_file,
                               log_file=str(log_file))
                return True
            else:
                self.log_error("magentic_ui_failed_to_start", 
                                return_code=process.poll())
                return False
                
        except Exception as e:
            self.log_error("magentic_ui_start_error", error=str(e))
            return False

    def start_mkdocs(self) -> bool:
        """Start MkDocs dev server on 127.0.0.1:8090 if mkdocs configuration exists"""
        mkdocs_file = self.project_root / "mkdocs.yml"
        if not mkdocs_file.exists():
            # No docs site configured
            return False

        log_file = self.project_root / "logs" / "mkdocs.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            cmd = ["uv", "run", "mkdocs", "serve", "-a", "127.0.0.1:8090"]
            process = subprocess.Popen(
                cmd,
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                cwd=str(self.project_root)
            )
            self.processes["mkdocs"] = process

            # Give it a moment to bind
            time.sleep(3)
            return process.poll() is None
        except FileNotFoundError:
            # mkdocs not installed
            self.log_warning("mkdocs_not_installed")
            return False
        except Exception as e:
            self.log_error("mkdocs_start_error", error=str(e))
            return False
    
    def check_system_health(self) -> Dict[str, bool]:
        """Check if all components are running"""
        health = {}
        
        # Check MCP agents
        for name, process in self.processes.items():
            if name == "magentic-ui":
                continue
            health[f"mcp_{name}"] = process.poll() is None
        
        # Check Magentic-UI
        if "magentic-ui" in self.processes:
            health["magentic_ui"] = self.processes["magentic-ui"].poll() is None
        
        # Check HTTP endpoints
        import requests
        try:
            # Check Magentic-UI
            response = requests.get("http://localhost:8080", timeout=5)
            health["magentic_ui_endpoint"] = response.status_code == 200
        except:
            health["magentic_ui_endpoint"] = False
        
        # Check MCP SSE endpoints
        mcp_ports = {"table": 3001, "knowledge": 3002}
        for name, port in mcp_ports.items():
            try:
                response = requests.head(f"http://localhost:{port}/sse", timeout=5)
                status = response.status_code
                # Treat any 2xx or 3xx response as healthy (e.g. redirects)
                health[f"mcp_{name}_endpoint"] = (status >= 200 and status < 400)
            except:
                health[f"mcp_{name}_endpoint"] = False
        
        return health
    
    def print_system_status(self):
        """Print current system status"""
        health = self.check_system_health()
        
        print("\n" + "="*60)
        print(" SERVICENOW MCP SYSTEM STATUS")
        print("="*60)
        
        print("\n COMPONENT STATUS:")
        for component, status in health.items():
            status_icon = "" if status else ""
            print(f"   {status_icon} {component.replace('_', ' ').title()}")
        
        print(f"\n ACCESS POINTS:")
        print(f"    Magentic-UI: http://localhost:8080")
        print(f"    Table API (SSE): http://localhost:3001/sse")
        print(f"    Knowledge API (SSE): http://localhost:3002/sse")
        
        print(f"\n LOG FILES:")
        log_dir = self.project_root / "logs"
        if log_dir.exists():
            for log_file in log_dir.glob("*.log"):
                size_kb = log_file.stat().st_size // 1024
                print(f"    {log_file.name}: {size_kb}KB")
        
        print("="*60)
    
    def start_system(self, enable_observability: bool = True, enable_ui: bool = True, config_file: str = "servicenow_final_config.yaml"):
        """Start the complete system"""
        print("Starting ServiceNow MCP System...")
        print(f" Project root: {self.project_root}")
        
        # Check Docker first if we need observability or UI
        if (enable_observability or enable_ui) and not self.check_docker():
            print(" Docker is not running. Please start Docker and try again.")
            print("   Docker is required for:")
            if enable_observability:
                print("    Observability stack (Grafana, Prometheus, Loki, Tempo, Pyroscope)")
            if enable_ui:
                print("    Magentic-UI")
            return False
        
        # Setup logging
        self.setup_logging(enable_observability)

        # Clear old logs at the very beginning
        self.clear_old_logs()
        
        success_count = 0
        total_components = 0
        
        # Start observability stack first
        if enable_observability:
            total_components += 1
            print(f"\n Starting observability stack...")
            if self.start_observability_stack():
                success_count += 1
            else:
                print("  Continuing without observability stack...")
                total_components -= 1  # Don't count observability if it failed
        
        # Start MCP agents
        agents = self.discover_mcp_agents()
        total_components += len(agents)
        
        print(f"\n Starting {len(agents)} MCP agents...")
        for agent_path in agents:
            if self.start_mcp_agent(agent_path):
                success_count += 1
                print(f"    {agent_path.name}")
            else:
                print(f"    {agent_path.name}")
        
        # Start Magentic-UI
        if enable_ui:
            total_components += 1
            print(f"\nStarting Magentic-UI...")
            if self.start_magentic_ui(config_file):
                success_count += 1
                print(f"   OK Magentic-UI")
            else:
                print(f"   ERR Magentic-UI")

        # # Start MkDocs documentation site (if configured)
        # total_components += 1
        # print(f"\nStarting MkDocs...")
        # if self.start_mkdocs():
        #     success_count += 1
        #     print("   OK MkDocs")
        # else:
        #     # Do not treat missing mkdocs as a failure; subtract from total
        #     total_components -= 1
        #     print("   SKIP MkDocs (not configured or not installed)")
        
        # Wait for everything to stabilize
        print(f"\nWaiting for system to stabilize...")
        time.sleep(10)
        
        # Print final status
        self.print_system_status()
        
        if success_count == total_components:
            print(f"\n System started successfully! ({success_count}/{total_components} components)")
            self.log_info("system_start_complete", 
                           success_count=success_count, 
                           total_components=total_components)
        else:
            print(f"\n  System started with issues ({success_count}/{total_components} components)")
            self.log_warning("system_start_partial", 
                              success_count=success_count, 
                              total_components=total_components)
        
        return success_count == total_components
    
    def stop_system(self):
        """Stop all system components"""
        print("\n Stopping ServiceNow MCP System...")
        
        stopped_count = 0
        for name, process in self.processes.items():
            try:
                if process.poll() is None:  # Still running
                    print(f"    Stopping {name}...")
                    process.terminate()
                    
                    # Wait for graceful shutdown
                    try:
                        process.wait(timeout=10)
                        print(f"    {name} stopped gracefully")
                        stopped_count += 1
                    except subprocess.TimeoutExpired:
                        print(f"    Force killing {name}...")
                        process.kill()
                        process.wait()
                        print(f"    {name} force stopped")
                        stopped_count += 1
                else:
                    print(f"     {name} already stopped")
                    stopped_count += 1
                    
            except Exception as e:
                print(f"    Error stopping {name}: {e}")
        
        # Stop observability stack (only if it was started)
        if hasattr(self, '_observability_started') and self._observability_started:
            try:
                self.stop_observability_stack()
            except Exception as e:
                print(f"  Error stopping observability stack: {e}")
        
        # Cleanup
        if self.logger:
            self.log_info("system_stop_complete", stopped_count=stopped_count)
        
        shutdown_observability()
        print(f" System stopped ({stopped_count} components)")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\n Received signal {signum}, shutting down...")
    if hasattr(signal_handler, 'manager'):
        signal_handler.manager.stop_system()
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="ServiceNow MCP System Starter")
    parser.add_argument("--no-observability", action="store_true", 
                       help="Disable observability stack")
    parser.add_argument("--no-ui", action="store_true", 
                       help="Don't start Magentic-UI")
    parser.add_argument("--no-docker", action="store_true",
                       help="Run without Docker (MCP agents only)")
    parser.add_argument("--config", default="servicenow_final_config.yaml",
                       help="Magentic-UI config file")
    parser.add_argument("--stop", action="store_true",
                       help="Stop the system instead of starting")
    parser.add_argument("--status", action="store_true",
                       help="Show system status")
    
    args = parser.parse_args()
    
    manager = SystemManager()
    signal_handler.manager = manager
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if args.status:
            manager.setup_logging(not args.no_observability)
            manager.print_system_status()
        elif args.stop:
            manager.setup_logging(not args.no_observability)
            manager.stop_system()
        else:
            # Handle --no-docker flag
            enable_observability = not args.no_observability and not args.no_docker
            enable_ui = not args.no_ui and not args.no_docker
            
            success = manager.start_system(
                enable_observability=enable_observability,
                enable_ui=enable_ui,
                config_file=args.config
            )
            
            if success:
                print(f"\n System is running! Press Ctrl+C to stop.")
                try:
                    # Keep the main process alive
                    while True:
                        time.sleep(60)
                        # Periodic health check
                        health = manager.check_system_health()
                        failed_components = [k for k, v in health.items() if not v]
                        if failed_components:
                            manager.logger.warning("health_check_failed_components", 
                                                 failed=failed_components)
                except KeyboardInterrupt:
                    pass
            else:
                print(f"\n System failed to start properly")
                sys.exit(1)
                
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f" Unexpected error: {e}")
        sys.exit(1)
    finally:
        manager.stop_system()

if __name__ == "__main__":
    main()