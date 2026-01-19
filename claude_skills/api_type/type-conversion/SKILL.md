---
name: autofix-type-conversion
description: Fixes type mismatch errors by adding appropriate casts or conversions.
---

# Type Conversion Skill

Fixes compilation errors related to incompatible type assignments or conversions.

## Detection Patterns
- `cannot convert 'X' to 'Y'`
- `invalid conversion from 'X' to 'Y'`
- `no viable conversion`
- `incompatible types`

## Strategy

1. **Identify Types**: Extract source and target types from error.
2. **Determine Conversion**: Choose appropriate cast or method.
3. **Apply Fix**: Add cast or conversion call.

## Instructions

### Step 1: Parse the Error
Extract:
- Source type (what you have)
- Target type (what is expected)
- Location of the conversion

### Step 2: Common Conversions

| From | To | Fix |
|------|-----|-----|
| `std::string` | `const char*` | `.c_str()` |
| `const char*` | `std::string` | Constructor or assignment |
| `int` | `enum` | `static_cast<EnumType>(val)` |
| `void*` | `T*` | `static_cast<T*>(ptr)` |
| `Base*` | `Derived*` | `dynamic_cast<Derived*>(base)` |
| `int64_t` | `int` | `static_cast<int>(val)` (with care) |

### Step 3: Apply Fix

**Example: string to const char***
```cpp
// Before (error)
void log(const char* msg);
std::string message = "Hello";
log(message);  // ERROR

// After
log(message.c_str());
```

**Example: enum cast**
```cpp
// Before
int value = 5;
MyEnum e = value;  // ERROR

// After
MyEnum e = static_cast<MyEnum>(value);
```

### Step 4: Verify
Ensure semantic correctness, not just compilation success.
