# 🍳 私人厨房 AI 助手

基于 **Vue3 + Vite + Element Plus + Pinia + Vue Router**（前端）与 **Node.js Express + SQLite**（后端）的全栈厨房 AI 问答应用。

支持：**文字问答 · 图片识食 · 联网搜菜谱 · 厨房记忆**

---

## ★ 通义千问 API 配置（必看）

**配置文件路径：项目根目录的 `.env` 文件**（`backend/config/ai.config.js` 会自动读取它）

### 第一步：获取 API Key

1. 打开阿里云 DashScope 控制台：https://dashscope.console.aliyun.com/apiKey
2. 登录阿里云账号，点击「创建 API Key」
3. 复制生成的 Key（格式类似 `sk-xxxxxxxx`）

### 第二步：在 .env 中填入 API Key

在项目根目录创建（或编辑）`.env` 文件，写入你的 Key：

```ini
DASHSCOPE_API_KEY=sk-你的千问API密钥
```

> 可选配置（有默认值，一般不用改）：
>
> ```ini
> DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
> ```

### 第三步：确认模型开通

在 DashScope 控制台确认已开通以下模型（有免费额度）：

| 用途 | 配置字段 | 推荐模型 |
|------|----------|----------|
| 文字对话 | `model` | `qwen-plus` / `qwen-turbo` |
| 图片识食 | `visionModel` | `qwen-vl-plus` |
| 联网搜菜谱 | `enableSearch: true` | 随文字模型启用 |

> 业务代码**不会硬编码**任何 API 信息，全部从项目根目录的 `.env` 文件读取。

---

## 怎么操作

### 1. 识图做菜（图片上传 → 识别 → 搜菜谱）

1. 启动前后端（见下方「启动项目」）
2. 浏览器打开 http://localhost:5173
3. 点击顶部导航 **「识图做菜」** 或首页 **「识图做菜」** 按钮
4. 上传/拖拽一张包含食材的照片
5. 点击 **「开始识图 & 搜菜谱」**
6. 等待约 10~30 秒，系统会：
   - 用 **千问视觉模型** 识别图片中的食材
   - 自动 **存入厨房记忆**
   - 用 **千问联网搜索** 查找这些食材能做什么菜
7. 可点击 **「继续追问小厨」** 跳转到聊天页深入询问

### 2. AI 智能问答

1. 点击 **「AI 问答」**
2. 输入厨房相关问题，Enter 发送
3. 对话历史自动保存，左侧可查看/删除
4. **记忆功能**：之前识图识别的食材会自动注入对话，小厨会结合记忆给个性化建议

### 3. 查看厨房记忆

在 **识图做菜** 页面右侧「我的厨房记忆」面板：
- 自动记录每次识图的食材
- 聊天时会自动读取这些记忆
- 可手动删除单条记忆

---

## 安装依赖

```bash
# 后端
cd backend
npm install

# 前端
cd frontend
npm install
```

---

## 启动项目

**两个终端分别运行：**

```bash
# 终端 1 — 后端 (http://localhost:3001)
cd backend
npm run dev

# 终端 2 — 前端 (http://localhost:5173)
cd frontend
npm run dev
```

浏览器访问：**http://localhost:5173**

> 📖 **不懂代码？** 请阅读 [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) — 零基础完整解读每一部分代码。

---

## 项目目录

```
mycooker1/
├── backend/
│   ├── config/ai.config.js        从 .env 读取 API 配置（一般不用改）
│   ├── routes/
│   │   ├── chat.js                文字对话（含记忆）
│   │   ├── history.js             对话历史
│   │   ├── image.js               图片识图 + 搜菜谱
│   │   └── memory.js              厨房记忆
│   ├── services/
│   │   ├── aiService.js           AI 请求转发 + 联网搜索
│   │   ├── visionService.js       千问视觉识图
│   │   └── memoryService.js       记忆存储
│   └── uploads/                   上传图片目录
└── frontend/
    └── src/
        ├── views/
        │   ├── Home.vue           首页
        │   ├── Chat.vue           AI 问答
        │   └── ImageAnalyze.vue   识图做菜
        └── components/
            ├── ImageUpload.vue    图片上传
            └── MemoryPanel.vue    记忆面板
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/image/analyze` | 上传图片识食 + 联网搜菜谱 |
| GET | `/api/image/history` | 识图历史 |
| GET/POST/DELETE | `/api/memory` | 厨房记忆管理 |
| POST | `/api/chat` | 文字对话（自动注入记忆） |
| GET | `/api/history` | 对话历史 |

---

## 常见问题

**Q: 提示「AI API 配置未完成」？**
A: 在项目根目录创建 `.env` 文件，填入 `DASHSCOPE_API_KEY=你的Key`。

**Q: 识图失败？**
A: 确认 DashScope 已开通 `qwen-vl-plus` 视觉模型，且图片清晰、包含可见食材。

**Q: 联网搜索不生效？**
A: 确认 `enableSearch: true`，且使用的是支持联网的千问模型（如 `qwen-plus`）。

**Q: 记忆在哪里？**
A: SQLite 数据库 `backend/data/mycooker.db` 的 `user_memory` 表，前端在识图页右侧查看。

---

## 技术栈

- **前端**：Vue 3 · Vite 6 · Element Plus · Pinia · Vue Router
- **后端**：Node.js 22+ · Express · Multer（图片上传）
- **AI**：通义千问（DashScope 兼容模式）· qwen-vl-plus 识图 · 联网搜索
- **数据库**：SQLite（Node.js 内置 `node:sqlite`）
