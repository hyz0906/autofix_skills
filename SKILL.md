---
name: autofix-skill
description: Automated build error repair for AOSP and OpenHarmony. Detects missing headers, undefined references, and signature mismatches, then applies fixes to BUILD.gn or Android.bp files.
---

# AutoFix-Skill

This skill provides automated build error repair capabilities for AOSP and OpenHarmony projects. It can analyze build logs, identify errors, and apply fixes to build configuration files.

## Capabilities

- **Missing Header Errors**: Automatically finds and adds include paths for missing header files
- **Undefined References**: Finds the library providing symbols and adds dependencies
- **Signature Mismatches**: Analyzes function call errors and provides suggestions

## Usage

### Fixing a Build Error from a Log File

```bash
cd /path/to/autofix_skill
PYTHONPATH=. python3 -m src.cli fix --log /path/to/build.log
```

### Fixing a Single Error Message

```bash
cd /path/to/autofix_skill
PYTHONPATH=. python3 -m src.cli fix --error "fatal error: 'missing_header.h' file not found"
```

### Preview Changes (Dry Run)

```bash
cd /path/to/autofix_skill
PYTHONPATH=. python3 -m src.cli fix --log build.log --dry-run
```

### Get JSON Output

```bash
cd /path/to/autofix_skill
PYTHONPATH=. python3 -m src.cli fix --log build.log --json
```

### Scan Available Skills

```bash
cd /path/to/autofix_skill
PYTHONPATH=. python3 -m src.cli scan
```

## Supported Build Systems

| Build System | File Type | Project |
|--------------|-----------|---------|
| GN | BUILD.gn | OpenHarmony, Chromium |
| Soong | Android.bp | AOSP |

## Error Types Handled

### Missing Header (`MissingHeaderSkill`)
Errors like:
- `fatal error: 'foo.h' file not found`
- `cannot open source file "bar.h"`

### Undefined Reference (`SymbolDepSkill`)
Errors like:
- `undefined reference to 'MyFunction'`
- `error LNK2019: unresolved external symbol`

### Signature Mismatch (`SignatureMismatchSkill`)
Errors like:
- `no matching function for call to 'foo(int, int)'`
- `too many arguments to function 'bar'`

## Installation for Claude Code

To make this skill available in Claude Code:

1. Copy this file to your Claude skills directory:
   ```bash
   cp SKILL.md ~/.claude/skills/autofix-skill/SKILL.md
   ```

2. Symlink the source code:
   ```bash
   ln -s /path/to/autofix_skill ~/.claude/skills/autofix-skill/autofix_skill
   ```

3. The skill is now available for use in Claude Code sessions.

## Examples

### Example 1: Fix Missing Header

When you encounter:
```
src/main.cpp:5:10: fatal error: 'config.h' file not found
```

Run:
```bash
PYTHONPATH=. python3 -m src.cli fix --error "fatal error: 'config.h' file not found" --root /path/to/project
```

### Example 2: Fix Linker Error

When you encounter:
```
ld.lld: error: undefined reference to 'AudioManager::getInstance()'
```

Run:
```bash
PYTHONPATH=. python3 -m src.cli fix --error "undefined reference to 'AudioManager::getInstance()'" --root /path/to/project
```

## Requirements

- Python 3.10+
- `ast-grep` (optional, for enhanced code search)
- `gn` binary (optional, for BUILD.gn formatting)
