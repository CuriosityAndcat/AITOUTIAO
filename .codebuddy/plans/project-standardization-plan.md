# AIToutiao 项目标准化改造方案（Plan）

> 生成时间：2026-07-10 | 性质：Tier 3 规划（分析 + 方案，未执行改造）
> 范围：`d:\AIToutiao` 全仓库（多语言、多模块 monorepo）

---

## 〇、一句话结论

这是一个**去中心化、零工程化**的多语言 monorepo：Python（pipeline / agent / engine_mode / knowledge-brain / wewrite / video-transcriber / sensevoice-asr / toutiao-auto-publisher）与 TypeScript（super-publisher-main，用 Bun）混合并存。**根目录没有任何统一的 lint / format / pre-commit / CI 配置**，且存在大量跨项目源码副本与依赖版本分歧。最紧急的隐患是 `engine_mode/lib/` 把 4 个项目复制进同一目录、在同一 Python 进程内加载，导致 fastapi / pydantic / playwright vs patchright 等依赖在**同一运行环境内真实冲突**。

---

## 一、现状诊断

### 1.1 目录结构与模块定位

| 模块 | 语言 | 角色 | 入口 |
|------|------|------|------|
| `pipeline.py` + 根脚本 | Python | 端到端流水线主入口（下载→转录→写作→配图→发布） | `pipeline.py` |
| `agent/` | Python | 自研 Agent 框架（对齐 OpenAI Agents + LangGraph），**无 requirements.txt** | `agent/__init__.py` |
| `engine_mode/` | Python | Streamlit 引擎模式（端口 8502），**内嵌 lib/ 副本** | `engine_mode/engine_app.py` |
| `knowledge-brain/` | Python | 知识库脚本集合（周报/分析） | `scripts/*.py` |
| `wewrite-main/` | Python | 微信写作工具 + toolkit（配图/合规/提示词） | `toolkit/cli.py` |
| `video-transcriber/` | Python | 转录服务（SenseVoice），**唯一规范较完整子项目** | `webmain.py` |
| `sensevoice-asr/` | Python | ASR 模型与推理（含大模型权重，已忽略） | — |
| `toutiao-auto-publisher/` | Python | 头条发布 FastAPI 服务 + backend | `backend/main.py` |
| `video-batch-download-main/` | Node(.mjs) | 抖音视频批量下载 | `scripts/download.mjs` |
| `super-publisher-main/` | TS(Bun)+Py | Claude 插件式发布 Skill 集合（9 个 skill） | `skills/*/SKILL.md` |
| `agentic-ai-main/`、`vision-tool/`、`wewrite-main/dist/`、`tests/` | 混合 | 参考项目 / 视觉工具 / 发布副本 / 根级测试 | — |

### 1.2 现有代码规范（ESLint / Prettier / 其它）

| 工具 | 是否存在 | 位置 |
|------|---------|------|
| `.eslintrc*` | ❌ 无 | 全仓库 |
| `.prettierrc*` | ❌ 无 | 全仓库 |
| `tsconfig.json` | ❌ 无 | TS 用 Bun 直跑 `.ts`，无编译配置 |
| `pyproject.toml (ruff/black)` | ❌ 无 | 仅 `video-transcriber` 有 pyproject（仅打包用，无 tool.ruff） |
| `.editorconfig` | ❌ 无 | — |
| `setup.cfg` / `.flake8` / `ruff.toml` | ❌ 无 | — |
| `pre-commit-config.yaml` | ❌ 无 | — |
| `.github/workflows` | ❌ 无 | `super-publisher-main/.github` 仅含 release.yml（无 test/lint 门禁） |

**结论：零统一代码规范。** 各模块内部风格如下：
- Python：普遍 snake_case + 4 空格缩进（PEP 8 基线）。
- 差异点：`agent/`、`engine_mode/agent/` 类型注解充分 + 详尽 docstring；`knowledge-brain/` 几乎无类型注解、docstring 稀疏；`wewrite-main/toolkit` 部分注解。
- TS（super-publisher）：kebab-case 文件名 + camelCase/PascalCase 标识符，ESM + `node:*` 前缀，遵循 Bun 风格（相对导入带 `.ts` 扩展名）。
- 导入风格不一致：`agent/` 用绝对 `from agent.x`；`knowledge-brain/`、`wewrite-main/toolkit` 用裸 `import config`（依赖运行时 sys.path 注入）。

