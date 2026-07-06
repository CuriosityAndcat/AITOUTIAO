---
name: diagnose-and-fix-pipeline-issues
overview: 诊断当前流水线四大问题的根本原因，并重写优化相关提示词和代码模块：配图质量下降、遗留问题未修复、文章风格偏差、缺少配图嵌入。
todos:
  - id: fix-metaphor-map
    content: 重写 cover_prompt_builder.py 的 _VISUAL_METAPHOR_MAP（具体化中文→英文映射）、_INLINE_TEMPLATES（新闻战地摄影风）、_build_inline_visual_context（单一场景而非碎片拼接）
    status: completed
  - id: fix-prompt-sanitizer
    content: 增强 prompt_sanitizer.py 的 to_english_visual 翻译映射，新增中译英具体视觉关键词表，避免丢失视觉细节
    status: completed
  - id: strengthen-humanize
    content: 重写 ai_writer.py 的 HUMANIZE_SYSTEM_PROMPT，新增改写率硬性指标（30%+改写率、段落数翻倍、句首不重复、个人态度标记）、输出前自检清单
    status: completed
  - id: enhance-story-narrative
    content: 增强 ai_writer.py 的 SYSTEM_PROMPT_STORY_NARRATIVE，新增河南方言词库、评书话术大全、比喻降维强制规则、情绪三段式要求、口头禅列表
    status: completed
  - id: inject-images-to-article
    content: 修改 pipeline.py 的 ImageGenStage，新增 _inject_images_into_article() 方法，在图片生成后将封面和内文配图引用回写到 markdown 文件
    status: completed
  - id: verify-all-fixes
    content: 使用测试链接重新运行完整流水线，对比修复前后四维度输出质量
    status: completed
    dependencies:
      - fix-metaphor-map
      - fix-prompt-sanitizer
      - strengthen-humanize
      - enhance-story-narrative
      - inject-images-to-article
---

## 产品概述

针对当前 AI 配图流水线的四大输出质量问题进行根因诊断和系统性修复。

## 四个核心问题及根因

### 问题① 配图质量退化

**现象**：首次中文 prompt 产出具体新闻配图（断裂武士刀/芯片拆解/地缘锁链/战略棋局），清洗后英文 prompt 变成抽象杂志风（孤岛剪影/迷雾/模糊对峙）。
**根因链**：

- `cover_prompt_builder.py` 的 `_VISUAL_METAPHOR_MAP` 将"日本"映射为 `a solitary island nation silhouette emerging from mist`，将"武器"映射为 `precision mechanical components under dramatic light` —— 所有中文具体关键词被替换为西方编辑杂志风的抽象隐喻
- `_INLINE_TEMPLATES` 使用"editorial photograph""magazine feature cover"语体，这是西方生活方式杂志而非中文新闻/战地摄影风格
- `_build_inline_visual_context()` 用逗号拼接 2-3 个抽象概念成碎片化场景（如 `classified document under magnifying glass, disassembled precision components on metallic inspection table`），AI 模型难以将碎片概念融合为单一连贯画面
- `prompt_sanitizer.py` 的 `to_english_visual()` 检测到 prompt 已是英文则直接返回，无法挽留在上层已被销毁的视觉细节

### 问题② humanize 改写率仅 0.6%

**现象**：1471 字文章，`01_ai_raw.md` 与 `02_humanized.md` 仅差异 9 个字符。
**根因**：

- `ai_writer.py` 第575-663行 HUMANIZE 提示词使用"必须消灭"但后面跟的是"→ 删掉，用自然转折替代"，这是建议语气而非强制量规
- 没有改写率硬性要求（如"每 100 字至少改动 30 处"）
- 没有结构破坏强制规则（如"原文是 6 段的，输出必须拆成 9 段以上"）
- temperature=0.8 但没有相应的 prompt 强制力做保障

### 问题③ story_narrative 缺乏"听风的蚕"味道

