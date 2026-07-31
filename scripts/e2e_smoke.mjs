import { createHash } from 'node:crypto'

const baseUrl = process.env.ALLAHPAN_E2E_BASE_URL || 'http://127.0.0.1:88'
const email = process.env.ALLAHPAN_E2E_EMAIL
const password = process.env.ALLAHPAN_E2E_PASSWORD

if (!email || !password) {
  throw new Error('请设置 ALLAHPAN_E2E_EMAIL 和 ALLAHPAN_E2E_PASSWORD')
}

const tag = `codex-e2e-${Date.now()}`
let token = ''
const cleanupIds = new Set()
const favoriteIds = new Set()
const evidence = {}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers })
  const contentType = response.headers.get('content-type') || ''
  if (!response.ok) {
    throw new Error(`${options.method || 'GET'} ${path} -> HTTP ${response.status}`)
  }
  if (!contentType.includes('application/json')) return response
  const body = await response.json()
  if (body.code !== undefined && body.code !== 200) {
    throw new Error(`${options.method || 'GET'} ${path} -> ${body.code}: ${body.message}`)
  }
  return body.code === undefined ? body : body.data
}

function json(value) {
  return {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  }
}

async function removeTestRecord(id) {
  try {
    await request(`/api/favorite/${id}`, { method: 'DELETE' })
  } catch {}
  try {
    await request(`/api/file/${id}`, { method: 'DELETE' })
  } catch {}
  try {
    await request(`/api/file/trash/${id}`, { method: 'DELETE' })
  } catch {}
}

async function pollSearch(keyword, expectedId) {
  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    const result = await request(`/api/search?keyword=${encodeURIComponent(keyword)}&pageSize=20`)
    const hit = (result.list || []).find((item) => Number(item.fileId) === Number(expectedId))
    if (hit) return hit
    await new Promise((resolve) => setTimeout(resolve, 750))
  }
  throw new Error(`搜索索引在 30 秒内未出现文件 ${expectedId}`)
}

async function uploadChunks(folderId, fileName, bytes) {
  const chunkSize = 2 * 1024 * 1024
  const md5 = createHash('md5').update(bytes).digest('hex')
  const totalChunks = Math.ceil(bytes.length / chunkSize)
  const init = await request('/api/file/chunk/init', {
    method: 'POST',
    ...json({
      fileName,
      fileSize: bytes.length,
      fileMd5: md5,
      contentType: 'application/octet-stream',
      parentId: folderId,
      chunkSize,
      totalChunks,
    }),
  })
  if (!['new', 'resumed'].includes(init.status)) return { init, md5 }

  const uploaded = new Set(init.uploadedChunks || [])
  for (let index = 0; index < totalChunks; index++) {
    if (uploaded.has(index)) continue
    const start = index * chunkSize
    const form = new FormData()
    form.append('uploadId', init.uploadId)
    form.append('chunkIndex', String(index))
    form.append('chunk', new Blob([bytes.subarray(start, Math.min(start + chunkSize, bytes.length))]), 'chunk')
    await request('/api/file/chunk/upload', { method: 'POST', body: form })
  }
  return { init, md5 }
}

