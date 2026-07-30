# VibeDApps

A multi-agent DApp generator. You give it a project spec (contract type,
features, stack choices) and it produces a working project: a Solidity
contract, a backend API, a frontend, a Hardhat test suite, a security
audit report, and the config to tie it all together.

The code started life as a research prototype for multi-agent code
generation. This repo keeps just the generation pipeline and packages it
as a normal Python tool. Everything runs in-process, so there is no
server, database, or Redis to set up.

## How it works

Six agents run in sequence over a shared context, so later stages can
see what earlier stages produced. The backend and frontend agents, for
example, get the actual contract ABI.

1. **SmartContractAgent** writes the Solidity (ERC20/721/1155, DAO,
   DeFi, marketplace, or custom). It picks one of three strategies:
   - `tool_based`: scaffold from OpenZeppelin templates, compile with
     Hardhat, return the real ABI and bytecode. Needs Node.js.
   - `hybrid`: tool scaffolding plus LLM customization.
   - `llm_only`: plain LLM generation. This is the fallback when no
     tools are installed.
2. **SmartContractAuditAgent** reviews the contract for security issues.
3. **BackendAgent** builds an API server from templates (Express,
   Hardhat, Truffle, Flask, FastAPI, Django, or a minimal server).
4. **FrontendAgent** builds the UI (React, Vue, Next.js, or plain HTML)
   wired to the contract ABI.
5. **TestGeneratorAgent** writes a Hardhat test suite.
6. **IntegrationAgent** produces config, deploy scripts, and the project
   README.

There are also eight review agents (security, code quality, performance,
error handling, test coverage, documentation, architecture, API
contracts) behind the `vibedapps review` command.

## Install

Needs Python 3.9 or newer.

```bash
pip install -e ".[cli]"
```

If you want tool-based contract generation (compiled contracts with real
ABIs), install Node.js and Hardhat 2.x as well:

```bash
npm install -g hardhat@^2.26.0
```

## Pick an LLM backend

Two options, interchangeable:

- **OpenAI API** (the default): `export OPENAI_API_KEY=sk-...`
- **Claude CLI** (`--llm claude-cli`): shells out to your local `claude`
  command, so it uses your existing CLI login instead of an API key.
  Slower per call, but there's no per-token bill.

## Usage

```bash
# Interactive wizard
vibedapps create --interactive

# From a spec file
vibedapps create --config examples/erc20.json --output ./my_dapp

# Same, but through the local claude CLI
vibedapps create --config examples/erc20.json --llm claude-cli

# Manage generated projects (stored under ~/.vibedapps/projects)
vibedapps list
vibedapps show <project_id>
vibedapps export <project_id> --output ./my_dapp

# Point the review agents at any codebase
vibedapps review ./my_dapp --agent security --severity high
```

### Spec file format

```json
{
  "projectName": "MyToken",
  "projectDescription": "An ERC20 token with minting and burning",
  "contractType": "erc20",
  "contractFeatures": {"mintable": true, "burnable": true},
  "backendType": "express",
  "backendLanguage": "javascript",
  "frontendFramework": "react",
  "uiComponents": {"darkMode": true, "wallets": ["MetaMask"]},
  "securityChecks": {"enabled": true},
  "deploymentOptions": {"network": "ethereum-sepolia"},
  "generationStrategy": null
}
```

`generationStrategy` can be `null` (auto), `"llm_only"`, `"tool_based"`,
or `"hybrid"`.

### Using it as a library

```python
import asyncio
from pathlib import Path
from vibedapps import DAppGenerator, ProjectSpec

async def main():
    generator = DAppGenerator()          # or DAppGenerator(llm_service=ClaudeCLIService())
    await generator.detect_tools()       # optional, enables tool-based generation
    result = await generator.generate(ProjectSpec(
        projectName="MyToken",
        projectDescription="An ERC20 token",
        contractType="erc20",
        contractFeatures={"mintable": True},
    ))
    generator.package(result, Path("./my_dapp"))

asyncio.run(main())
```

## What you get

```
my_dapp/
├── contracts/         Solidity contract
├── backend/           API server, ABI already wired in
├── frontend/          UI, ABI already wired in
├── test/              Hardhat test suite
├── audit/             security_report.md
├── hardhat.config.js  so `npx hardhat test` works out of the box
├── package.json
└── README.md
```

To run the generated tests:

```bash
cd my_dapp
npm install --save-dev "hardhat@^2.26.0" "@nomicfoundation/hardhat-toolbox@^5.0.0" "@openzeppelin/contracts@^5.0.0"
npx hardhat test
```

The tests deploy the contract with its actual constructor arguments,
taken from the compiled ABI, or parsed out of the Solidity source when
running in LLM-only mode.

## Notes on tool-based generation

At startup the generator checks which dev tools are installed
(`npx hardhat --version`, `forge --version`) and picks a strategy per
contract type. With Hardhat available, standard contracts (ERC20, ERC721,
ERC1155) are built from OpenZeppelin v5 templates and compiled in a
temporary project; Hardhat 2.x and `@openzeppelin/contracts@5` get
installed there automatically. The compiled ABI and bytecode flow into
the backend and frontend. Without Node.js, generation still works but
falls back to LLM-only mode, and the ABI is a placeholder until you
compile the contract yourself.

One version caveat: Hardhat has to be 2.x. The generated
`hardhat.config.js` is CommonJS, which Hardhat 3 refuses to load.
