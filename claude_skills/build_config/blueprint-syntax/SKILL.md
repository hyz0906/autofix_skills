---
name: autofix-blueprint-syntax
description: Fixes syntax errors in Android.bp files.
---

# Blueprint Syntax Skill

Fixes parsing and syntax errors in Android Blueprint (Android.bp) files.

## Detection Patterns
- `Android.bp:X:Y: parse error`
- `expected ',' before ']'`
- `unexpected '}'`
- `unrecognized property`

## Strategy

1. **Locate Error**: Find the exact line and column in Android.bp.
2. **Identify Issue**: Parse the syntax error description.
3. **Fix Syntax**: Apply the appropriate correction.

## Instructions

### Step 1: Go to Error Location
From: `Android.bp:42:15: parse error: expected ',' before ']'`
Open Android.bp at line 42.

### Step 2: Common Fixes

**Missing comma:**
```json
// Before (error)
srcs: [
    "file1.cpp"
    "file2.cpp"
]
// After
srcs: [
    "file1.cpp",
    "file2.cpp",
]
```

**Trailing comma issue:**
```json
// Before (error in some cases)
deps: [
    "libfoo",
]  // Trailing comma is OK in Android.bp
```

**Missing colon:**
```json
// Before
name "mylib"
// After
name: "mylib",
```

**Unclosed bracket:**
```json
// Before
srcs: [
    "main.cpp",
// Missing ]
// After
srcs: [
    "main.cpp",
],
```

### Step 3: Validate
Run `m blueprint_tools` or check with Android build.
