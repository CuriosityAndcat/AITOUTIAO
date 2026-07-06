---
name: toutiao-benchmark-style-generation
overview: 基于今日头条三大头部军事/时政账号（听风的蚕、牛弹琴、静思有我）的写作风格深度分析，构建 6 种对应风格，批量生成示例文章，输出对标选型文档。
todos:
  - id: update-enum-desc
    content: 更新 models.py 中 ContentStyle 枚举的描述，对齐对标账号映射关系
    status: completed
  - id: add-five-prompts
    content: 在 ai_writer.py 中新增 5 组风格的 System Prompt 和 User Prompt 常量，定义共享军事红线模板和 STYLE_ROUTER 字典
    status: completed
    dependencies:
      - update-enum-desc
  - id: refactor-toutie
    content: 重构 generate_toutie 方法，用 STYLE_ROUTER 字典路由替代 if/elif 链
    status: completed
    dependencies:
      - add-five-prompts
  - id: create-batch-script
    content: 创建 _batch_style_demo.py 批量生成脚本，以统一话题循环 6 种风格调用 AIWriter
    status: completed
    dependencies:
      - refactor-toutie
  - id: generate-options-doc
    content: 运行批量脚本，将 6 篇生成结果汇编为 STYLE_OPTIONS.md 风格选型文档
    status: completed
    dependencies:
      - create-batch-script
---

## 产品概述

基于对今日头条三大对标账号（听风的蚕、牛弹琴、静思有我）的真实写作风格深度分析，构建6种差异化微头条写作风格，每种风格包含专属 System Prompt 和 User Prompt。通过 DeepSeek API 批量生成风格示例文章，最终汇编为风格选型文档。

## 对标分析结果

### 听风的蚕（1800万+粉丝，军事评书型）

- **风格DNA**：用评书节奏讲军事，设悬念→铺背景→起冲突→揭真相→留扣子
- **语言特征**：口语化极强，"咱们""这家伙""哎哟喂"，河南方言韵味
- **温度设定**：0.85（需要更高的创造性来模拟评书节奏感）

### 牛弹琴（篇篇10万+，冷静克制型）

- **风格DNA**：事实为主、观点为辅，2000字黄金篇幅，幽默诙谐但不泛滥
- **语言特征**：像朋友聊天、娓娓道来、在情绪泛滥的舆论场中提供"冷静的声音"
- **温度设定**：0.6（需要保持克制和准确性）

### 静思有我（硬核论证型）

- **风格DNA**：提出问题→多角度分析→证据支撑→深度结论，逻辑链严密
- **语言特征**：冷静理性、重逻辑、"零基础看懂全球"的降维能力
- **温度设定**：0.5（最小化随机性，保证逻辑严谨）

## 核心任务

- 新增5组风格 Prompt（对标账号3组 + 快讯速报 + 互动讨论），复用军事红线模板
- 用字典路由（STYLE_ROUTER）替代 if/elif 链，实现 O(1) 风格切换
- 批量生成6篇不同风格示例文章
- 汇编 Markdown 风格选型文档

## Tech Stack

- 语言：Python 3.12
- AI SDK：openai（兼容 DeepSeek API）
- 模型：deepseek-chat
- 框架：FastAPI（已有）

## 实现方案

### 六种风格 Prompt 矩阵

| ContentStyle | 对标 | System Prompt | User Prompt | Temp |
| --- | --- | --- | --- | --- |
| military | 现有专属风格 | SYSTEM_PROMPT_MILITARY（已有） | MILITARY_TOUTIE_PROMPT（已有） | 0.7 |
| story_narrative | 听风的蚕 | SYSTEM_PROMPT_STORY_NARRATIVE（新增） | STORY_NARRATIVE_PROMPT（新增） | 0.85 |
| sharp_commentary | 牛弹琴 | SYSTEM_PROMPT_SHARP_COMMENTARY（新增） | SHARP_COMMENTARY_PROMPT（新增） | 0.6 |
| data_list | 静思有我 | SYSTEM_PROMPT_DATA_LIST（新增） | DATA_LIST_PROMPT（新增） | 0.5 |
| flash_news | 头条快讯 | SYSTEM_PROMPT_FLASH_NEWS（新增） | FLASH_NEWS_PROMPT（新增） | 0.5 |
| discussion | 社区运营 | SYSTEM_PROMPT_DISCUSSION（新增） | DISCUSSION_PROMPT（新增） | 0.7 |


### STYLE_ROUTER 字典路由

将 `generate_toutie` 中的 if/elif 二元分支替换为字典查找：

```python
STYLE_ROUTER: dict[ContentStyle, tuple[str|None, str, float]] = {
    ContentStyle.MILITARY: (SYSTEM_PROMPT_MILITARY, MILITARY_TOUTIE_PROMPT, 0.7),
    ContentStyle.GENERAL: (None, TOUTIE_PROMPT, 0.7),
    ContentStyle.STORY_NARRATIVE: (SYSTEM_PROMPT_STORY_NARRATIVE, STORY_NARRATIVE_PROMPT, 0.85),
    ContentStyle.SHARP_COMMENTARY: (SYSTEM_PROMPT_SHARP_COMMENTARY, SHARP_COMMENTARY_PROMPT, 0.6),
    ContentStyle.DATA_LIST: (SYSTEM_PROMPT_DATA_LIST, DATA_LIST_PROMPT, 0.5),
    ContentStyle.FLASH_NEWS: (SYSTEM_PROMPT_FLASH_NEWS, FLASH_NEWS_PROMPT, 0.5),
    ContentStyle.DISCUSSION: (SYSTEM_PROMPT_DISCUSSION, DISCUSSION_PROMPT, 0.7),
}
```

`generate_toutie` 简化为：

1. 查 `STYLE_ROUTER[content_style]` 获取三元组
2. 用获取的 system/user/temperature 调用 `_call_ai`

### 军事红线复用

所有军事类风格的 System Prompt 末尾统一追加以下共享段落：

- "军事真实性红线"（禁止编造武器数据、虚构事件）
- "国家立场红线"（禁止抹黑中国、使用西方叙事框架）

实现方式：定义 `MILITARY_RED_LINES` 常量，各 System Prompt 通过字符串拼接引用。

### 关键设计决策

1. **字典路由替代 if/elif**：O(1) 查找，新增风格只需追加一行，无需修改控制流
2. **Temperature 按风格微调**：评书型 0.85（创造性），克制冷 0.6（准确性），论证型 0.5（逻辑严谨）
3. **共享红线模板**：DRY 原则，所有风格统一遵守军事真实性+国家立场红线

## Agent Extensions

### Skill

- **find-skills**
- Purpose: 确认是否需要额外技能支持 Prompt 调优或批量测试
- Expected outcome: 如无需要则跳过，确保不遗漏工具链

### SubAgent

- **code-explorer**
- Purpose: 批量脚本执行前验证项目目录结构和依赖完整性
- Expected outcome: 确认所有导入路径存在、依赖无缺失