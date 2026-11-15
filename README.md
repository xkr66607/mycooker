# 私厨 AI 助手 · RAG + Agent 版

一个**真正带检索增强生成（RAG）**的厨房饮食助手：上传自己的菜谱 / 营养资料，
提问时会先从知识库检索相关片段，再让大模型基于这些片段作答，并标注引用来源。

技术栈：FastAPI + Chroma + 通义千问（qwen-plus / text-embedding-v4）+ 原生 HTML/JS 前端。

![对话界面](docs/screenshot-desktop.png)

<table>
<tr>
<td width="50%"><img src="docs/screenshot-sources.png" alt="来源卡片"></td>
<td width="50%"><img src="docs/screenshot-mobile.png" alt="移动端"></td>
</tr>
</table>

**它和普通 ChatGPT 套壳的区别：**

| | 普通套壳 | 本项目 |
|---|---|---|
| 知识来源 | 模型自己记得的 | 你上传的文档 |
| 能否溯源 | 不能 | 每句话标注来自哪份文件第几节 |
| 知识过期 | 只能等模型升级 | 传新文档立刻生效 |
| 不知道时 | 一本正经编 | 明确说「知识库里没有」，通用建议另行标注 |
| 多轮对话 | 可能忘记上下文 | 指代消解 + 长期口味记忆 |

---

## 一、怎么启动

```bat
:: Windows 直接双击 start_server.bat
:: 或者命令行：
venv\Scripts\python.exe run_app.py
```

启动后浏览器自动打开 <http://127.0.0.1:8001>。

首次在新机器上部署：

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

然后在 `.env` 里填好 Key（照 `.env.example` 抄一份改名即可）。

---

## 一·五、怎么换模型

模型分三块，**能力不同，不能随便互换**：

| 配置块 | 用途 | 能换成什么 |
|---|---|---|
| `CHAT_*` | 文本对话 | 千问 / DeepSeek / 任意 OpenAI 兼容服务 |
| `VISION_*` | 看食材照片 | 千问 `qwen-vl-*` / GPT-4o 等**有视觉能力**的 |
| `EMBEDDING_*` | 把文字变向量 | 千问 `text-embedding-v4` / OpenAI 等**有 embedding 接口**的 |

### 换对话模型

**方式一：通过千问（DashScope）调 DeepSeek** —— 只改模型名，一行搞定：

```ini
CHAT_MODEL=deepseek-v4.1-flash
```

**方式二：走 DeepSeek 官方 API** —— 三行都要填：

```ini
CHAT_API_KEY=sk-你的DeepSeekKey
CHAT_BASE_URL=https://api.deepseek.com
CHAT_MODEL=deepseek-chat
```

> ⚠️ **最容易踩的坑：两家平台模型命名不一样。**
>
> | 平台 | 模型名 |
> |---|---|
> | 千问 DashScope | `deepseek-v4.1-flash` / `deepseek-v4-pro` |
> | DeepSeek 官方 | `deepseek-chat` / `deepseek-reasoner` |
>
> 混着填会得到 `404 The model xxx does not exist`。代码里已经把这种错误翻译成人话了。

### 为什么视觉仍然用千问

`deepseek-v4.1-flash` **确实支持看图**，实测能准确读出截图里的文字。
但它是**推理模型**——回答前要先思考，而思考 token 也算钱。

同一张图、同一句提示词：

| 模型 | 耗时 | 思考 token | 正文 token | 稳定性 |
|---|---|---|---|---|
| `qwen3-vl-plus` | 5.7 s | 0 | 29 | 稳定 |
| `deepseek-v4.1-flash` | 9~15 s | **1378 ~ 5190** | 67 | 配额给小了正文就是空 |

思考长度每次都不一样（实测跳了 4 倍），所以用它做视觉得把
`VISION_MAX_TOKENS` 抬到 8000 才勉强稳。为了列一个食材清单花 5000 个 token，
不划算。**所以视觉默认 `qwen3-vl-plus`，对话随你选。**

### embedding 为什么不能换 DeepSeek

```bash
POST https://api.deepseek.com/embeddings    → 404
POST https://api.deepseek.com/v1/embeddings → 404
```

DeepSeek 官方文档的 12 个端点里没有任何向量接口。向量只能用千问。

代码里三块配置是彼此隔离的：`VISION_*` 不继承 `CHAT_*`，换对话模型不影响图片识别。
配错了 `/api/health` 的 `config_warnings` 会明确提示，前端顶栏亮红色角标。

---

## 二、它到底怎么工作的

```
用户提问
   │
   ├─ 1. 把问题（+ 上一轮提问）向量化  ──► text-embedding-v4，1024 维
   │
   ├─ 2. 在 Chroma 里做余弦相似度检索  ──► 取回 Top-K 片段，过滤低分
   │
   ├─ 3. 把片段拼成带编号的上下文      ──► [1] 《文件名》章节 · 相关度 0.76
   │
   ├─ 4. 系统提示词 + 长期偏好 + 上下文 + 历史 + 当前问题 ──► qwen-plus
   │
   └─ 5. 流式返回（SSE），同时解析正文里的 [1][2] 标注
          └─► 前端渲染成可折叠的来源卡片
```

