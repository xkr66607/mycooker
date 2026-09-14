<template>
  <div class="chat-input-wrapper">
    <div class="chat-input-card">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="1"
        :autosize="{ minRows: 1, maxRows: 5 }"
        placeholder="问我任何厨房问题，例如：番茄炒蛋怎么做？"
        :disabled="loading"
        @keydown.enter.exact.prevent="handleSend"
      />
      <el-button
        type="primary"
        :icon="Promotion"
        circle
        class="send-btn"
        :loading="loading"
        :disabled="!inputText.trim()"
        @click="handleSend"
      />
    </div>
    <p class="input-hint">Enter 发送 · Shift+Enter 换行 · 仅限厨房饮食相关话题</p>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { Promotion } from '@element-plus/icons-vue';

defineProps({
  loading: { type: Boolean, default: false }
});

const emit = defineEmits(['send']);
const inputText = ref('');

function handleSend() {
  const text = inputText.value.trim();
  if (!text) return;
  emit('send', text);
  inputText.value = '';
}
</script>

<style scoped>
.chat-input-wrapper {
  padding: 16px 24px 20px;
  background: linear-gradient(to top, var(--color-bg) 80%, transparent);
}

.chat-input-card {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px 16px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  transition: border-color var(--transition), box-shadow var(--transition);
}

.chat-input-card:focus-within {
  border-color: var(--color-primary-light);
  box-shadow: var(--shadow-lg);
}

.chat-input-card :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none !important;
  padding: 4px 0;
  font-size: 15px;
  font-family: var(--font-body);
  resize: none;
  background: transparent;
}

.send-btn {
  flex-shrink: 0;
  width: 42px !important;
  height: 42px !important;
}

.input-hint {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 10px;
}
</style>
