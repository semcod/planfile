"""Planfile core models - merged from models.py + models_v2.py + new Ticket type.

This is now a compatibility shim - the actual implementation is in planfile.core.models package.
"""

# Re-export everything from the new package for backward compatibility
from planfile.core.models import *  # noqa: F401,F403
from planfile.core.models import __all__  # noqa: F401
