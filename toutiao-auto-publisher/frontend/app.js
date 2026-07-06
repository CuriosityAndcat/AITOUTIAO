/*
今日头条自动发布工具 — 前端交互逻辑
*/

// ===== 全局状态 =====
let state = {
    contentType: 'article',   // 'toutie' | 'article'
    generatedTitle: '',
    generatedContent: '',
    coverPath: null,
    taskId: null,
    loginChecked: false,
};

// ===== API 基础地址 =====
const API = '';  // 同源，无需指定

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    checkLoginStatus();
    setContentType('article');
    bindEvents();
});

function bindEvents() {
    // 标题字数统计
    const titleInput = document.getElementById('titleInput');
    if (titleInput) {
        titleInput.addEventListener('input', () => {
            const len = titleInput.value.length;
            document.getElementById('titleCharCount').textContent = `${len}/30`;
        });
    }

    // 主题输入框回车触发生成
    const topicInput = document.getElementById('topicInput');
    if (topicInput) {
        topicInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                generateContent();
            }
        });
    }
}

// ===== 登录状态 =====
async function checkLoginStatus() {
    try {
        const res = await fetch(`${API}/api/login-status`);
        const data = await res.json();
        const el = document.getElementById('loginStatus');
        if (data.authenticated) {
            el.innerHTML = `<span class="w-2 h-2 rounded-full bg-green-400 pulse-dot"></span><span class="text-green-100">已登录${data.auth_age_hours ? `（${data.auth_age_hours}h前）` : ''}</span>`;
            el.className = 'flex items-center space-x-2 bg-green-500/30 px-3 py-1.5 rounded-full text-sm';
        } else {
            el.innerHTML = `<span class="w-2 h-2 rounded-full bg-red-400 pulse-dot"></span><span>未登录</span>`;
            el.className = 'flex items-center space-x-2 bg-red-500/30 px-3 py-1.5 rounded-full text-sm';
        }
        if (data.warning) {
            console.warn('登录警告：', data.warning);
        }
    } catch (e) {
        console.error('登录状态检查失败：', e);
    }
}

async function triggerLogin() {
    const btn = document.getElementById('btnLogin');
    btn.textContent = '等待扫码...';
    btn.disabled = true;
    addLog('🔐 正在打开浏览器，请扫码登录今日头条...');

    try {
        const res = await fetch(`${API}/api/login`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            addLog('✅ 登录成功！');
            checkLoginStatus();
        } else {
            addLog(`❌ 登录失败：${data.message}`);
        }
    } catch (e) {
        addLog(`❌ 登录接口调用失败：${e.message}`);
    } finally {
        btn.textContent = '重新登录';
        btn.disabled = false;
    }
}

// ===== 内容类型切换 =====
function setContentType(type) {
    state.contentType = type;
    const btnToutie = document.getElementById('btnToutie');
    const btnArticle = document.getElementById('btnArticle');
    const charHint = document.getElementById('charHint');

    if (type === 'toutie') {
        btnToutie.className = 'px-4 py-2 rounded-md text-sm font-medium transition bg-white shadow-sm text-indigo-600';
        btnArticle.className = 'px-4 py-2 rounded-md text-sm font-medium transition';
        charHint.textContent = '微头条模式 · 建议 200-1000 字';
        document.getElementById('maxCharsInput').value = 1000;
    } else {
        btnArticle.className = 'px-4 py-2 rounded-md text-sm font-medium transition bg-white shadow-sm text-indigo-600';
        btnToutie.className = 'px-4 py-2 rounded-md text-sm font-medium transition';
        charHint.textContent = '文章模式 · 建议 1000-5000 字';
        document.getElementById('maxCharsInput').value = 5000;
    }
}

