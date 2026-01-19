---
name: autofix-symbol-dep
description: Fixes linker 'undefined reference' errors by finding and adding the library dependency.
---

# Symbol Dependency Skill

Fixes linker errors where symbols cannot be resolved.

## Detection Patterns
- `undefined reference to 'X'`
- `unresolved external symbol X` (MSVC)
- `ld.lld: error: undefined symbol: X`

## Strategy

1. **Extract Symbol**: Parse the mangled or demangled symbol name.
2. **Find Library**: Search for which library defines the symbol.
3. **Add Dependency**: Update build file to link against the library.

## Instructions

### Step 1: Extract Symbol Name
From: `undefined reference to '_ZN5MyApp10initializeEv'`
Demangle: `MyApp::initialize()`

### Step 2: Find the Defining Library
Search for the symbol definition:
```bash
# Find source files containing the function
grep -r "void MyApp::initialize" --include="*.cpp"
# Or search for class definition
grep -r "class MyApp" --include="*.h"
```

Then find which build target compiles that source file.

### Step 3: Add Dependency

**GN (BUILD.gn):**
```gn
deps = [
  "//path/to:my_library",
]
```

**Soong (Android.bp):**
```json
shared_libs: ["libmyapp"],
// or
static_libs: ["libmyapp"],
```

**CMake:**
```cmake
target_link_libraries(my_target PRIVATE my_library)
```

### Step 4: Verify
Re-run the linker or full build to confirm resolution.

## Common Android Libraries
| Symbol Pattern | Library |
|----------------|---------|
| `android::` | `libutils`, `libcutils` |
| `AudioFlinger` | `libaudioflinger` |
| `binder::` | `libbinder` |
