---
name: autofix-visibility
description: Fixes Soong visibility restriction errors by updating module visibility lists.
---

# Visibility Skill

Fixes Android Soong build errors related to module visibility restrictions.

## Detection Patterns
- `module "X" is not visible to "//path/to:Y"`
- `visibility "//foo" is not visible from "//bar"`

## Strategy

1. **Identify Source/Target**: Parse which module needs visibility to which.
2. **Update Visibility**: Add the requesting module's path to the target's visibility list.

## Instructions

### Step 1: Parse the Error
Extract:
- **Target module**: The module being requested (has restricted visibility)
- **Requesting module**: The module trying to use the target

### Step 2: Locate Target's Android.bp
Find the Android.bp file that defines the target module.

### Step 3: Update Visibility

**Before:**
```
cc_library {
    name: "libprivate",
    visibility: ["//system/core"],
}
```

**After:**
```
cc_library {
    name: "libprivate",
    visibility: [
        "//system/core",
        "//vendor/my_app",  // ADD the requesting module's path
    ],
}
```

### Visibility Patterns
- `["//visibility:public"]` - Visible to all
- `["//visibility:private"]` - Only same package
- `["//path/to/package"]` - Specific package
- `["//path/to/package:__subpackages__"]` - Package and subpackages
