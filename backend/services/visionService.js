const { callAI, validateVisionConfig } = require('./aiService');
const aiConfig = require('../config/ai.config');

/**
 * 使用千问视觉模型识别图片中的食材
 * @param {string} base64Image - base64 编码的图片（含 data:image/xxx;base64, 前缀或纯 base64）
 * @returns {Promise<{ ingredients: string[], description: string, confidence: string }>}
 */
async function analyzeFoodImage(base64Image) {
  const missing = validateVisionConfig();
  if (missing.length > 0) {
    throw new Error(
      `视觉 API 配置未完成，请在 backend/config/ai.config.js 中填写：${missing.join(', ')}`
    );
  }

  // 确保 base64 格式正确
  let imageUrl = base64Image;
  if (!base64Image.startsWith('data:')) {
    imageUrl = `data:image/jpeg;base64,${base64Image}`;
  }

  const messages = [
    {
      role: 'user',
      content: [
        { type: 'image_url', image_url: { url: imageUrl } },
        { type: 'text', text: aiConfig.visionPrompt }
      ]
    }
  ];

  const raw = await callAI(messages, {
    model: aiConfig.visionModel,
    enableSearch: false,
    timeout: 90000
  });

  return parseVisionResult(raw);
}

/** 解析视觉模型返回的 JSON */
function parseVisionResult(raw) {
  try {
    // 尝试直接解析
    return JSON.parse(raw);
  } catch {
    // 从 markdown 代码块中提取 JSON
    const jsonMatch = raw.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[1].trim());
    }
    // 尝试找到 { ... } 结构
    const braceMatch = raw.match(/\{[\s\S]*\}/);
    if (braceMatch) {
      return JSON.parse(braceMatch[0]);
    }
    throw new Error('无法解析识图结果，请重试或更换图片');
  }
}

module.exports = { analyzeFoodImage };
