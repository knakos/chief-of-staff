"""
Performance monitoring utilities for Chief of Staff backend.
"""
import time
import logging
import functools
from typing import Dict, Any, Callable
import asyncio

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Simple performance monitoring class."""
    
    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}
    
    def record_timing(self, operation: str, duration: float):
        """Record timing for an operation."""
        if operation not in self.metrics:
            self.metrics[operation] = {
                'count': 0,
                'total_time': 0,
                'avg_time': 0,
                'min_time': float('inf'),
                'max_time': 0
            }
        
        m = self.metrics[operation]
        m['count'] += 1
        m['total_time'] += duration
        m['avg_time'] = m['total_time'] / m['count']
        m['min_time'] = min(m['min_time'], duration)
        m['max_time'] = max(m['max_time'], duration)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return self.metrics.copy()
    
    def log_stats(self):
        """Log current performance statistics."""
        logger.info("=== Performance Statistics ===")
        for operation, stats in self.metrics.items():
            logger.info(
                f"{operation}: {stats['count']} calls, "
                f"avg: {stats['avg_time']:.3f}s, "
                f"min: {stats['min_time']:.3f}s, "
                f"max: {stats['max_time']:.3f}s"
            )

# Global performance monitor instance
perf_monitor = PerformanceMonitor()

def monitor_performance(operation_name: str = None):
    """Decorator to monitor function performance."""
    def decorator(func: Callable):
        name = operation_name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.perf_counter() - start_time
                    perf_monitor.record_timing(name, duration)
                    if duration > 1.0:  # Log slow operations
                        logger.warning(f"Slow operation {name}: {duration:.3f}s")
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.perf_counter() - start_time
                    perf_monitor.record_timing(name, duration)
                    if duration > 1.0:  # Log slow operations
                        logger.warning(f"Slow operation {name}: {duration:.3f}s")
            return sync_wrapper
    return decorator

def monitor_db_operation(operation_name: str):
    """Decorator specifically for database operations."""
    return monitor_performance(f"db.{operation_name}")

def monitor_claude_operation(operation_name: str):
    """Decorator specifically for Claude API operations.""" 
    return monitor_performance(f"claude.{operation_name}")

def log_performance_stats():
    """Log current performance statistics."""
    perf_monitor.log_stats()

def get_performance_stats() -> Dict[str, Any]:
    """Get performance statistics for API endpoint."""
    return perf_monitor.get_stats()