import json
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from vibedapps.agents.base_agent import AgentConfig, BaseAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class SmartContractAuditAgent(BaseAgent):
    """Agent specialized for auditing smart contracts."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        # Default config if not provided
        if not config:
            config = AgentConfig(
                name="Smart Contract Auditor",
                description="Audits smart contracts for security vulnerabilities and best practices",
                capabilities=["security_audit", "gas_optimization", "code_quality", "compliance_check"],
                model="gpt-4o",
                temperature=0.1,  # Very low temperature for consistent, deterministic analysis
                system_prompt=(
                    "You are a specialized agent for auditing smart contracts. "
                    "You excel at identifying security vulnerabilities, gas inefficiencies, "
                    "and code quality issues in blockchain code. Your task is to thoroughly "
                    "analyze smart contracts for potential risks, following industry best practices "
                    "and security standards."
                )
            )

        super().__init__(config, memory_store or InMemoryStore(), llm_service)

        # Register specialized endpoints
        self._register_specialized_endpoints()

        # Common vulnerability patterns to check
        self.vulnerability_patterns = {
            "reentrancy": r"(\.\s*transfer\s*\(|\.\s*send\s*\(|\.call\s*\{.*\}\s*\()",
            "integer_overflow": r"(\+\+|\+=|-=|\*=|\/=|%=)",
            "unchecked_return": r"(\.transfer\s*\(|\.send\s*\()",
            "tx_origin": r"tx\.origin",
            "delegatecall": r"delegatecall",
            "assembly": r"assembly",
            "selfdestruct": r"selfdestruct|suicide",
            "timestamp_dependence": r"block\.timestamp|now",
            "weak_randomness": r"blockhash|block\.difficulty",
            "unsafe_math": r"(\+|-|\*|\/(?!\/)|%)",
        }

    def _register_specialized_endpoints(self):
        """Register specialized endpoints for this agent."""
        router = APIRouter()

        @router.post("/audit")
        async def audit_contract(contract_code: str):
            """Audit a smart contract for security vulnerabilities."""
            return await self.specialized_capability(contract_code=contract_code)

        @router.post("/gas-optimization")
        async def gas_optimization(contract_code: str):
            """Analyze a smart contract for gas optimization opportunities."""
            return await self.optimize_gas(contract_code)

        @router.post("/compliance")
        async def check_compliance(contract_code: str, standard: str = "ERC20"):
            """Check compliance with a standard (ERC20, ERC721, etc.)."""
            return await self.check_compliance(contract_code, standard)

        # Add the router to the app
        self.app.include_router(router, prefix="/api/audit")

    async def specialized_capability(self, **kwargs) -> Any:
        """Audit a smart contract for security vulnerabilities."""
        contract_code = kwargs.get("contract_code", "")

        if not contract_code:
            raise HTTPException(status_code=400, detail="No contract code provided")

        # Initial static analysis
        static_analysis = self._perform_static_analysis(contract_code)

        # Deep audit with LLM
        deep_audit = await self._perform_deep_audit(contract_code, static_analysis)

        # Generate final report
        audit_report = {
            "summary": deep_audit.get("summary", ""),
            "risk_level": deep_audit.get("risk_level", "Unknown"),
            "vulnerabilities": deep_audit.get("vulnerabilities", []),
            "recommendations": deep_audit.get("recommendations", []),
            "gas_optimizations": deep_audit.get("gas_optimizations", []),
            "code_quality": deep_audit.get("code_quality", []),
            "static_analysis": static_analysis
        }

        # Store the audit report in memory
        contract_name = self._extract_contract_name(contract_code) or "Unknown"
        await self.memory.store_knowledge(
            self.id, f"audit_report_{contract_name}", audit_report
        )

        return audit_report

    async def optimize_gas(self, contract_code: str) -> Dict[str, Any]:
        """Analyze a smart contract for gas optimization opportunities."""
        if not contract_code:
            raise HTTPException(status_code=400, detail="No contract code provided")

        # Extract contract name
        contract_name = self._extract_contract_name(contract_code) or "Unknown"

        # Gas optimization prompt
        optimization_prompt = (
            "Analyze the following Solidity smart contract code for gas optimization opportunities:\n\n"
            f"```solidity\n{contract_code}\n```\n\n"
            "Focus on the following aspects:\n"
            "1. Storage optimization (packing variables, using appropriate data types)\n"
            "2. Function optimization (view/pure modifiers, visibility, loops)\n"
            "3. Memory management (memory vs storage usage)\n"
            "4. Expensive operations (repeated calculations, avoidable storage reads/writes)\n"
            "5. Using newer Solidity features for gas savings\n\n"
            "Provide a detailed report of optimization opportunities with code examples for improvement. "
            "For each issue, explain the gas impact and prioritize based on potential savings."
        )

        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": optimization_prompt}
        ]

        # Get optimization analysis from LLM
        optimization_analysis = await self.llm.generate_completion(
            messages=messages,
            model=self.config.model,
            temperature=0.2
        )

        # Parse the optimization analysis (simplified for demo)
        # In a real implementation, you'd want to parse this more robustly
        optimization_report = {
            "contract_name": contract_name,
            "analysis": optimization_analysis,
            "overview": "Gas optimization report overview"
        }

        return optimization_report

    async def check_compliance(self, contract_code: str, standard: str) -> Dict[str, Any]:
        """Check compliance with a standard (ERC20, ERC721, etc.)."""
        if not contract_code:
            raise HTTPException(status_code=400, detail="No contract code provided")

        # Extract contract name
        contract_name = self._extract_contract_name(contract_code) or "Unknown"

        # Define standard interfaces
        interfaces = {
            "ERC20": [
                "function totalSupply() external view returns (uint256)",
                "function balanceOf(address account) external view returns (uint256)",
                "function transfer(address recipient, uint256 amount) external returns (bool)",
                "function allowance(address owner, address spender) external view returns (uint256)",
                "function approve(address spender, uint256 amount) external returns (bool)",
                "function transferFrom(address sender, address recipient, uint256 amount) external returns (bool)",
                "event Transfer(address indexed from, address indexed to, uint256 value)",
                "event Approval(address indexed owner, address indexed spender, uint256 value)"
            ],
            "ERC721": [
                "function balanceOf(address owner) external view returns (uint256 balance)",
                "function ownerOf(uint256 tokenId) external view returns (address owner)",
                "function safeTransferFrom(address from, address to, uint256 tokenId) external",
                "function transferFrom(address from, address to, uint256 tokenId) external",
                "function approve(address to, uint256 tokenId) external",
                "function getApproved(uint256 tokenId) external view returns (address operator)",
                "function setApprovalForAll(address operator, bool _approved) external",
                "function isApprovedForAll(address owner, address operator) external view returns (bool)",
                "event Transfer(address indexed from, address indexed to, uint256 indexed tokenId)",
                "event Approval(address indexed owner, address indexed approved, uint256 indexed tokenId)",
                "event ApprovalForAll(address indexed owner, address indexed operator, bool approved)"
            ],
            "ERC1155": [
                "function balanceOf(address account, uint256 id) external view returns (uint256)",
                "function balanceOfBatch(address[] calldata accounts, uint256[] calldata ids) external view returns (uint256[] memory)",
                "function setApprovalForAll(address operator, bool approved) external",
                "function isApprovedForAll(address account, address operator) external view returns (bool)",
                "function safeTransferFrom(address from, address to, uint256 id, uint256 amount, bytes calldata data) external",
                "function safeBatchTransferFrom(address from, address to, uint256[] calldata ids, uint256[] calldata amounts, bytes calldata data) external",
                "event TransferSingle(address indexed operator, address indexed from, address indexed to, uint256 id, uint256 value)",
                "event TransferBatch(address indexed operator, address indexed from, address indexed to, uint256[] ids, uint256[] values)",
                "event ApprovalForAll(address indexed account, address indexed operator, bool approved)",
                "event URI(string value, uint256 indexed id)"
            ]
        }

        if standard not in interfaces:
            raise HTTPException(status_code=400, detail=f"Unknown standard: {standard}")

        # Compliance check prompt
        compliance_prompt = (
            f"Check if the following Solidity contract is compliant with the {standard} standard.\n\n"
            f"```solidity\n{contract_code}\n```\n\n"
            f"The {standard} standard requires the following interfaces:\n"
            f"{json.dumps(interfaces[standard], indent=2)}\n\n"
            "Analyze the contract and report:\n"
            "1. Is the contract fully compliant with the standard?\n"
            "2. Which required functions or events are missing or incorrectly implemented?\n"
            "3. Are there any deviations from the standard that could cause interoperability issues?\n"
            "4. What would be required to make this contract fully compliant?\n\n"
            "Provide a detailed compliance analysis."
        )

        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": compliance_prompt}
        ]

        # Get compliance analysis from LLM
        compliance_analysis = await self.llm.generate_completion(
            messages=messages,
            model=self.config.model,
            temperature=0.2
        )

        return {
            "contract_name": contract_name,
            "standard": standard,
            "analysis": compliance_analysis
        }

    def _perform_static_analysis(self, contract_code: str) -> Dict[str, Any]:
        """Perform initial static analysis on the contract code."""
        results = {
            "patterns_found": {},
            "complexity": self._calculate_complexity(contract_code),
            "loc": len(contract_code.split('\n')),
            "potential_issues": []
        }

        # Check for vulnerability patterns
        for vuln_name, pattern in self.vulnerability_patterns.items():
            matches = re.findall(pattern, contract_code)
            if matches:
                results["patterns_found"][vuln_name] = len(matches)
                results["potential_issues"].append({
                    "type": vuln_name,
                    "severity": self._get_vulnerability_severity(vuln_name),
                    "matches": len(matches)
                })

        # Check for other code quality indicators
        if "// SPDX-License-Identifier:" not in contract_code:
            results["potential_issues"].append({
                "type": "missing_license",
                "severity": "Low",
                "description": "Missing SPDX license identifier"
            })

        if not re.search(r"pragma solidity \^?[0-9]+\.[0-9]+\.[0-9]+", contract_code):
            results["potential_issues"].append({
                "type": "missing_pragma",
                "severity": "Medium",
                "description": "Missing or incomplete pragma directive"
            })

        # Check for unused variables
        variable_declarations = re.findall(r"(uint|int|bool|address|bytes|string)(\d*\s+)(private|public|internal)?\s+(\w+)", contract_code)
        for match in variable_declarations:
            var_name = match[3]
            var_occurrences = re.findall(r"\b" + var_name + r"\b", contract_code)
            if len(var_occurrences) <= 1:  # Only appears in declaration
                results["potential_issues"].append({
                    "type": "unused_variable",
                    "severity": "Low",
                    "description": f"Potentially unused variable: {var_name}"
                })

        return results

    async def _perform_deep_audit(self, contract_code: str, static_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Perform deep audit using LLM."""
        # Create an audit prompt based on static analysis results
        issues_summary = "\n".join([
            f"- {issue['type']} (Severity: {issue['severity']})"
            for issue in static_analysis["potential_issues"]
        ])

        audit_prompt = (
            "Perform a comprehensive security audit on the following Solidity smart contract:\n\n"
            f"```solidity\n{contract_code}\n```\n\n"
            "Initial static analysis has identified the following potential issues:\n"
            f"{issues_summary}\n\n"
            "Please analyze the contract for:\n"
            "1. Security vulnerabilities (reentrancy, integer overflow/underflow, access control issues, etc.)\n"
            "2. Gas optimization opportunities\n"
            "3. Code quality and best practices\n"
            "4. Logical errors and business logic flaws\n\n"
            "Respond with ONLY a JSON object (no prose, no markdown fences) of the form:\n"
            "{\n"
            '  "risk_level": "Critical|High|Medium|Low|Informational",\n'
            '  "summary": "one-paragraph overall assessment",\n'
            '  "vulnerabilities": [\n'
            '    {"title": "...", "severity": "Critical|High|Medium|Low|Informational",\n'
            '     "location": "...", "description": "...", "recommendation": "..."}\n'
            "  ],\n"
            '  "recommendations": ["..."],\n'
            '  "gas_optimizations": ["..."]\n'
            "}\n"
            "If there are no vulnerabilities, return an empty list for that field."
        )

        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": audit_prompt}
        ]

        # Get audit result from LLM
        audit_result = await self.llm.generate_completion(
            messages=messages,
            model=self.config.model,
            temperature=0.2
        )

        # Preferred path: parse structured JSON (robust across LLM providers).
        structured = self._parse_audit_json(audit_result)
        if structured is not None:
            return structured

        # Fallback: legacy regex parse of free-text audit output.
        # In a real implementation, you'd want to parse this more robustly
        vulnerabilities = []
        recommendations = []
        gas_optimizations = []
        code_quality = []
        summary = ""
        risk_level = "Unknown"

        # Extract summary (first paragraph)
        summary_match = re.search(r"^(.+?)(?=\n\n|\n#|\n\*)", audit_result, re.DOTALL)
        if summary_match:
            summary = summary_match.group(1).strip()

        # Extract risk level
        risk_match = re.search(r"risk\s+(level|assessment|rating)?\s*:?\s*(critical|high|medium|low|informational)",
                               audit_result, re.IGNORECASE)
        if risk_match:
            risk_level = risk_match.group(2).capitalize()

        # Extract vulnerabilities (simplified)
        vuln_sections = re.findall(r"(?:## |### |\*\*|\d+\. )(.*?vulnerability.*?)(?=\n## |\n### |\n\*\*|\n\d+\. |\Z)",
                                   audit_result, re.IGNORECASE | re.DOTALL)
        for section in vuln_sections:
            lines = section.split('\n')
            title = lines[0].strip().replace('*', '').replace('#', '')
            description = '\n'.join(lines[1:]).strip()

            severity_match = re.search(r"severity\s*:?\s*(critical|high|medium|low|informational)",
                                       description, re.IGNORECASE)
            severity = severity_match.group(1).capitalize() if severity_match else "Unknown"

            vulnerabilities.append({
                "title": title,
                "description": description,
                "severity": severity
            })

        # Extract recommendations (simplified)
        rec_sections = re.findall(r"(?:## |### |\*\*|\d+\. )(.*?recommend.*?)(?=\n## |\n### |\n\*\*|\n\d+\. |\Z)",
                                  audit_result, re.IGNORECASE | re.DOTALL)
        for section in rec_sections:
            lines = section.split('\n')
            title = lines[0].strip().replace('*', '').replace('#', '')
            description = '\n'.join(lines[1:]).strip()

            recommendations.append({
                "title": title,
                "description": description
            })

        # Build the final report
        deep_audit = {
            "summary": summary,
            "risk_level": risk_level,
            "vulnerabilities": vulnerabilities,
            "recommendations": recommendations,
            "gas_optimizations": gas_optimizations,
            "code_quality": code_quality
        }

        return deep_audit

    @staticmethod
    def _parse_audit_json(audit_result: str):
        """Parse a structured-JSON audit response.

        Returns a normalized deep-audit dict, or None if the response is not
        parseable JSON (so the caller can fall back to regex parsing).
        """
        if not audit_result:
            return None
        text = audit_result.strip()
        # Strip a surrounding markdown fence if present.
        if text.startswith("```"):
            lines = text.split("\n")[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        # Isolate the outermost JSON object.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except (ValueError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None

        valid = {"Critical", "High", "Medium", "Low", "Informational"}
        risk = str(data.get("risk_level", "Unknown")).capitalize()
        if risk not in valid:
            risk = "Unknown"

        vulns = []
        for v in data.get("vulnerabilities", []) or []:
            if isinstance(v, dict):
                sev = str(v.get("severity", "Unknown")).capitalize()
                vulns.append({
                    "title": v.get("title", "Untitled"),
                    "description": v.get("description", ""),
                    "severity": sev if sev in valid else "Unknown",
                    "location": v.get("location", ""),
                    "recommendation": v.get("recommendation", ""),
                })
            elif isinstance(v, str):
                vulns.append({"title": v, "description": "", "severity": "Unknown"})

        recs = data.get("recommendations", []) or []
        recommendations = [
            {"title": r, "description": ""} if isinstance(r, str) else r for r in recs
        ]

        return {
            "summary": data.get("summary", ""),
            "risk_level": risk,
            "vulnerabilities": vulns,
            "recommendations": recommendations,
            "gas_optimizations": data.get("gas_optimizations", []) or [],
            "code_quality": [],
        }

    def _extract_contract_name(self, contract_code: str) -> Optional[str]:
        """Extract the contract name from the code."""
        contract_match = re.search(r"contract\s+(\w+)", contract_code)
        if contract_match:
            return contract_match.group(1)
        return None

    def _calculate_complexity(self, contract_code: str) -> Dict[str, Any]:
        """Calculate code complexity metrics."""
        complexity = {
            "cyclomatic_complexity": 0,
            "nesting_depth": 0,
            "function_count": 0
        }

        # Count control flow statements as a simple cyclomatic complexity measure
        control_flow = re.findall(r"\b(if|for|while|do|case)\b", contract_code)
        complexity["cyclomatic_complexity"] = len(control_flow) + 1  # Base complexity + branches

        # Count functions
        functions = re.findall(r"function\s+\w+", contract_code)
        complexity["function_count"] = len(functions)

        # Calculate maximum nesting depth (simplified)
        lines = contract_code.split('\n')
        current_depth = 0
        max_depth = 0
        for line in lines:
            opening = line.count('{')
            closing = line.count('}')
            current_depth += opening - closing
            max_depth = max(max_depth, current_depth)
        complexity["nesting_depth"] = max_depth

        return complexity

    def _get_vulnerability_severity(self, vulnerability_type: str) -> str:
        """Get the severity level for a vulnerability type."""
        severity_map = {
            "reentrancy": "High",
            "integer_overflow": "Medium",
            "unchecked_return": "Medium",
            "tx_origin": "High",
            "delegatecall": "High",
            "assembly": "Medium",
            "selfdestruct": "High",
            "timestamp_dependence": "Low",
            "weak_randomness": "Medium",
            "unsafe_math": "Medium"
        }
        return severity_map.get(vulnerability_type, "Unknown")
