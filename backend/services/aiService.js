const aiConfig = require('../config/ai.config');

/**
 * 根据点分隔路径从对象中取值
 */
function getNestedValue(obj, pathStr) {
  return pathStr.split('.').reduce((acc, key) => {
    if (acc == null) return undefined;
    return acc[key];
  }, obj);
}

/**
 * 校验 API 配置是否已填写
 */
function validateConfig() {
  const missing = [];
  if (!aiConfig.baseUrl) missing.push('baseUrl');
  if (!aiConfig.apiKey) missing.push('apiKey');
  if (!aiConfig.model) missing.push('model');
  return missing;
}

function validateVisionConfig() {
  const missing = validateConfig();
  if (!aiConfig.visionModel) missing.push('visionModel');
  return missing;
}

/**
 * 将配置模板中的占位符替换为实际值
 */
function buildRequestBody(messages, model, extraParams = {}) {
  const template = JSON.parse(JSON.stringify(aiConfig.requestBodyTemplate));

  function replacePlaceholders(obj) {
    if (typeof obj === 'string') {
      return obj
        .replace('{{messages}}', JSON.stringify(messages))
        .replace('{{model}}', model || aiConfig.model);
    }
    if (Array.isArray(obj)) return obj.map(replacePlaceholders);
    if (obj && typeof obj === 'object') {
      const result = {};
      for (const [key, value] of Object.entries(obj)) {
        if (value === '{{messages}}') result[key] = messages;
        else if (value === '{{model}}') result[key] = model || aiConfig.model;
        else result[key] = replacePlaceholders(value);
      }
      return result;
    }
    return obj;
  }

  const body = replacePlaceholders(template);
  body.model = model || aiConfig.model;

  return { ...body, ...extraParams };
}

/**
 * 通用 AI API 调用
 * @param {Array} messages - 消息数组
 * @param {Object} options - { model, enableSearch, timeout }
 */
async function callAI(messages, options = {}) {
  const missing = validateConfig();
  if (missing.length > 0) {
    throw new Error(
      `AI API 配置未完成，请在 backend/config/ai.config.js 中填写：${missing.join(', ')}`
    );
  }

  const extraParams = {};
  const useSearch = options.enableSearch ?? false;
  if (useSearch && aiConfig.enableSearch && aiConfig.searchParamKey) {
    extraParams[aiConfig.searchParamKey] = true;
  }

  const requestBody = buildRequestBody(messages, options.model, extraParams);
  const url = `${aiConfig.baseUrl.replace(/\/$/, '')}${aiConfig.chatEndpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${aiConfig.apiKey}`,
    ...aiConfig.extraHeaders
  };

  const timeout = options.timeout || aiConfig.timeout;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      method: aiConfig.method,
      headers,
      body: JSON.stringify(requestBody),
      signal: controller.signal
    });

    const data = await response.json();

    if (!response.ok) {
      const errMsg =
        data.error?.message || data.message || JSON.stringify(data);
      throw new Error(`AI API 请求失败 (${response.status}): ${errMsg}`);
    }

    const content = getNestedValue(data, aiConfig.responseContentPath);
    if (content === undefined || content === null) {
      throw new Error(
        '无法从响应中解析 AI 回复，请检查 ai.config.js 中的 responseContentPath'
      );
    }

    return content;
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('AI API 请求超时，请稍后重试');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * 构建带记忆的系统提示词
 */
function buildSystemPrompt(memoryContext) {
  let prompt = aiConfig.systemPrompt;
  if (memoryContext) {
    prompt += `\n\n【用户记忆档案】\n${memoryContext}`;
  }
  return prompt;
}

/**
 * 文字对话（含历史上下文 + 记忆）
 */
async function chatWithAI(historyMessages, userMessage, memoryContext = '') {
  const messages = [
    { role: 'system', content: buildSystemPrompt(memoryContext) }
  ];

  historyMessages.forEach((msg) => {
    if (msg.role === 'user' || msg.role === 'assistant') {
      messages.push({ role: msg.role, content: msg.content });
    }
  });

  messages.push({ role: 'user', content: userMessage });
  return callAI(messages, { enableSearch: false });
}

/**
 * 联网搜索菜谱推荐
 */
async function searchRecipesByIngredients(ingredients) {
  const list = Array.isArray(ingredients) ? ingredients.join('、') : ingredients;
  const prompt = aiConfig.recipeSearchPrompt.replace('{{ingredients}}', list);

  const messages = [
    { role: 'system', content: aiConfig.systemPrompt },
    { role: 'user', content: prompt }
  ];

  return callAI(messages, { enableSearch: true, timeout: 120000 });
}

module.exports = {
  callAI,
  chatWithAI,
  searchRecipesByIngredients,
  validateConfig,
  validateVisionConfig,
  getNestedValue
};