// ===== AI 生成内容 =====
async function generateContent() {
    const topic = document.getElementById('topicInput').value.trim();
    if (!topic) {
        alert('请输入主题或关键词');
        return;
    }

    const btn = document.getElementById('btnGenerate');
    btn.classList.add('loading');
    btn.innerHTML = '<span class="animate-spin">⏳</span> AI 生成中...';

    addLog(`🤖 开始生成${state.contentType === 'toutie' ? '微头条' : '文章'}内容，主题：「${topic}」`);

    try {
        const res = await fetch(`${API}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic,
                content_type: state.contentType,
                max_chars: parseInt(document.getElementById('maxCharsInput').value) || undefined,
                tone: document.getElementById('toneSelect').value,
            }),
        });
        const data = await res.json();

        if (data.success) {
            state.generatedTitle = data.title || '';
            state.generatedContent = data.content;
            document.getElementById('titleInput').value = data.title || '';
            document.getElementById('contentInput').value = data.content;
            document.getElementById('charCount').textContent = `${data.char_count} 字`;
            updateTitleCharCount();
            addLog(`✅ 内容生成成功，共 ${data.char_count} 字`);

            // 切换到预览面板
            showPanel('panel2');
            setStep(2);
        } else {
            addLog(`❌ 生成失败：${data.error}`);
            alert(`生成失败：${data.error}`);
        }
    } catch (e) {
        addLog(`❌ 接口调用失败：${e.message}`);
        alert(`接口调用失败：${e.message}\n\n请确保后端服务已启动（python main.py）`);
    } finally {
        btn.classList.remove('loading');
        btn.innerHTML = '<span>✨</span><span>AI 生成内容</span>';
    }
}

function updateTitleCharCount() {
    const len = document.getElementById('titleInput').value.length;
    document.getElementById('titleCharCount').textContent = `${len}/30`;
}

// ===== 面板切换 =====
function showPanel(panelId) {
    ['panel1', 'panel2', 'panel3', 'panel4'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
    });
    document.getElementById(panelId).classList.remove('hidden');
}

function setStep(step) {
    for (let i = 1; i <= 4; i++) {
        const el = document.getElementById(`step${i}`);
        el.className = 'flex items-center space-x-2 border-b-2 border-transparent pb-2 text-gray-400';
        el.querySelector('span:first-child').className = 'w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-bold';
    }
    for (let i = 1; i <= step; i++) {
        const el = document.getElementById(`step${i}`);
        if (i < step) {
            el.className = 'step-done flex items-center space-x-2 border-b-2 pb-2';
        } else {
            el.className = 'step-active flex items-center space-x-2 border-b-2 pb-2';
        }
    }
}

function goBack() {
    showPanel('panel1');
    setStep(1);
}

function goToPublish() {
    // 保存编辑后的标题和内容
    state.generatedTitle = document.getElementById('titleInput').value;
    state.generatedContent = document.getElementById('contentInput').value;
    showPanel('panel3');
    setStep(3);
}

function goBackToEdit() {
    showPanel('panel2');
    setStep(2);
}

// ===== 封面上传 =====
function handleCoverUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // 前端只做预览，实际上传需要后端接口
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('coverImg').src = e.target.result;
        document.getElementById('coverPreview').classList.remove('hidden');
        document.getElementById('coverDropZone').classList.add('hidden');
    };
    reader.readAsDataURL(file);

    // 保存文件引用（实际发布时需要通过后端上传）
    state.coverFile = file;
}

// ===== 开始发布 =====
async function startPublish() {
    const title = document.getElementById('titleInput').value.trim();
    const content = document.getElementById('contentInput').value.trim();

    if (!title || !content) {
        alert('标题和内容不能为空');
        return;
    }

    if (title.length < 2 || title.length > 30) {
        alert('标题长度需要在 2-30 字之间');
        return;
    }

    showPanel('panel4');
    setStep(4);

    const btn = document.getElementById('btnPublish');
    btn.classList.add('loading');

    addLog('🚀 正在启动发布任务...');

    try {
        const res = await fetch(`${API}/api/publish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                content,
                cover_path: state.coverPath,
                auto_publish: document.getElementById('autoPublishCheck').checked,
                content_type: state.contentType,
            }),
        });
        const data = await res.json();

        if (data.success) {
            state.taskId = data.task_id;
            addLog(`📋 任务已创建，ID：${data.task_id}`);
            // 开始轮询任务状态
            pollTaskStatus(data.task_id);
        } else {
            addLog(`❌ 发布请求失败：${data.message}`);
        }
    } catch (e) {
        addLog(`❌ 发布接口调用失败：${e.message}`);
    }
}

