import { useState } from 'react'

const NAV_ITEMS = ['灵感模式', '我的小说', '写作台', '设置']

const NOVELS = [
  { title: '剑域苍穹', genre: '玄幻', done: 12, total: 30, updated: '2小时前', status: 'active' },
  { title: '都市修真记', genre: '都市', done: 8, total: 20, updated: '昨天', status: 'active' },
  { title: '星际迷途', genre: '科幻', done: 5, total: 25, updated: '3天前', status: 'active' },
  { title: '锦绣山河', genre: '历史', done: 18, total: 40, updated: '1周前', status: 'done' },
  { title: '末世求生', genre: '末世', done: 0, total: 20, updated: '从未编辑', status: 'empty' },
  { title: '修仙问道', genre: '仙侠', done: 30, total: 30, updated: '1个月前', status: 'done' },
]

const FILTERS = ['全部', '进行中', '已完成']

const GENRE_ICONS: Record<string, string> = { '玄幻': '⚔️', '都市': '🏙️', '科幻': '🚀', '历史': '🏯', '末世': '💀', '仙侠': '☁️' }

export default function NovelWorkspace() {
  const [activeNav] = useState('我的小说')
  const [filter, setFilter] = useState('全部')
  const [query, setQuery] = useState('')

  const filtered = NOVELS.filter(n => {
    if (filter === '进行中' && n.status !== 'active') return false
    if (filter === '已完成' && n.status !== 'done') return false
    if (query && !n.title.includes(query)) return false
    return true
  })

  return (
    <div style={{ minHeight: '100vh', background: '#0A0A0A', fontFamily: 'Inter, sans-serif', color: '#fff' }}>
      {/* Nav */}
      <nav style={{ background: '#0A0A0A', borderBottom: '1px solid #1C1C1C', padding: '0 32px', height: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#FFE500', fontSize: 22, fontWeight: 700 }}>✦</span>
          <span style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 18 }}>Arboris Novel</span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {NAV_ITEMS.map(item => (
            <button key={item} style={{ padding: '6px 16px', borderRadius: 8, fontSize: 14, fontWeight: 500, border: 'none', cursor: 'pointer', background: activeNav === item ? '#1C1C1C' : 'transparent', color: activeNav === item ? '#FFE500' : '#888' }}>
              {item}
            </button>
          ))}
        </div>
        <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#FFE500', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#000', fontSize: 15, cursor: 'pointer' }}>创</div>
      </nav>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 32px' }}>
        {/* Page header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 36 }}>
          <div>
            <h1 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 900, fontSize: 40, marginBottom: 6 }}>我的小说库</h1>
            <p style={{ color: '#888', fontSize: 15 }}>共 {NOVELS.length} 部小说 · {NOVELS.reduce((s, n) => s + n.done, 0)} 章已生成</p>
          </div>
          <button style={{ background: '#FFE500', color: '#000', border: 'none', borderRadius: 12, padding: '12px 24px', fontWeight: 700, fontSize: 15, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18, fontWeight: 400 }}>+</span> 新建小说
          </button>
        </div>

        {/* Search + filters */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 32 }}>
          <div style={{ position: 'relative', flex: 1, maxWidth: 400 }}>
            <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: '#888', fontSize: 16 }}>🔍</span>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="搜索小说名称..."
              style={{ width: '100%', padding: '10px 16px 10px 44px', background: '#141414', border: '1px solid #2A2A2A', borderRadius: 12, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}
            />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {FILTERS.map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{ padding: '10px 20px', borderRadius: 12, fontSize: 14, fontWeight: 500, border: 'none', cursor: 'pointer', background: filter === f ? '#FFE500' : '#141414', color: filter === f ? '#000' : '#888', borderColor: '#2A2A2A', borderWidth: filter === f ? 0 : 1, borderStyle: 'solid' }}>
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Novel grid */}
        {filtered.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
            {filtered.map((n, i) => (
              <div key={i} style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 18, padding: 24, cursor: 'pointer', transition: 'border-color 0.2s' }}>
                {/* Card top */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
                  <div style={{ width: 52, height: 52, borderRadius: 14, background: '#1C1C1C', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26 }}>
                    {GENRE_ICONS[n.genre] || '📖'}
                  </div>
                  <span style={{ background: '#FFE500', color: '#000', fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 999 }}>{n.genre}</span>
                </div>

                <h3 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 18, marginBottom: 6 }}>{n.title}</h3>
                <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>上次编辑：{n.updated}</p>

                {/* Progress */}
                <div style={{ marginBottom: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ color: '#888', fontSize: 12 }}>章节进度</span>
                    <span style={{ color: '#fff', fontSize: 12, fontWeight: 600 }}>{n.done}/{n.total} 章</span>
                  </div>
                  <div style={{ height: 6, background: '#2A2A2A', borderRadius: 999 }}>
                    <div style={{ height: '100%', width: `${Math.round(n.done / n.total * 100)}%`, background: '#FFE500', borderRadius: 999 }}/>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: 10 }}>
                  <button style={{ flex: 1, padding: '9px', background: '#FFE500', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 13, color: '#000', cursor: 'pointer' }}>
                    进入写作台
                  </button>
                  <button style={{ flex: 1, padding: '9px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, fontWeight: 500, fontSize: 13, color: '#fff', cursor: 'pointer' }}>
                    查看详情
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '80px 0' }}>
            <div style={{ fontSize: 64, marginBottom: 20 }}>📭</div>
            <h3 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 22, marginBottom: 10 }}>还没有小说</h3>
            <p style={{ color: '#888', fontSize: 15, marginBottom: 28 }}>还没有小说，去灵感模式开始吧~</p>
            <button style={{ background: '#FFE500', color: '#000', border: 'none', borderRadius: 12, padding: '12px 28px', fontWeight: 700, fontSize: 15, cursor: 'pointer' }}>
              💡 进入灵感模式
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
