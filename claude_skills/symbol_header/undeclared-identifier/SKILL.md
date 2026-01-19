---
name: autofix-undeclared-identifier
description: Fixes 'undeclared identifier' errors by adding missing #include or namespace qualifiers.
---

# Undeclared Identifier Skill

Fixes errors where a symbol is used but not declared in the current scope.

## Detection Patterns
- `use of undeclared identifier 'X'`
- `'X' was not declared in this scope`
- `error: 'X' undeclared`

## Strategy

1. **Extract Identifier**: Get the undeclared symbol name.
2. **Classify Symbol**: Is it a standard library symbol, project symbol, or macro?
3. **Find Definition**: Search the codebase for where this symbol is defined.
4. **Add Include/Import**: Add the necessary #include or using statement.

## Instructions

### Step 1: Identify the Symbol
Parse the error message to extract the undeclared identifier.

### Step 2: Check Standard Library
Common C++ standard library symbols:

| Symbol | Header | Namespace |
|--------|--------|-----------|
| `vector` | `<vector>` | `std::` |
| `string` | `<string>` | `std::` |
| `cout`, `cin`, `endl` | `<iostream>` | `std::` |
| `map`, `unordered_map` | `<map>`, `<unordered_map>` | `std::` |
| `unique_ptr`, `shared_ptr` | `<memory>` | `std::` |
| `thread`, `mutex` | `<thread>`, `<mutex>` | `std::` |
| `LOG`, `ALOG*` | `<android/log.h>` | - |

### Step 3: Search Project for Definition
If not a standard symbol, search the codebase:
```
grep -r "class X" --include="*.h"
grep -r "struct X" --include="*.h"
grep -r "#define X" --include="*.h"
```

### Step 4: Apply Fix
Add the appropriate #include at the top of the file:
```cpp
#include <vector>  // For std::vector
#include "project/MyClass.h"  // For project symbols
```

Or add namespace qualifier:
```cpp
std::vector<int> items;  // Instead of: vector<int> items;
```
