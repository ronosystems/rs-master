# apps/shared/utils/converters.py

from decimal import Decimal
from typing import Optional, Union

def safe_float(value: Optional[Union[Decimal, float, int, str]]) -> Optional[float]:
    """Safely convert Decimal or None to float"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def safe_decimal(value: Optional[Union[float, int, str]]) -> Optional[Decimal]:
    """Safely convert to Decimal"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return None

def safe_int(value: Optional[Union[int, str]]) -> Optional[int]:
    """Safely convert to int"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None