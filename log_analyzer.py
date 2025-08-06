#!/usr/bin/env python3
"""
Log Analysis Utility for ServiceNow MCP System
Systematically analyze logs to identify and debug issues
"""

import os
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import argparse
from dataclasses import dataclass
from collections import defaultdict, Counter

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    source: str
    data: Dict[str, Any]
    raw_line: str

@dataclass
class AnalysisResult:
    total_entries: int
    error_count: int
    warning_count: int
    critical_issues: List[str]
    common_errors: List[Tuple[str, int]]
    recommendations: List[str]

class LogAnalyzer:
    """Comprehensive log analyzer for debugging system issues"""
    
    def __init__(self):
        self.log_entries: List[LogEntry] = []
        self.error_patterns = {
            'api_key_issues': [
                r'Incorrect API key provided',
                r'Invalid API key',
                r'Authentication failed',
                r'401.*api.*key',
                r'\$\{OPENAI.*KEY\}'  # Unresolved environment variable
            ],
            'connection_issues': [
                r'Connection refused',
                r'Connection timeout',
                r'Failed to connect',
                r'Network is unreachable',
                r'Name or service not known'
            ],
            'mcp_issues': [
                r'MCP.*error',
                r'FastMCP.*error',
                r'Server.*not.*responding',
                r'Transport.*error'
            ],
            'environment_issues': [
                r'Environment variable.*not set',
                r'Missing.*environment',
                r'SN_.*not.*found'
            ],
            'configuration_issues': [
                r'Configuration.*error',
                r'Invalid.*config',
                r'YAML.*error',
                r'Config.*not.*found'
            ],
            'async_issues': [
                r'Already running asyncio',
                r'Event loop.*already running',
                r'RuntimeError.*asyncio',
                r'Cannot enter into task'
            ]
        }
    
    def parse_log_line(self, line: str, source: str = "unknown") -> Optional[LogEntry]:
        """Parse a single log line into a LogEntry"""
        line = line.strip()
        if not line:
            return None
        
        # Try to parse JSON structured logs first
        try:
            if line.startswith('{') and line.endswith('}'):
                data = json.loads(line)
                return LogEntry(
                    timestamp=data.get('timestamp', ''),
                    level=data.get('level', 'INFO'),
                    message=data.get('event', data.get('message', '')),
                    source=source,
                    data=data,
                    raw_line=line
                )
        except json.JSONDecodeError:
            pass
        
        # Parse standard log format
        # Pattern: LEVEL:     message
        # Pattern: timestamp | LEVEL | module:function:line - message
        patterns = [
            # Uvicorn/FastAPI logs
            r'^(?P<level>INFO|DEBUG|WARNING|ERROR|CRITICAL):\s+(?P<message>.+)$',
            # Structured logs with timestamp
            r'^(?P<timestamp>[\d\-T:\.\sZ]+)\s*\|\s*(?P<level>\w+)\s*\|\s*(?P<module>[\w\.]+):(?P<function>\w+):(?P<line>\d+)\s*-\s*(?P<message>.+)$',
            # Simple timestamp + message
            r'^(?P<timestamp>[\d\-T:\.\sZ]+):\s*(?P<message>.+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                groups = match.groupdict()
                return LogEntry(
                    timestamp=groups.get('timestamp', ''),
                    level=groups.get('level', 'INFO'),
                    message=groups.get('message', line),
                    source=source,
                    data=groups,
                    raw_line=line
                )
        
        # Fallback: treat as unstructured message
        return LogEntry(
            timestamp='',
            level='INFO',
            message=line,
            source=source,
            data={},
            raw_line=line
        )
    
    def load_log_file(self, file_path: Path, source_name: str = None) -> int:
        """Load and parse a log file"""
        if not file_path.exists():
            print(f"Warning: Log file not found: {file_path}")
            return 0
        
        source = source_name or file_path.stem
        count = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    entry = self.parse_log_line(line, source)
                    if entry:
                        self.log_entries.append(entry)
                        count += 1
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
        
        return count
    
    def load_all_logs(self, logs_dir: Path = None) -> Dict[str, int]:
        """Load all available log files"""
        if logs_dir is None:
            logs_dir = Path("logs")
        
        results = {}
        
        # Load from logs directory
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                count = self.load_log_file(log_file, log_file.stem)
                results[str(log_file)] = count
        
        # Load specific application logs
        app_logs = [
            "magentic_ui.log",
            "table_sse_server.log", 
            "knowledge_sse_server.log"
        ]
        
        for log_name in app_logs:
            log_path = Path(log_name)
            if log_path.exists():
                count = self.load_log_file(log_path, log_name.replace('.log', ''))
                results[str(log_path)] = count
        
        return results
    
    def analyze_errors(self) -> Dict[str, List[LogEntry]]:
        """Categorize and analyze errors"""
        categorized_errors = defaultdict(list)
        
        for entry in self.log_entries:
            if entry.level in ['ERROR', 'CRITICAL']:
                # Categorize by error pattern
                categorized = False
                for category, patterns in self.error_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, entry.message, re.IGNORECASE):
                            categorized_errors[category].append(entry)
                            categorized = True
                            break
                    if categorized:
                        break
                
                if not categorized:
                    categorized_errors['other_errors'].append(entry)
        
        return dict(categorized_errors)
    
    def find_critical_issues(self) -> List[str]:
        """Identify critical issues that need immediate attention"""
        critical_issues = []
        
        # Check for API key issues
        api_key_errors = 0
        for entry in self.log_entries:
            if any(re.search(pattern, entry.message, re.IGNORECASE) 
                   for pattern in self.error_patterns['api_key_issues']):
                api_key_errors += 1
        
        if api_key_errors > 0:
            critical_issues.append(f"🚨 API Key Issues: {api_key_errors} authentication failures detected")
        
        # Check for async/event loop issues
        async_errors = 0
        for entry in self.log_entries:
            if any(re.search(pattern, entry.message, re.IGNORECASE)
                   for pattern in self.error_patterns['async_issues']):
                async_errors += 1
        
        if async_errors > 0:
            critical_issues.append(f"🚨 Async Issues: {async_errors} event loop conflicts detected")
        
        # Check for connection issues
        connection_errors = 0
        for entry in self.log_entries:
            if any(re.search(pattern, entry.message, re.IGNORECASE)
                   for pattern in self.error_patterns['connection_issues']):
                connection_errors += 1
        
        if connection_errors > 0:
            critical_issues.append(f"🚨 Connection Issues: {connection_errors} network failures detected")
        
        return critical_issues
    
    def generate_recommendations(self, categorized_errors: Dict[str, List[LogEntry]]) -> List[str]:
        """Generate actionable recommendations based on error analysis"""
        recommendations = []
        
        if 'api_key_issues' in categorized_errors:
            recommendations.append(
                "🔧 Fix OpenAI API Key: Set OPENAI_API_KEY environment variable with valid key. "
                "Check that ${OPENAI_API_KEY} is being resolved correctly in config files."
            )
        
        if 'async_issues' in categorized_errors:
            recommendations.append(
                "🔧 Fix Async Issues: Remove nested asyncio.run() calls. "
                "Let FastMCP manage the event loop directly with mcp.run()."
            )
        
        if 'connection_issues' in categorized_errors:
            recommendations.append(
                "🔧 Fix Connection Issues: Verify service URLs and network connectivity. "
                "Check that MCP servers are running on expected ports."
            )
        
        if 'mcp_issues' in categorized_errors:
            recommendations.append(
                "🔧 Fix MCP Issues: Verify MCP server configuration and transport settings. "
                "Ensure SSE endpoints are properly configured."
            )
        
        if 'environment_issues' in categorized_errors:
            recommendations.append(
                "🔧 Fix Environment: Set required environment variables (SN_INSTANCE, SN_USER, SN_PASS, OPENAI_API_KEY)."
            )
        
        return recommendations
    
    def analyze(self) -> AnalysisResult:
        """Perform comprehensive log analysis"""
        categorized_errors = self.analyze_errors()
        critical_issues = self.find_critical_issues()
        recommendations = self.generate_recommendations(categorized_errors)
        
        # Count error types
        error_count = sum(1 for entry in self.log_entries if entry.level in ['ERROR', 'CRITICAL'])
        warning_count = sum(1 for entry in self.log_entries if entry.level == 'WARNING')
        
        # Find most common error messages
        error_messages = [entry.message for entry in self.log_entries if entry.level in ['ERROR', 'CRITICAL']]
        common_errors = Counter(error_messages).most_common(5)
        
        return AnalysisResult(
            total_entries=len(self.log_entries),
            error_count=error_count,
            warning_count=warning_count,
            critical_issues=critical_issues,
            common_errors=common_errors,
            recommendations=recommendations
        )
    
    def print_analysis(self, result: AnalysisResult):
        """Print formatted analysis results"""
        print("=" * 60)
        print("🔍 LOG ANALYSIS REPORT")
        print("=" * 60)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total log entries: {result.total_entries}")
        print(f"   Errors: {result.error_count}")
        print(f"   Warnings: {result.warning_count}")
        
        if result.critical_issues:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in result.critical_issues:
                print(f"   {issue}")
        
        if result.common_errors:
            print(f"\n🔥 MOST COMMON ERRORS:")
            for error, count in result.common_errors:
                print(f"   [{count}x] {error[:100]}...")
        
        if result.recommendations:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in result.recommendations:
                print(f"   {rec}")
        
        print("\n" + "=" * 60)
    
    def export_errors(self, output_file: str = "error_analysis.json"):
        """Export detailed error analysis to JSON"""
        categorized_errors = self.analyze_errors()
        
        export_data = {}
        for category, entries in categorized_errors.items():
            export_data[category] = [
                {
                    'timestamp': entry.timestamp,
                    'level': entry.level,
                    'message': entry.message,
                    'source': entry.source,
                    'raw_line': entry.raw_line
                }
                for entry in entries
            ]
        
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"📄 Detailed error analysis exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Analyze ServiceNow MCP System logs")
    parser.add_argument("--logs-dir", type=str, help="Directory containing log files")
    parser.add_argument("--export", action="store_true", help="Export detailed analysis to JSON")
    parser.add_argument("--file", type=str, help="Analyze specific log file")
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer()
    
    if args.file:
        # Analyze specific file
        log_file = Path(args.file)
        count = analyzer.load_log_file(log_file)
        print(f"Loaded {count} entries from {log_file}")
    else:
        # Load all available logs
        logs_dir = Path(args.logs_dir) if args.logs_dir else None
        file_counts = analyzer.load_all_logs(logs_dir)
        
        print("📂 LOADED LOG FILES:")
        for file_path, count in file_counts.items():
            print(f"   {file_path}: {count} entries")
    
    # Perform analysis
    result = analyzer.analyze()
    analyzer.print_analysis(result)
    
    # Export if requested
    if args.export:
        analyzer.export_errors()


if __name__ == "__main__":
    main()