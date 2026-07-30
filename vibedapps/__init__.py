"""
VibeDApps: a multi-agent DApp generator.

Takes a project spec and generates the whole application: smart contract,
backend API, frontend, tests, and the integration glue between them.
"""

__version__ = "0.1.0"

from vibedapps.pipeline import DAppGenerator, ProjectSpec

__all__ = ["DAppGenerator", "ProjectSpec", "__version__"]