try {
  const index = await request('/')
  evidence.productionStatic = (await index.text()).includes('<div id="app"></div>')

  const login = await request('/api/auth/login-by-password', {
    method: 'POST',
    ...json({ email, password }),
  })
  token = login.token
  evidence.login = Boolean(token)

  const folder = await request('/api/file/create-folder', {
    method: 'POST',
    ...json({ folderName: tag, parentId: 0 }),
  })
  cleanupIds.add(folder.id)

  const smallText = `AllahPan ${tag} 可用性与搜索一致性验证`
  const form = new FormData()
  form.append('file', new Blob([smallText], { type: 'text/plain' }), `${tag}.txt`)
  form.append('parentId', String(folder.id))
  const small = await request('/api/file/upload', { method: 'POST', body: form })
  cleanupIds.add(small.id)

  const page = await request(`/api/file/list?parentId=${folder.id}&paged=true&pageNum=1&pageSize=100`)
  if (!(page.list || []).some((item) => Number(item.id) === Number(small.id))) {
    throw new Error('分页文件列表未返回刚上传的文件')
  }
  evidence.pagination = { total: page.total, pageSize: page.pageSize }

  const rangeResponse = await request(`/api/file/${small.id}/download`, {
    headers: { Range: 'bytes=0-7' },
  })
  const rangeText = Buffer.from(await rangeResponse.arrayBuffer()).toString('utf8')
  if (rangeResponse.status !== 206 || rangeText !== smallText.slice(0, 8)) {
    throw new Error('Range 下载内容或状态码不正确')
  }
  evidence.rangeDownload = {
    status: rangeResponse.status,
    contentRange: rangeResponse.headers.get('content-range'),
  }

  const renamed = await request(`/api/file/${small.id}/rename`, {
    method: 'PUT',
    ...json({ newName: `${tag}-renamed.txt` }),
  })
  if (renamed.storageKey !== small.storageKey) throw new Error('重命名不应复制或更换对象键')
  const moved = await request(`/api/file/${small.id}/move`, {
    method: 'PUT',
    ...json({ targetParentId: 0 }),
  })
  if (moved.storageKey !== small.storageKey) throw new Error('移动不应复制或更换对象键')
  await request(`/api/file/${small.id}/move`, {
    method: 'PUT',
    ...json({ targetParentId: folder.id }),
  })
  evidence.stableObjectKey = true

  await request(`/api/favorite/${small.id}`, { method: 'POST' })
  favoriteIds.add(small.id)
  const favorites = await request('/api/favorite/list?pageNum=1&pageSize=100')
  if (!favorites.some((item) => Number(item.id) === Number(small.id))) {
    throw new Error('收藏列表未返回刚收藏的文件')
  }
  await request(`/api/favorite/${small.id}`, { method: 'DELETE' })
  favoriteIds.delete(small.id)
  evidence.favoriteJoin = true

  const searchHit = await pollSearch(tag, small.id)
  evidence.search = { fileId: searchHit.fileId }

  const largeBytes = Buffer.alloc(10 * 1024 * 1024 + 123, 0x61)
  Buffer.from(tag).copy(largeBytes, 0)
  const firstName = `${tag}-large.bin`
  const firstUpload = await uploadChunks(folder.id, firstName, largeBytes)
  if (!['new', 'resumed'].includes(firstUpload.init.status)) {
    throw new Error(`首次分片上传状态异常: ${firstUpload.init.status}`)
  }
  const firstComplete = await request('/api/file/chunk/complete', {
    method: 'POST',
    ...json({ uploadId: firstUpload.init.uploadId }),
  })
  cleanupIds.add(firstComplete.id)
  const repeatedComplete = await request('/api/file/chunk/complete', {
    method: 'POST',
    ...json({ uploadId: firstUpload.init.uploadId }),
  })
  if (Number(repeatedComplete.id) !== Number(firstComplete.id)) {
    throw new Error('完成接口重试未返回同一结果')
  }

  const secondName = `${tag}-instant.bin`
  const instant = await uploadChunks(folder.id, secondName, largeBytes)
  if (instant.init.status !== 'instant') {
    throw new Error(`相同内容未走秒传: ${instant.init.status}`)
  }
  const instantComplete = await request('/api/file/chunk/complete', {
    method: 'POST',
    ...json({ uploadId: instant.init.uploadId }),
  })
  cleanupIds.add(instantComplete.id)
  if (instantComplete.storageKey !== firstComplete.storageKey) {
    throw new Error('秒传未复用已有存储对象')
  }
  await pollSearch(secondName, instantComplete.id)
  evidence.chunkUpload = {
    idempotentResult: true,
    instantUpload: true,
    instantIndexed: true,
    chunkCount: Math.ceil(largeBytes.length / (2 * 1024 * 1024)),
  }

  const sseController = new AbortController()
  const ssePromise = fetch(
    `${baseUrl}/api/file/watch?token=${encodeURIComponent(token)}`,
    { signal: sseController.signal },
  ).then(async (response) => {
    if (!response.ok) throw new Error(`SSE HTTP ${response.status}`)
    const reader = response.body.getReader()
    let text = ''
    const deadline = Date.now() + 35_000
    while (Date.now() < deadline) {
      const remaining = deadline - Date.now()
      const chunk = await Promise.race([
        reader.read(),
        new Promise((resolve) => setTimeout(() => resolve({ timeout: true }), remaining)),
      ])
      if (chunk.timeout || chunk.done) break
      text += Buffer.from(chunk.value).toString('utf8')
    }
    return text
  })

  const timings = []
  for (let i = 0; i < 20; i++) {
    const start = performance.now()
    await request('/api/file/list?parentId=0&paged=true&pageNum=1&pageSize=100')
    timings.push(performance.now() - start)
  }
  const sseText = await ssePromise
  sseController.abort()
  if (!sseText.includes(':connected') || !sseText.includes(':heartbeat')) {
    throw new Error('SSE 35 秒内未持续收到连接确认和心跳')
  }
  evidence.sseAndConcurrency = {
    connected: true,
    heartbeat: true,
    listAverageMs: Math.round(timings.reduce((a, b) => a + b, 0) / timings.length),
    listMaxMs: Math.round(Math.max(...timings)),
  }

  console.log(JSON.stringify({ success: true, tag, evidence }, null, 2))
} finally {
  for (const id of favoriteIds) {
    try { await request(`/api/favorite/${id}`, { method: 'DELETE' }) } catch {}
  }
  // 文件先于文件夹清理，确保只删除本次测试产生的数据。
  for (const id of [...cleanupIds].reverse()) {
    await removeTestRecord(id)
  }
}
