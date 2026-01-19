# AutoFix Native Skills - User Guide

## Overview

The AutoFix Native Skills are a collection of Claude Code skills designed to help you automatically diagnose and fix build errors in C++, Java, Rust, and Android/OpenHarmony projects — without running any external Python scripts.

## Quick Start

### Step 1: Start with the Router
When you encounter a build error, invoke the **Router Skill**:
```
Use autofix-router to analyze this error: [paste error message]
```

The Router will identify the error type and recommend the specific skill to use.

### Step 2: Apply the Recommended Skill
Follow the Router's recommendation and invoke the specific skill:
```
Use autofix-missing-header to fix this error.
```

Each skill contains step-by-step instructions that the Agent will follow to resolve the issue.

---

## Available Skills

### Router (Entry Point)
| Skill | Path | Description |
|-------|------|-------------|
| **autofix-router** | `router/` | Analyzes errors and routes to the correct skill |

### Symbol & Header Category
| Skill | Path | Error Patterns |
|-------|------|----------------|
| **missing-header** | `symbol_header/` | `fatal error: 'X.h' file not found` |
| **undeclared-identifier** | `symbol_header/` | `use of undeclared identifier 'X'` |
| **java-import** | `symbol_header/` | `cannot find symbol` (Java) |
| **namespace** | `symbol_header/` | `'X' is not a member of 'std'` |

### Linkage & Dependency Category
| Skill | Path | Error Patterns |
|-------|------|----------------|
| **symbol-dep** | `linkage_dependency/` | `undefined reference to 'X'` |
| **visibility** | `linkage_dependency/` | Soong visibility restrictions |
| **rust-dep** | `linkage_dependency/` | `can't find crate 'X'` |
| **multiple-def** | `linkage_dependency/` | `multiple definition of 'X'` |

### API & Type Category
| Skill | Path | Error Patterns |
|-------|------|----------------|
| **signature-mismatch** | `api_type/` | `no matching function for call` |
| **type-conversion** | `api_type/` | `cannot convert 'X' to 'Y'` |

### Build Configuration Category
| Skill | Path | Error Patterns |
|-------|------|----------------|
| **flag-cleaner** | `build_config/` | `unknown argument: '-fX'` |
| **permission** | `build_config/` | `Permission denied` |
| **blueprint-syntax** | `build_config/` | Android.bp parse errors |
| **gn-scope** | `build_config/` | BUILD.gn undefined identifier |

---

## Example Workflows

### Example 1: Missing Header
**Error:**
```
src/main.cpp:5:10: fatal error: 'utils/config.h' file not found
```

**Workflow:**
1. Router identifies: `missing-header` skill
2. Skill instructs:
   - Search project for `config.h`
   - Found at `src/common/utils/config.h`
   - Fix: Update `#include "utils/config.h"` to `#include "common/utils/config.h"`

### Example 2: Linker Error
**Error:**
```
ld.lld: error: undefined reference to 'MyClass::initialize()'
```

**Workflow:**
1. Router identifies: `symbol-dep` skill
2. Skill instructs:
   - Search for `MyClass::initialize` definition
   - Found in `libmyclass`
   - Fix: Add `shared_libs: ["libmyclass"]` to Android.bp

---

## Installation in Claude Code

Copy the `claude_skills/` directory to your Claude Code skills location:
```bash
cp -r claude_skills/* ~/.claude/skills/
```

Or symlink:
```bash
ln -s $(pwd)/claude_skills/* ~/.claude/skills/
```
