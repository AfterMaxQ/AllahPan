<template>
  <transition name="transfer-slide">
    <aside v-if="transferStore.panelVisible" class="transfer-panel" :class="{ mobile: isMobile }">
      <div class="panel-header">
        <div>
          <h3>传输列表</h3>
          <p>网络速度 {{ formatSpeed(transferStore.totalSpeed) }}</p>
        </div>
        <el-button text circle :icon="Close" @click="transferStore.closePanel()" />
      </div>

      <el-tabs v-model="activeTab" stretch>
        <el-tab-pane :label="`上传 ${transferStore.uploads.length}`" name="upload">
          <div class="panel-toolbar">
            <span>{{ uploadRunningText }}</span>
            <el-button text size="small" @click="transferStore.clearFinished('upload')">清空已完成</el-button>
          </div>
          <div v-if="transferStore.uploads.length" class="task-list">
            <TransferTaskItem
              v-for="task in transferStore.uploads"
              :key="task.id"
              :task="task"
              @cancel="transferStore.cancelTask"
              @retry="transferStore.retryTask"
            />
          </div>
          <el-empty v-else description="暂无上传任务" :image-size="80" />
        </el-tab-pane>

        <el-tab-pane :label="`下载 ${transferStore.downloads.length}`" name="download">
          <div class="panel-toolbar">
            <span>{{ downloadRunningText }}</span>
            <el-button text size="small" @click="transferStore.clearFinished('download')">清空已完成</el-button>
          </div>
          <div v-if="transferStore.downloads.length" class="task-list">
            <TransferTaskItem
              v-for="task in transferStore.downloads"
              :key="task.id"
              :task="task"
              @cancel="transferStore.cancelTask"
              @retry="transferStore.retryTask"
            />
          </div>
          <el-empty v-else description="暂无下载任务" :image-size="80" />
        </el-tab-pane>
      </el-tabs>
    </aside>
  </transition>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Close } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import { useTransferStore } from '@/stores/transfer'
import { formatSpeed } from '@/utils/transfer'
import TransferTaskItem from './TransferTaskItem.vue'

const { isMobile } = useResponsive()
const transferStore = useTransferStore()
const activeTab = ref('upload')

const uploadRunningText = computed(() => {
  const running = transferStore.uploads.filter((task) => task.status === 'running').length
  const queued = transferStore.uploads.filter((task) => task.status === 'queued').length
  return `进行中 ${running}，等待 ${queued}`
})

const downloadRunningText = computed(() => {
  const running = transferStore.downloads.filter((task) => task.status === 'running').length
  const queued = transferStore.downloads.filter((task) => task.status === 'queued').length
  return `进行中 ${running}，等待 ${queued}`
})
</script>

<style scoped>
.transfer-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 380px;
  height: 100vh;
  z-index: 2200;
  padding: 18px;
  background: var(--ap-bg-page);
  border-left: 1px solid var(--ap-border-color);
  box-shadow: -12px 0 28px rgba(61, 50, 38, 0.08);
  display: flex;
  flex-direction: column;
}
.transfer-panel.mobile {
  top: auto;
  bottom: 0;
  left: 0;
  width: 100vw;
  height: 70vh;
  border-left: none;
  border-top: 1px solid var(--ap-border-color);
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -8px 28px rgba(61, 50, 38, 0.1);
  padding: 12px 16px;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
}
.panel-header h3 {
  margin: 0 0 4px 0;
  font-size: 18px;
  color: var(--ap-text-main);
}
.panel-header p {
  margin: 0;
  font-size: 12px;
  color: var(--ap-text-sub);
}
.panel-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--ap-text-sub);
}
.task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: calc(100vh - 180px);
  overflow-y: auto;
  padding-right: 4px;
}
.transfer-panel.mobile .task-list {
  max-height: calc(70vh - 140px);
}
.transfer-slide-enter-active,
.transfer-slide-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.transfer-slide-enter-from,
.transfer-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
@media (max-width: 768px) {
  .transfer-slide-enter-from,
  .transfer-slide-leave-to {
    transform: translateY(100%);
  }
}
</style>
