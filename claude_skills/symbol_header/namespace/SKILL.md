---
name: autofix-namespace
description: Fixes 'not a member of namespace' errors by adding namespace qualifiers or using declarations.
---

# Namespace Skill

Fixes C++ namespace-related compilation errors.

## Detection Patterns
- `'X' is not a member of 'std'`
- `'X' is not a member of 'namespace'`
- `'X' was not declared in this scope` (when namespace issue)

## Strategy

1. **Identify Symbol**: Extract the symbol and expected namespace.
2. **Add Qualifier**: Prefix the symbol with namespace, or add `using`.

## Instructions

### Step 1: Parse Error
From: `'cout' is not a member of 'std'`
Symbol: `cout`, Namespace: `std`

### Step 2: Common Fixes

**Add namespace prefix:**
```cpp
// Before
cout << "Hello";  // ERROR
// After
std::cout << "Hello";
```

**Add using declaration:**
```cpp
// At top of file or function
using std::cout;
// Or
using namespace std;  // Less recommended
```

### Common std:: Symbols
| Symbol | Namespace |
|--------|-----------|
| `cout`, `cin`, `endl` | `std::` |
| `vector`, `map`, `set` | `std::` |
| `string` | `std::` |
| `unique_ptr`, `shared_ptr` | `std::` |
| `chrono::*` | `std::chrono::` |
