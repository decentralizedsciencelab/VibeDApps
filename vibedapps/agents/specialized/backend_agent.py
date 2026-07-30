import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from vibedapps.agents.base_agent import AgentConfig, BaseAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore

_TEMPLATE_PN_SENTINEL = "__DAPP_TPL_PN_S3NT1NEL__"


class BackendAgent(BaseAgent):
    """Agent specialized for generating backend API code for DApps."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        # Default config if not provided
        if not config:
            config = AgentConfig(
                name="DApp Backend Generator",
                description="Generates backend API code for interacting with blockchain and smart contracts",
                capabilities=["express", "hardhat", "truffle", "flask", "fastapi", "django", "minimal"],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a specialized agent for generating backend code for decentralized applications. "
                    "You excel at creating APIs that interact with blockchain networks and smart contracts. "
                    "Your task is to generate backend code based on user specifications, "
                    "following best practices for security and performance."
                )
            )

        super().__init__(config, memory_store or InMemoryStore(), llm_service)

        # Register specialized endpoints
        self._register_specialized_endpoints()

        # Backend templates by type and language
        self.templates = {
            "javascript": {
                "express": self._get_express_template,
                "hardhat": self._get_hardhat_template,
                "truffle": self._get_truffle_template,
                "minimal": self._get_minimal_js_template,
            },
            "python": {
                "flask": self._get_flask_template,
                "fastapi": self._get_fastapi_template,
                "django": self._get_django_template,
                "minimal": self._get_minimal_py_template,
            }
        }

    def _register_specialized_endpoints(self):
        """Register specialized endpoints for this agent."""
        router = APIRouter()

        @router.post("/generate")
        async def generate_backend(specifications: Dict[str, Any]):
            """Generate backend code based on specifications."""
            return await self.specialized_capability(specifications=specifications)

        @router.post("/web3-integration")
        async def generate_web3_integration(contract_details: Dict[str, Any]):
            """Generate Web3 integration code for a smart contract."""
            return await self.generate_web3_integration(contract_details)

        # Add the router to the app
        self.app.include_router(router, prefix="/api/backend")

    def _apply_template_substitutions(
        self,
        templates: Dict[str, str],
        specifications: Dict[str, Any],
        contract_details: Optional[Dict[str, Any]] = None
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

        Returns:
            Dict of filename -> customized content
        """
        project_name = specifications.get("projectName", "dapp-api")
        project_description = specifications.get("projectDescription", "")
        network = specifications.get("deploymentOptions", {}).get("network", "ethereum-sepolia")

        # Extract contract information if available
        contract_name = contract_details.get("contract_name", "MyContract") if contract_details else "MyContract"
        contract_address = contract_details.get("contract_address", "0x0000000000000000000000000000000000000000") if contract_details else "0x0000000000000000000000000000000000000000"
        contract_abi = contract_details.get("contract_abi", []) if contract_details else []

        # Common substitutions
        substitutions = {
            "{{PROJECT_NAME}}": project_name,
            "{{PROJECT_DESCRIPTION}}": project_description,
            "{{NETWORK}}": network,
            "{{CONTRACT_NAME}}": contract_name,
            "{{CONTRACT_ADDRESS}}": contract_address,
            "{{CONTRACT_ABI}}": json.dumps(contract_abi, indent=2) if contract_abi else "[]",
            "MyToken": contract_name,  # Common default in templates
            "my-token": project_name.lower().replace(" ", "-"),
            "MY_TOKEN": project_name.upper().replace(" ", "_").replace("-", "_"),
        }

        # Apply substitutions to all template files
        customized = {}
        for filename, content in templates.items():
            customized_content = content
            for placeholder, value in substitutions.items():
                customized_content = customized_content.replace(placeholder, value)
            customized[filename] = customized_content

        # The templates read the ABI from config/contractABI.json and the
        # address from the CONTRACT_ADDRESS env var rather than via {{...}}
        # placeholders, so the substitution map above never actually injects
        # the contract data. Populate those runtime-config files directly.
        zero_addr = "0x0000000000000000000000000000000000000000"
        if contract_abi:
            for fname in list(customized.keys()):
                if fname.endswith("contractABI.json"):
                    customized[fname] = json.dumps(contract_abi, indent=2)
        if contract_address and contract_address != zero_addr:
            for fname, content in customized.items():
                if fname.endswith(".env"):
                    customized[fname] = content.replace(
                        f"CONTRACT_ADDRESS={zero_addr}",
                        f"CONTRACT_ADDRESS={contract_address}",
                    )

        return customized

    async def specialized_capability(self, **kwargs) -> Any:
        """Generate backend code based on specifications."""
        specifications = kwargs.get("specifications", {})
        generation_context = kwargs.get("context")  # New: receive shared context

        if not specifications:
            raise HTTPException(status_code=400, detail="No specifications provided")

        # Extract backend details
        backend_type = specifications.get("backendType", "express")
        backend_language = specifications.get("backendLanguage", "javascript")
        project_name = specifications.get("projectName", "dapp-api")
        project_description = specifications.get("projectDescription", "")
        contract_details = specifications.get("contractDetails", {})
        network = specifications.get("deploymentOptions", {}).get("network", "ethereum-sepolia")

        # NEW: If we have a generation context, extract contract details from it
        if generation_context:
            primary_contract = generation_context.get_primary_contract()
            if primary_contract:
                contract_details = {
                    "contract_name": primary_contract.name,
                    "contract_address": primary_contract.deployed_address or "0x0000000000000000000000000000000000000000",
                    "contract_abi": primary_contract.abi,
                    "contract_bytecode": primary_contract.bytecode,
                }

        # Get the template function based on language and type
        language_templates = self.templates.get(backend_language)
        if not language_templates:
            raise HTTPException(status_code=400, detail=f"Unsupported language: {backend_language}")

        template_func = language_templates.get(backend_type)
        if not template_func:
            raise HTTPException(status_code=400, detail=f"Unsupported backend type: {backend_type}")

        # Generate base templates
        templates = template_func(project_name)

        # NEW STRATEGY: Use template substitution instead of LLM rewriting
        # This is faster, more reliable, and produces functional code
        backend_code = self._apply_template_substitutions(
            templates=templates,
            specifications=specifications,
            contract_details=contract_details
        )

        # Store the generated backend code in memory
        await self.memory.store_knowledge(
            self.id, f"backend_{project_name}", backend_code
        )

        return {
            "project_name": project_name,
            "backend_type": backend_type,
            "backend_language": backend_language,
            "files": backend_code
        }

    async def generate_web3_integration(self, contract_details: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Web3 integration code for a smart contract."""
        if not contract_details:
            raise HTTPException(status_code=400, detail="No contract details provided")

        contract_name = contract_details.get("contract_name", "MyContract")
        contract_type = contract_details.get("contract_type", "custom")
        contract_abi = contract_details.get("contract_abi", [])
        language = contract_details.get("language", "javascript")

        integration_prompt = (
            f"Generate Web3 integration code in {language} for interacting with a {contract_type} smart contract named '{contract_name}'.\n\n"
            f"Contract ABI: {json.dumps(contract_abi, indent=2)}\n\n"
            f"Include code for the following operations:\n"
            f"1. Connecting to the blockchain network\n"
            f"2. Loading the contract ABI\n"
            f"3. Creating contract instances\n"
            f"4. Reading from the contract\n"
            f"5. Writing to the contract\n"
            f"6. Handling events\n"
            f"7. Error handling\n\n"
            f"Return the code in a format that can be easily integrated into a {language} backend."
        )

        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": integration_prompt}
        ]

        integration_code = await self.llm.generate_completion(
            messages=messages,
            model=self.config.model,
            temperature=0.3
        )

        return {
            "contract_name": contract_name,
            "language": language,
            "integration_code": integration_code
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

    def _load_backend_template(self, framework: str, project_name: str) -> Dict[str, str]:
        """Load a backend template set from templates/backend/<framework>/.

        Returns a {relative_path: file_content} dict with the project name
        injected. Templates were extracted verbatim from the former inline
        strings; the loader reproduces the original output byte-for-byte.
        """
        base = Path(__file__).resolve().parents[2] / "templates" / "backend" / framework
        files: Dict[str, str] = {}
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(base).as_posix()
                files[rel] = path.read_text().replace(_TEMPLATE_PN_SENTINEL, project_name)
        return files

    def _get_express_template(self, project_name: str) -> Dict[str, str]:
        """Express.js backend template (templates/backend/express/)."""
        return self._load_backend_template("express", project_name)

    def _get_hardhat_template(self, project_name: str) -> Dict[str, str]:
        """hardhat backend template (templates/backend/hardhat/)."""
        return self._load_backend_template("hardhat", project_name)

    def _get_truffle_template(self, project_name: str) -> Dict[str, str]:
        """truffle backend template (templates/backend/truffle/)."""
        return self._load_backend_template("truffle", project_name)

    def _get_minimal_js_template(self, project_name: str) -> Dict[str, str]:
        """minimal_js backend template (templates/backend/minimal_js/)."""
        return self._load_backend_template("minimal_js", project_name)

    def _get_flask_template(self, project_name: str) -> Dict[str, str]:
        """flask backend template (templates/backend/flask/)."""
        return self._load_backend_template("flask", project_name)

    def _get_fastapi_template(self, project_name: str) -> Dict[str, str]:
        """fastapi backend template (templates/backend/fastapi/)."""
        return self._load_backend_template("fastapi", project_name)

    def _get_django_template(self, project_name: str) -> Dict[str, str]:
        """django backend template (templates/backend/django/)."""
        return self._load_backend_template("django", project_name)

    def _get_minimal_py_template(self, project_name: str) -> Dict[str, str]:
        """minimal_py backend template (templates/backend/minimal_py/)."""
        return self._load_backend_template("minimal_py", project_name)
