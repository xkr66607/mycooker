<template>
  <div
    class="message"
    :class="[message.role === 'user' ? 'message--user' : 'message--ai']"
  >
    <div class="message-avatar">
      <span v-if="message.role === 'user'">👤</span>
      <span v-else>🧑‍🍳</span>
    </div>
    <div class="message-body">
      <div class="message-label">
        {{ message.role === 'user' ? '我' : '小厨 AI' }}
      </div>
      <div class="message-content">
        <div v-if="loading" class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
        <div v-else class="message-text" v-html="formattedContent"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  message: { type: Object, required: true },
  loading: { type: Boolean, default: false }
});

/** 简单 Markdown 渲染：换行、列表、加粗 */
const formattedContent = computed(() => {
  if (!props.message.content) return '';
  let text = props.message.content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/^[-•]\s+(.+)$/gm, '<li>$1</li>');
  text = text.replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul>${match}</ul>`);
  text = text.replace(/\n/g, '<br/>');

  return text;
});
</script>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
  animation: fadeIn 0.35s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.message--user {
  flex-direction: row-reverse;
  margin-left: auto;
}

.message--ai {
  margin-right: auto;
}

.message-avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  box-shadow: var(--shadow-sm);
}

.message--user .message-avatar {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
}

.message--ai .message-avatar {
  background: linear-gradient(135deg, #fef3e2, #fde8d0);
}

.message-body {
  flex: 1;
  min-width: 0;
}

.message-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}

.message--user .message-label {
  text-align: right;
}

.message-content {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  line-height: 1.7;
  font-size: 15px;
  transition: box-shadow var(--transition);
}

.message--user .message-content {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: var(--shadow-md);
}

.message--ai .message-content {
  background: var(--color-bg-card);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: 4px;
  box-shadow: var(--shadow-sm);
}

.message-text :deep(ul) {
  padding-left: 20px;
  margin: 8px 0;
}

.message-text :deep(li) {
  margin: 4px 0;
}

.message-text :deep(strong) {
  font-weight: 600;
}

/* 打字动画 */
.typing-indicator {
  display: flex;
  gap: 5px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary-light);
  animation: pulse-soft 1.2s ease-in-out infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
</style>
