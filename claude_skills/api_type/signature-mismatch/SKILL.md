---
name: autofix-signature-mismatch
description: Fixes function call errors with wrong number or type of arguments.
---

# Signature Mismatch Skill

Fixes errors where function calls don't match their declarations.

## Detection Patterns
- `no matching function for call to 'X'`
- `too many arguments to function 'X'`
- `too few arguments to function 'X'`
- `candidate function not viable`

## Strategy

1. **Identify Function**: Extract the function name and call location.
2. **Find Declaration**: Locate the function's declaration/definition.
3. **Compare Signatures**: Match call arguments against expected parameters.
4. **Fix Mismatch**: Adjust the call site or (rarely) the declaration.

## Instructions

### Step 1: Parse the Error
Extract:
- Function name
- Expected vs. provided argument count/types
- Location of the call

### Step 2: Find Function Declaration
```bash
grep -r "returnType functionName(" --include="*.h"
```

### Step 3: Analyze and Fix

**Case: Too many arguments**
```cpp
// Declaration: void foo(int a);
// Call: foo(1, 2);  // ERROR: too many
// Fix: foo(1);
```

**Case: Too few arguments**
```cpp
// Declaration: void bar(int a, int b);
// Call: bar(1);  // ERROR: too few
// Fix: bar(1, 0);  // Add default or required value
```

**Case: Wrong type**
```cpp
// Declaration: void process(const char* str);
// Call: process(myString);  // myString is std::string
// Fix: process(myString.c_str());
```

### Step 4: Verify
Ensure the fix compiles and maintains intended behavior.
