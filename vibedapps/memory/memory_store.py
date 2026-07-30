import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, NamedTuple, Optional

from vibedapps.communication.message import Message

logger = logging.getLogger(__name__)


class MemoryStore(ABC):
    """Abstract base class for agent memory stores."""

    @abstractmethod
    async def add_message(self, agent_id: str, message: Message) -> None:
        """Add a message to the agent's memory."""
        pass

    @abstractmethod
    async def get_conversation(
            self, agent_id: str, conversation_id: str, limit: Optional[int] = None
    ) -> List[Message]:
        """Get conversation history for a specific conversation."""
        pass

    @abstractmethod
    async def get_all_conversations(self, agent_id: str) -> Dict[str, List[Message]]:
        """Get all conversations for an agent."""
        pass

    @abstractmethod
    async def store_knowledge(self, agent_id: str, key: str, value: Any) -> None:
        """Store knowledge in the agent's memory."""
        pass

    @abstractmethod
    async def get_knowledge(self, agent_id: str, key: str) -> Optional[Any]:
        """Retrieve knowledge from the agent's memory."""
        pass

    @abstractmethod
    async def clear_memory(self, agent_id: str) -> None:
        """Clear an agent's memory."""
        pass


@dataclass
class TimestampedMessage:
    """Message with timestamp for TTL tracking."""
    message: Message
    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


@dataclass
class TimestampedKnowledge:
    """Knowledge entry with timestamp for TTL tracking."""
    value: Any
    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


@dataclass
class MemoryStoreConfig:
    """Configuration for InMemoryStore with TTL and size limits."""
    # TTL settings (in seconds)
    message_ttl: int = 3600  # 1 hour default
    knowledge_ttl: int = 86400  # 24 hours default

    # Size limits
    max_messages_per_conversation: int = 100
    max_conversations_per_agent: int = 50
    max_knowledge_entries_per_agent: int = 1000
    max_total_messages: int = 10000
    max_total_knowledge: int = 5000

    # Cleanup settings
    cleanup_interval: int = 300  # 5 minutes
    enable_auto_cleanup: bool = True


class MemoryStats(NamedTuple):
    """Statistics about memory store usage."""
    total_agents: int
    total_conversations: int
    total_messages: int
    total_knowledge_entries: int
    oldest_message_age_seconds: Optional[float]
    oldest_knowledge_age_seconds: Optional[float]


