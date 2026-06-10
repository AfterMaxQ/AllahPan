import SparkMD5 from 'spark-md5'

/**
 * 分片计算文件 MD5，避免大文件内存溢出。
 * @param {File} file
 * @param {Function} onProgress - 回调 (0-100)
 * @returns {Promise<string>}
 */
export function calculateMD5(file, onProgress) {
  return new Promise((resolve, reject) => {
    const chunkSize = 2 * 1024 * 1024 // 2MB
    const chunks = Math.ceil(file.size / chunkSize)
    let currentChunk = 0
    const spark = new SparkMD5.ArrayBuffer()
    const fileReader = new FileReader()

    fileReader.onload = (e) => {
      spark.append(e.target.result)
      currentChunk++

      if (currentChunk < chunks) {
        if (onProgress) onProgress(Math.round((currentChunk / chunks) * 100))
        loadNext()
      } else {
        if (onProgress) onProgress(100)
        resolve(spark.end())
      }
    }

    fileReader.onerror = () => reject(new Error('文件读取失败'))

    const loadNext = () => {
      const start = currentChunk * chunkSize
      const end = Math.min(start + chunkSize, file.size)
      fileReader.readAsArrayBuffer(file.slice(start, end))
    }

    loadNext()
  })
}
