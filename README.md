# AutoFix-Skill

> **Universal Automated Build Error Repair System for AOSP & OpenHarmony**

AutoFix-Skill is a powerful, extensible framework designed to automatically detect, analyze, and repair compilation and linking errors in large-scale build systems like AOSP (Soong) and OpenHarmony (GN). It abstracts the complexities of different build systems and provides a unified interface for intelligent code repair.

## 🚀 Key Features

*   **Universal Build Adapter**: Seamlessly supports **Soong (Android.bp)**, **GN (BUILD.gn)**, **Kbuild (Linux Kernel)**, **CMake**, and **Makefiles**.
*   **30+ Specialized Skills**: Atomic repair capabilities covering:
    *   Missing headers and undeclared identifiers.
    *   Linker errors (undefined vars, vtables, symbols).
    *   API mismatches (signature, type conversion, deprecated APIs).
    *   Build configuration issues (flags, permissions, syntax).
*   **Context-Aware Analysis**: Uses regex, `ast-grep`, and semantic analysis to understand the *root cause* of errors, not just the symptoms.
*   **Categories**:
    *   `symbol_header`: Namespace, forward decls, headers.
    *   `linkage_dependency`: Library linking, visibility, Rust crates.
    *   `api_type`: Function signatures, const correctness, overrides.
    *   `build_config`: Compiler flags, script permissions, ninja cache.

## 📦 Installation

Prerequisites:
- Python 3.10+
- `gn` (optional, for formatting)
- `ast-grep` (optional, for deep context search)

```bash
git clone https://github.com/your-org/autofix-skill.git
cd autofix-skill
pip install -r requirements.txt  # If exists, or just use standard libs
```

## 🛠️ Usage

### Quick Fix (Log File)
Feed a build log file to automatically fix errors found within it:

```bash
PYTHONPATH=. python3 -m src.cli fix --log /path/to/build.log --root /path/to/project
```

### Fix Specific Error Pattern
Directly target a known error string:

```bash
PYTHONPATH=. python3 -m src.cli fix --error "fatal error: 'utils.h' file not found"
```

### Dry Run (Preview)
See what changes would be made without modifying files:

```bash
PYTHONPATH=. python3 -m src.cli fix --log build.log --dry-run
```

### Scan Available Skills
List all registered skills and their active error patterns:

```bash
PYTHONPATH=. python3 -m src.cli scan
```

## 📂 Project Structure

```
autofix-skill/
├── src/
│   ├── build_adapters/     # Adapters for GN, Soong, Make, etc.
│   ├── skills/             # The core logic, categorized
│   │   ├── symbol_header/  # Header/Symbol related skills
│   │   ├── linkage_dependency/ # Linker/Dep skills
│   │   ├── api_type/       # Type/API mismatch skills
│   │   └── build_config/   # Config/Flag skills
│   ├── skill_registry/     # Manager for loading/running skills
│   ├── orchestrator/       # Pipeline controller
│   └── cli.py              # Command line interface
├── tests/                  # Categorized test suite
│   ├── test_cat_symbol_header.py
│   ├── test_cat_linkage.py
│   ├── ...
└── docs/                   # Detailed documentation
    ├── USER_GUIDE.md
    └── API.md
```

## 🧪 Testing

The project maintains high code quality with a comprehensive test suite (120+ tests).

```bash
# Run all tests
PYTHONPATH=. python3 -m pytest tests/ -v
```

## 🤝 Contributing

See `docs/API.md` to learn how to implement a new `BaseSkill`.

## 📄 License

Apache 2.0