class InMemoryStore(MemoryStore):
    """
    In-memory implementation of MemoryStore with TTL and size limits.

    Features:
    - TTL (time-to-live) for messages and knowledge entries
    - Configurable size limits per conversation, agent, and globally
    - Thread-safe operations using asyncio.Lock
    - Automatic cleanup of expired entries
    - LRU-style eviction when limits are reached
    """

    def __init__(self, config: Optional[MemoryStoreConfig] = None):
        """
        Initialize the in-memory store.

        Args:
            config: Configuration for TTL and size limits. Uses defaults if not provided.
        """
        self.config = config or MemoryStoreConfig()

        # Structure: {agent_id: {conversation_id: [TimestampedMessage]}}
        self.conversations: Dict[str, Dict[str, List[TimestampedMessage]]] = {}
        # Structure: {agent_id: {key: TimestampedKnowledge}}
        self.knowledge: Dict[str, Dict[str, TimestampedKnowledge]] = {}

        # Thread safety locks
        self._conversations_lock = asyncio.Lock()
        self._knowledge_lock = asyncio.Lock()

        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        logger.info(
            "InMemoryStore initialized",
            extra={
                "message_ttl": self.config.message_ttl,
                "knowledge_ttl": self.config.knowledge_ttl,
                "max_messages_per_conversation": self.config.max_messages_per_conversation
            }
        )

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self.config.enable_auto_cleanup and self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Memory store cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._shutdown_event.set()
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Memory store cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Background loop for cleaning up expired entries."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def cleanup_expired(self) -> Dict[str, int]:
        """
        Remove expired messages and knowledge entries.

        Returns:
            Dictionary with counts of removed items
        """
        now = datetime.now(timezone.utc).timestamp()
        removed_messages = 0
        removed_knowledge = 0

        # Cleanup expired messages
        async with self._conversations_lock:
            for agent_id in list(self.conversations.keys()):
                for conv_id in list(self.conversations[agent_id].keys()):
                    messages = self.conversations[agent_id][conv_id]
                    original_count = len(messages)

                    # Filter out expired messages
                    self.conversations[agent_id][conv_id] = [
                        msg for msg in messages
                        if (now - msg.created_at) < self.config.message_ttl
                    ]

                    removed_messages += original_count - len(self.conversations[agent_id][conv_id])

                    # Remove empty conversations
                    if not self.conversations[agent_id][conv_id]:
                        del self.conversations[agent_id][conv_id]

                # Remove agents with no conversations
                if not self.conversations[agent_id]:
                    del self.conversations[agent_id]

        # Cleanup expired knowledge
        async with self._knowledge_lock:
            for agent_id in list(self.knowledge.keys()):
                for key in list(self.knowledge[agent_id].keys()):
                    entry = self.knowledge[agent_id][key]
                    if (now - entry.created_at) >= self.config.knowledge_ttl:
                        del self.knowledge[agent_id][key]
                        removed_knowledge += 1

                # Remove agents with no knowledge
                if not self.knowledge[agent_id]:
                    del self.knowledge[agent_id]

        if removed_messages > 0 or removed_knowledge > 0:
            logger.info(
                "Memory cleanup completed",
                extra={
                    "removed_messages": removed_messages,
                    "removed_knowledge": removed_knowledge
                }
            )

        return {"messages": removed_messages, "knowledge": removed_knowledge}

    def _get_total_message_count(self) -> int:
        """Get total message count across all agents."""
        total = 0
        for agent_convs in self.conversations.values():
            for messages in agent_convs.values():
                total += len(messages)
        return total

    def _get_total_knowledge_count(self) -> int:
        """Get total knowledge entry count across all agents."""
        total = 0
        for agent_knowledge in self.knowledge.values():
            total += len(agent_knowledge)
        return total

    async def _enforce_conversation_limits(self, agent_id: str, conversation_id: str) -> None:
        """Enforce size limits for a conversation (remove oldest messages if needed)."""
        if agent_id not in self.conversations:
            return
        if conversation_id not in self.conversations[agent_id]:
            return

        messages = self.conversations[agent_id][conversation_id]

        # Enforce per-conversation limit
        if len(messages) > self.config.max_messages_per_conversation:
            excess = len(messages) - self.config.max_messages_per_conversation
            self.conversations[agent_id][conversation_id] = messages[excess:]
            logger.debug(
                f"Trimmed {excess} messages from conversation {conversation_id}"
            )

    async def _enforce_agent_conversation_limits(self, agent_id: str) -> None:
        """Enforce max conversations per agent (remove oldest conversations if needed)."""
        if agent_id not in self.conversations:
            return

        agent_convs = self.conversations[agent_id]
        if len(agent_convs) > self.config.max_conversations_per_agent:
            # Sort conversations by oldest message timestamp
            sorted_convs = sorted(
                agent_convs.items(),
                key=lambda x: min(m.created_at for m in x[1]) if x[1] else float('inf')
            )

            # Remove oldest conversations
            excess = len(sorted_convs) - self.config.max_conversations_per_agent
            for conv_id, _ in sorted_convs[:excess]:
                del self.conversations[agent_id][conv_id]
                logger.debug(f"Removed old conversation {conv_id} for agent {agent_id}")

    async def _enforce_global_message_limits(self) -> None:
        """Enforce global message limit by removing oldest messages."""
        total = self._get_total_message_count()
        if total <= self.config.max_total_messages:
            return

        # Collect all messages with their location
        all_messages = []
        for agent_id, agent_convs in self.conversations.items():
            for conv_id, messages in agent_convs.items():
                for i, msg in enumerate(messages):
                    all_messages.append((agent_id, conv_id, i, msg.created_at))

        # Sort by timestamp (oldest first)
        all_messages.sort(key=lambda x: x[3])

        # Remove oldest messages
        excess = total - self.config.max_total_messages
        removed = 0
        for agent_id, conv_id, _, _ in all_messages[:excess]:
            if (agent_id in self.conversations and
                conv_id in self.conversations[agent_id] and
                self.conversations[agent_id][conv_id]):
                self.conversations[agent_id][conv_id].pop(0)
                removed += 1

        logger.info(f"Enforced global limit: removed {removed} oldest messages")

    async def add_message(self, agent_id: str, message: Message) -> None:
        """Add a message to the agent's memory with TTL tracking."""
        async with self._conversations_lock:
            if agent_id not in self.conversations:
                self.conversations[agent_id] = {}

            conversation_id = message.conversation_id
            if conversation_id not in self.conversations[agent_id]:
                self.conversations[agent_id][conversation_id] = []

            # Wrap message with timestamp
            timestamped_msg = TimestampedMessage(message=message)
            self.conversations[agent_id][conversation_id].append(timestamped_msg)

            # Enforce limits
            await self._enforce_conversation_limits(agent_id, conversation_id)
            await self._enforce_agent_conversation_limits(agent_id)
            await self._enforce_global_message_limits()

    async def get_conversation(
            self, agent_id: str, conversation_id: str, limit: Optional[int] = None
    ) -> List[Message]:
        """Get conversation history for a specific conversation (excluding expired)."""
        async with self._conversations_lock:
            if (agent_id not in self.conversations or
                    conversation_id not in self.conversations[agent_id]):
                return []

            now = datetime.now(timezone.utc).timestamp()
            messages = self.conversations[agent_id][conversation_id]

            # Filter out expired messages and extract the actual Message objects
            valid_messages = [
                msg.message for msg in messages
                if (now - msg.created_at) < self.config.message_ttl
            ]

            if limit:
                # Get the most recent messages up to the limit
                return valid_messages[-limit:]
            return valid_messages

    async def get_all_conversations(self, agent_id: str) -> Dict[str, List[Message]]:
        """Get all conversations for an agent (excluding expired messages)."""
        async with self._conversations_lock:
            if agent_id not in self.conversations:
                return {}

            now = datetime.now(timezone.utc).timestamp()
            result = {}

            for conv_id, messages in self.conversations[agent_id].items():
                valid_messages = [
                    msg.message for msg in messages
                    if (now - msg.created_at) < self.config.message_ttl
                ]
                if valid_messages:  # Only include non-empty conversations
                    result[conv_id] = valid_messages

            return result

    async def store_knowledge(self, agent_id: str, key: str, value: Any) -> None:
        """Store knowledge in the agent's memory with TTL tracking."""
        async with self._knowledge_lock:
            if agent_id not in self.knowledge:
                self.knowledge[agent_id] = {}

            # Check agent knowledge limit
            if len(self.knowledge[agent_id]) >= self.config.max_knowledge_entries_per_agent:
                # Remove oldest entry
                oldest_key = min(
                    self.knowledge[agent_id].keys(),
                    key=lambda k: self.knowledge[agent_id][k].created_at
                )
                del self.knowledge[agent_id][oldest_key]
                logger.debug(f"Evicted oldest knowledge entry '{oldest_key}' for agent {agent_id}")

            # Check global knowledge limit
            if self._get_total_knowledge_count() >= self.config.max_total_knowledge:
                # Find and remove globally oldest entry
                oldest_agent = None
                oldest_key = None
                oldest_time = float('inf')

                for aid, entries in self.knowledge.items():
                    for k, entry in entries.items():
                        if entry.created_at < oldest_time:
                            oldest_time = entry.created_at
                            oldest_agent = aid
                            oldest_key = k

                if oldest_agent and oldest_key:
                    del self.knowledge[oldest_agent][oldest_key]
                    logger.debug("Evicted globally oldest knowledge entry")

            self.knowledge[agent_id][key] = TimestampedKnowledge(value=value)

    async def get_knowledge(self, agent_id: str, key: str) -> Optional[Any]:
        """Retrieve knowledge from the agent's memory (if not expired)."""
        async with self._knowledge_lock:
            if agent_id not in self.knowledge or key not in self.knowledge[agent_id]:
                return None

            entry = self.knowledge[agent_id][key]
            now = datetime.now(timezone.utc).timestamp()

            # Check if expired
            if (now - entry.created_at) >= self.config.knowledge_ttl:
                # Remove expired entry
                del self.knowledge[agent_id][key]
                return None

            return entry.value

    async def clear_memory(self, agent_id: str) -> None:
        """Clear an agent's memory."""
        async with self._conversations_lock:
            if agent_id in self.conversations:
                del self.conversations[agent_id]

        async with self._knowledge_lock:
            if agent_id in self.knowledge:
                del self.knowledge[agent_id]

    async def get_stats(self) -> MemoryStats:
        """Get statistics about memory store usage."""
        now = datetime.now(timezone.utc).timestamp()

        total_agents = len(set(self.conversations.keys()) | set(self.knowledge.keys()))
        total_conversations = sum(len(convs) for convs in self.conversations.values())
        total_messages = self._get_total_message_count()
        total_knowledge = self._get_total_knowledge_count()

        # Find oldest message
        oldest_message_age = None
        for agent_convs in self.conversations.values():
            for messages in agent_convs.values():
                for msg in messages:
                    age = now - msg.created_at
                    if oldest_message_age is None or age > oldest_message_age:
                        oldest_message_age = age

        # Find oldest knowledge
        oldest_knowledge_age = None
        for agent_knowledge in self.knowledge.values():
            for entry in agent_knowledge.values():
                age = now - entry.created_at
                if oldest_knowledge_age is None or age > oldest_knowledge_age:
                    oldest_knowledge_age = age

        return MemoryStats(
            total_agents=total_agents,
            total_conversations=total_conversations,
            total_messages=total_messages,
            total_knowledge_entries=total_knowledge,
            oldest_message_age_seconds=oldest_message_age,
            oldest_knowledge_age_seconds=oldest_knowledge_age
        )