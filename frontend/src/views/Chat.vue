<template>
  <div class="chat-page">
    <HistorySidebar />

    <div class="chat-main">
      <!-- 消息区域 -->
      <div ref="messagesRef" class="messages-area">
        <!-- 欢迎界面 -->
        <div v-if="chatStore.messages.length === 0 && !chatStore.loading" class="welcome">
          <div class="welcome-icon">🧑‍🍳</div>
          <h2>你好，我是小厨 AI</h2>
          <p>您的私人厨房助手，专注饮食搭配、菜谱推荐、烹饪技巧等厨房话题</p>
          <div class="quick-questions">
            <div
              v-for="q in quickQuestions"
              :key="q"
              class="quick-q"
              @click="handleSend(q)"
            >
              {{ q }}
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="messages-list">
          <ChatMessage
            v-for="(msg, idx) in chatStore.messages"
            :key="idx"
            :message="msg"
          />
          <ChatMessage
            v-if="chatStore.loading"
            :message="{ role: 'assistant', content: '' }"
            :loading="true"
          />
        </div>
      </div>

      <!-- 输入区域 -->
      <ChatInput :loading="chatStore.loading" @send="handleSend" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useChatStore } from '@/stores/chat';
import ChatMessage from '@/components/ChatMessage.vue';
import ChatInput from '@/components/ChatInput.vue';
import HistorySidebar from '@/components/HistorySidebar.vue';

const route = useRoute();
const router = useRouter();
const chatStore = useChatStore();
const messagesRef = ref(null);

const quickQuestions = [
  '🍳 番茄炒蛋怎么做？',
  '🥗 推荐一份低卡晚餐',
  '🧊 蔬菜怎么保存更久？',
  '💪 一周减脂餐计划'
];

/** 路由变化时加载对应对话 */
onMounted(async () => {
  if (route.params.id) {
    await chatStore.loadConversation(Number(route.params.id));
  }
});

watch(
  () => route.params.id,
  async (id) => {
    if (id) {
      await chatStore.loadConversation(Number(id));
    } else {
      chatStore.resetCurrent();
    }
  }
);

/** 消息更新后滚动到底部 */
watch(
  () => [chatStore.messages.length, chatStore.loading],
  async () => {
    await nextTick();
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
    }
  }
);

async function handleSend(text) {
  try {
    await chatStore.sendMessage(text);
    // 新对话创建后更新 URL
    if (chatStore.currentConversationId && !route.params.id) {
      router.replace(`/chat/${chatStore.currentConversationId}`);
    }
  } catch (err) {
    ElMessage.error(err.message || '发送失败，请稍后重试');
  }
}
</script>

<style scoped>
.chat-page {
  display: flex;
  height: calc(100vh - 64px);
  overflow: hidden;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--color-bg);
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

/* 欢迎界面 */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  text-align: center;
  padding: 40px 20px;
  animation: fadeIn 0.5s ease;
}

.welcome-icon {
  font-size: 64px;
  margin-bottom: 20px;
  animation: float 3s ease-in-out infinite;
}

.welcome h2 {
  font-family: var(--font-display);
  font-size: 28px;
  color: var(--color-primary-dark);
  margin-bottom: 10px;
}

.welcome p {
  color: var(--color-text-secondary);
  font-size: 15px;
  max-width: 420px;
  line-height: 1.7;
  margin-bottom: 32px;
}

.quick-questions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  max-width: 520px;
  width: 100%;
}

.quick-q {
  padding: 14px 18px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition);
  text-align: left;
}

.quick-q:hover {
  border-color: var(--color-primary-light);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

/* 消息列表 */
.messages-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
  padding-bottom: 16px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .messages-area { padding: 16px; }
  .quick-questions { grid-template-columns: 1fr; }
}
</style>
