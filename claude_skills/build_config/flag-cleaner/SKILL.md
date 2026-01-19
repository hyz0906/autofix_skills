---
name: autofix-flag-cleaner
description: Removes unsupported or unknown compiler flags from build configurations.
---

# Flag Cleaner Skill

Fixes build errors caused by compiler flags that are not supported by the current toolchain.

## Detection Patterns
- `unknown argument: '-fX'`
- `unsupported option '-fX'`
- `unknown warning option '-Wno-X'`
- `unrecognized command line option`

## Strategy

1. **Extract Flag**: Parse the unsupported flag from the error.
2. **Locate Build File**: Find where the flag is defined.
3. **Remove Flag**: Delete the flag from the build configuration.

## Instructions

### Step 1: Identify the Flag
From error: `clang: error: unknown argument: '-fno-strict-overflow'`
Flag: `-fno-strict-overflow`

### Step 2: Find the Build File
Search for the flag in build files:
```bash
grep -r "fno-strict-overflow" --include="*.bp" --include="*.gn" --include="CMakeLists.txt"
```

### Step 3: Remove the Flag

**In Android.bp:**
```json
// Before
cflags: ["-Wall", "-fno-strict-overflow", "-O2"],
// After
cflags: ["-Wall", "-O2"],
```

**In BUILD.gn:**
```gn
// Before
cflags = [ "-Wall", "-fno-strict-overflow" ]
// After  
cflags = [ "-Wall" ]
```

**In CMakeLists.txt:**
```cmake
# Before
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-strict-overflow")
# After
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}")
```

### Common Problematic Flags
| Flag | Issue |
|------|-------|
| `-fno-strict-overflow` | GCC-only, not in Clang |
| `-Wno-unused-but-set-*` | GCC-only warning |
| `-fstack-protector-strong` | Older toolchains |
