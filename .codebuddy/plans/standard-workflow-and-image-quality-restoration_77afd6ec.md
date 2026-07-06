---
name: standard-workflow-and-image-quality-restoration
overview: 将视频→文章的完整内容生成流程整理为标准SOP文档，并将配图Prompt系统从英文新闻摄影风格回退升级到之前效果更好的中文军事视觉隐喻风格（断裂武士刀、国旗色调锁链拉扯、棋盘等），以恢复更高的图片表现力。
todos:
  - id: create-workflow-doc
    content: 创建 WORKFLOW_STANDARD.md 标准化流程文档，覆盖素材获取、AI写作、人工化改写、配图Prompt构建、配图生成、图文组装6大阶段及完整子步骤清单
    status: completed
  - id: add-cn-prompt-templates
    content: 在 cover_prompt_builder.py 中新增 _STYLE_TEMPLATES_CN（故事性封面模板）、_INLINE_TEMPLATES_CN（三级内文模板）、_VISUAL_GUIDE_CN（视觉风格指南常量），严格复刻 fresh_test_story_narrative 参考风格
    status: completed
  - id: add-prompt-lang-param
    content: 在 CoverPromptBuilder 新增 prompt_lang 参数，build_cover 和 build_inline_prompts 依据该参数选择中文或英文模板，并透传 target_lang 给 sanitize
    status: completed
    dependencies:
      - add-cn-prompt-templates
  - id: fix-sanitizer-keep-mode
    content: 修改 prompt_sanitizer.py 的 strip_chinese_labels，新增 keep_cn_visual 逻辑：当 target_lang='keep' 时仅剥离平台/频道标签，保留视觉描述正文
    status: completed
  - id: wire-ai-writer-pipeline
    content: 在 ai_writer.py 的 generate_cover_image/generate_inline_images/generate_all_images 中新增 prompt_lang 参数并透传，同步修改 pipeline.py 的 ImageGenStage.run()
    status: completed
    dependencies:
      - add-prompt-lang-param
      - fix-sanitizer-keep-mode
  - id: verify-end-to-end
    content: 用测试脚本验证中文 Prompt 模式端到端流程：build_all → sanitize(keep) → 样例输出，确保 Prompt 风格与 fresh_test_story_narrative 一致
    status: completed
    dependencies:
      - wire-ai-writer-pipeline
---

## 用户需求

### 需求一：标准化流程文档

将本次"日本与乌克兰合作后乌克兰联合中国制裁日本"事件的文章改写完整流程整理成标准化文档，以便后续处理视频链接时严格按照该文档执行全流程。要求覆盖从素材获取到最终配图稿件的每一个环节。

### 需求二：配图风格升级

当前生成的图片（20260704_220947）采用英文新闻摄影 Prompt 风格，视觉表现力较弱。需调整风格以恢复之前更高水准——严格参考 `fresh_test_story_narrative` 中的参考图片效果：

- 封面：断裂日本武士刀 + 日本国旗红日褪色 + 无人机剪影 + 芯片散落
- 配图①：导弹制导芯片拆解放大镜微距特写，印有模糊日文标识
- 配图②：日本地图剪影被国旗色锁链左右拉扯，破碎协议纸币飘落
- 配图③：国际象棋棋盘投影经纬线，日本旗棋子被推倒，星条旗/红旗棋子对峙

参考图片的视觉核心特征：**暗色基底+红金点缀+冷暖对冲色调、电影级侧光/聚光强明暗对比、横版16:9重心偏左、金属科技质感忌卡通化、四张图共用统一暗色基调与电影布光语言**。

### 预期产出

1. 项目根目录的 `WORKFLOW_STANDARD.md` 标准化流程文档
2. `cover_prompt_builder.py` 新增中文 Prompt 生成模式
3. 配套代码适配（`ai_writer.py`、`pipeline.py`、`prompt_sanitizer.py`）

## 技术方案

### 整体策略

**方案一（标准化文档）**：在项目根目录创建 `WORKFLOW_STANDARD.md`，基于已验证的完整流程（`outputs/20260704/20260704_220947/` 输出结果）编写。文档采用清单式+代码块格式，覆盖5个阶段12个子步骤。

**方案二（中文 Prompt 模式）**：在 `cover_prompt_builder.py` 中新增中文 Prompt 模板体系，与现有英文模板并存。通过 `prompt_lang` 参数控制切换。中文模板严格参考 `fresh_test_story_narrative` 的视觉语言：4张图共用统一暗色基调 + 电影级冷暖对冲布光 + 具体国家符号（而非抽象隐喻）+ 层叠复合构图。

### 实现架构

```
cover_prompt_builder.py
├── _VISUAL_METAPHOR_MAP (现有，不变)
├── _STYLE_TEMPLATES (现有英文，不变)
├── _INLINE_TEMPLATES (现有英文，不变)
├── ★ _STYLE_TEMPLATES_CN (新增：中文故事性封面模板)
├── ★ _INLINE_TEMPLATES_CN (新增：中文内文配图模板)
├── ★ _VISUAL_GUIDE_CN (新增：中文视觉风格指南常量)
└── CoverPromptBuilder
    ├── __init__(style, prompt_lang='en')  # 新增参数
    ├── build_cover()  # 依据 prompt_lang 选择模板
    └── build_inline_prompts()  # 依据 prompt_lang 选择模板
```

### 关键设计决策

1. **中文模板而非翻译回填**：不采用"先生成英文再翻译回中文"的方案，因为翻回来的中文会丢失特定的视觉公式化语言（如"暗色调为主，一道强烈侧光从右上角打下来，照亮断裂的刀刃"）。直接编写中文模板可精确控制视觉语言。

2. **prompt_lang 参数贯穿调用链**：

- `CoverPromptBuilder(style, prompt_lang='cn')` → `build_cover()` / `build_inline_prompts()` 使用中文模板
- `AIWriter.generate_cover_image(content_style='story_narrative', prompt_lang='cn')` → 透传给 Builder
- `AIWriter.generate_inline_images()` → 同样透传
- `AIWriter.generate_all_images()` → 接收并透传
- `pipeline.py ImageGenStage.run()` → 新增配置读取

3. **sanitize 适配**：`prompt_sanitizer.py` 的 `sanitize(prompt, target_lang='keep')` 已支持保留中文（只剥标签、不转英文），但 `strip_chinese_labels()` 会误删中文 Prompt 中的视觉描述正文。需要微调：当 `target_lang='keep'` 时，仅剥离平台/频道标签（"今日头条""微头条""军事类配图"），保留视觉描述（"画面主体：""背景""光影""色调"开头的内容）。

### 目录结构

```
d:/AIToutiao/
├── WORKFLOW_STANDARD.md          # [NEW] 标准化流程文档
├── wewrite-main/toolkit/
│   ├── cover_prompt_builder.py   # [MODIFY] 新增中文 Prompt 模板和 prompt_lang 参数
│   └── prompt_sanitizer.py       # [MODIFY] strip_chinese_labels 新增 keep_cn_visual 模式
├── toutiao-auto-publisher/backend/
│   └── ai_writer.py              # [MODIFY] generate_cover_image/generate_inline_images/generate_all_images 新增 prompt_lang 参数
└── pipeline.py                   # [MODIFY] ImageGenStage 调用时传入 prompt_lang
```