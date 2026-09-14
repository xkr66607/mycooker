<template>
  <div
    class="upload-zone"
    :class="{ dragging, 'has-preview': previewUrl }"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="handleDrop"
    @click="triggerFileInput"
  >
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      hidden
      @change="handleFileChange"
    />

    <div v-if="previewUrl" class="preview-area">
      <img :src="previewUrl" alt="预览" class="preview-img" />
      <div class="preview-overlay">
        <el-button circle :icon="RefreshRight" @click.stop="triggerFileInput" />
        <el-button circle type="danger" :icon="Delete" @click.stop="clearPreview" />
      </div>
    </div>

    <div v-else class="upload-placeholder">
      <div class="upload-icon">📷</div>
      <p class="upload-title">点击或拖拽上传食材图片</p>
      <p class="upload-hint">支持 JPG、PNG、WEBP，最大 10MB</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { RefreshRight, Delete } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

const emit = defineEmits(['select', 'clear']);

const fileInput = ref(null);
const previewUrl = ref('');
const selectedFile = ref(null);
const dragging = ref(false);

function triggerFileInput() {
  fileInput.value?.click();
}

function handleFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 10MB');
    return;
  }
  selectedFile.value = file;
  previewUrl.value = URL.createObjectURL(file);
  emit('select', file);
}

function handleFileChange(e) {
  const file = e.target.files?.[0];
  if (file) handleFile(file);
}

function handleDrop(e) {
  dragging.value = false;
  const file = e.dataTransfer.files?.[0];
  if (file) handleFile(file);
}

function clearPreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = '';
  selectedFile.value = null;
  if (fileInput.value) fileInput.value.value = '';
  emit('clear');
}

defineExpose({ clearPreview, selectedFile });
</script>

<style scoped>
.upload-zone {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-card);
  cursor: pointer;
  transition: all var(--transition);
  overflow: hidden;
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-zone:hover,
.upload-zone.dragging {
  border-color: var(--color-primary-light);
  background: rgba(45, 106, 79, 0.04);
  box-shadow: var(--shadow-md);
}

.upload-placeholder {
  text-align: center;
  padding: 40px;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.upload-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary-dark);
  margin-bottom: 8px;
}

.upload-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.preview-area {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 240px;
}

.preview-img {
  width: 100%;
  height: 100%;
  min-height: 240px;
  object-fit: contain;
  background: #f5f5f5;
}

.preview-overlay {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity var(--transition);
}

.preview-area:hover .preview-overlay {
  opacity: 1;
}
</style>
