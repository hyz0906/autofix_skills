# AutoFix-Skill 系统设计文档 (System Design Document)

## 1. 系统总体架构 (High-Level Design)

### 1.1 组件关系图

AutoFix-Skill 采用插件化架构，核心组件通过定义的标准协议进行解耦。

* **Orchestrator (任务编排器):** 系统的总控中心，负责环境探测、加载特定 Skill、驱动修复流水线及结果审计。
* **Skill Registry (Skill 注册表):** 维护所有原子化修复能力的仓库，支持动态发现和按错误类型（Error Code）索引。
* **Context Engine (上下文引擎):** 基于 `ast-grep` 和 `tree-sitter` 构建，负责在全量源码树中进行语义级符号检索与定义定位。
* **Build Adapters (构建适配器):** 屏蔽具体构建系统（Soong, GN 等）语法差异的抽象层，提供对构建配置文件的结构化修改能力。

### 1.2 One Codebase 策略

为了实现本地与 CI 的高度一致性，系统设计了**环境适配抽象层 (Host Abstraction Layer)**：

* **环境无关性：** 所有的 Skill 逻辑操作的是抽象的“构建对象”，而非具体文件路径。
* **路径映射：** 在本地模式下，系统通过 `git rev-parse --show-toplevel` 获取根目录；在 CI 模式下，通过环境变量（如 `CI_PROJECT_DIR`）注入。
* **工具密封化：** 关键工具如 `ast-grep (sg)` 和 `tree-sitter` 插件随软件包发布，不依赖系统全局安装。

---

## 2. 核心模块详细设计 (Detailed Component Design)

### 2.1 Skill Registry & Lifecycle

每个 Skill 必须实现 `BaseSkill` 接口，其生命周期由编排器严格控制：

1. **Detect (探测):** 根据报错日志特征（正则或错误码）判断该 Skill 是否适用。
2. **Analyze (分析):** 调用 Context Engine 确认错误上下文（如：该缺失函数是否在其他模块导出？）。
3. **Pre-check (预检查):** 验证环境，确保目标构建文件可写且符合预期格式。
4. **Execute (执行):** 调用 Build Adapter 生成修复指令并写入文件。
5. **Verify (验证):** 调用本地构建工具（mm/hb build）进行增量编译验证。

### 2.2 Context Engine (基于 ast-grep)

为了避免庞大的全局索引，系统采用**增量式按需扫描方案**：

* **本地索引：** 针对常用目录（如 `foundation/` 或 `frameworks/`）生成的 `sg` 索引文件缓存。
* **规则动态生成：** 当识别到 `error: 'X' was not declared in this scope` 时，Engine 动态生成一份 `ast-grep` 搜索规则，匹配所有 `function_definition` 且名称为 `X` 的节点。
* **调用示例：** `sg scan --pattern 'void $FUNC(...)' --json`。

### 2.3 Universal Build Adapter 接口

采用 **Adapter Pattern** 统一操作。

```python
class IBuildAdapter(ABC):
    @abstractmethod
    def get_module_info(self, file_path: str) -> dict:
        """解析 Android.bp/BUILD.gn 获取所属模块属性"""
        pass

    @abstractmethod
    def inject_dependency(self, target_module: str, dep_name: str, dep_type: str):
        """注入 static_libs 或 deps"""
        pass

    @abstractmethod
    def modify_include_path(self, target_module: str, path: str):
        """修改 include_dirs 或 public_configs"""
        pass

```

* **Soong (Android.bp):** 使用 Python 的 `blueprint` 解析库，将文件转为 AST，修改后再回写，保持注释和缩进。
* **GN (BUILD.gn):** 利用 `gn format` 特性，结合正则匹配和作用域分析进行精准修改。

---

## 3. 数据结构与协议 (Data Structures & Protocols)

### 3.1 Diagnostic Object Schema

标准化后的错误描述：

```json
{
  "uid": "uuid-v4",
  "build_system": "soong",
  "error_code": "C2039",
  "location": { "file": "base/test.cpp", "line": 42 },
  "symbol": "MyFunction",
  "raw_log": "error: 'MyFunction' is not a member of 'NamespaceX'..."
}

```

### 3.2 Execution Plan (JSON)

Skill 生成的中间指令，保证适配器执行的**幂等性**：

```json
{
  "version": "1.0",
  "steps": [
    {
      "action": "ADD_DEPENDENCY",
      "params": {
        "target": "lib_media_service",
        "dependency": "//foundation/multimedia:audio_client",
        "type": "shared_library"
      }
    }
  ]
}

```

---

## 4. 关键流程设计 (Sequence Diagrams / Logic Flows)

### 4.1 异常修复流水线 (以 E0020 为例)

1. **Orchestrator** 监控编译输出，捕获到 `E0020: identifier not found`。
2. 调用 **Skill_MissingSymbol** 进行探测。
3. **Context Engine** 在源码树执行 `sg` 搜索，发现该符号在 `external/libcxx/` 的头文件中定义。
4. **Build Adapter** 查找 `base/test.cpp` 对应的 `Android.bp`。
5. Adapter 调用 `modify_include_path` 向模块注入头文件搜索路径。
6. Orchestrator 重新执行 `mm`。

### 4.2 冲突检测逻辑

系统维护一个 **File Modification Transaction (FMT)** 机制：

* 当多个 Skill 尝试修改同一文件时，系统会计算文件内容的 `sha256`。
* 执行前检查：若文件当前 `sha256` 与任务开始时不符，则触发重新分析（Re-analysis）逻辑，防止覆盖开发者的手动修改或其他 Skill 的变更。

---

## 5. 部署与集成 (Deployment & Integration)

### 5.1 本地模式 (Local Agent)

* **CLI 包装：** 提供 `autofix` 命令行工具。
* **Coding Agent 集成：** 对于 Claude Code 等工具，通过标准 I/O 提供 JSON 输出。Agent 通过执行 `autofix --fix [error_id]` 触发自动修复，避免 LLM 直接操作复杂的构建脚本。

### 5.2 DevOps 模式

* **GitLab CI 集成：** 在 `after_script` 或编译失败的钩子中调用。
* **清理机制：** 在 CI 环境中，系统在尝试修复前会保存 `git status` 快照。修复完成后，仅保留修改的构建文件，清理编译产物（`.o`, `.ninja` 文件），确保下次构建环境洁净。

---

## 6. 安全与容错设计 (Safety & Reliability)

### 6.1 代码回滚机制

* **Git-based Rollback:** 系统在执行任何修改前会执行 `git add . && git stash`。
* **Verification Fail:** 若验证编译依然失败，系统自动执行 `git checkout -- <file>` 还原。

### 6.2 沙箱化限制

* **Path Whitelisting:** 限制 Adapter 只能访问当前 `lunch` 目标或 `hb set` 目标覆盖的子目录。
* **Dry-run 模式：** 默认支持 `--dry-run`，仅输出预计修改的 Diff 而不实际写入，供开发者在本地预览。
