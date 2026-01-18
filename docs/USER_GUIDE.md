# AutoFix-Skill User Guide

## Overview

AutoFix-Skill is an automated build error repair system for AOSP and OpenHarmony projects. It analyzes build error logs, identifies the root cause, and applies fixes to your build configuration files.

## Installation

### Prerequisites

- Python 3.10+
- `ast-grep` (optional, for enhanced code search)
- `gn` (optional, for BUILD.gn formatting)

### Setup

```bash
# Clone or navigate to the project
cd autofix_skill

# Run with PYTHONPATH
PYTHONPATH=. python3 -m src.cli --help
```

## Quick Start

### Fixing Build Errors

**From a log file:**
```bash
PYTHONPATH=. python3 -m src.cli fix --log build_errors.log
```

**From a single error message:**
```bash
PYTHONPATH=. python3 -m src.cli fix --error "fatal error: 'missing_header.h' file not found"
```

**Dry run (preview changes):**
```bash
PYTHONPATH=. python3 -m src.cli fix --log build.log --dry-run
```

**JSON output:**
```bash
PYTHONPATH=. python3 -m src.cli fix --log build.log --json
```

### Scanning Available Skills

```bash
PYTHONPATH=. python3 -m src.cli scan
```

This shows all registered skills and their capabilities.

### CI Mode

For non-interactive CI/CD environments:
```bash
PYTHONPATH=. python3 -m src.cli fix --log build.log --ci --json
```

Exit codes:
- `0`: All errors fixed successfully
- `1`: Some errors could not be fixed

## Supported Error Types

### 1. Missing Header Errors
**Skill:** `MissingHeaderSkill`

Detects errors like:
- `fatal error: 'foo.h' file not found`
- `cannot find include file: 'bar.h'`

**Fix:** Searches for the header file in the source tree and adds the appropriate include path to the build configuration.

### 2. Undefined Reference Errors
**Skill:** `SymbolDepSkill`

Detects errors like:
- `undefined reference to 'MyFunction'`
- `error: undefined symbol: SomeClass::method`
- `error LNK2019: unresolved external symbol`

**Fix:** Finds the library providing the symbol and adds it as a dependency.

### 3. Function Signature Mismatches
**Skill:** `SignatureMismatchSkill`

Detects errors like:
- `no matching function for call to 'foo(int, int)'`
- `too many arguments to function 'bar'`
- `cannot convert 'X' to 'Y'`

**Analysis:** Provides detailed analysis and suggestions (automatic fix not always possible).

## Supported Build Systems

### GN (BUILD.gn)
Used by OpenHarmony and Chromium-based projects.

**Capabilities:**
- Add dependencies (`deps`)
- Add include paths (`include_dirs`)
- Modify compiler flags (`cflags`)

### Soong (Android.bp)
Used by AOSP (Android Open Source Project).

**Capabilities:**
- Add shared/static/header library dependencies
- Add include directories
- Modify compiler flags

## Configuration

### Environment Detection

AutoFix-Skill automatically detects the build environment:

| Marker File | Environment | Build System |
|-------------|-------------|--------------|
| `out/ohos_config.json` | OpenHarmony | GN |
| `build/envsetup.sh` | AOSP | Soong |

### Specifying Root Directory

```bash
PYTHONPATH=. python3 -m src.cli fix --root /path/to/source --log build.log
```

## Troubleshooting

### "No skills matched the error"

This means no registered skill recognized the error pattern. Check:
1. The error message format matches supported patterns
2. Run `scan` to see available skills

### "Could not find header file"

The skill searched but couldn't locate the header. Check:
1. The header file exists in the source tree
2. The search path is correct

### "gn format failed"

The GN binary is not in PATH or failed. The file was still modified, but may need manual formatting.

## Development

### Adding New Skills

See [API.md](API.md) for the skill development guide.

### Running Tests

```bash
cd autofix_skill
PYTHONPATH=. python3 -m pytest tests/ -v
```
