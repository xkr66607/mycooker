import { defineStore } from 'pinia';
import {
  sendChatMessage,
  getConversations,
  getConversation,
  createConversation,
  saveMessage,
  deleteConversation
} from '@/api';

export const useChatStore = defineStore('chat', {
  state: () => ({
    /** 当前对话 ID */
    currentConversationId: null,
    /** 当前对话消息列表 */
    messages: [],
    /** 历史对话列表 */
    conversations: [],
    /** 是否正在等待 AI 回复 */
    loading: false,
    /** 侧边栏是否展开（桌面端） */
    sidebarOpen: true
  }),

  getters: {
    /** 供 AI 请求使用的历史上下文（不含 system） */
    historyForAI: (state) =>
      state.messages.map((m) => ({ role: m.role, content: m.content }))
  },

  actions: {
    /** 加载历史对话列表 */
    async fetchConversations() {
      const res = await getConversations();
      this.conversations = res.data || [];
    },

    /** 加载指定对话的消息 */
    async loadConversation(id) {
      const res = await getConversation(id);
      this.currentConversationId = res.data.conversation.id;
      this.messages = res.data.messages || [];
    },

    /** 开始新对话 */
    async startNewConversation() {
      const res = await createConversation('新对话');
      this.currentConversationId = res.data.id;
      this.messages = [];
      await this.fetchConversations();
      return res.data.id;
    },

    /** 发送用户消息并获取 AI 回复 */
    async sendMessage(content) {
      if (!content.trim() || this.loading) return;

      // 若无当前对话，先创建
      if (!this.currentConversationId) {
        await this.startNewConversation();
      }

      const userMsg = { role: 'user', content: content.trim() };
      this.messages.push({ ...userMsg, created_at: new Date().toISOString() });
      this.loading = true;

      try {
        // 持久化用户消息
        await saveMessage(this.currentConversationId, 'user', content.trim());

        // 请求 AI（携带历史上下文，不含刚加入的用户消息以避免重复）
        const history = this.messages.slice(0, -1).map((m) => ({
          role: m.role,
          content: m.content
        }));

        const res = await sendChatMessage(content.trim(), history);
        const aiContent = res.data.content;

        const aiMsg = { role: 'assistant', content: aiContent };
        this.messages.push({ ...aiMsg, created_at: new Date().toISOString() });

        // 持久化 AI 回复
        await saveMessage(this.currentConversationId, 'assistant', aiContent);
        await this.fetchConversations();
      } catch (err) {
        // 移除失败的用户消息
        this.messages.pop();
        throw err;
      } finally {
        this.loading = false;
      }
    },

    /** 删除对话 */
    async removeConversation(id) {
      await deleteConversation(id);
      if (this.currentConversationId === id) {
        this.currentConversationId = null;
        this.messages = [];
      }
      await this.fetchConversations();
    },

    /** 重置当前对话状态 */
    resetCurrent() {
      this.currentConversationId = null;
      this.messages = [];
    },

    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen;
    }
  }
});