### 1.3 依赖版本与分歧 / 冲突

**核心冲突（同一运行环境内会真实打架，尤其 engine_mode 合并加载）：**

| 包 | video-transcriber | toutiao-auto-publisher | wewrite-main | sensevoice-asr | 风险 |
|----|----|----|----|----|------|
| fastapi | `==0.104.1` | `==0.115.0` | — | — | ⚠️ 版本分歧 |
| pydantic | `==2.5.2` | `==2.9.0` | 未声明 | — | ⚠️ 分歧 |
| pydantic-settings | `==2.1.0` | `==2.6.0` | — | — | ⚠️ 分歧 |
| uvicorn | `==0.24.0` | `==0.30.0` | — | — | ⚠️ 分歧 |
| python-multipart | `==0.0.6` | `==0.0.12` | — | — | ⚠️ 分歧 |
| openai | `1.109.1`(env) | `==1.55.0` | — | — | ⚠️ 分歧 |
| requests | `2.32.5`(env) | — | `==2.33.1` | — | ⚠️ 分歧 |
| numpy | `==2.2.6`(env) | — | — | `>=2.0.0` | ✅ 兼容 |
| playwright vs patchright | — | `patchright>=1.48.0` | `playwright==1.58.0` | — | ⚠️ **patchright 是 playwright fork，同环境装两者会冲突** |

**其它缺口：**
- `agent/`、`engine_mode/agent/`、**没有 requirements.txt**，却依赖 `langgraph` / `pydantic` / `openai`，依赖未声明。
- `knowledge-brain/scripts/requirements.txt` 极简（仅 PyYAML、requests），实际 import 的 LLM/依赖未声明。
- `engine_mode/` 顶层同样**无统一 requirements**，依赖散落在 `lib/*/requirements.txt` 与 engine_app.py 的 try-import 中。
- `video-transcriber/environment.yml` 是一个**庞大的 Anaconda 全量环境**（425 行），含大量与本项目的无关包（spyder、scrapy、bokeh…），不可作为依赖基线。

### 1.4 文档 / 测试覆盖率 / 构建流程

| 项 | 现状 |
|----|------|
| 文档 | 根级 `AGENT.md`（Agent 行为规约）、`WORKFLOW_STANDARD.md`（SOP）、`STYLE_OPTIONS.md`（写作风格）；各子项目 README 较全（video-transcriber 甚至有 `CLAUDE.md`）。**缺根级 `ARCHITECTURE.md` 与全局 `CONTRIBUTING.md`**。 |
| 构建 | Python 无构建（直跑脚本 / Streamlit / FastAPI）；TS 用 Bun 直跑 `.ts`，无 webpack/vite/tsc。**无统一构建入口**（Makefile 不存在）。 |
| 测试 | 仅 `video-transcriber`（pytest.ini + tests/ + conftest，覆盖率 core/api/utils）、`wewrite-main/tests`（converter/context_budget）、`super-publisher`（1 个 .ts + 3 个 .py）、根 `tests/`（11 个 agent 测试）。**engine_mode / knowledge-brain / toutiao-auto-publisher / sensevoice-asr 无测试**。`agent/` 的测试在根 `tests/` 下、与源码分离。 |
| CI | 无。`.github` 不存在；super-publisher 的 release.yml 只做发布。 |

### 1.5 源码副本冗余（维护噩梦）

| 副本 | 来源 | 风险 |
|------|------|------|
| `engine_mode/agent/` | = `agent/`（完整拷贝） | 两份 Agent 实现并行、易漂移 |
| `engine_mode/lib/sensevoice-asr/`、`lib/toutiao-auto-publisher/`、`lib/video-batch-download-main/`、`lib/wewrite-main/` | 4 个外部项目拷贝 | 同进程加载 → 真实依赖冲突；升级需手动同步 |
| `wewrite-main/dist/openclaw/` | = `wewrite-main/`（完整拷贝） | 双份维护 |
| `wewrite-main/toolkit/config.py` ↔ `toutiao-auto-publisher/backend/config.py` | 平行重复配置加载器（yaml vs pydantic-settings） | 无共享抽象 |

