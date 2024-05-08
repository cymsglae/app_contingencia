from __future__ import annotations
from enum import Enum


class RunStatus(Enum):
    """The Run Status Codes"""

    SUBMITTED = "submitted"
    WAITING = "waiting"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    COMPLETEDWITHERRORS = "completedWithErrors"
    FAILED = "failed"
    TIMEDOUT = "timedOut"
    CANCELLED = "cancelled"
