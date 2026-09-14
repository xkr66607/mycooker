# 私人厨房 AI 助手 — 代码完全解读（零基础版）

> 这份文档假设你**没有编程基础**，会用「餐厅比喻」和「流程图」带你理解每一部分代码在干什么。
> 建议按顺序阅读，遇到不懂的名词可以看文末「术语表」。

---

## 一、这个项目到底是什么？

你可以把它想象成一家**智能餐厅**：

| 角色 | 对应什么 | 干什么 |
|------|----------|--------|
| **顾客（你）** | 浏览器里的网页 | 看界面、上传图片、打字提问 |
| **前台服务员** | 前端（Vue3） | 接待顾客、展示菜单、传递点单 |
| **后厨经理** | 后端（Express） | 接收点单、查数据库、联系外部 AI |
| **外部大厨** | 通义千问 API | 真正「思考」和「识图」的 AI |
| **账本** | SQLite 数据库 | 记录对话历史、识图记录、厨房记忆 |

**重要原则：**
- 你的浏览器**从不直接**联系千问 API（避免密钥泄露、跨域问题）
- 所有 AI 请求都经过**你自己的后端**转发
- API 密钥只写在 `backend/config/ai.config.js` 这一个文件里

---

## 二、项目文件夹地图

```
mycooker1/
│
├── backend/          ← 【后厨】Node.js 后端，端口 3001
│   ├── server.js           入口：启动整个后端
│   ├── config/
│   │   └── ai.config.js    ★ 唯一需要你填 API Key 的文件
│   ├── db/
│   │   └── database.js     数据库建表
│   ├── routes/             各种「接口地址」
│   │   ├── chat.js         文字聊天
│   │   ├── history.js      对话历史
│   │   ├── image.js        图片识图
│   │   └── memory.js       厨房记忆
│   ├── services/           真正干活的「业务逻辑」
│   │   ├── aiService.js    调用千问（文字+联网）
│   │   ├── visionService.js 调用千问识图
│   │   └── memoryService.js 读写记忆
│   ├── uploads/            用户上传的图片存这里
│   └── data/
│       └── mycooker.db     SQLite 数据库文件
│
└── frontend/         ← 【前台】Vue3 网页，端口 5173
    ├── index.html          网页骨架
    ├── vite.config.js      开发工具配置（含代理）
    └── src/
        ├── main.js         前端入口
        ├── App.vue         根组件（外壳）
        ├── router/index.js 页面路由（URL 对应哪个页面）
        ├── api/index.js    向后端发请求的封装
        ├── stores/chat.js  聊天状态管理（Pinia）
        ├── views/          完整页面
        │   ├── Home.vue        首页
        │   ├── Chat.vue         AI 问答页
        │   └── ImageAnalyze.vue 识图做菜页
        └── components/     可复用的小组件
            ├── AppHeader.vue      顶部导航
            ├── ChatMessage.vue    聊天气泡
            ├── ChatInput.vue        输入框
            ├── HistorySidebar.vue   对话历史侧边栏
            ├── ImageUpload.vue      图片上传区
            └── MemoryPanel.vue      记忆面板
```

---

## 三、整体工作流程（先看大图）

### 3.1 文字聊天流程

```
你在网页输入「番茄炒蛋怎么做？」
        ↓
Chat.vue → ChatInput 触发发送
        ↓
stores/chat.js 的 sendMessage()
        ↓
api/index.js  POST /api/chat
        ↓
Vite 代理转发到 localhost:3001
        ↓
routes/chat.js  接收请求
        ↓
memoryService  读取你的「厨房记忆」
        ↓
aiService.chatWithAI()  组装消息 + 调用千问
        ↓
千问返回回答
        ↓
history 路由把消息存入 SQLite
        ↓
回答显示在 ChatMessage 气泡里
```

### 3.2 识图做菜流程

```
你上传一张食材照片
        ↓
ImageAnalyze.vue → ImageUpload 组件
        ↓
api/index.js  POST /api/image/analyze（FormData 传文件）
        ↓
routes/image.js
   ├─ multer 保存图片到 uploads/
   ├─ visionService  千问视觉模型识图 → 得到食材列表
   ├─ memoryService  食材存入「厨房记忆」
   ├─ aiService.searchRecipesByIngredients()  千问联网搜菜谱
   └─ 识图结果存入 image_records 表
        ↓
页面展示：食材标签 + 菜谱推荐
```

---

## 四、后端代码逐个解读

### 4.1 `server.js` — 后厨总开关

**作用：** 启动后端服务，把所有模块「组装」在一起。