---

## 二、需检索 / 收集的信息清单（Information Retrieval Checklist）

> 在执行改造前，必须补齐以下信息（部分需跑命令或询问用户）：

### A. 依赖与冲突（需实际探测）
- [ ] 在**干净 venv** 中按各 `requirements.txt` 安装，验证 `engine_mode` 合并运行时的 fastapi/pydantic/playwright-patchright 是否真冲突（`pip install` 后 `python -c "import fastapi, pydantic"`）。
- [ ] 用 `pip-audit` / `safety` 扫描所有依赖的已知 CVE（torch、transformers、fastapi 等大依赖尤其关注）。
- [ ] 用 `pip index versions <pkg>` 或 `uv` 查询各依赖最新稳定版，确定统一升级基线。
- [ ] 确认 `patchright` 与 `playwright` 是否必须共存（若只是历史 fork，统一为其中一个）。

### B. 测试覆盖率（需实测）
- [ ] 对每个含测试的模块跑 `pytest --cov` 取真实覆盖率数字（video-transcriber、wewrite-main、super-publisher、tests/）。
- [ ] 确认 `engine_mode`、`knowledge-brain`、`toutiao-auto-publisher`、`sensevoice-asr` 是否真的零测试（仅静态确认不足以定覆盖率目标）。

### C. 部署与运行形态（需确认）
- [ ] 线上到底怎么跑：`streamlit_app.py`（8501）、`engine_mode/engine_app.py`（8502）、`toutiao-auto-publisher/backend/main.py`（8000）三者关系？是否为同一部署单元？
- [ ] 是否用 Docker 部署（已发现 `sensevoice-asr` 与 `video-transcriber` 各有 Dockerfile，但根级无统一镜像）。
- [ ] Python 版本基线：各模块要求 3.10+ / 3.12（environment.yml 是 3.12.7），需统一目标版本。

### D. 风格与协作偏好（需与用户确认）
- [ ] 团队是否接受 **Ruff** 作为 Python 统一 linter+formatter（替代 black/isort/flake8）？
- [ ] TS 侧确认用 **ESLint flat config + Prettier**（Bun 生态常用），还是保持现状零配置？
- [ ] 是否引入 **Conventional Commits** 与语义化版本？
- [ ] 是否接受 pre-commit 钩子（提交前自动 lint/format）？

### E. 副本取舍（需决策）
- [ ] `engine_mode/lib/*` 副本能否改为 **git submodule / 包安装 / 相对 import**，以消除同进程冲突？
- [ ] `wewrite-main/dist/openclaw/` 是否应改为**构建产物**（CI 生成），不入库？

---

## 三、业界同类型项目标准化最佳实践

### Python（来自 Ruff 官方、Astral、DEV Community 2025 指南）
1. **Ruff 一统 lint + format**：用 Rust 编写的极速工具，单依赖替代 `flake8 + isort + black + pyupgrade + autoflake`，`pyproject.toml` 集中配置 `[tool.ruff]` 与 `[tool.ruff.format]`。
2. **pyproject.toml 单一真相源**：所有工具（ruff、pytest、mypy、coverage）配置收敛到一个文件，不再散落 setup.cfg/.flake8/tox.ini。
3. **pre-commit 钩子**：`ruff-pre-commit` 在提交前自动修复；配合 `ruff check --fix` / `ruff format`。
4. **Monorepo 依赖管理**：用 `uv` 或 PDM Workspace / 共享 `[tool.uv.sources]`，避免各子项目重复声明；跨项目共享版本锁定。
5. **严格但渐进**：先 `ruff check`（error 级），再逐步开启 `E/F/I/UP/B` 等规则，禁止一次全开导致 PR 爆炸。

