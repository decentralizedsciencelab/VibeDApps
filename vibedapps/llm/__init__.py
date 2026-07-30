"""
LLM service backends.

OpenAIService talks to the OpenAI API; ClaudeCLIService is a drop-in
replacement that shells out to the local `claude` CLI (no API key needed).
"""

from .claude_cli_service import ClaudeCLIService
from .openai_service import OpenAIService

__all__ = ['OpenAIService', 'ClaudeCLIService']