```javascript
const app = express();           // 创建 Express 应用
app.use(cors());                 // 允许前端跨域访问
app.use(express.json());         // 解析 JSON 请求体

app.use('/uploads', express.static(...));  // 让上传的图片可以通过 URL 访问

const db = initDatabase();       // 连接/创建 SQLite 数据库
app.locals.db = db;              // 把 db 挂到 app 上，所有路由都能用

app.use('/api/chat', chatRouter);     // /api/chat/* 交给 chat.js 处理
app.use('/api/history', historyRouter);
app.use('/api/image', imageRouter);
app.use('/api/memory', memoryRouter);

app.listen(3001);                // 在 3001 端口监听
```

**你需要知道的：** 这是后端启动时第一个运行的文件。改端口在这里改 `PORT`。

---

### 4.2 `config/ai.config.js` — ★ 最重要的配置文件

**作用：** 存放千问 API 的所有配置，**业务代码不硬编码密钥**。

| 字段 | 含义 | 你要改吗？ |
|------|------|-----------|
| `baseUrl` | 千问 API 地址 | 不用，已填好 |
| `apiKey` | 你的密钥 | **要填** |
| `model` | 文字模型，如 `qwen-plus` | 可选 |
| `visionModel` | 识图模型，如 `qwen-vl-plus` | 可选 |
| `enableSearch` | 是否联网搜菜谱 | 建议 `true` |
| `systemPrompt` | 告诉 AI「你是厨房助手」 | 可选改 |
| `visionPrompt` | 告诉 AI「怎么识图、返回 JSON」 | 一般不用改 |
| `recipeSearchPrompt` | 搜菜谱时的问题模板 | 一般不用改 |

**安全提醒：** 不要把含真实 `apiKey` 的文件上传到公开 GitHub。如果泄露，去阿里云控制台重新生成 Key。

---

### 4.3 `db/database.js` — 数据库建表

**作用：** 项目第一次运行时，自动创建 SQLite 数据库和表。

**四张表：**

| 表名 | 存什么 | 举例 |
|------|--------|------|
| `conversations` | 一场对话的元信息 | id=1, title="番茄炒蛋怎么做" |
| `messages` | 对话里的每条消息 | role=user, content="你好" |
| `user_memory` | 厨房记忆 | category=ingredient, value="识别食材：番茄、鸡蛋" |
| `image_records` | 识图历史 | filename, ingredients, recipe_result |

**SQLite 是什么？** 一个存在本地文件（`mycooker.db`）里的轻量数据库，不需要安装 MySQL。

---

### 4.4 `services/aiService.js` — 和千问对话的核心

**三个关键函数：**

#### `callAI(messages, options)` — 万能调用器
- 从 `ai.config.js` 读取 URL、Key、模型
- 组装 HTTP 请求发给千问
- 如果 `enableSearch: true`，会加上 `enable_search: true` 让千问联网
- 从返回 JSON 里取出 AI 的文字（路径由 `responseContentPath` 指定）

#### `chatWithAI(history, userMessage, memoryContext)` — 文字聊天
- 把「系统提示词 + 记忆 + 历史对话 + 当前问题」拼成 messages
- 调用 `callAI`，不联网（普通聊天）

#### `searchRecipesByIngredients(ingredients)` — 搜菜谱
- 把食材列表填进 `recipeSearchPrompt` 模板
- 调用 `callAI`，**开启联网搜索**

---

### 4.5 `services/visionService.js` — 图片识食

**作用：** 把图片发给千问的**视觉模型**（qwen-vl-plus）。

```javascript
messages: [{
  role: 'user',
  content: [
    { type: 'image_url', image_url: { url: 'data:image/jpeg;base64,...' } },
    { type: 'text', text: '请识别图片中的食材...' }
  ]
}]
```

千问返回 JSON 字符串 → `parseVisionResult()` 解析成：
```json
{
  "ingredients": ["番茄", "鸡蛋"],
  "description": "案板上的番茄和鸡蛋",
  "confidence": "high"
}
```

---

### 4.6 `services/memoryService.js` — 厨房记忆

**作用：** 让 AI「记住」你之前识图过的食材。

| 函数 | 干什么 |
|------|--------|
| `saveIngredientsMemory()` | 识图后保存食材 |
| `getMemoryContext()` | 聊天前读取记忆，格式化成文字注入 AI |
| `listMemories()` | 前端记忆面板展示 |
| `saveImageRecord()` | 保存完整识图记录 |

**记忆怎么用在聊天里？**  
`routes/chat.js` 每次聊天前调用 `getMemoryContext()`，把结果追加到 systemPrompt 后面，千问就能看到「用户之前识别过番茄、鸡蛋」。

---

### 4.7 四个路由文件 — 对外提供的「接口」

