import { onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@/stores/user'

/**
 * 监听服务端文件变更事件（SSE）。
 * EventSource 不支持自定义 HTTP 请求头，JWT 通过查询参数 ?token= 传递。
 */
export function useFileWatcher(onChange) {
  let eventSource = null

  const connect = () => {
    const userStore = useUserStore()
    const token = userStore.token
    if (!token) {
      // 未登录，延迟重试
      setTimeout(connect, 3000)
      return
    }

    eventSource = new EventSource(`/api/file/watch?token=${encodeURIComponent(token)}`)

    eventSource.addEventListener('file-created', (e) => {
      try { onChange(JSON.parse(e.data)) } catch {}
    })

    eventSource.addEventListener('file-deleted', (e) => {
      try { onChange(JSON.parse(e.data)) } catch {}
    })

    eventSource.addEventListener('file-updated', (e) => {
      try { onChange(JSON.parse(e.data)) } catch {}
    })

    eventSource.addEventListener('sync-complete', () => {
      onChange({ type: 'sync' })
    })

    eventSource.addEventListener('connected', () => {
      // 连接成功
    })

    eventSource.onerror = () => {
      // EventSource 会自动重连
      eventSource?.close()
      setTimeout(connect, 3000)
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    eventSource?.close()
  })
}