// ===== 轮询任务状态 =====
function pollTaskStatus(taskId) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`${API}/api/task/${taskId}`);
            const task = await res.json();

            // 更新进度（根据状态）
            if (task.status === 'running') {
                setProgress(50, task.message || '正在发布中...');
                addLog(`⏳ ${task.message}`);
            } else if (task.status === 'success') {
                clearInterval(interval);
                setProgress(100, '发布成功！');
                addLog(`🎉 ${task.message}`);
                showPublishResult(true, task.message);
            } else if (task.status === 'failed') {
                clearInterval(interval);
                setProgress(100, '发布失败');
                addLog(`❌ ${task.message}`);
                showPublishResult(false, task.message);
            }
        } catch (e) {
            addLog(`⚠️ 状态查询失败：${e.message}`);
        }
    }, 2000);

    // 最多轮询 5 分钟
    setTimeout(() => clearInterval(interval), 300000);
}

// ===== 进度和日志 =====
function setProgress(percent, text) {
    document.getElementById('progressBar').style.width = `${percent}%`;
    document.getElementById('progressPercent').textContent = `${percent}%`;
    document.getElementById('progressText').textContent = text;
}

function addLog(msg) {
    const logArea = document.getElementById('logArea');
    const time = new Date().toLocaleTimeString('zh-CN');
    logArea.innerHTML += `<div>[${time}] ${msg}</div>`;
    logArea.scrollTop = logArea.scrollHeight;
}

function showPublishResult(success, message) {
    const el = document.getElementById('publishResult');
    el.classList.remove('hidden');
    el.className = `p-4 rounded-xl text-center text-sm font-medium ${success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`;
    el.textContent = message;
}

// ===== 重置 =====
function resetAll() {
    state = {
        contentType: 'article',
        generatedTitle: '',
        generatedContent: '',
        coverPath: null,
        taskId: null,
        loginChecked: false,
    };
    document.getElementById('topicInput').value = '';
    document.getElementById('titleInput').value = '';
    document.getElementById('contentInput').value = '';
    document.getElementById('coverPreview').classList.add('hidden');
    document.getElementById('coverDropZone').classList.remove('hidden');
    document.getElementById('publishResult').classList.add('hidden');
    document.getElementById('logArea').innerHTML = '';
    setProgress(0, '准备中...');
    showPanel('panel1');
    setStep(1);
    setContentType('article');
}

// ===== 历史任务 =====
async function loadTaskHistory() {
    try {
        const res = await fetch(`${API}/api/tasks?limit=5`);
        const tasks = await res.json();
        const container = document.getElementById('taskHistory');
        if (tasks.length === 0) {
            container.innerHTML = '<div class="text-xs text-gray-400">暂无历史任务</div>';
            return;
        }
        container.innerHTML = tasks.map(t => `
            <div class="flex items-center justify-between p-2 bg-gray-50 rounded-lg text-xs">
                <span class="font-medium">${t.task_type === 'publish' ? '🚀 发布' : '✍️ 生成'} ${t.task_id}</span>
                <span class="${t.status === 'success' ? 'text-green-600' : t.status === 'failed' ? 'text-red-600' : 'text-yellow-600'}">${t.status}</span>
            </div>
        `).join('');
    } catch (e) {
        console.error('加载历史任务失败：', e);
    }
}
