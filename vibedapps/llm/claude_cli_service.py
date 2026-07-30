"""
Claude CLI-backed LLM service.

Drop-in replacement for OpenAIService that routes completions through the
local `claude` CLI (Claude Code) instead of the OpenAI API. This avoids
per-call API spend by using the user's existing CLI auth.

Implements the subset of the OpenAIService interface exercised by the agent
pipeline: generate_completion() plus the circuit-breaker no-ops that main_api
calls at startup. Embeddings are stubbed (not on the generation path).

Model is forced to Sonnet regardless of the caller's `model=` argument, since
callers pass OpenAI model ids (e.g. "gpt-4o") that mean nothing here.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ClaudeCLIService:
    """LLM service that shells out to `claude -p --model <model>`."""

    def __init__(
        self,
        model: str = "sonnet",
        cli_path: str = "claude",
        timeout: float = 900.0,
    ):
        self.model = model
        self.cli_path = cli_path
        self.timeout = timeout
        # call accounting so a run can be audited for realness
        self.call_count = 0
        self.total_wall_seconds = 0.0

    # ---- interface parity with OpenAIService (main_api calls these) ----
    async def register_circuit_breakers(self) -> None:
        return None

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        return {"backend": "claude_cli", "model": self.model}

    async def reset_circuit_breakers(self) -> None:
        return None

    @staticmethod
    def _flatten_messages(messages: List[Dict[str, str]]) -> str:
        """Collapse a chat-style message list into a single CLI prompt."""
        system = [m["content"] for m in messages if m.get("role") == "system"]
        convo = [m for m in messages if m.get("role") != "system"]
        parts: List[str] = []
        if system:
            parts.append("\n\n".join(system))
        for m in convo:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "assistant":
                parts.append(f"[Previous assistant response]\n{content}")
            else:
                parts.append(content)
        return "\n\n".join(parts).strip()

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> str:
        """Generate a completion via the claude CLI. Returns raw text."""
        prompt = self._flatten_messages(messages)

        loop = asyncio.get_event_loop()
        t0 = loop.time()
        proc = await asyncio.create_subprocess_exec(
            self.cli_path,
            "-p",
            "--model",
            self.model,
            "--output-format",
            "text",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(
                f"claude CLI timed out after {self.timeout}s (model={self.model})"
            )

        elapsed = loop.time() - t0
        self.call_count += 1
        self.total_wall_seconds += elapsed

        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            raise RuntimeError(f"claude CLI failed (rc={proc.returncode}): {err[:500]}")

        text = stdout.decode(errors="replace").strip()
        logger.info("claude_cli_completion call=%d elapsed=%.1fs chars=%d",
                    self.call_count, elapsed, len(text))
        return text

    async def generate_embeddings(self, texts, model: str = "unused"):
        """Stubbed — embeddings are not on the DApp generation path."""
        dim = 8
        return [[0.0] * dim for _ in (texts if isinstance(texts, list) else [texts])]
