"""Backward-compatible runtime composition facade.

Domain dispatchers depend on ``aibi_runtime.use_cases`` directly.  This module
remains only for verifier and integration compatibility while callers migrate.
"""

from .use_cases.agent_interaction import *  # noqa: F401,F403
from .use_cases.analysis import *  # noqa: F401,F403
from .use_cases.control import *  # noqa: F401,F403
from .use_cases.data import *  # noqa: F401,F403
from .use_cases.delivery import *  # noqa: F401,F403
from .use_cases.lifecycle import *  # noqa: F401,F403
