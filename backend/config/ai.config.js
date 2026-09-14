/**
 * ============================================================
 *  AI 智能体 API 配置文件（通义千问 / 阿里云 DashScope）
 *  【重要】API Key 请写在项目根目录的 .env 文件中，不要提交到 Git
 *  获取 Key：https://dashscope.console.aliyun.com/apiKey
 * ============================================================
 */

const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../../.env') });

module.exports = {
  // ---------- 千问 API 连接（OpenAI 兼容模式） ----------
  /** API 基础地址 — 千问填下面这行即可 */
  baseUrl: process.env.DASHSCOPE_BASE_URL || 'https://dashscope.aliyuncs.com/compatible-mode/v1',

  /** 从 .env 读取的 API Key */
  apiKey: process.env.DASHSCOPE_API_KEY,

  /** 聊天接口路径（千问兼容模式默认即可） */
  chatEndpoint: '/chat/completions',

  method: 'POST',
  timeout: 120000,

  extraHeaders: {},

  // ---------- 模型配置 ----------
  /** 文字对话模型：qwen-plus / qwen-turbo / qwen-max 等 */
  model: 'qwen-plus',

  /** 视觉识图模型：qwen-vl-plus / qwen-vl-max（识别图片中的食材） */
  visionModel: 'qwen-vl-plus',

  /** 文字对话请求体模板（千问联网搜索见 enableSearch） */
  requestBodyTemplate: {
    model: '',
    messages: '{{messages}}',
    stream: false,
    temperature: 0.7,
    max_tokens: 4096
  },

  /** 是否开启千问内置联网搜索（推荐 true，用于搜全网菜谱） */
  enableSearch: true,

  /** 联网搜索时的额外请求参数字段名（千问兼容模式为 enable_search） */
  searchParamKey: 'enable_search',

  responseContentPath: 'choices.0.message.content',

  // ---------- 系统提示词 ----------
  systemPrompt: `你是一位专业的「私人厨房 AI 助手」，名字叫「小厨」。你的职责是帮助用户解决一切与厨房、饮食相关的问题。

【服务范围】仅限以下话题：
- 饮食搭配与营养均衡
- 食材选购、处理与预处理技巧
- 菜谱推荐（中式、西式、日韩等）
- 烹饪技巧（火候、调味、刀工等）
- 健康饮食与膳食规划
- 减脂餐、增肌餐等特殊饮食方案
- 食材保存、保鲜与储存方法
- 厨房工具使用与选购建议

【记忆能力】
系统会注入用户的历史记忆（曾识别过的食材、偏好等），请结合这些信息给出个性化建议。

【行为规范】
1. 回答要实用、具体，尽量给出步骤或示例
2. 涉及用量时给出明确的分量建议
3. 若用户提问与厨房/饮食无关，礼貌拒绝并引导回到厨房话题
4. 使用亲切、专业的语气，适当使用 emoji
5. 回答使用中文，条理清晰，必要时使用列表或分步骤说明`,

  // ---------- 识图专用提示词 ----------
  visionPrompt: `请仔细分析这张图片，识别其中所有可见的食材和食物（包括蔬菜、水果、肉类、海鲜、调料、半成品等）。

请严格按以下 JSON 格式返回，不要添加任何其他文字：
{
  "ingredients": ["食材1", "食材2"],
  "description": "对图片内容的简要描述（一句话）",
  "confidence": "high/medium/low"
}

注意：
- ingredients 数组只包含具体食材名称，用中文
- 若图片中没有食物/食材，ingredients 返回空数组
- 不要猜测看不清的内容`,

  // ---------- 菜谱搜索提示词模板 ----------
  /** {{ingredients}} 会被替换为食材列表 */
  recipeSearchPrompt: `用户上传了一张图片，识别出以下食材：{{ingredients}}

请联网搜索这些食材可以制作哪些菜品，并给出详细推荐：

1. **推荐菜品**（至少 5 道，按难易度排序）
   - 菜名、所需食材、简要做法（3-5 步）、烹饪时间、难度

2. **经典搭配** — 这些食材组合的经典名菜

3. **创意料理** — 1-2 道创意菜建议

4. **营养提示** — 这些食材的营养价值和搭配建议

5. **保存建议** — 若有易腐食材，给出保存方法

请引用搜索到的真实菜谱信息，标注参考来源（网站名即可）。`
};