### TypeScript（来自 typescript-eslint 官方、AdvancedFrontends 2025、掘金/腾讯云 2025）
1. **ESLint Flat Config（`eslint.config.js`）**：2025 已稳定，取代 `.eslintrc*`；用 `@typescript-eslint` + `typescript-eslint` 推荐集。
2. **Prettier 不参与 lint 规则冲突**：ESLint 关掉格式化规则，只做静态检查，格式化交给 Prettier（`eslint-config-prettier`）。
3. **Bun 生态**：`bun run` 直跑 TS；可用 `tsc --noEmit` 做类型检查门禁；可选 `biome` 作为 ruff 等价物（lint+format 一体）。
4. **提交钩子**：husky + lint-staged（或统一接入根 pre-commit）。
5. **一致性**：line-length、引号、尾逗号统一（与 Python 侧尽量对齐，如 100 列）。

### 通用工程化基线
- **.editorconfig**：跨编辑器统一缩进/换行/末尾换行。
- **CI 门禁**：每次 PR 跑 `lint + type-check + test + coverage 门槛`；失败阻断合并。
- **Conventional Commits + 语义化版本**：便于生成 CHANGELOG 与自动发布（super-publisher 已有 CHANGELOG.md）。
- **文档体系**：根 `README` + `ARCHITECTURE.md` + `CONTRIBUTING.md` + 各模块 `README` + `CLAUDE.md`/`AGENTS.md` 供 AI 编码助手消费。

---

## 四、标准化改造具体执行步骤（Execution Steps）

> 每步可独立提交，建议按序推进；步骤 1/2/3 为低风险"加护栏"，应最先做。

### 步骤 1：根级统一 Python 规范（低风险、高收益）
- 新增根 `pyproject.toml`，含 `[tool.ruff]`（target-version py310、line-length 100、select E/F/I/UP/B/D）、`[tool.ruff.format]`、`[tool.pytest.ini_options]`、`[tool.coverage.run]`。
- 新增根 `.editorconfig`（4 空格、UTF-8、LF）。
- 新增 `.pre-commit-config.yaml`（ruff-pre-commit + 末尾换行 + 大文件检查）。
- 涉及文件：`pyproject.toml`（新）、`.editorconfig`（新）、`.pre-commit-config.yaml`（新）。

### 步骤 2：TS 侧规范（仅 super-publisher-main）
- 新增 `super-publisher-main/eslint.config.js`（flat config + typescript-eslint 推荐 + eslint-config-prettier）。
- 新增 `super-publisher-main/.prettierrc.json`（与 Python 对齐 100 列 / 双引号 / 尾逗号）。
- 补 `tsconfig.json`（`strict: true`、`noEmit` 类型检查用）。
- 为 `wechat-post-publisher/scripts/package.json` 补 `scripts.format` / `scripts.lint`。

### 步骤 3：依赖统一与冲突消解
- 建立**顶层依赖基线文档**（或 `requirements-common.txt`），统一 fastapi / pydantic / pydantic-settings / uvicorn / python-multipart / openai / requests 到一组兼容版本。
- 为 `agent/`、`engine_mode/agent/`、`knowledge-brain/` 补齐缺失的 requirements。
- 决策并统一 `playwright` vs `patchright`（建议统一为 patchright 或 playwright 之一）。
- 用 `pip-audit` 扫描并升级有 CVE 的依赖。
- 验证 `engine_mode` 合并运行时 import 通过。

### 步骤 4：消除源码副本冗余
- `engine_mode/lib/*` 改为 submodule 或包依赖引用；清理 `engine_mode/agent/` 副本，统一引用根 `agent/`。
- `wewrite-main/dist/openclaw/` 移出版本库，改为 CI 构建产物。
- 抽象 `config` 加载层，合并 wewrite / toutiao 两套 config。

### 步骤 5：统一测试与 CI
- 为 `engine_mode / knowledge-brain / toutiao-auto-publisher / sensevoice-asr` 补最小冒烟测试。
- 设定覆盖率门槛（建议核心模块 ≥ 60%，video-transcriber 维持现有高覆盖）。
- 新增根 `.github/workflows/ci.yml`：lint（ruff + eslint）+ type-check（tsc/mypy 可选）+ pytest + coverage。
- 可选：用 CodeBuddy automation 定时跑 lint 巡检。

