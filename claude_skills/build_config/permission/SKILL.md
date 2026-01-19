---
name: autofix-permission
description: Fixes script permission errors by making files executable.
---

# Permission Skill

Fixes build errors where scripts cannot be executed due to missing permissions.

## Detection Patterns
- `Permission denied`
- `EACCES: permission denied`
- `cannot execute`
- `not executable`

## Strategy

1. **Identify Script**: Extract the script path from the error.
2. **Make Executable**: Add execute permission to the file.

## Instructions

### Step 1: Parse the Error
From: `bash: ./configure: Permission denied`
Script: `./configure`

### Step 2: Apply Fix
```bash
chmod +x ./configure
```

Or for multiple scripts:
```bash
chmod +x scripts/*.sh
```

### Step 3: For Version Control
If using git, also update the file mode:
```bash
git update-index --chmod=+x ./configure
```

### Common Scripts Needing Permissions
- `configure`
- `autogen.sh`
- `build.sh`
- `*.py` (if run directly)
- Scripts in `scripts/` directories
