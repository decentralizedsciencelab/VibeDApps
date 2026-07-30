"""
React Scaffold Adapter for frontend project initialization.

Supports both create-react-app and Vite for React project scaffolding,
with Web3 integration for DApp development.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from vibedapps.tools.adapters.base import ToolAdapter
from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.models import ToolExecutionResult

logger = logging.getLogger(__name__)


class ReactScaffoldAdapter(ToolAdapter):
    """Adapter for React project scaffolding with Web3 integration."""
    
    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        """Initialize the React scaffold adapter."""
        super().__init__(tool_executor)
        self._tool_name = "react-scaffold"
    
    def get_cli_command(self) -> str:
        """Get the CLI command for React scaffolding."""
        return "npx"
    
    def get_capabilities(self) -> List[str]:
        """Get React scaffold capabilities."""
        return [
            "frontend_init",
            "web3_integration",
            "component_generation",
            "wallet_connection",
            "contract_interaction"
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
        Initialize a React project with Web3 support.
        
        Args:
            project_path: Path where the project should be initialized
            config: Configuration with options:
                - tool: str - "vite" or "create-react-app" (default: "vite")
                - typescript: bool - Use TypeScript (default: True)
                - template: str - Template to use
                - install_web3: bool - Install Web3 libraries (default: True)
                
        Returns:
            ToolExecutionResult with initialization results
        """
        logger.info(f"Initializing React project at {project_path}")
        
        tool = config.get("tool", "vite")
        typescript = config.get("typescript", True)
        install_web3 = config.get("install_web3", True)
        
        # Create project directory
        project_dir = Path(project_path)
        project_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Initialize React project
            if tool == "vite":
                result = await self._initialize_with_vite(
                    project_path,
                    typescript
                )
            else:  # create-react-app
                result = await self._initialize_with_cra(
                    project_path,
                    typescript
                )
            
            if not result.is_success:
                return result
            
            # Install Web3 libraries if requested
            if install_web3:
                web3_result = await self._install_web3_libraries(project_path)
                if not web3_result.is_success:
                    logger.warning(f"Web3 library installation failed: {web3_result.stderr}")
            
            # Verify project structure
            required_files = ["package.json", "src"]
            structure_valid = await self.verify_project_structure(project_path, required_files)
            
            if not structure_valid:
                result.success = False
                result.error_message = "Project structure validation failed"
            
            logger.info("React project initialization completed")
            return result
        
        except Exception as e:
            error_msg = f"React project initialization error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ToolExecutionResult(
                command="npx create-react-app / vite",
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=0.0,
                success=False,
                error_message=error_msg
            )
    
    async def _initialize_with_vite(
        self,
        project_path: str,
        typescript: bool
    ) -> ToolExecutionResult:
        """
        Initialize project using Vite.
        
        Args:
            project_path: Path to initialize project
            typescript: Whether to use TypeScript
            
        Returns:
            ToolExecutionResult with initialization results
        """
        logger.info("Initializing with Vite")
        
        template = "react-ts" if typescript else "react"
        project_name = Path(project_path).name
        
        # Create Vite project
        result = await self.tool_executor.execute(
            command="npm",
            args=["create", "vite@latest", project_name, "--", "--template", template],
            cwd=str(Path(project_path).parent),
            timeout=300
        )
        
        if result.is_success:
            # Install dependencies
            install_result = await self.tool_executor.execute(
                command="npm",
                args=["install"],
                cwd=project_path,
                timeout=600
            )
            
            if not install_result.is_success:
                return install_result
        
        return result
    
    async def _initialize_with_cra(
        self,
        project_path: str,
        typescript: bool
    ) -> ToolExecutionResult:
        """
        Initialize project using create-react-app.
        
        Args:
            project_path: Path to initialize project
            typescript: Whether to use TypeScript
            
        Returns:
            ToolExecutionResult with initialization results
        """
        logger.info("Initializing with create-react-app")
        
        project_name = Path(project_path).name
        args = ["create-react-app", project_name]
        
        if typescript:
            args.append("--template")
            args.append("typescript")
        
        result = await self.tool_executor.execute(
            command="npx",
            args=args,
            cwd=str(Path(project_path).parent),
            timeout=600
        )
        
        return result
    
    async def _install_web3_libraries(
        self,
        project_path: str
    ) -> ToolExecutionResult:
        """
        Install Web3 libraries (ethers.js, wagmi, RainbowKit).
        
        Args:
            project_path: Path to the project
            
        Returns:
            ToolExecutionResult with installation results
        """
        logger.info("Installing Web3 libraries")
        
        libraries = [
            "ethers",
            "wagmi",
            "@rainbow-me/rainbowkit",
            "viem"
        ]
        
        result = await self.tool_executor.execute(
            command="npm",
            args=["install"] + libraries,
            cwd=project_path,
            timeout=600
        )
        
        return result
    
    async def configure_web3(
        self,
        project_path: str,
        config: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        Configure Web3 integration in the React project.
        
        Args:
            project_path: Path to the project
            config: Configuration with options:
                - chains: List[str] - Blockchain networks to support
                - wallet_connect_project_id: str - WalletConnect project ID
                
        Returns:
            ToolExecutionResult with configuration results
        """
        logger.info("Configuring Web3 integration")
        
        try:
            # Create Web3 configuration file
            web3_config = self._generate_web3_config(config)
            
            config_path = Path(project_path) / "src" / "web3Config.ts"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w') as f:
                f.write(web3_config)
            
            # Create wallet connection provider
            provider_code = self._generate_wallet_provider(config)
            
            provider_path = Path(project_path) / "src" / "components" / "WalletProvider.tsx"
            provider_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(provider_path, 'w') as f:
                f.write(provider_code)
            
            logger.info("Web3 configuration completed")
            
            return ToolExecutionResult(
                command="configure web3",
                exit_code=0,
                stdout="Web3 configuration files created",
                stderr="",
                execution_time=0.1,
                success=True
            )
        
        except Exception as e:
            error_msg = f"Web3 configuration error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ToolExecutionResult(
                command="configure web3",
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=0.0,
                success=False,
                error_message=error_msg
            )
    
    def _generate_web3_config(self, config: Dict[str, Any]) -> str:
        """
        Generate Web3 configuration code.
        
        Args:
            config: Configuration options
            
        Returns:
            TypeScript configuration code
        """
        chains = config.get("chains", ["mainnet", "sepolia"])
        wallet_connect_id = config.get("wallet_connect_project_id", "YOUR_PROJECT_ID")
        
        return f'''import {{ configureChains, createConfig }} from 'wagmi';
import {{ mainnet, sepolia, polygon, optimism, arbitrum }} from 'wagmi/chains';
import {{ publicProvider }} from 'wagmi/providers/public';
import {{ getDefaultWallets }} from '@rainbow-me/rainbowkit';

// Configure chains
const {{ chains, publicClient, webSocketPublicClient }} = configureChains(
  [mainnet, sepolia],
  [publicProvider()]
);

// Configure wallets
const {{ connectors }} = getDefaultWallets({{
  appName: 'My DApp',
  projectId: '{wallet_connect_id}',
  chains,
}});

// Create wagmi config
export const wagmiConfig = createConfig({{
  autoConnect: true,
  connectors,
  publicClient,
  webSocketPublicClient,
}});

export {{ chains }};
'''
    
    def _generate_wallet_provider(self, config: Dict[str, Any]) -> str:
        """
        Generate wallet provider component.
        
        Args:
            config: Configuration options
            
        Returns:
            React component code
        """
        return '''import React from 'react';
import { WagmiConfig } from 'wagmi';
import { RainbowKitProvider } from '@rainbow-me/rainbowkit';
import { wagmiConfig, chains } from '../web3Config';
import '@rainbow-me/rainbowkit/styles.css';

interface WalletProviderProps {
  children: React.ReactNode;
}

export const WalletProvider: React.FC<WalletProviderProps> = ({ children }) => {
  return (
    <WagmiConfig config={wagmiConfig}>
      <RainbowKitProvider chains={chains}>
        {children}
      </RainbowKitProvider>
    </WagmiConfig>
  );
};
'''
    
    async def generate_wallet_component(
        self,
        project_path: str
    ) -> ToolExecutionResult:
        """
        Generate wallet connection component.
        
        Args:
            project_path: Path to the project
            
        Returns:
            ToolExecutionResult with generation results
        """
        logger.info("Generating wallet connection component")
        
        try:
            component_code = '''import React from 'react';
import { ConnectButton } from '@rainbow-me/rainbowkit';

export const WalletConnect: React.FC = () => {
  return (
    <div className="wallet-connect">
      <ConnectButton />
    </div>
  );
};
'''
            
            component_path = Path(project_path) / "src" / "components" / "WalletConnect.tsx"
            component_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(component_path, 'w') as f:
                f.write(component_code)
            
            logger.info("Wallet component generated")
            
            return ToolExecutionResult(
                command="generate wallet component",
                exit_code=0,
                stdout=f"Component created: {component_path}",
                stderr="",
                execution_time=0.1,
                success=True
            )
        
        except Exception as e:
            error_msg = f"Component generation error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ToolExecutionResult(
                command="generate wallet component",
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=0.0,
                success=False,
                error_message=error_msg
            )
    
    async def generate_contract_interaction_component(
        self,
        project_path: str,
        contract_name: str,
        contract_abi: List[Dict[str, Any]],
        contract_address: str
    ) -> ToolExecutionResult:
        """
        Generate contract interaction component.
        
        Args:
            project_path: Path to the project
            contract_name: Name of the contract
            contract_abi: Contract ABI
            contract_address: Contract address
            
        Returns:
            ToolExecutionResult with generation results
        """
        logger.info(f"Generating contract interaction component for {contract_name}")
        
        try:
            # Generate component code
            component_code = self._generate_contract_component_code(
                contract_name,
                contract_abi,
                contract_address
            )
            
            component_path = Path(project_path) / "src" / "components" / f"{contract_name}Interaction.tsx"
            component_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(component_path, 'w') as f:
                f.write(component_code)
            
            # Generate contract config
            config_code = self._generate_contract_config(
                contract_name,
                contract_abi,
                contract_address
            )
            
            config_path = Path(project_path) / "src" / "contracts" / f"{contract_name}Config.ts"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w') as f:
                f.write(config_code)
            
            logger.info(f"Contract interaction component generated for {contract_name}")
            
            return ToolExecutionResult(
                command=f"generate contract component {contract_name}",
                exit_code=0,
                stdout=f"Component created: {component_path}\\nConfig created: {config_path}",
                stderr="",
                execution_time=0.1,
                success=True
            )
        
        except Exception as e:
            error_msg = f"Contract component generation error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ToolExecutionResult(
                command=f"generate contract component {contract_name}",
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=0.0,
                success=False,
                error_message=error_msg
            )
    
    def _generate_contract_component_code(
        self,
        contract_name: str,
        contract_abi: List[Dict[str, Any]],
        contract_address: str
    ) -> str:
        """
        Generate React component code for contract interaction.
        
        Args:
            contract_name: Name of the contract
            contract_abi: Contract ABI
            contract_address: Contract address
            
        Returns:
            React component code
        """
        # Extract read and write functions from ABI
        read_functions = [
            func for func in contract_abi
            if func.get('type') == 'function' and func.get('stateMutability') in ['view', 'pure']
        ]
        
        write_functions = [
            func for func in contract_abi
            if func.get('type') == 'function' and func.get('stateMutability') not in ['view', 'pure']
        ]
        
        component_name = contract_name
        config_name = contract_name.lower()
        
        return f'''import React, {{ useState }} from 'react';
import {{ useContractRead, useContractWrite, usePrepareContractWrite }} from 'wagmi';
import {{ {config_name}Config }} from '../contracts/{component_name}Config';

export const {component_name}Interaction: React.FC = () => {{
  // State for function inputs
  const [inputs, setInputs] = useState<Record<string, any>>({{}});

  // Example read function (customize based on your contract)
  const {{ data: readData, isLoading: isReading }} = useContractRead({{
    ...{config_name}Config,
    functionName: 'exampleReadFunction',
  }});

  // Example write function (customize based on your contract)
  const {{ config }} = usePrepareContractWrite({{
    ...{config_name}Config,
    functionName: 'exampleWriteFunction',
    args: [],
  }});

  const {{ write, isLoading: isWriting }} = useContractWrite(config);
  
  return (
    <div className="{config_name}-interaction">
      <h2>{component_name} Contract</h2>
      
      {{/* Add your contract interaction UI here */}}
      <div>
        <h3>Read Functions</h3>
        {{/* Add read function calls */}}
      </div>
      
      <div>
        <h3>Write Functions</h3>
        {{/* Add write function calls */}}
      </div>
    </div>
  );
}};
'''
    
    def _generate_contract_config(
        self,
        contract_name: str,
        contract_abi: List[Dict[str, Any]],
        contract_address: str
    ) -> str:
        """
        Generate contract configuration file.
        
        Args:
            contract_name: Name of the contract
            contract_abi: Contract ABI
            contract_address: Contract address
            
        Returns:
            TypeScript configuration code
        """
        abi_json = json.dumps(contract_abi, indent=2)
        
        return f'''export const {contract_name.lower()}Config = {{
  address: '{contract_address}' as `0x${{string}}`,
  abi: {abi_json},
}} as const;
'''
