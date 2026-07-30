import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from vibedapps.communication.message import Message, MessageRole
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import MemoryStore


class AgentConfig(BaseModel):
    """Configuration for an agent."""
    name: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    model: str = "gpt-4o"
    temperature: float = 0.7
    system_prompt: Optional[str] = None


class BaseAgent(ABC):
    """Base class for all agents in the system."""

    def __init__(
            self,
            config: AgentConfig,
            memory_store: MemoryStore,
            llm_service: Optional[OpenAIService] = None,
    ):
        self.id = str(uuid.uuid4())
        self.config = config
        self.memory = memory_store
        self.llm = llm_service or OpenAIService()
        self._initialize_api()

    def _initialize_api(self) -> FastAPI:
        """Initialize the FastAPI application for this agent."""
        self.app = FastAPI(
            title=f"Agent: {self.config.name}",
            description=f"API for {self.config.name} agent: {self.config.description}"
        )

        # Register standard endpoints
        self._register_endpoints()

        return self.app

    def _register_endpoints(self) -> None:
        """Register standard endpoints for the agent."""

        @self.app.get("/")
        async def root():
            return {
                "agent_id": self.id,
                "name": self.config.name,
                "description": self.config.description,
                "capabilities": self.config.capabilities
            }

        @self.app.post("/receive_message")
        async def receive_message(message: Message):
            return await self.process_message(message)

        @self.app.get("/status")
        async def status():
            return {"status": "active", "agent_id": self.id}

    async def process_message(self, message: Message) -> Dict[str, Any]:
        """Process an incoming message and generate a response."""
        # Store the incoming message
        await self.memory.add_message(self.id, message)

        # Get conversation history
        conversation_history = await self.memory.get_conversation(
            self.id, limit=10, conversation_id=message.conversation_id
        )

        # Process with the LLM
        response_content = await self._think(conversation_history, message)

        # Create response message
        response = Message(
            sender_id=self.id,
            recipient_id=message.sender_id,
            content=response_content,
            conversation_id=message.conversation_id,
            role=MessageRole.ASSISTANT,
            metadata={"agent_name": self.config.name}
        )

        # Store the response
        await self.memory.add_message(self.id, response)

        return {"response": response.dict()}

    async def _think(self, conversation_history: List[Message], current_message: Message) -> str:
        """Process the conversation history and current message with the LLM."""
        # Format conversation for the LLM
        formatted_messages = self._format_conversation_for_llm(conversation_history, current_message)

        # Get response from LLM
        response = await self.llm.generate_completion(
            messages=formatted_messages,
            model=self.config.model,
            temperature=self.config.temperature
        )

        return response

    def _format_conversation_for_llm(
            self, conversation_history: List[Message], current_message: Message
    ) -> List[Dict[str, str]]:
        """Format conversation history for the LLM API."""
        messages = []

        # Add system prompt if specified
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})

        # Add conversation history
        for msg in conversation_history:
            role = "assistant" if msg.role == MessageRole.ASSISTANT else "user"
            messages.append({"role": role, "content": msg.content})

        # Add the current message if it's not already in the history
        if not any(msg.id == current_message.id for msg in conversation_history):
            messages.append({"role": "user", "content": current_message.content})

        return messages

    async def send_message(
            self, recipient_id: str, content: str, conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a message to another agent."""
        # Create message
        message = Message(
            sender_id=self.id,
            recipient_id=recipient_id,
            content=content,
            conversation_id=conversation_id or str(uuid.uuid4()),
            role=MessageRole.USER,
            metadata={"agent_name": self.config.name}
        )

        # Store outgoing message
        await self.memory.add_message(self.id, message)

        # Lookup recipient address from registry (to be implemented)
        recipient_url = await self._get_agent_url(recipient_id)

        # Send message via HTTP
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{recipient_url}/receive_message",
                json=message.model_dump(mode='json'),
                timeout=30.0
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to send message to agent {recipient_id}"
                )

            return response.json()

    async def _get_agent_url(self, agent_id: str) -> str:
        """Get the URL for an agent from the registry."""
        # This would typically call the registry service
        # For now, return a placeholder
        return f"http://agent-{agent_id}:8000"

    async def chat(self, message_content: str, context: List[Dict[str, str]] = None) -> str:
        """Process a chat message and provide a response."""
        if context is None:
            context = []

        # Create a formatted conversation for the LLM
        messages = []
        
        # Add system prompt if available
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        
        # Add provided context
        messages.extend(context)
        
        # Add the current message
        messages.append({"role": "user", "content": message_content})
        
        # Get response from LLM
        try:
            response = await self.llm.generate_completion(
                messages=messages,
                model=self.config.model,
                temperature=self.config.temperature
            )
            return response
        except Exception as e:
            print(f"Error in chat method: {str(e)}")
            return f"I'm sorry, I encountered an error processing your message: {str(e)}"

    @abstractmethod
    async def specialized_capability(self, **kwargs) -> Any:
        """Each agent subclass should implement its specialized capabilities."""
        pass