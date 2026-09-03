"""
TestSphere AI — Models
Defines common data types and structures.
"""
from typing import NamedTuple

class StrategyInfo(NamedTuple):
    current_strategy: str
    previous_strategy: str
    version: str
    updated_at: str
    updated_by: str