路由 = 一个 URL + 一种操作。

| 文件 | 主要接口 | 说明 |
|------|----------|------|
| `chat.js` | `POST /api/chat` | 发消息，得 AI 回复 |
| `history.js` | `GET/POST/DELETE /api/history` | 对话 CRUD |
| `image.js` | `POST /api/image/analyze` | 上传图片识图 |
| `memory.js` | `GET/POST/DELETE /api/memory` | 记忆管理 |

**`image.js` 识图四步（核心逻辑）：**
1. multer 接收并保存图片
2. 转 base64 → visionService 识图
3. memoryService 存记忆
4. aiService 联网搜菜谱 → 存 image_records → 返回前端

---

## 五、前端代码逐个解读

### 5.1 前端三大核心概念（先搞懂这个）

| 概念 | 文件 | 比喻 |
|------|------|------|
| **路由 Router** | `router/index.js` | 电梯楼层按钮：/ 首页、/chat 问答、/analyze 识图 |
| **状态 Store** | `stores/chat.js` | 前台收银台的「当前订单状态」 |
| **API 层** | `api/index.js` | 专门给后端打电话的「内线电话」 |

---

### 5.2 `main.js` — 前端入口

```javascript
createApp(App)        // 创建 Vue 应用
  .use(createPinia()) // 启用状态管理
  .use(router)        // 启用路由
  .use(ElementPlus)   // 启用 UI 组件库（按钮、输入框等）
  .mount('#app')       // 挂载到 index.html 的 <div id="app">
```

---

### 5.3 `router/index.js` — 页面导航

| URL | 页面 | 文件 |
|-----|------|------|
| `/` | 首页 | Home.vue |
| `/chat` | 新对话 | Chat.vue |
| `/chat/5` | 第 5 号历史对话 | Chat.vue（加载 id=5 的消息） |
| `/analyze` | 识图做菜 | ImageAnalyze.vue |

---

### 5.4 `api/index.js` — 和后端通信

所有函数都是「发 HTTP 请求到 `/api/...`」：

```javascript
sendChatMessage(message, history)  → POST /api/chat
analyzeImage(file)                 → POST /api/image/analyze
getMemories()                      → GET /api/memory
// ...
```

**Vite 代理：** `vite.config.js` 里配置了：
- 浏览器访问 `/api/*` → 自动转发到 `http://localhost:3001/api/*`
- 浏览器访问 `/uploads/*` → 转发到后端静态文件

所以你写 `baseURL: '/api'` 就行，不用写完整地址。

---

### 5.5 `stores/chat.js` — 聊天状态中心

**state（数据）：**
- `messages` — 当前屏幕上的消息列表
- `conversations` — 左侧历史对话列表
- `loading` — 是否正在等 AI 回复

**sendMessage 流程（最重要）：**
1. 没有对话？先 `createConversation` 创建
2. 把用户消息显示到屏幕 + 存数据库
3. 带历史上下文调 `sendChatMessage`
4. 收到 AI 回复 → 显示 + 存数据库

---

### 5.6 页面和组件

#### `views/Home.vue` — 首页
- 展示功能介绍、快捷问题
- 按钮跳转到 `/chat` 或 `/analyze`

#### `views/Chat.vue` — AI 问答页
- 左侧：`HistorySidebar` 历史对话
- 中间：消息列表（`ChatMessage`）
- 底部：`ChatInput` 输入框

#### `views/ImageAnalyze.vue` — 识图页
- 左侧：`ImageUpload` 上传 + 结果展示
- 右侧：`MemoryPanel` 记忆 + 识图历史

#### `components/ChatMessage.vue` — 聊天气泡
- `role === 'user'` → 绿色气泡靠右
- `role === 'assistant'` → 白色气泡靠左
- 简单 Markdown 渲染（加粗、列表）

#### `components/ImageUpload.vue` — 图片上传
- 支持点击选择和拖拽
- 本地预览（`URL.createObjectURL`）
- 通过 `@select` 事件把 File 对象传给父组件

---

## 六、一次完整操作背后发生了什么？

### 场景 A：你问「鸡蛋怎么保存？」

1. **ChatInput** 按 Enter → 触发 `handleSend`
2. **chat store** `sendMessage("鸡蛋怎么保存？")`
3. **api** `POST /api/chat` body: `{ message, history }`
4. **chat.js** 读 memory → 调 `chatWithAI`
5. **aiService** 组装 messages → 请求千问 → 得到回复
6. **history.js** 消息写入 `messages` 表
7. 前端收到 `{ success: true, data: { content: "..." } }`
8. **ChatMessage** 渲染 AI 气泡

