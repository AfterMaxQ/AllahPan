/**
 * Directory uploads may expose a relative path instead of a plain file name,
 * especially on Safari. Only the final path segment belongs in upload metadata.
 */
export function uploadFileName(file) {
  const candidate = file?.webkitRelativePath || file?.name || ''
  const normalized = candidate.replaceAll('\\', '/')
  return normalized.slice(normalized.lastIndexOf('/') + 1)
}
