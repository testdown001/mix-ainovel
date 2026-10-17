export function formatReleaseTime(value: string | null | undefined) {
  // The API provides timezone-aware ISO timestamps. Never let browsers guess a
  // timezone for a legacy/invalid value and turn unknown metadata into a date.
  const hasTimezone =
    typeof value === 'string' &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
  const date = hasTimezone ? new Date(value) : null
  if (!date || !Number.isFinite(date.getTime())) {
    return { text: '未知', title: '未记录有效时间' }
  }
  return {
    text: date.toLocaleString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short',
    }),
    title: `${date.toISOString()} (UTC)`,
  }
}

export function releaseSourceLabel(source: string) {
  switch (source) {
    case 'image':
      return '构建镜像'
    case 'environment':
      return '部署环境'
    case 'git':
      return '开发目录 Git'
    default:
      return '未知来源'
  }
}