**现象**：输出有评书框架但缺少河南方言、茶馆说书人顿挫、生动比喻、情绪曲线。
**根因**：

- SYSTEM_PROMPT_STORY_NARRATIVE 只有标语（"口语化极强""用日常比喻解释"）但没有给出具体方言词库
- 缺少比喻降维公式（当前说"战略威慑→我手里有家伙"，但没有要求每 200 字一个比喻的硬性规则）
- 情绪没有量化要求：只说"情绪饱满但不浮夸"，没有要求"三段情绪起伏曲线"

### 问题④ 图片未回写到文章

**现象**：微头条最终 markdown 没有图片引用。
**根因**：`pipeline.py` 第693-701行 ImageGenStage 只将图片路径写入 `state.outputs`，但没有回写到 `generated_content` 或更新 markdown 文件。WriteStage 在先，ImageGenStage 在后，写阶段不会等待后续结果。

## 核心功能

- 修复 cover_prompt_builder 的隐喻映射表，将抽象杂志风替换为具体新闻战地摄影风
- 修复 prompt_sanitizer 保留视觉细节
- 重写 HUMANIZE 提示词为强制规则，增加改写率硬性要求
- 重写 STORY_NARRATIVE 提示词为具体方言词库+比喻公式+情绪曲线
- 在 ImageGenStage 增加图片回写步骤

## 技术栈

- 后端：Python 3，现有项目无需新增依赖
- 图片生成：复用 `wewrite-main/toolkit/image_gen.py`（9 provider 自动 fallback）
- 文本处理：正则表达式 + 提示词工程

## 实现方案

### 策略总览

四项修复涉及 4 个文件（`cover_prompt_builder.py`, `prompt_sanitizer.py`, `ai_writer.py`, `pipeline.py`），均为提示词/映射/模板层面的修改，不改变架构。

### 修复① 配图质量 — `cover_prompt_builder.py` + `prompt_sanitizer.py`

**核心策略**：将抽象隐喻映射改为具体场景映射，将 magazine editorial 模板改为新闻/战地摄影模板。

**具体修改**：

1. `_VISUAL_METAPHOR_MAP` 重写核心词条（第30-84行）：

- `"日本"` → 不再是 `a solitary island nation silhouette emerging from mist`，改为 `a cracked red circle (Japanese flag motif) fading against a dark stormy sky, symbolic of national decline`
- `"武器"` → 不再是 `precision mechanical components under dramatic light`，改为 `weapon components laid out on an inspection table under harsh fluorescent lighting, forensic photography style`
- `"芯片"` → `extreme macro of a microchip circuit board, gold traces and silicon die visible under magnifying lens, industrial espionage aesthetic`
- `"拆解"` → `disassembled military hardware components tagged with evidence markers on a metal workbench, investigative journalism photography`
- `"博弈"` → `overhead shot of a geopolitical chess board, pieces cast dramatic shadows across a world map projection, dim war-room lighting`
- `"对峙"` → `two opposing forces visualized as metallic chains pulling a fractured national symbol in opposite directions, dramatic tension`
- 新增词条：`"制裁"→`、`"制裁"→`、`"无人机"→`

2. `_INLINE_TEMPLATES`（第127-148行）重写三级模板为三种场景类型：

- index=0：`A forensic photojournalism close-up of {scene}. Harsh key light from above, evidence-marker labels visible, metallic surfaces with wear marks, high contrast news documentary style, 8K`
- index=1：`A dramatic news wire photograph of {scene}. Strong directional lighting casting long shadows, tension visible in the composition, photojournalism color grading with crushed blacks, 8K`
- index=2：`An overhead strategic map-room photograph of {scene}. Top-down documentary angle, dim atmospheric war-room lighting with selective spot illumination on key elements, intelligence briefing aesthetic, 8K`

3. `_build_inline_visual_context()`（第343-383行）修复碎片化：不再拼接多个概念为 `"concept1, concept2"`，而是取**最高匹配度**的单一隐喻作为场景核心，确保生成单一连贯画面。