### 场景 B：你上传一张有番茄和鸡蛋的照片

1. **ImageUpload** 选中文件 → **ImageAnalyze** 点「开始识图」
2. **api** `POST /api/image/analyze`（multipart 表单）
3. **image.js**：
   - 保存图片 → `uploads/1736xxx.jpg`
   - 千问 VL 识图 → `["番茄","鸡蛋"]`
   - 写入 `user_memory`
   - 千问联网 → 返回 5+ 道菜谱
   - 写入 `image_records`
4. 页面显示食材标签和菜谱 Markdown
5. 你点「继续追问小厨」→ 跳转 Chat 并自动发送一条消息

---

## 七、数据存在哪里？

| 数据 | 位置 | 怎么查看 |
|------|------|----------|
| 对话历史 | `backend/data/mycooker.db` → conversations + messages | 聊天页左侧 |
| 厨房记忆 | 同上 → user_memory | 识图页右侧记忆面板 |
| 识图记录 | 同上 → image_records | 识图页识图历史 |
| 上传图片 | `backend/uploads/` 文件夹 | 文件管理器 |

---

## 八、你想改功能时，该改哪个文件？

| 我想… | 改这个文件 |
|-------|-----------|
| 换 API Key / 换模型 | `backend/config/ai.config.js` |
| 改 AI 人设和说话风格 | `ai.config.js` 的 `systemPrompt` |
| 改识图提示词 | `ai.config.js` 的 `visionPrompt` |
| 改搜菜谱的问题模板 | `ai.config.js` 的 `recipeSearchPrompt` |
| 改后端端口 | `backend/server.js` 的 `PORT` |
| 改前端端口/代理 | `frontend/vite.config.js` |
| 改首页文案 | `frontend/src/views/Home.vue` |
| 改聊天气泡样式 | `frontend/src/components/ChatMessage.vue` |
| 改整体配色 | `frontend/src/styles/global.css` 的 `:root` 变量 |
| 新增一个 API 接口 | `backend/routes/` 新建 + `server.js` 注册 |
| 新增一个页面 | `frontend/src/views/` 新建 + `router/index.js` 注册 |

---

## 九、术语表（零基础必看）

| 术语 | 解释 |
|------|------|
| **前端** | 浏览器里看到的网页和交互 |
| **后端** | 运行在服务器上的程序，处理数据和 API |
| **API** | 前后端约定的「接口地址」，如 `/api/chat` |
| **路由** | URL 路径对应哪个处理函数 |
| **JSON** | `{ "key": "value" }` 格式的数据交换格式 |
| **Vue 组件** | 一个 `.vue` 文件 = 一块 UI（模板+逻辑+样式） |
| **Pinia Store** | 跨组件共享的数据（如当前聊天消息） |
| **Express** | Node.js 的 Web 框架，写后端 API 用 |
| **SQLite** | 本地文件数据库，不需要单独安装 |
| **代理 Proxy** | 开发时 Vite 帮你把 `/api` 请求转给后端 |
| **base64** | 把图片转成文本字符串，方便 HTTP 传输 |
| **multer** | Express 的中间件，专门处理文件上传 |
| **CORS** | 跨域策略，允许前端网页访问后端 API |
| **systemPrompt** | 给 AI 的「角色设定」，决定 AI 怎么回答 |

---

## 十、常见问题

**Q：为什么前端不直接调千问？**  
A：API Key 放在前端会被任何人看到。必须通过后端转发。

**Q：node_modules 是什么？**  
A：`npm install` 下载的第三方库，不用读里面的代码。

**Q：改代码后要重启吗？**  
A：后端 `npm run dev` 会自动重启；前端 Vite 会自动热更新。改 `ai.config.js` 建议重启后端。

**Q：数据库怎么清空？**  
A：删除 `backend/data/mycooker.db`，重启后端会自动重建空库。

**Q：识图很慢正常吗？**  
A：正常。要调两次千问（识图 + 联网搜菜谱），约 15~40 秒。

---

## 十一、推荐阅读顺序

如果你是完全新手，建议按这个顺序打开代码对照看：

1. `backend/config/ai.config.js` — 先搞懂配置
2. `backend/server.js` — 后端怎么启动
3. `frontend/src/router/index.js` — 有哪些页面
4. `frontend/src/views/Chat.vue` — 聊天页长什么样
5. `frontend/src/stores/chat.js` — 发消息时发生了什么
6. `backend/routes/chat.js` + `services/aiService.js` — AI 怎么被调用
7. `frontend/src/views/ImageAnalyze.vue` + `backend/routes/image.js` — 识图全流程

---

*文档版本：与项目 mycooker1 同步 · 如有新功能以实际代码为准*
