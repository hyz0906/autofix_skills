# AutoFix-Skill

AutoFix-Skill is a universal automated build error repair system for AOSP/OpenHarmony.

## Architecture

* **Orchestrator**: Central control system for environment detection, skill loading, and pipeline driving.
* **Skill Registry**: Repository of atomic repair capabilities.
* **Context Engine**: Semantic symbol retrieval and definition positioning based on `ast-grep` and `tree-sitter`.
* **Build Adapters**: Abstraction layer for build systems (Soong, GN, etc.).

## One Codebase Strategy

* **Environment Agnostic**: Skills operate on abstract "build objects".
* **Path Mapping**: HOST vs CI support.
* **Tool Hermeticity**: Critical tools like `ast-grep` are bundled.
