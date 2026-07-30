"""
Heterogeneous Code Generation Module

This module provides diverse code generation sources to reduce vulnerability homogeneity
by mixing LLM-generated code with verified templates and symbolic invariants.
"""

from .hybrid_generator import GenerationStrategy, HeterogeneousGenerator
from .pattern_composer import ComposedContract, PatternComposer
from .symbolic_generator import Invariant, SymbolicGenerator
from .template_library import Pattern, TemplateLibrary

__all__ = [
    'TemplateLibrary',
    'Pattern',
    'SymbolicGenerator',
    'Invariant',
    'PatternComposer',
    'ComposedContract',
    'HeterogeneousGenerator',
    'GenerationStrategy'
]
