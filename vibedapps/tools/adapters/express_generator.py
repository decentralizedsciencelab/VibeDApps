"""
Express Generator Adapter for backend API scaffolding.

Provides Express.js project initialization with contract integration
and API route generation from contract ABIs.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from vibedapps.tools.adapters.base import ToolAdapter
from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.models import ToolExecutionResult

logger = logging.getLogger(__name__)


class ExpressGeneratorAdapter(ToolAdapter):
    """Adapter for Express.js backend scaffolding."""
    
    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        """Initialize the Express generator adapter."""
        super().__init__(tool_executor)
        self._tool_name = "express-generator"
    
    def get_cli_command(self) -> str:
        """Get the CLI command for Express generator."""
        return "npx"
    
    def get_capabilities(self) -> List[str]:
        """Get Express generator capabilities."""
        return [
            "backend_init",
            "api_generation",
            "contract_integration",
            "middleware_setup",
            "route_generation"
        ]
    
    async def validate_installation(self) -> bool:
        """
        Check if npm/npx is available.
        
        Returns:
            True if npm is available, False otherwise
        """
        try:
            result = await self.tool_executor.execute(
                command="npm",
                args=["--version"],
                cwd=".",
                timeout=30,
                raise_on_error=False
            )
            
            if result.is_success:
                logger.info(f"npm validation successful: {result.stdout.strip()}")
                return True
            
            logger.warning("npm validation failed")
            return False
        
        except Exception as e:
            logger.error(f"npm validation error: {e}")
            return False
    
    def get_version(self) -> Optional[str]:
        """
        Get npm version.
        
        Returns:
            Version string if available, None otherwise
        """
        try:
            import asyncio
            
            result = asyncio.run(self.tool_executor.execute(
                command="npm",
                args=["--version"],
                cwd=".",
                timeout=30,
                raise_on_error=False
            ))
            
            if result.is_success:
                return result.stdout.strip()
            
            return None
        
        except Exception as e:
            logger.warning(f"Failed to get npm version: {e}")
            return None
    
    async def initialize_project(
        self,
        project_path: str,
        config: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        Initialize an Express.js project.
        
        Args:
            project_path: Path where the project should be initialized
            config: Configuration with options:
                - view_engine: str - View engine (default: "ejs")
                - git: bool - Add .gitignore (default: True)
                - typescript: bool - Use TypeScript (default: False)
                
        Returns:
            ToolExecutionResult with initialization results
        """
        logger.info(f"Initializing Express project at {project_path}")
        
        view_engine = config.get("view_engine", "ejs")
        use_git = config.get("git", True)
        typescript = config.get("typescript", False)
        
        # Create project directory
        project_dir = Path(project_path)
        project_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Initialize Express project
            project_name = project_dir.name
            args = ["express-generator", project_name, "--view", view_engine]
            
            if use_git:
                args.append("--git")
            
            result = await self.tool_executor.execute(
                command="npx",
                args=args,
                cwd=str(project_dir.parent),
                timeout=120
            )
            
            if not result.is_success:
                return result
            
            # Install dependencies
            install_result = await self.tool_executor.execute(
                command="npm",
                args=["install"],
                cwd=project_path,
                timeout=600
            )
            
            if not install_result.is_success:
                logger.warning(f"Dependency installation failed: {install_result.stderr}")
            
            # Install additional dependencies for Web3 integration
            web3_result = await self._install_web3_dependencies(project_path)
            if not web3_result.is_success:
                logger.warning(f"Web3 dependency installation failed: {web3_result.stderr}")
            
            # Configure middleware
            await self._configure_middleware(project_path)
            
            # Verify project structure
            required_files = ["package.json", "app.js", "routes"]
            structure_valid = await self.verify_project_structure(project_path, required_files)
            
            if not structure_valid:
                result.success = False
                result.error_message = "Project structure validation failed"
            
            logger.info("Express project initialization completed")
            return result
        
        except Exception as e:
            error_msg = f"Express project initialization error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ToolExecutionResult(
                command="npx express-generator",
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=0.0,
                success=False,
                error_message=error_msg
            )
    
    async def _install_web3_dependencies(
        self,
        project_path: str
    ) -> ToolExecutionResult:
        """
        Install Web3 and blockchain-related dependencies.
        
        Args:
            project_path: Path to the project
            
        Returns:
            ToolExecutionResult with installation results
        """
        logger.info("Installing Web3 dependencies")
        
        dependencies = [
            "ethers",
            "cors",
            "dotenv",
            "express-validator"
        ]
        
        result = await self.tool_executor.execute(
            command="npm",
            args=["install"] + dependencies,
            cwd=project_path,
            timeout=600
        )
        
        return result
    
    async def _configure_middleware(
        self,
        project_path: str
    ) -> None:
        """
        Configure Express middleware for CORS, body parsing, etc.
        
        Args:
            project_path: Path to the project
        """
        logger.info("Configuring Express middleware")
        
        try:
            app_js_path = Path(project_path) / "app.js"
            
            if not app_js_path.exists():
                logger.warning("app.js not found, skipping middleware configuration")
                return
            
            # Read existing app.js
            with open(app_js_path) as f:
                app_content = f.read()
            
            # Add middleware configuration if not already present
            if "cors" not in app_content:
                # Find the position to insert middleware (after express() initialization)
                insert_pos = app_content.find("var app = express();")
                if insert_pos != -1:
                    insert_pos = app_content.find("\n", insert_pos) + 1
                    
                    middleware_code = """
// CORS configuration
const cors = require('cors');
app.use(cors());

// Environment variables
require('dotenv').config();

"""
                    app_content = app_content[:insert_pos] + middleware_code + app_content[insert_pos:]
                    
                    # Write updated app.js
                    with open(app_js_path, 'w') as f:
                        f.write(app_content)
                    
                    logger.info("Middleware configuration added to app.js")
        
        except Exception as e:
            logger.warning(f"Failed to configure middleware: {e}")
    
    async def generate_contract_routes(
        self,
        project_path: str,
        contract_name: str,
        contract_abi: List[Dict[str, Any]],
        contract_address: str
    ) -> ToolExecutionResult:
        """
        Generate Express routes for contract interaction.
        
        Args:
            project_path: Path to the project
            contract_name: Name of the contract
            contract_abi: Contract ABI
            contract_address: Contract address
            
        Returns:
            ToolExecutionResult with generation results
        """
        logger.info(f"Generating routes for contract: {contract_name}")
        
        try:
            # Generate route file
            route_code = self._generate_route_code(
                contract_name,
                contract_abi,
                contract_address
            )
            
            route_path = Path(project_path) / "routes" / f"{contract_name.lower()}.js"
            route_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(route_path, 'w') as f:
                f.write(route_code)
            
            # Generate contract service
            service_code = self._generate_service_code(
                contract_name,
                contract_abi,
                contract_address
            )
            
            service_path = Path(project_path) / "services" / f"{contract_name.lower()}Service.js"
            service_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(service_path, 'w') as f:
                f.write(service_code)
            
            # Update app.js to include the new route
            await self._register_route(project_path, contract_name)
            
            logger.info(f"Routes generated for {contract_name}")
            
            return ToolExecutionResult(
                command=f"generate routes {contract_name}",
                exit_code=0,
                stdout=f"Route created: {route_path}\\nService created: {service_path}",
                stderr="",
                execution_time=0.1,
                success=True
            )
        
        except Exception as e:
            error_msg = f"Route generation error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ToolExecutionResult(
                command=f"generate routes {contract_name}",
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=0.0,
                success=False,
                error_message=error_msg
            )
    
    def _generate_route_code(
        self,
        contract_name: str,
        contract_abi: List[Dict[str, Any]],
        contract_address: str
    ) -> str:
        """
        Generate Express route code for contract.
        
        Args:
            contract_name: Name of the contract
            contract_abi: Contract ABI
            contract_address: Contract address
            
        Returns:
            Express route code
        """
        # Extract functions from ABI
        read_functions = [
            func for func in contract_abi
            if func.get('type') == 'function' and func.get('stateMutability') in ['view', 'pure']
        ]
        
        write_functions = [
            func for func in contract_abi
            if func.get('type') == 'function' and func.get('stateMutability') not in ['view', 'pure']
        ]
        
        # Generate route handlers
        route_handlers = []
        
        for func in read_functions[:3]:  # Limit to first 3 for example
            func_name = func.get('name', 'unknown')
            route_handlers.append(f"""
// GET /{func_name}
router.get('/{func_name}', async (req, res) => {{
  try {{
    const result = await {contract_name.lower()}Service.{func_name}();
    res.json({{ success: true, data: result }});
  }} catch (error) {{
    res.status(500).json({{ success: false, error: error.message }});
  }}
}});
""")
        
        for func in write_functions[:3]:  # Limit to first 3 for example
            func_name = func.get('name', 'unknown')
            route_handlers.append(f"""
// POST /{func_name}
router.post('/{func_name}', async (req, res) => {{
  try {{
    const {{ ...params }} = req.body;
    const result = await {contract_name.lower()}Service.{func_name}(params);
    res.json({{ success: true, data: result }});
  }} catch (error) {{
    res.status(500).json({{ success: false, error: error.message }});
  }}
}});
""")
        
        return f'''const express = require('express');
const router = express.Router();
const {contract_name.lower()}Service = require('../services/{contract_name.lower()}Service');

// Contract: {contract_name}
// Address: {contract_address}

{''.join(route_handlers)}

module.exports = router;
'''
    
    def _generate_service_code(
        self,
        contract_name: str,
        contract_abi: List[Dict[str, Any]],
        contract_address: str
    ) -> str:
        """
        Generate service code for contract interaction.
        
        Args:
            contract_name: Name of the contract
            contract_abi: Contract ABI
            contract_address: Contract address
            
        Returns:
            Service code
        """
        abi_json = json.dumps(contract_abi, indent=2)
        
        # Extract functions
        read_functions = [
            func for func in contract_abi
            if func.get('type') == 'function' and func.get('stateMutability') in ['view', 'pure']
        ]
        
        write_functions = [
            func for func in contract_abi
            if func.get('type') == 'function' and func.get('stateMutability') not in ['view', 'pure']
        ]
        
        # Generate service methods
        service_methods = []
        
        for func in read_functions[:3]:
            func_name = func.get('name', 'unknown')
            service_methods.append(f"""
  async {func_name}() {{
    try {{
      const result = await this.contract.{func_name}();
      return result;
    }} catch (error) {{
      console.error('Error calling {func_name}:', error);
      throw error;
    }}
  }}
""")
        
        for func in write_functions[:3]:
            func_name = func.get('name', 'unknown')
            service_methods.append(f"""
  async {func_name}(params) {{
    try {{
      // Note: This requires a signer with private key
      // Configure your wallet/signer in the constructor
      const tx = await this.contract.{func_name}(...Object.values(params));
      const receipt = await tx.wait();
      return receipt;
    }} catch (error) {{
      console.error('Error calling {func_name}:', error);
      throw error;
    }}
  }}
""")
        
        return f'''const {{ ethers }} = require('ethers');

class {contract_name}Service {{
  constructor() {{
    // Configure provider
    const rpcUrl = process.env.RPC_URL || 'http://localhost:8545';
    this.provider = new ethers.JsonRpcProvider(rpcUrl);
    
    // Contract configuration
    this.contractAddress = '{contract_address}';
    this.contractABI = {abi_json};
    
    // Initialize contract
    this.contract = new ethers.Contract(
      this.contractAddress,
      this.contractABI,
      this.provider
    );
    
    // For write operations, you'll need a signer
    // Uncomment and configure if needed:
    // const privateKey = process.env.PRIVATE_KEY;
    // const wallet = new ethers.Wallet(privateKey, this.provider);
    // this.contract = this.contract.connect(wallet);
  }}
{''.join(service_methods)}
}}

module.exports = new {contract_name}Service();
'''
    
    async def _register_route(
        self,
        project_path: str,
        contract_name: str
    ) -> None:
        """
        Register the new route in app.js.
        
        Args:
            project_path: Path to the project
            contract_name: Name of the contract
        """
        logger.info(f"Registering route for {contract_name}")
        
        try:
            app_js_path = Path(project_path) / "app.js"
            
            if not app_js_path.exists():
                logger.warning("app.js not found, skipping route registration")
                return
            
            # Read existing app.js
            with open(app_js_path) as f:
                app_content = f.read()
            
            route_name = contract_name.lower()
            
            # Check if route is already registered
            if f"/{route_name}" in app_content:
                logger.info(f"Route /{route_name} already registered")
                return
            
            # Add route import
            import_line = f"var {route_name}Router = require('./routes/{route_name}');\n"
            
            # Find position to insert import (after other route imports)
            import_pos = app_content.rfind("var ")
            if import_pos != -1:
                import_pos = app_content.find("\n", import_pos) + 1
                app_content = app_content[:import_pos] + import_line + app_content[import_pos:]
            
            # Add route usage
            use_line = f"app.use('/{route_name}', {route_name}Router);\n"
            
            # Find position to insert usage (after other app.use statements for routes)
            use_pos = app_content.rfind("app.use('")
            if use_pos != -1:
                use_pos = app_content.find("\n", use_pos) + 1
                app_content = app_content[:use_pos] + use_line + app_content[use_pos:]
            
            # Write updated app.js
            with open(app_js_path, 'w') as f:
                f.write(app_content)
            
            logger.info(f"Route /{route_name} registered in app.js")
        
        except Exception as e:
            logger.warning(f"Failed to register route: {e}")
    
    async def create_env_template(
        self,
        project_path: str,
        config: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        Create .env.example template file.
        
        Args:
            project_path: Path to the project
            config: Configuration with environment variables
            
        Returns:
            ToolExecutionResult with creation results
        """
        logger.info("Creating .env.example template")
        
        try:
            env_content = """# RPC Configuration
RPC_URL=http://localhost:8545

# Private Key (for write operations)
# PRIVATE_KEY=your_private_key_here

# Contract Addresses
# CONTRACT_ADDRESS=0x...

# Server Configuration
PORT=3000
NODE_ENV=development
"""
            
            env_path = Path(project_path) / ".env.example"
            
            with open(env_path, 'w') as f:
                f.write(env_content)
            
            logger.info(".env.example created")
            
            return ToolExecutionResult(
                command="create .env.example",
                exit_code=0,
                stdout=f"Template created: {env_path}",
                stderr="",
                execution_time=0.1,
                success=True
            )
        
        except Exception as e:
            error_msg = f"Env template creation error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ToolExecutionResult(
                command="create .env.example",
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=0.0,
                success=False,
                error_message=error_msg
            )
