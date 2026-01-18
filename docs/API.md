# AutoFix-Skill API Documentation

## Overview

This document describes the internal API for developing skills and extending AutoFix-Skill.

## Architecture

The system is composed of:
1.  **CLI**: Entry point.
2.  **Orchestrator**: Manages the pipeline (Environment -> Diagnostic -> Skill -> Plan -> Execution).
3.  **Skill Registry**: Loads and routes errors to skills.
4.  **Skills**: Implementation logic categorized by error domain.
5.  **Build Adapters**: Interface to underlying build systems.

## Core Classes

### `DiagnosticObject`

Represents a single build error.

```python
@dataclass
class DiagnosticObject:
    uid: str                      # Unique identifier
    build_system: str             # 'gn', 'soong', 'cmake', 'kbuild', 'makefile'
    error_code: str               # Error type identifier
    location: Dict[str, Any]      # {'file': str, 'line': int}
    symbol: str                   # Affected symbol name
    raw_log: str                  # Original error message
```

### `BaseSkill`

Abstract base class for all skills.

```python
class BaseSkill(ABC):
    error_codes: List[str] = []  # Error patterns handled
    
    @abstractmethod
    def detect(self, diagnostic: DiagnosticObject) -> bool:
        pass
    
    @abstractmethod
    def analyze(self, diagnostic, context) -> Dict:
        pass
    
    @abstractmethod
    def execute(self, diagnostic, analysis_result) -> ExecutionPlan:
        pass
```

## Creating a New Skill

### 1. Choose a Category
Decide where your skill belongs:
- `src/skills/symbol_header/`
- `src/skills/linkage_dependency/`
- `src/skills/api_type/`
- `src/skills/build_config/`

### 2. Implementation

```python
# src/skills/category/my_skill.py

from src.skill_registry.manager import BaseSkill, register_skill, DiagnosticObject, ExecutionPlan

@register_skill
class MySkill(BaseSkill):
    error_codes = ['my error']

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        return 'my error' in diagnostic.raw_log

    def analyze(self, diagnostic, context):
        return {'info': 'data'}

    def execute(self, diagnostic, analysis_result):
        plan = ExecutionPlan()
        # Add steps...
        return plan
```

### 3. Registration
Add the import to `src/skills/__init__.py`.

```python
# src/skills/__init__.py
from src.skills.category.my_skill import MySkill
```

### 4. Testing
Create a test file in `tests/test_cat_category.py` (or add to existing).

```python
def test_my_skill():
    skill = MySkill()
    # ... assert detect() ...
```

## Build Adapters

Locally implemented adapters reside in `src/build_adapters/`.

### Supported Adapters
- `SoongAdapter`: Parses `Android.bp` (using Blueprint syntax).
- `GNAdapter`: Parses `BUILD.gn`.
- `CMakeAdapter`: Parses `CMakeLists.txt` (regex based).
- `KbuildAdapter`: Parses `Makefile` / `Kbuild` for kernels.
- `MakefileAdapter`: Generic Makefile support.

### `IBuildAdapter` Interface

```python
class IBuildAdapter(ABC):
    def find_build_file(self, source_file: Path) -> Path: ...
    def get_module_info(self, file_path: Path) -> ModuleInfo: ...
    def inject_dependency(self, target, dep, type) -> bool: ...
    def modify_include_path(self, target, path, action) -> bool: ...
```