### 关键设计取舍

| 问题 | 做法 | 为什么 |
|------|------|--------|
| 切分粒度 | 先按 Markdown 标题切"节"，节内超长再按句子切 | 一块只讲一件事，向量才准确；混着多个主题的块检索必然不准 |
| 章节前缀 | 每个片段的文本前面拼 `【章节标题】` | 让向量带上主题上下文，短片段也能被正确召回 |
| 相似度门槛 | 低于 0.38 的片段直接丢弃 | 实测低于这个值的都是"同文档不同主题"，塞进去只会干扰模型 |
| 检索失败怎么办 | 明确告知"知识库没有"，通用建议要标注来源性质 | 不允许模型拿常识硬编，这是幻觉的主要来源 |
| 多轮指代 | 短问句会拼接上一轮提问再检索 | 「那减脂版怎么调整？」单独拿去检索什么都搜不到 |
| 引用校验 | 正则提取 `[N]`，越界编号丢弃，未使用的置灰 | 模型可能编出不存在的编号，必须做边界校验 |

---

## 二·五、Agent 模式（默认开启）

上面的流程有个根本问题：**检索是代码决定的，不是模型决定的。**
代码固定检索一次、固定取 Top-5，然后祈祷这 5 条里刚好有答案。

实测暴露了三种它答不好的情况：

| 情况 | RAG 版表现 | 为什么 |
|------|-----------|--------|
| 多跳问题 | 只能答一半 | 「红烧肉多少热量」需要先取用量、再查营养、再算三件事，一次检索凑不齐 |
| 闲聊 | 照样检索 5 条 | 「你好呀」也去查知识库，拉回一堆无关片段塞进上下文，还可能被带偏 |
| 需要算数 | 模型自己心算 | 大模型算乘法经常错，而且错得很自信 |

Agent 模式把「查不查、查几次、查什么」交给模型决定：

```
用户提问
   │
   ├─ 模型判断：这个问题需要什么信息？
   │
   ├─ 要查 → 调用工具（search_kb / get_dish / calc_nutrition / list_dishes）
   │           │
   │           └─ 工具结果塞回对话历史 → 回到第一步重新判断
   │
   └─ 不需要了 → 输出最终答案（流式）
```

核心就是一个循环，不到 20 行：

```python
for step in range(MAX_STEPS):
    resp = call_model(messages, tools=TOOLS)
    if not resp.tool_calls:
        return resp.content          # 模型说"不用查了"，输出答案
    for call in resp.tool_calls:
        result = execute(call.name, call.args)
        messages.append(tool_result(call.id, result))
```

### 四个工具

| 工具 | 干什么 | 什么时候用 |
|------|--------|-----------|
| `search_kb` | 语义检索知识库 | 问做法、配比、营养知识、保存方法 |
| `get_dish` | 按菜名精确取一道菜 | 问知识库里那 6 道菜（比语义检索准，不会召回无关片段） |
| `list_dishes` | 列出所有菜名 | 问「你会做什么」「有什么菜」 |
| `calc_nutrition` | 按食材和克数算热量/蛋白质/脂肪 | 任何要给出具体数字的问题 |

### 三个必须知道的坑

**1. 工具描述就是模型的唯一判断依据。**
模型看不到函数体，它只看 `description` 里那几行字。描述写得含糊，它就会该调不调、或者乱调。
所以每个描述都按「是什么 / 有什么内容 / 什么时候用」三段写。

**2. 流式返回的 tool_calls 是碎片，必须按 `index` 分组拼。**
模型可能一次并行发多个调用。把所有碎片直接拼起来会得到
`search_kbsearch_kb` 和 `{...}{...}`，`json.loads` 直接报 `Extra data`。
规则是：**组内拼，组间不拼。**

**3. 必须有步数上限。**
模型有可能反复查同一个词、或者揪着一个报错的工具不放。
`AGENT_MAX_STEPS=6` 不是性能参数，是保险丝 —— 没有它，一个问题可能烧掉一整天额度。

### 实测对比（同一批问题，同一模型）

| 问题 | RAG 版 | Agent 版 |
|------|--------|----------|
| 闲聊「你好呀」 | 固定检索 1 次，11.0s | **0 次工具**，6.6s |
| 单跳「糖醋汁比例」 | 正确，6.3s | 正确，7.6s |
| 多跳「红烧肉多少热量」 | 「算不出有知识库依据的数」，给 3800–4300 的估算 | **整锅 3130 千卡 / 一人份 783 千卡**，精确 |
| 「知识库里有哪几道菜」 | **答 4 道（错，实际 6 道）** | **答 6 道（对）** |
| 「糖醋排骨怎么做」 | 如实说没有，8.3s | 如实说没有 + 找到可套用的糖醋汁比例，19.0s |

