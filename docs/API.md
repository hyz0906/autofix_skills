# AutoFix-Skill API Documentation

## Overview

This document describes the internal API for developing skills and extending AutoFix-Skill.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                           │
│                        (cli.py)                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Orchestrator                           │
│                   (orchestrator/base.py)                    │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Environment │  │  Pipeline   │  │    Git Rollback     │  │
│  │  Detection  │  │  Execution  │  │     Mechanism       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Skill Registry                           │
│                (skill_registry/manager.py)                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   SkillManager                      │    │
│  │  - register(skill_class)                            │    │
│  │  - get_skills_for_error(error_code)                 │    │
│  │  - get_all_skills()                                 │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│ MissingHeader   │ │ SymbolDep   │ │ SignatureMismatch│
│    Skill        │ │   Skill     │ │      Skill       │
└────────┬────────┘ └──────┬──────┘ └────────┬────────┘
         │                 │                  │
         └────────────────┬┴──────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│  Context Engine │ │ GN Adapter  │ │  Soong Adapter  │
│  (ast-grep)     │ │             │ │                 │
└─────────────────┘ └─────────────┘ └─────────────────┘
```

## Core Classes

### DiagnosticObject

Represents a single build error.

```python
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class DiagnosticObject:
    uid: str                      # Unique identifier
    build_system: str             # 'gn' or 'soong'
    error_code: str               # Error type identifier
    location: Dict[str, Any]      # {'file': str, 'line': int, 'column': int}
    symbol: str                   # Affected symbol name (if applicable)
    raw_log: str                  # Original error message
    metadata: Optional[Dict] = None
```

### ExecutionPlan

Describes actions to fix an error.

```python
@dataclass
class ExecutionPlan:
    version: str = "1.0"
    steps: List[Dict[str, Any]] = field(default_factory=list)
    
# Example step:
{
    'action': 'ADD_DEPENDENCY',
    'params': {
        'target': 'my_target',
        'dependency': '//path/to:library',
        'type': 'shared_library'
    }
}
```

### BaseSkill

Abstract base class for all skills.

```python
from abc import ABC, abstractmethod

class BaseSkill(ABC):
    error_codes: List[str] = []  # Error patterns this skill handles
    
    @abstractmethod
    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this skill can handle the diagnostic."""
        pass
    
    @abstractmethod
    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the error and gather information for fixing."""
        pass
    
    @abstractmethod
    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate the fix plan."""
        pass
    
    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Optional: Verify preconditions before execution."""
        return True
    
    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Optional: Verify the fix was successful."""
        return SkillResult.SUCCESS
```

## Creating a New Skill

### Step 1: Create the Skill Class

```python
# src/skills/my_new_skill.py

from src.skill_registry.manager import (
    BaseSkill,
    DiagnosticObject,
    ExecutionPlan,
    SkillResult,
    register_skill,
)

@register_skill  # Auto-registers with SkillManager
class MyNewSkill(BaseSkill):
    error_codes = ['my_error_pattern']
    
    def __init__(self, name: str = "MyNewSkill"):
        super().__init__(name)
    
    def detect(self, diagnostic: DiagnosticObject) -> bool:
        return 'my_error_pattern' in diagnostic.raw_log.lower()
    
    def analyze(self, diagnostic, context):
        # Gather information needed to fix
        return {'key': 'value'}
    
    def execute(self, diagnostic, analysis_result):
        plan = ExecutionPlan()
        plan.steps.append({
            'action': 'MY_ACTION',
            'params': analysis_result
        })
        return plan
```

### Step 2: Import in CLI (for registration)

```python
# In src/cli.py, add:
from src.skills import my_new_skill  # noqa: F401
```

### Step 3: Add Tests

```python
# tests/test_my_new_skill.py

def test_detect_my_error():
    skill = MyNewSkill()
    diag = DiagnosticObject(
        uid='test',
        build_system='gn',
        error_code='my_error_pattern',
        location={'file': 'test.cpp', 'line': 1},
        symbol='',
        raw_log="my_error_pattern: something went wrong"
    )
    assert skill.detect(diag) is True
```

## Build Adapters

### IBuildAdapter

Abstract interface for build system adapters.

```python
class IBuildAdapter(ABC):
    @abstractmethod
    def find_build_file(self, source_file: Path) -> Optional[Path]:
        """Find the build file for a source file."""
        pass
    
    @abstractmethod
    def get_module_info(self, file_path: Path) -> Optional[ModuleInfo]:
        """Get module information from a build file."""
        pass
    
    @abstractmethod
    def inject_dependency(
        self,
        target_module: str,
        dep_name: str,
        dep_type: str = 'shared_library'
    ) -> bool:
        """Add a dependency to a module."""
        pass
    
    @abstractmethod
    def modify_include_path(
        self,
        target_module: str,
        path: str,
        action: str = 'add'
    ) -> bool:
        """Add or remove an include path."""
        pass
```

### ModuleInfo

```python
@dataclass
class ModuleInfo:
    name: str
    path: Path
    module_type: str
    dependencies: List[str] = field(default_factory=list)
    include_dirs: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
```

## Context Engine

### AstGrepClient

Wrapper for semantic code search.

```python
class AstGrepClient:
    def search_pattern(
        self,
        pattern: str,
        language: str = 'cpp',
        directory: Optional[Path] = None
    ) -> List[SearchMatch]:
        """Search for a code pattern."""
        pass
    
    def search_function_definition(
        self,
        function_name: str,
        language: str = 'cpp',
        directory: Optional[Path] = None
    ) -> List[SearchMatch]:
        """Find function definitions."""
        pass
    
    def search_header_file(
        self,
        header_name: str,
        directory: Optional[Path] = None
    ) -> List[Path]:
        """Find header files by name."""
        pass
```

## Logging

Use the centralized logger:

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message")
```

## Testing

Run all tests:
```bash
PYTHONPATH=. python3 -m pytest tests/ -v
```

Run specific test file:
```bash
PYTHONPATH=. python3 -m pytest tests/test_my_skill.py -v
```

Run with coverage:
```bash
PYTHONPATH=. python3 -m pytest tests/ --cov=src --cov-report=html
```