4. `prompt_sanitizer.py` 的 `to_english_visual()`（第100-119行）：增强中文→英文翻译映射表，确保当 prompt 含中文时提取具体视觉元素翻译，而非回退到通用骨架。

### 修复② humanize 改写率 — `ai_writer.py`

**核心策略**：将 HUMANIZE_SYSTEM_PROMPT 从"建议"改为"强制作业清单"。

**具体修改**（第575-663行替换）：

- 新增"改写硬性指标"区块：
- 每 100 字至少 3 处词语替换（"进行→搞""实施→干了""呈现→看着像"）
- 段落数必须翻倍（原文 N 段 → 输出 2N 段以上）
- 至少 5 处句首不同（不重复使用同一句首词）
- 必须加入 3 处个人态度标记
- 新增"输出前自检清单"：逐项打勾，未通过则重新改写
- 新增"改写率要求"：输出与原文重复率不得超过 70%（即至少 30% 实质性改写）

### 修复③ story_narrative 风格 — `ai_writer.py`

**核心策略**：将抽象的风格描述替换为具体的语言资产库。

**具体修改**（第236-309行增强）：

- SYSTEM_PROMPT_STORY_NARRATIVE 新增"河南方言词库"：中、咋整、恁、家伙、俺、得劲、不瓤、乖乖、了不得了
- 新增"评书话术大全"：话说这...、这一回俺给恁讲讲...、列位看官...、啪！...、且听下回分解
- 新增"比喻降维强制规则"：每 200 字至少出现一个用日常事物解释军事/政治概念的比喻，比喻必须用"就像...""好比...""等于说..."
- 新增"情绪三段式要求"：开场悬念（紧张/震惊）→ 中段揭秘（愤怒/讽刺/拍案）→ 收尾扣子（意味深长/期待）
- 新增"必须使用口头禅"：哎哟喂、您猜怎么着、说到这儿、高啊、我服了

### 修复④ 图片回写 — `pipeline.py`

**核心策略**：在 ImageGenStage.run() 末尾增加 `_inject_images_into_article()` 方法。

**具体修改**（第619-730行附近）：

- 新增方法 `_inject_images_into_article()`：
- 读取已有的 markdown 文件
- 在文章开头插入封面图引用（`![封面](images/xxx.png)`）
- 在文章段落中按叙事节点位置插入内文配图引用
- 覆盖写回原 markdown 文件
- 同时更新 `state.outputs["generated_content"]` 为含图版本
- 在 `run()` 方法的 `return True` 之前调用该方法

## 实施说明

### 向后兼容

- 所有修改均为提示词/模板/映射层面的内容替换，不改变函数签名或调用接口
- `pipeline.py` 新增方法不影响现有流程

### 验证方式

- 使用同一测试链接 `https://v.douyin.com/1TENCBpLB-k/` 对比修复前后输出
- 验证配图 prompt 具体性（是否出现具体场景描述而非抽象隐喻）
- 验证 humanize 改写率（diff 01_ai_raw.md vs 02_humanized.md 是否显著提升）
- 验证文章 markdown 是否包含图片引用

## 目录结构

```
d:/AIToutiao/
├── wewrite-main/toolkit/
│   ├── cover_prompt_builder.py    # [MODIFY] 重写 _VISUAL_METAPHOR_MAP 具体化、重写 _INLINE_TEMPLATES 新闻风、修复 _build_inline_visual_context 单一场景
│   └── prompt_sanitizer.py        # [MODIFY] 增强 to_english_visual 的翻译映射，保留视觉细节
├── toutiao-auto-publisher/backend/
│   └── ai_writer.py               # [MODIFY] 重写 HUMANIZE_SYSTEM_PROMPT 为强制规则、增强 SYSTEM_PROMPT_STORY_NARRATIVE 加入方言词库和比喻公式
└── pipeline.py                    # [MODIFY] ImageGenStage 新增 _inject_images_into_article() 回写方法
```