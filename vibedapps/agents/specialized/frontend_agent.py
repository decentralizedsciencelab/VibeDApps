import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from vibedapps.agents.base_agent import AgentConfig, BaseAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore

_TEMPLATE_PN_SENTINEL = "__DAPP_TPL_PN_S3NT1NEL__"


class FrontendAgent(BaseAgent):
    """Agent specialized for generating frontend code for DApps."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        # Default config if not provided
        if not config:
            config = AgentConfig(
                name="Frontend Generator",
                description="Generates modern, responsive frontend code for decentralized applications",
                capabilities=["react", "vue", "nextjs", "html"],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a specialized agent for generating frontend code for decentralized applications. "
                    "You excel at creating modern, responsive, and user-friendly interfaces that interact "
                    "with blockchain networks and smart contracts. Your task is to generate frontend code "
                    "based on user specifications, following best practices for web development and Web3 integration."
                )
            )

        super().__init__(config, memory_store or InMemoryStore(), llm_service)

        # Register specialized endpoints
        self._register_specialized_endpoints()

        # Frontend templates by framework
        self.framework_templates = {
            "react": self._get_react_template,
            "vue": self._get_vue_template,
            "nextjs": self._get_nextjs_template,
            "pure": self._get_html_template,
            "html": self._get_html_template,
        }

    def _register_specialized_endpoints(self):
        """Register specialized endpoints for this agent."""
        router = APIRouter()

        @router.post("/generate")
        async def generate_frontend(specifications: Dict[str, Any]):
            """Generate frontend code based on specifications."""
            return await self.specialized_capability(specifications=specifications)

        @router.post("/components")
        async def generate_components(component_details: Dict[str, Any]):
            """Generate specific UI components."""
            return await self.generate_components(component_details)

        # Add the router to the app
        self.app.include_router(router, prefix="/api/frontend")

    def _apply_template_substitutions(
        self,
        templates: Dict[str, str],
        specifications: Dict[str, Any],
        contract_details: Optional[Dict[str, Any]] = None,
        backend_url: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Apply direct template substitutions instead of asking LLM to rewrite.

        This method takes the complete templates and performs variable substitution
        for project-specific values. This is much faster and more reliable than
        asking the LLM to "customize" the templates.

        Args:
            templates: Dict of filename -> template content
            specifications: Project specifications
            contract_details: Optional contract details including ABI
            backend_url: Optional backend API URL

        Returns:
            Dict of filename -> customized content
        """
        project_name = specifications.get("projectName", "dapp-ui")
        project_description = specifications.get("projectDescription", "")

        # Extract contract information if available
        contract_name = contract_details.get("contract_name", "MyContract") if contract_details else "MyContract"
        contract_address = contract_details.get("contract_address", "0x0000000000000000000000000000000000000000") if contract_details else "0x0000000000000000000000000000000000000000"
        contract_abi = contract_details.get("contract_abi", []) if contract_details else []

        # Backend URL
        api_url = backend_url or "http://localhost:3001"

        # Common substitutions
        substitutions = {
            "{{PROJECT_NAME}}": project_name,
            "{{PROJECT_DESCRIPTION}}": project_description,
            "{{CONTRACT_NAME}}": contract_name,
            "{{CONTRACT_ADDRESS}}": contract_address,
            "{{CONTRACT_ABI}}": json.dumps(contract_abi, indent=2) if contract_abi else "[]",
            "{{BACKEND_URL}}": api_url,
            "{{API_URL}}": api_url,
            "MyToken": contract_name,  # Common default in templates
            "my-token": project_name.lower().replace(" ", "-"),
            "MY_TOKEN": project_name.upper().replace(" ", "_").replace("-", "_"),
            "My Token DApp": project_name,
        }

        # Apply substitutions to all template files
        customized = {}
        for filename, content in templates.items():
            customized_content = content
            for placeholder, value in substitutions.items():
                customized_content = customized_content.replace(placeholder, value)
            customized[filename] = customized_content

        return customized

    async def specialized_capability(self, **kwargs) -> Any:
        """Generate frontend code based on specifications."""
        specifications = kwargs.get("specifications", {})
        generation_context = kwargs.get("context")  # New: receive shared context

        if not specifications:
            raise HTTPException(status_code=400, detail="No specifications provided")

        # Extract frontend details
        framework = specifications.get("frontendFramework", "react")
        project_name = specifications.get("projectName", "dapp-ui")
        project_description = specifications.get("projectDescription", "")
        ui_components = specifications.get("uiComponents", {})
        contract_details = specifications.get("contractDetails", {})

        # NEW: If we have a generation context, extract contract and backend details
        backend_url = None
        if generation_context:
            primary_contract = generation_context.get_primary_contract()
            if primary_contract:
                contract_details = {
                    "contract_name": primary_contract.name,
                    "contract_address": primary_contract.deployed_address or "0x0000000000000000000000000000000000000000",
                    "contract_abi": primary_contract.abi,
                }

            # Get backend URL from context
            if generation_context.backend:
                backend_url = f"http://localhost:{generation_context.backend.port}"

        # Get the template function based on framework
        template_func = self.framework_templates.get(framework, self._get_react_template)

        # Generate base templates
        templates = template_func(project_name)

        # NEW STRATEGY: Use template substitution instead of LLM rewriting
        # This is faster, more reliable, and produces functional code
        frontend_code = self._apply_template_substitutions(
            templates=templates,
            specifications=specifications,
            contract_details=contract_details,
            backend_url=backend_url
        )

        # Store the generated frontend code in memory
        await self.memory.store_knowledge(
            self.id, f"frontend_{project_name}", frontend_code
        )

        return {
            "project_name": project_name,
            "framework": framework,
            "files": frontend_code
        }

    async def generate_components(self, component_details: Dict[str, Any]) -> Dict[str, Any]:
        """Generate specific UI components."""
        if not component_details:
            raise HTTPException(status_code=400, detail="No component details provided")

        component_type = component_details.get("type", "unknown")
        framework = component_details.get("framework", "react")
        contract_interaction = component_details.get("contractInteraction", False)
        specifications = component_details.get("specifications", {})

        component_prompt = (
            f"Generate a {framework} component for a DApp with the following specifications:\n\n"
            f"Component Type: {component_type}\n"
            f"Contract Interaction: {'Yes' if contract_interaction else 'No'}\n"
            f"Specifications: {json.dumps(specifications, indent=2)}\n\n"
            f"The component should be well-structured, responsive, and follow best practices. "
            f"If contract interaction is required, include appropriate Web3 integration code. "
            f"Return only the component code without any surrounding explanations."
        )

        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": component_prompt}
        ]

        component_code = await self.llm.generate_completion(
            messages=messages,
            model=self.config.model,
            temperature=0.3
        )

        return {
            "component_type": component_type,
            "framework": framework,
            "code": component_code
        }

    def _extract_code_blocks(self, text: str) -> Dict[str, str]:
        """Extract code blocks from text when JSON parsing fails."""
        files = {}
        lines = text.split("\n")
        current_file = None
        current_content = []

        for line in lines:
            if line.startswith("```") and ":" in line:
                # If we were already collecting a file, save it
                if current_file and current_content:
                    files[current_file] = "\n".join(current_content)
                    current_content = []

                # Extract filename
                parts = line.strip("`").split(":", 1)
                if len(parts) > 1:
                    current_file = parts[1].strip()
                else:
                    current_file = f"file_{len(files)}.txt"
            elif line.startswith("```") and current_file:
                # End of a code block
                files[current_file] = "\n".join(current_content)
                current_file = None
                current_content = []
            elif current_file is not None:
                # Add line to current file content
                current_content.append(line)

        # If there's any file content left
        if current_file and current_content:
            files[current_file] = "\n".join(current_content)

        return files

    def _load_frontend_template(self, framework: str, project_name: str) -> Dict[str, str]:
        """Load a frontend template set from templates/frontend/<framework>/."""
        base = Path(__file__).resolve().parents[2] / "templates" / "frontend" / framework
        files: Dict[str, str] = {}
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(base).as_posix()
                files[rel] = path.read_text().replace(_TEMPLATE_PN_SENTINEL, project_name)
        return files

    def _get_react_template(self, project_name: str) -> Dict[str, str]:
        """react frontend template (templates/frontend/react/)."""
        return self._load_frontend_template("react", project_name)

    def _get_vue_template(self, project_name: str) -> Dict[str, str]:
        """vue frontend template (templates/frontend/vue/)."""
        return self._load_frontend_template("vue", project_name)

    def _get_nextjs_template(self, project_name: str) -> Dict[str, str]:
        """nextjs frontend template (templates/frontend/nextjs/)."""
        return self._load_frontend_template("nextjs", project_name)

    def _get_html_template(self, project_name: str) -> Dict[str, str]:
        """html frontend template (templates/frontend/html/)."""
        return self._load_frontend_template("html", project_name)
