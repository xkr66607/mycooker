import axios from 'axios';

/** 统一 axios 实例，开发环境通过 Vite 代理转发到后端 */
const request = axios.create({
  baseURL: '/api',
  timeout: 180000,
  headers: { 'Content-Type': 'application/json' }
});

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message =
      error.response?.data?.message ||
      error.message ||
      '网络请求失败，请检查后端服务是否启动';
    return Promise.reject(new Error(message));
  }
);

/** 发送聊天消息 */
export function sendChatMessage(message, history = []) {
  return request.post('/chat', { message, history });
}

/** 获取对话列表 */
export function getConversations() {
  return request.get('/history');
}

/** 获取对话详情（含消息） */
export function getConversation(id) {
  return request.get(`/history/${id}`);
}

/** 创建新对话 */
export function createConversation(title) {
  return request.post('/history', { title });
}

/** 保存消息到对话 */
export function saveMessage(conversationId, role, content) {
  return request.post(`/history/${conversationId}/messages`, { role, content });
}

/** 删除对话 */
export function deleteConversation(id) {
  return request.delete(`/history/${id}`);
}

/** 健康检查 */
export function checkHealth() {
  return request.get('/health');
}

/** 上传图片并识图 + 搜菜谱 */
export function analyzeImage(file) {
  const formData = new FormData();
  formData.append('image', file);
  return request.post('/image/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  });
}

/** 识图历史列表 */
export function getImageHistory() {
  return request.get('/image/history');
}

/** 识图详情 */
export function getImageDetail(id) {
  return request.get(`/image/history/${id}`);
}

/** 获取用户记忆 */
export function getMemories(category) {
  return request.get('/memory', { params: category ? { category } : {} });
}

/** 保存用户偏好记忆 */
export function saveMemory(key, value) {
  return request.post('/memory', { key, value });
}

/** 删除记忆 */
export function deleteMemory(id) {
  return request.delete(`/memory/${id}`);
}

export default request;
