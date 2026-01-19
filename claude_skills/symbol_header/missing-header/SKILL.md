---
name: autofix-missing-header
description: Fixes 'file not found' errors by locating headers and adding include paths or #include statements.
---

# Missing Header Skill

Fixes C/C++ compilation errors where header files cannot be found.

## Detection Patterns
- `fatal error: 'X.h' file not found`
- `cannot open source file "X.h"`
- `No such file or directory` (for headers)

## Strategy

1. **Extract Header Name**: Parse the error to get the missing header (e.g., `utils/config.h`).
2. **Search for Header**: Use file search to locate the header in the project.
3. **Determine Fix Type**:
   - If header exists elsewhere → Add include path to build file OR fix the #include path.
   - If header is a system/standard header → Add appropriate #include.
4. **Apply Fix**: Modify the source file or build configuration.

## Instructions

### Step 1: Parse the Error
Extract:
- **Source file**: The file that failed to compile.
- **Header name**: The missing header path.

### Step 2: Search for the Header
```
find . -name "config.h" -type f
```
Or use semantic search to locate the header.

### Step 3: Apply the Fix

**Option A: Fix #include path in source file**
If the header is at `src/utils/config.h` but included as `#include "config.h"`:
```cpp
// Before
#include "config.h"
// After
#include "utils/config.h"
```

**Option B: Add include directory to build file**
For GN (`BUILD.gn`):
```gn
include_dirs = [ "src/utils" ]
```
For Soong (`Android.bp`):
```json
local_include_dirs: ["src/utils"],
```

### Step 4: Verify
Re-run the build or check that the include now resolves.

## Common Header Mappings
| Symbol | Header |
|--------|--------|
| `std::vector` | `<vector>` |
| `std::string` | `<string>` |
| `std::cout` | `<iostream>` |
| `printf` | `<cstdio>` |
| `NULL` | `<cstddef>` |
