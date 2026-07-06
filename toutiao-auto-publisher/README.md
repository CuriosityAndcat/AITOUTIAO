# 今日头条自动发布工具

AI 自动写作 + Playwright 浏览器自动化发布，一站式完成今日头条微头条和文章的创作与发布。

## 功能特性

- 🤖 **AI 自动写作**：输入主题/关键词，自动生成微头条（200-1000字）或文章（1000-5000字）
- 🌐 **浏览器自动化发布**：Playwright 控制 Chrome，自动填写标题、正文、封面并点击发布
- 🔐 **Cookie 持久化登录**：扫码登录一次，后续自动复用，无需重复登录
- 🖥️ **Web 管理界面**：简洁的单页面操作界面，流程清晰
- 📊 **任务状态追踪**：实时查看发布进度和操作日志

## 快速开始

### 1. 安装依赖

```bash
cd d:\AIToutiao\toutiao-auto-publisher\backend
pip install -r requirements.txt
```

### 2. 安装 Playwright 浏览器

```bash
playwright install chrome
```

### 3. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 AI API Key：

```bash
cp .env.example .env
# 编辑 .env 文件，填入 AI_API_KEY
```

### 4. 启动服务

```bash
cd backend
python main.py
```

访问 `http://localhost:8000` 打开 Web 界面。

### 5. 首次登录

在 Web 界面点击「重新登录」，扫码登录今日头条创作者后台。登录成功后 Cookie 会自动保存。

## 使用流程

1. **选择内容类型**：微头条（短文）或文章（长文）
2. **输入主题**：输入关键词或主题描述
3. **AI 生成**：点击「AI 生成内容」，等待生成完成
4. **预览编辑**：检查生成的内容，可手动修改
5. **发布设置**：上传封面（可选），确认发布选项
6. **一键发布**：点击「开始发布」，浏览器自动完成发布

## 项目结构

```
toutiao-auto-publisher/
├── backend/
│   ├── main.py              # FastAPI 后端主应用
│   ├── ai_writer.py         # AI 内容生成模块
│   ├── publisher_service.py # 发布服务（复用现有代码）
│   ├── config.py            # 配置管理
│   ├── models.py            # Pydantic 数据模型
│   └── requirements.txt     # Python 依赖
├── frontend/
│   ├── index.html           # Web 界面
│   └── app.js              # 前端交互逻辑
├── .env                     # 环境变量配置
└── README.md
```

## 注意事项

- 发布时浏览器会自动打开，**请勿操作该浏览器窗口**，以免干扰自动化流程
- Cookie 有效期约 7 天，过期后需重新登录
- 建议使用真实 Chrome 浏览器（非 headless 模式）以获得最佳兼容性
- 今日头条对发布频率有一定限制，建议勿过于频繁发布

## 技术栈

- **后端**：FastAPI + Playwright + OpenAI SDK
- **前端**：Vanilla JS + Tailwind CSS
- **浏览器自动化**：patchright（Playwright 反爬虫增强版）
