---
name: autofix-gn-scope
description: Fixes scope and variable errors in BUILD.gn files.
---

# GN Scope Skill

Fixes GN build file errors related to undefined variables or scope issues.

## Detection Patterns
- `Undefined identifier`
- `Assignment had no effect`
- `Can't load buildconfig`
- `Unknown variable`

## Strategy

1. **Identify Variable**: Find the undefined or misused variable.
2. **Check Scope**: Determine if it's a scope or declaration issue.
3. **Fix Definition**: Add declaration or fix scope reference.

## Instructions

### Step 1: Parse the Error
From: `Undefined identifier: my_sources`
Variable: `my_sources`

### Step 2: Common Fixes

**Undefined variable - add declaration:**
```gn
# Before
sources = my_sources  # ERROR: undefined

# After
my_sources = [ "main.cpp" ]
sources = my_sources
```

**Using variable before definition:**
```gn
# Before (error)
executable("app") {
  sources = common_sources  # ERROR
}
common_sources = [ "util.cpp" ]

# After (move declaration up)
common_sources = [ "util.cpp" ]
executable("app") {
  sources = common_sources
}
```

**Scope issue with inner blocks:**
```gn
# Variables defined in if blocks may not be visible outside
if (is_debug) {
  debug_flags = [ "-g" ]
}
# debug_flags might be undefined here if is_debug is false
```

### Step 3: GN Best Practices
- Declare variables before use
- Use `defined()` to check optional variables
- Import shared configs with `import("path")`