**结论要诚实：Agent 不是全面更好。**
它明确赢在三处：闲聊不浪费检索、多跳能给精确数字、列举类问题不会漏。
代价是工具调用变多（0 → 11 次）、慢问题更慢（拒答题 8.3s → 19.0s）。
平均耗时差不多（9.9s vs 10.4s），因为省下的无效检索抵消了多出来的工具调用。

### 怎么关掉

```bash
MYCOOKER_AGENT=0
```

关掉就退回固定检索的老做法。两种模式的事件格式兼容，前端不用改 ——
留着这个开关就是为了能随时跑上面的对比表。

---

## 三、目录结构

```
mycooker/
├── main.py                 # FastAPI 入口，装配路由与静态前端
├── config.py               # 全部配置集中在这里，改参数只改这一个文件
├── run_app.py              # 一键启动（拉起服务 + 开浏览器）
├── start_server.bat        # Windows 启动脚本
├── requirements.txt
├── .env                    # API Key 等敏感配置（不要提交到 git）
│
├── rag/                    # ── RAG 核心 ──
│   ├── embeddings.py       # 调 DashScope 向量接口（含重试、批量、乱序还原）
│   ├── splitter.py         # 文档解析 + 两级切分（按节 → 按句）
│   ├── store.py            # Chroma 增删查，距离转相似度
│   ├── ingest.py           # 入库流水线：字节 → 解析 → 切分 → 向量 → 存储
│   ├── pipeline.py         # RAG 模式：检索 → 拼上下文 → 流式生成 → 引用解析
│   ├── tools.py            # Agent 能用的工具（定义 + 实现 + 路由）
│   └── agent.py            # Agent 模式：模型自主决策的工具调用循环
│
├── memory/
│   └── store.py            # SQLite：会话历史 + 长期口味偏好
│
├── api/v1/
│   ├── chat.py             # 对话（SSE 流式）、会话列表、消息读取
│   ├── kb.py               # 知识库上传 / 列表 / 删除 / 检索测试
│   └── memory.py           # 长期记忆增删查
│
├── static/index.html       # 前端（单文件，零构建，零外部依赖）
├── seeds/                  # 三篇示例知识库，可直接上传体验
├── data/                   # 运行时生成：chroma/、uploads/、mycooker.db
└── _legacy/                # 旧版本代码（Node 前端、旧 agent 实现），可删
```

---

## 四、接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查：配置是否齐全、三块模型各是哪个厂商、知识库多少条 |
| POST | `/api/v1/chat/stream` | 流式对话（SSE）。请求体加 `"agent": false` 可本次强制走 RAG 模式 |
| GET | `/api/v1/chat/conversations` | 会话列表 |
| GET | `/api/v1/chat/messages?conversation_id=` | 某会话的消息 |
| DELETE | `/api/v1/chat/conversations/{id}` | 删除会话 |
| POST | `/api/v1/kb/upload` | 上传文档入库（multipart） |
| GET | `/api/v1/kb/sources` | 已入库文档列表 |
| DELETE | `/api/v1/kb/sources/{source_id}` | 删除某文档 |
| GET | `/api/v1/kb/stats` | 知识库统计 |
| POST | `/api/v1/kb/search` | **纯检索测试，不经过模型**（调 RAG 的第一工具） |
| GET | `/api/v1/kb/config` | 当前生效的切分/检索参数 |
| GET / POST / DELETE | `/api/v1/memory/facts` | 长期口味记忆 |

---

## 五、调参速查

都在 `config.py`，也可以用环境变量覆盖（前缀 `MYCOOKER_`）。

| 参数 | 默认 | 调大 / 调小的效果 |
|------|------|------------------|
| `CHUNK_SIZE` | 350 | 调大 → 上下文更完整但检索变糊；调小 → 精准但可能丢上下文 |
| `CHUNK_OVERLAP` | 60 | 保证跨块的信息不被切断，一般为 chunk_size 的 15%~20% |
| `TOP_K` | 5 | 送进模型的片段数，太多会稀释重点 |
| `MIN_SCORE` | 0.38 | 调高 → 更保守，宁可说不知道；调低 → 召回多但容易答非所问 |
| `HISTORY_TURNS` | 6 | 带多少轮历史进 prompt |

**检索效果不好时的排查顺序：**
1. `POST /api/v1/kb/search` 直接看命中什么 → 如果检索就不对，是切分或 embedding 问题
2. 检索对但回答不对 → 是 prompt 问题
3. 回答里有不存在的来源 → 是引用校验问题

---

## 六、已知限制

- 扫描版 PDF（图片型）无法解析，需要 OCR，当前不支持
- 单个文件上限 20MB，切分后总片段数没有硬上限
- 没有多用户/鉴权，仅供本地单人使用
- 互联网兜底搜索（Tavily）已预留配置但当前版本未接入