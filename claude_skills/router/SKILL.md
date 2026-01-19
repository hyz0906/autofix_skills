---
name: autofix-router
description: Analyzes build errors and routes to the appropriate AutoFix skill. Use this as the entry point when encountering a build failure.
---

# AutoFix Router

You are an expert build error analyzer. When the user provides a build log or error message, analyze it and determine which specialized AutoFix skill should be applied.

## Error Categories

### 1. Symbol & Header Errors
**Use skills in `symbol_header/` for:**
- `fatal error: 'X.h' file not found` → **missing-header**
- `use of undeclared identifier 'X'` → **undeclared-identifier**
- `'X' is not a member of 'std'` → **namespace**
- `cannot find symbol` (Java) → **java-import**
- `incomplete type 'X' used` → **forward-decl**
- `'MACRO' was not declared` → **macro-undefined**
- `No rule to make target 'X.o'` → **kbuild-object**

### 2. Linkage & Dependency Errors
**Use skills in `linkage_dependency/` for:**
- `undefined reference to 'X'` → **symbol-dep**
- `unresolved external symbol` (MSVC) → **symbol-dep**
- `can't find crate` (Rust) → **rust-dep**
- `visibility "//foo" is not visible` → **visibility**
- `multiple definition of 'X'` → **multiple-def**
- `undefined reference to vtable` → **vtable**
- `vendor variant` / `VNDK` errors → **variant-mismatch**

### 3. API & Type Errors
**Use skills in `api_type/` for:**
- `no matching function for call` → **signature-mismatch**
- `too many/few arguments` → **signature-mismatch**
- `cannot convert 'X' to 'Y'` → **type-conversion**
- `invalid conversion from` → **type-conversion**
- `discards qualifiers` (const) → **const-mismatch**
- `unimplemented pure virtual` → **override-missing**
- `deprecated` warnings → **deprecated-api**
- `LINUX_VERSION_CODE` issues → **version-guard**

### 4. Build Configuration Errors
**Use skills in `build_config/` for:**
- `parse error` in Android.bp → **blueprint-syntax**
- `Undefined identifier` in BUILD.gn → **gn-scope**
- `unknown argument: '-fX'` → **flag-cleaner**
- `Permission denied` on scripts → **permission**
- `ninja: error: ... is dirty` → **ninja-cache**

## Instructions

1. **Parse the Error**: Extract the file path, line number, and error message.
2. **Match Category**: Compare against the patterns above.
3. **Invoke Skill**: Use the matched skill from the appropriate category directory.
4. **If Uncertain**: If no clear match, analyze the error semantically and pick the closest fit.

## Example

**Input:**
```
src/main.cpp:42:10: fatal error: 'utils/config.h' file not found
```

**Analysis:**
- Pattern: `fatal error: '...' file not found`
- Category: Symbol & Header
- Skill: `missing-header`

**Action:** Navigate to `symbol_header/missing-header/SKILL.md` and follow its instructions.
