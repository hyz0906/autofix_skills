# 面向 AOSP/OpenHarmony 的通用自动化编译错误修复 Skill 系统 (AutoFix-Skill System) 需求文档

## 1. 业务目标与愿景 (Business Objectives)

在 AOSP 和 OpenHarmony 等超大规模代码库中，构建系统极其复杂且异构。本系统的愿景是构建一套**平台无关、构建系统感知**的自动化修复方案：

* **提升开发效能：** 自动解决超过 70% 的琐碎编译错误（如头文件缺失、库依赖未定义、函数签名不匹配），将开发者的平均故障修复时间（MTTR）从小时级降低至分钟级。
* **流水线自愈：** 在 DevOps 门禁阶段实现“检测-分析-修复-验证”的闭环，显著减少因环境差异或代码合并导致的阻塞，提高 CI 周期吞吐量。
* **知识沉淀：** 将资深工程师的修复经验转化为可复用的原子化 Skills，消除不同构建系统（Soong/GN/Kbuild）之间的认知鸿沟。

---

## 2. 系统架构设计 (System Architecture)

系统采用 **“One Codebase, Dual Use”** 的理念，确保同一套 Skill 代码既能作为本地 Coding Agent 的工具插件，也能作为 CI 脚本的执行引擎。

### 2.1 三层解耦架构

1. **任务编排层 (Orchestrator)：**
* **职责：** 环境探测、编译日志获取、多轮修复状态机管理。
* **环境感知：** 通过探测当前目录的特征文件（如 `build/envsetup.sh`, `out/ohos_config.json`）自动识别目标平台及主构建框架。


2. **Skill 逻辑层 (Skill Logic)：**
* **职责：** 核心诊断与策略生成。
* **组织形式：** 采用原子化插件设计（Atomic Skills）。每个 Skill 对应一类特定的编译错误场景，如 `MissingIncludeSkill` 或 `SymbolDepSkill`。


3. **构建系统适配层 (Build System Adapters)：**
* **职责：** 屏蔽 Soong, GN, Ninja, CMake 等语法的差异，提供统一的读写接口（CRUD）。
* **抽象化：** Skill 层仅下达“向模块 A 添加头文件搜索路径 B”的指令，由适配层决定是修改 `Android.bp` 的 `include_dirs` 还是 `BUILD.gn` 的 `public_configs`。



---

## 3. 核心功能需求 (Functional Requirements)

### 3.1 错误诊断 (Diagnosis)

* **多模式解析：** 支持解析不同构建工具的 stderr 输出。
* **标准化错误对象：** 将原始日志转化为包含 `error_code` (如 C2065), `file_path`, `line_number`, `offending_symbol` 的标准化 JSON 对象。

### 3.2 上下文检索 (Context Retrieval)

* **语义化检索：** 在不依赖远端 LSIF/MCP 的情况下，集成 **ast-grep (sg)** 针对本地源码树进行高效扫描。
* **符号索引：** 自动扫描全局 `include` 目录及导出符号（Exported Symbols），构建轻量级本地缓存以支持快速定位函数定义。

### 3.3 自动化修复策略 (Repair Strategies)

* **Missing Header 算法：** 识别错误 -> `ast-grep` 搜索头文件 -> 定位所属模块 -> 修改构建文件中的包含路径或依赖。
* **Symbol Dependency 算法：** 识别未定义引用 -> 检索符号表确定目标库 -> 更新当前模块的 `static_libs` 或 `deps`。
* **Version Compatibility：** 识别内核 API 版本差异，自动插入基于 `LINUX_KERNEL_VERSION` 的宏定义判断。

### 3.4 构建系统适配器 (Adapters)

* **抽象修改接口：**
* `add_header_lib(module, lib_name)`
* `add_include_path(module, path)`
* `update_cflags(module, flag)`


* **原子化写入：** 修改构建文件时保持原始格式（Formatting-aware），避免产生大规模的 Diff 噪音。

---

## 4. 非功能需求 (Non-Functional Requirements)

* **可移植性 (Portability)：** * 系统必须以全密闭（Hermetic）方式运行，不依赖系统级全局变量。
* 支持在 Python 虚拟环境下的一键式部署，兼容 macOS/Linux 开发机及标准的 Docker 编译容器。


* **安全性 (Security)：**
* **影响范围限制：** 修复操作仅限于受编译错误直接影响的模块目录。
* **配置锁定：** 禁止修改安全相关的配置（如 SeLinux Policy, 签名证书路径）。


* **性能 (Performance)：**
* 在千万行级代码（AOSP 规模）下，符号搜索的首次响应时间不得超过 10 秒，后续增量搜索应在 2 秒内完成。
* 诊断逻辑需支持多线程并行解析大规模日志。



---

## 5. 技术栈建议 (Technology Stack)

* **开发语言：** Python 3.10+ (利用其丰富的库支持及 CI 环境的通用性)。
* **代码分析引擎：** * **ast-grep (sg)：** 用于结构化、语义化的代码模式匹配。
* **tree-sitter：** 用于精确解析 `Android.bp` 和 `BUILD.gn` 的语法树。


* **构建工具集成：** 调用 AOSP 的 `envsetup.sh` 及 OpenHarmony 的 `hb` 工具链。
* **数据交换：** 统一采用 JSON Schema 定义 Skills 之间的输入输出标准。

---

## 6. 典型用户用例 (User Stories & Workflows)

### 场景 A：本地开发环境的“一键修复”

* **用户：** 驱动开发工程师。
* **操作：** 在集成好的本地 Coding Agent (如 Claude Code) 中输入：`"fix this build error"`。
* **流程：** Agent 调用本地 `AutoFix-Skill` -> 解析 Ninja 日志 -> 发现缺少头文件 -> 调用 `ast-grep` 找到头文件在 `external/` 目录下 -> 自动修改当前目录的 `Android.bp` -> 触发增量编译验证。

### 场景 B：DevOps 门禁侧的“自愈机制”

* **用户：** 自动化 CI 系统。
* **触发：** 在 PR 提交后的构建阶段，Jenkins 监测到 `Build Failed`。
* **流程：** CI 脚本调用 `fix_agent --mode=auto --log=build.log` -> 系统分析出是由于接口变更导致的函数签名错误 -> 自动生成修复 Patch -> **重新尝试构建** -> 若通过，则将 Patch 作为建议评论发布在 PR 上或自动提交 Fix Commit。
