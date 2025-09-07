"""
Datetime utilities for consistent timezone handling across the application.
All times are stored in UTC and converted to local time on the frontend.
"""
from datetime import datetime, timezone
from typing import Optional

def utc_now() -> datetime:
    """Return current UTC time in timezone-aware format"""
    return datetime.now(timezone.utc)

def utc_timestamp() -> str:
    """Return current UTC timestamp as ISO string"""
    return utc_now().isoformat()

def parse_datetime(dt_string: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to timezone-aware datetime object"""
    if not dt_string:
        return None
    
    try:
        # Handle both with and without timezone info
        if dt_string.endswith('Z'):
            dt_string = dt_string[:-1] + '+00:00'
        
        dt = datetime.fromisoformat(dt_string)
        
        # If naive datetime, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        return dt
    except (ValueError, TypeError):
        return None

def to_utc(dt: datetime) -> datetime:
    """Convert any datetime to UTC"""
    if dt.tzinfo is None:
        # Naive datetime, assume UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)