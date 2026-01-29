"""
Simple log collector utility for task execution logs.
"""
import time
from typing import Dict, List, Optional


class TaskLogCollector:
    """
    Simple log collector that stores log messages in memory.

    Usage:
        collector = TaskLogCollector()
        collector.info("Task started")
        collector.warning("Something went wrong")
        logs = collector.get_logs()
    """

    def __init__(self, max_records: int = 1000):
        """
        Initialize the log collector.

        Args:
            max_records: Maximum number of log records to keep in memory
        """
        self.records: List[Dict] = []
        self.max_records = max_records

    def _add_log(
        self, level: str, message: str,
        exception: Optional[str] = None
    ):
        """
        Add a log entry.

        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
            exception: Optional exception traceback
        """
        if len(self.records) >= self.max_records:
            self.records.pop(0)

        log_entry = {
            'level': level,
            'message': message,
            'timestamp': time.time(),
        }

        if exception:
            log_entry['exception'] = exception

        self.records.append(log_entry)

    def info(self, message: str):
        """Add an INFO level log."""
        self._add_log('INFO', message)

    def warning(self, message: str):
        """Add a WARNING level log."""
        self._add_log('WARNING', message)

    def error(self, message: str, exception: Optional[str] = None):
        """Add an ERROR level log."""
        self._add_log('ERROR', message, exception)

    def debug(self, message: str):
        """Add a DEBUG level log."""
        self._add_log('DEBUG', message)

    def get_logs(self) -> List[Dict]:
        """
        Get all collected log records.

        Returns:
            List of log entry dictionaries
        """
        return list(self.records)

    def get_warnings_and_errors(self) -> List[Dict]:
        """
        Get only warning and error level logs.

        Returns:
            List of warning and error log entries
        """
        return [
            log for log in self.records
            if log['level'] in ('WARNING', 'ERROR', 'CRITICAL')
        ]

    def get_summary(self) -> Dict:
        """
        Get a summary of collected logs.

        Returns:
            Dictionary with log counts by level
        """
        summary = {
            'total': len(self.records),
            'by_level': {}
        }

        for log in self.records:
            level = log['level']
            summary['by_level'][level] = summary['by_level'].get(level, 0) + 1

        return summary

    def clear(self) -> None:
        """Clear all collected logs."""
        self.records.clear()
