---
name: autofix-rust-dep
description: Fixes Rust 'can't find crate' errors by adding dependencies to Cargo.toml or rustlibs.
---

# Rust Dependency Skill

Fixes Rust compilation errors related to missing crates.

## Detection Patterns
- `can't find crate for 'X'`
- `unresolved import 'X'`
- `could not find 'X' in 'Y'`

## Strategy

1. **Identify Crate**: Extract the missing crate name.
2. **Add to Build**: Update Cargo.toml or Android.bp rustlibs.

## Instructions

### Step 1: Parse Error
From: `can't find crate for 'serde'`
Crate: `serde`

### Step 2: Add Dependency

**Cargo.toml:**
```toml
[dependencies]
serde = "1.0"
```

**Android.bp (AOSP):**
```json
rust_library {
    rustlibs: [
        "libserde",
    ],
}
```

### Common Rust Crates
| Crate | Android.bp name |
|-------|-----------------|
| `serde` | `libserde` |
| `log` | `liblog_rust` |
| `libc` | `liblibc` |