### 步骤 6：文档体系补全
- 根 `ARCHITECTURE.md`（模块关系图、数据流、依赖边界）。
- 根 `CONTRIBUTING.md`（开发环境搭建、代码规范、提交规范、测试运行）。
- 为无 README 的模块补 `skills/*/README`（super-publisher 部分 skill 仅 SKILL.md）。
- 将 `AGENT.md` / `WORKFLOW_STANDARD.md` 在 `ARCHITECTURE.md` 中交叉引用。

### 步骤 7：代码风格基线落地
- 对 `knowledge-brain/`、`wewrite-main/toolkit` 低规范文件补类型注解与 docstring（目标对齐 `agent/`）。
- 统一导入风格：消除运行时 `sys.path` 注入裸 import，改为包相对/绝对导入（含 engine_mode 的 importlib 预加载改为规范包结构）。
- 运行 `ruff check --fix` + `ruff format` 全仓格式化（一次性大 PR，建议单独提交并 review）。

### 步骤 8：统一构建 / 运行入口
- 新增根 `Makefile` 或 `scripts/`：封装 `install / lint / test / format / run-pipeline / run-engine / run-publisher`。
- 统一 Python 启动脚本（替换散落的 `_*.py` 临时调试脚本，移入 `tools/` 或 `scripts/`）。

---

## 五、最终需达成的标准化规范目标（Goals）

| 维度 | 目标状态 | 验收标准 |
|------|---------|---------|
| **Python Lint/Format** | 全仓用 Ruff 统一 | 根 `pyproject.toml` 配置；`ruff check` 无 error；`ruff format` 已应用 |
| **TS Lint/Format** | ESLint flat config + Prettier | `eslint.config.js` + `.prettierrc`；`eslint .` 无 error |
| **编辑器统一** | `.editorconfig` | 跨 IDE 缩进/换行一致 |
| **提交门禁** | pre-commit 钩子 | 提交前自动 ruff/eslint + 格式修复 |
| **依赖一致** | 无跨项目版本分歧；无同环境冲突 | fastapi/pydantic/uvicorn/openai/requests 版本统一；playwright/patchright 二选一；`pip-audit` 无高危 CVE |
| **依赖声明完整** | 每个 Python 模块有 requirements（或纳入 workspace） | `agent/` `knowledge-brain/` `engine_mode/` 均能 `pip install -r` 复现 |
| **零源码副本** | lib/ 与 dist/openclaw 不再存副本 | `engine_mode` 合并加载不冲突；副本改为引用/构建产物 |
| **测试覆盖** | 核心模块有测试 + CI 门禁 | pytest 全绿；核心模块覆盖率 ≥ 60%；CI 跑 lint+test |
| **CI** | 每次 PR 自动 lint+test | `.github/workflows/ci.yml` 存在且绿 |
| **文档** | 根 ARCHITECTURE + CONTRIBUTING + 各模块 README | 新人可 30 分钟内按文档跑通 |
| **代码风格** | 类型注解 + docstring 基线统一 | knowledge-brain 等低规范模块达到 agent/ 级别基线 |
| **构建入口** | 统一 Makefile/scripts | 一条命令完成 install/lint/test/run |

---

## 六、风险与建议

1. **不要一次性全开 Ruff 全部规则**：避免 PR 爆炸，建议 error 级优先，渐进开启。
2. **engine_mode 副本是最大雷**：同进程多版本 fastapi/pydantic 可能在运行时静默出错，改造优先级最高。
3. **environment.yml 不可作基线**：它是 Anaconda 全量环境，需提炼出本项目真实依赖。
4. **保留 AI 助手友好的 `AGENTS.md`/`CLAUDE.md`**：video-transcriber 的 CLAUDE.md 是范本，应推广到各模块。
5. **改造前先固化现状**：先提交当前状态，再分步改造，每步独立可回滚。

---

*本方案为规划输出，未对任何文件做修改。确认后可由任一步骤开始执行。*
