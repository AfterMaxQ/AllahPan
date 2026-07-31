import { onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@/stores/user'

/**
 * 监听服务端文件变更事件（SSE）。
 * EventSource 不支持自定义 HTTP 请求头，JWT 通过查询参数 ?token= 传递。
 */
export function useFileWatcher(onChange) {
  let eventSource = null
  let retryTimer = null
  let stopped = false

  const connect = () => {
    if (stopped) return
    const userStore = useUserStore()
    const token = userStore.token
    if (!token) {
      // 未登录，延迟重试
      retryTimer = setTimeout(connect, 3000)
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
      // 浏览器原生 EventSource 会按服务端 retry 指令自动重连。
      // 不主动 close + 新建，避免一次断线产生多个并行连接和计时器。
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    stopped = true
    if (retryTimer) clearTimeout(retryTimer)
    eventSource?.close()
  })
}
