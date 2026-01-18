# AutoFix-Skill User Guide

## Introduction

AutoFix-Skill is an intelligent build repair system. It is designed to run in CI/CD pipelines or on a developer's local machine to automatically resolve common compilation and linking errors.

## Installation

1. Clone the repository.
2. Ensure Python 3.10+ is installed.
3. Install dependencies (if any listed in `pyproject.toml` or `requirements.txt`).

## Command Line Interface

The main entry point is `src/cli.py`.

### `fix` Command

Analyzes an error source and applies fixes.

**Arguments:**
- `--log <file>`: Path to a build log file containing errors.
- `--error "<string>"`: A single error string to analyze directly.
- `--root <dir>`: The root directory of the source code (optional, defaults to current dir).
- `--dry-run`: Preview changes without modifying files.
- `--json`: Output results in JSON format.
- `--ci`: CI mode (non-interactive, optimizes for pipeline output).

**Examples:**

```bash
# Fix from log
python3 -m src.cli fix --log build.log

# Dry run with specific root
python3 -m src.cli fix --log out/error.log --root ~/android/master --dry-run
```

### `scan` Command

Lists all available skills and the error patterns they detect.

```bash
python3 -m src.cli scan
```

## Supported Error Categories

### 1. Symbol & Header (`src/skills/symbol_header/`)
These skills handle missing declarations and definitions at the source level.
- **MissingHeaderSkill**: Detects `fatal error: 'foo.h' file not found`. Adds `#include`.
- **UndeclaredIdentifierSkill**: Detects `use of undeclared identifier`. Adds imports/includes or namespace qualifiers.
- **NamespaceSkill**: Detects `not a member of 'std'`. Adds `std::` prefix.
- **JavaImportSkill**: Detects `cannot find symbol` (Java). Adds `import pkg.Class;`.

### 2. Linkage & Dependency (`src/skills/linkage_dependency/`)
These skills handle linker errors and module dependencies.
- **SymbolDepSkill**: Detects `undefined reference`. Finds the defining library and adds it to `shared_libs` (Android.bp) or `deps` (GN).
- **RustDepSkill**: Detects missing Crates. Adds to `rustlibs`.
- **VisibilitySkill**: Detects visibility violations. Modifies `visibility` lists.
- **MultipleDefSkill**: Detects `multiple definition`. Removes duplicate sources.

### 3. API & Type Safety (`src/skills/api_type/`)
These skills handle semantic code errors.
- **SignatureMismatchSkill**: Detects `no matching function`. Suggests argument fixes.
- **TypeConversionSkill**: Detects invalid conversions. Suggests casts (`static_cast`, etc.).
- **DeprecatedAPISkill**: Detects deprecated warnings. Suggests replacements.

### 4. Build Configuration (`src/skills/build_config/`)
These skills maintain the build system health.
- **BlueprintSyntaxSkill**: Fixes syntax errors in `Android.bp`.
- **GNScopeSkill**: Fixes scope issues in `BUILD.gn`.
- **FlagCleanerSkill**: Removes unsupported or unknown compiler flags.
- **PermissionSkill**: Fixes `Permission denied` on build scripts.

## Advanced Usage

### CI/CD Integration

AutoFix-Skill can be used in Jenkins or GitLab CI.
See `ci/jenkins_pipeline.groovy` and `ci/gitlab_ci.yml` for examples.

### Customizing Headers

You can customize the mapping of symbols to headers in `src/skills/symbol_header/undeclared_identifier.py` (via `STD_HEADER_MAP` or external configuration).

## Integration with Claude Code

You can register this project as a skill in Claude Code to enable the AI assistant to automatically fix build errors during your chat sessions.

### Installation

1.  **Locate Skills Directory**: Find your Claude Code skills directory (typically `~/.claude/skills` or check documentation).
2.  **Create Directory**: Create a folder for the skill.
    ```bash
    mkdir -p ~/.claude/skills/autofix-skill
    ```
3.  **Install Definition**: Copy the `SKILL.md` file.
    ```bash
    cp (path/to/autofix-skill)/SKILL.md ~/.claude/skills/autofix-skill/SKILL.md
    ```
4.  **Link Source Code**: Symlink the toolkit so Claude can execute the scripts.
    ```bash
    # Assuming you are in the autofix-skill repository root
    ln -s $(pwd) ~/.claude/skills/autofix-skill/autofix_skill
    ```

### Using in Chat

Once installed, you can ask Claude to fix errors naturally.

**Examples:**
> "I'm getting a missing header error in my build. Can you fix it?"
> "Run the autofix skill on the latest build log."
> "Scan the build log 'out/error.log' and repair any linkage issues."

Claude will use the instruction in `SKILL.md` to map your requests to the `src.cli` commands.
