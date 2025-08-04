#!/usr/bin/env python3
"""
Cleanup script to remove all junk files and directories
"""

import os
import shutil
import glob
from pathlib import Path

def cleanup_junk():
    """Remove all unnecessary files and directories"""
    
    print("🧹 Cleaning up junk files and directories...")
    print("=" * 50)
    
    # Define patterns for junk files/directories
    junk_patterns = [
        # Python cache
        "__pycache__",
        "*.pyc",
        "*.pyo", 
        "*.pyd",
        ".pytest_cache",
        
        # Development/test files
        "test_*.py",
        "*_test.py",
        "validate_*.py",
        "check_*.py",
        "test_agents_api.py",
        "test_mcp_agents.py",
        "test_openapi.py",
        "test_setup.py",
        "test_knowledge_setup.py",
        "test_minimal_config.yaml",
        
        # Old/deprecated files
        "servicenow_openapi_generator.py",
        "start_servicenow_agents.py", 
        "start_servicenow_mcp_servers.py",
        "generate_servicenow_servers.py",
        "create_final_servicenow_specs.py",
        "start_final_magentic_ui.py",
        
        # Old stdio server files (we use SSE now)
        "servicenow_table_server.py",
        "servicenow_knowledge_server.py",
        
        # Old directories
        "agents/",
        "mcp_servers/", 
        "integration/",
        "config/",
        "servicenow/",
        
        # macOS files
        ".DS_Store",
        "*.DS_Store",
        
        # Logs and temp files
        "*.log",
        "*.tmp",
        ".servicenow_logs/",
        ".servicenow_pids/",
        
        # Documentation files (except main README)
        "FINAL_SUMMARY.md",
        "SETUP_COMPLETE.md",
        
        # Reference docs (keeping main specs)
        "reference_docs/",
        "ServiceNow Developers_files/",
        
        # Old config files
        "servicenow_config.yaml",
        "servicenow_config.py",
    ]
    
    # Current directory
    current_dir = Path(".")
    
    removed_count = 0
    
    # Remove files and directories matching patterns
    for pattern in junk_patterns:
        if "/" in pattern:  # Directory pattern
            for item in current_dir.glob(pattern):
                if item.exists():
                    try:
                        if item.is_dir():
                            shutil.rmtree(item)
                            print(f"🗂️  Removed directory: {item}")
                        else:
                            item.unlink()
                            print(f"📄 Removed file: {item}")
                        removed_count += 1
                    except Exception as e:
                        print(f"❌ Failed to remove {item}: {e}")
        else:  # File pattern
            for item in current_dir.glob(pattern):
                if item.exists() and item.is_file():
                    try:
                        item.unlink()
                        print(f"📄 Removed file: {item}")
                        removed_count += 1
                    except Exception as e:
                        print(f"❌ Failed to remove {item}: {e}")
    
    # Remove empty directories
    empty_dirs = []
    for root, dirs, files in os.walk(".", topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            try:
                if not any(dir_path.iterdir()):  # Empty directory
                    empty_dirs.append(dir_path)
            except (OSError, PermissionError):
                pass
    
    for empty_dir in empty_dirs:
        try:
            empty_dir.rmdir()
            print(f"📁 Removed empty directory: {empty_dir}")
            removed_count += 1
        except Exception as e:
            print(f"❌ Failed to remove empty directory {empty_dir}: {e}")
    
    print("\n" + "=" * 50)
    print(f"✅ Cleanup complete! Removed {removed_count} items")
    print("\n📋 Remaining important files:")
    
    # List remaining important files
    important_files = [
        "pyproject.toml",
        "requirements.txt", 
        "requirements.lock",
        "uv.lock",
        ".env",
        "README.md",
        "servicenow_final_config.yaml",
        "servicenow_table_sse_server.py",
        "servicenow_knowledge_sse_server.py", 
        "start_servicenow_sse_system.py",
        "openapi_specs/",
    ]
    
    for item in important_files:
        path = Path(item)
        if path.exists():
            if path.is_dir():
                file_count = len(list(path.glob("*")))
                print(f"   📂 {item} ({file_count} files)")
            else:
                print(f"   📄 {item}")

if __name__ == "__main__":
    cleanup_junk()