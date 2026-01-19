---
name: autofix-multiple-def
description: Fixes 'multiple definition' linker errors by removing duplicate symbols.
---

# Multiple Definition Skill

Fixes linker errors where the same symbol is defined in multiple translation units.

## Detection Patterns
- `multiple definition of 'X'`
- `already defined in`
- `duplicate symbol`

## Strategy

1. **Identify Symbol**: Extract the duplicated symbol.
2. **Find Definitions**: Locate all places where it's defined.
3. **Remove Duplicates**: Keep one, remove or fix others.

## Instructions

### Step 1: Parse Error
From: `multiple definition of 'globalVar'; first defined in a.o`

### Step 2: Common Causes & Fixes

**Global variable in header:**
```cpp
// Wrong: header.h
int globalVar = 0;  // Defined in every .cpp that includes

// Fix Option 1: extern declaration
// header.h
extern int globalVar;
// source.cpp
int globalVar = 0;

// Fix Option 2: inline (C++17)
inline int globalVar = 0;
```

**Function defined in header:**
```cpp
// Wrong
void foo() { ... }  // in header

// Fix: make inline
inline void foo() { ... }
```

**Same source compiled twice:**
Check build file for duplicate source file entries.
