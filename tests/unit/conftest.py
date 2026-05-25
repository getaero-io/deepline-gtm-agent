"""
Shared fixtures and test configuration for unit tests.
"""
import sys
from unittest.mock import MagicMock

# Stub heavy dependencies that unit tests don't need
_STUB_MODULES = [
    "deepagents",
    "langchain_core",
    "langchain_core.tools",
    "langchain_core._api",
    "langchain_core._api.deprecation",
    "redis",
    "langgraph",
    "langgraph.checkpoint",
    "langgraph.checkpoint.redis",
]

for mod in _STUB_MODULES:
    sys.modules.setdefault(mod, MagicMock())
