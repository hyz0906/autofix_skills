---
name: autofix-java-import
description: Fixes Java 'cannot find symbol' errors by adding import statements or library dependencies.
---

# Java Import Skill

Fixes Java compilation errors related to missing classes or packages.

## Detection Patterns
- `error: cannot find symbol` + `symbol: class X`
- `error: package X does not exist`
- `error: cannot access X`

## Strategy

1. **Extract Symbol**: Get the missing class or package name.
2. **Find Package**: Determine the full qualified name.
3. **Add Import**: Insert import statement after package declaration.
4. **Add Dependency** (if needed): Update build file with library.

## Instructions

### Step 1: Parse the Error
Extract class name or package from error message.

### Step 2: Common Android/Java Mappings

| Class | Import | Library (Android.bp) |
|-------|--------|----------------------|
| `RecyclerView` | `androidx.recyclerview.widget.RecyclerView` | `androidx.recyclerview_recyclerview` |
| `LiveData` | `androidx.lifecycle.LiveData` | `androidx.lifecycle_lifecycle-livedata` |
| `Gson` | `com.google.gson.Gson` | `gson` |
| `Log` | `android.util.Log` | (built-in) |
| `Bundle` | `android.os.Bundle` | (built-in) |

### Step 3: Add Import Statement
Insert after the `package` declaration:
```java
package com.example.myapp;

import androidx.recyclerview.widget.RecyclerView;  // ADD THIS

public class MainActivity {
```

### Step 4: Add Dependency (if external library)
In `Android.bp`:
```
static_libs: [
    "androidx.recyclerview_recyclerview",
],
```

In `build.gradle`:
```groovy
implementation 'androidx.recyclerview:recyclerview:1.2.1'
```
