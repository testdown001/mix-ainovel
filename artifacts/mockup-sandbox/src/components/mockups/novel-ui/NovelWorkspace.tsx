import { useState } from 'react'

const NAV_ITEMS = ['灵感模式', '我的小说', '写作台', '设置']
const FILTERS = ['全部', '进行中', '已完成', '草稿']

const NOVELS = [
  { title: '星际边疆', genre: '科幻', icon: '🚀', done: 12, total: 30, lastEdit: '2小时前', progress: 40, color: '#0A1A2A' },
  { title: '剑破九霄', genre: '仙侠', icon: '⚔️', done: 28, total: 60, lastEdit: '昨天', progress: 47, color: '#2A1A0A' },
  { title: '都市修仙录', genre: '都市', icon: '🏙️', done: 5, total: 40, lastEdit: '3天前', progress: 12, color: '#0A1A0A' },
  { title: '末日之城', genre: '末世', icon: '💀', done: 20, total: 20, lastEdit: '1周前', progress: 100, color: '#2A0A0A' },
  { title: '穿越大明朝', genre: '历史', icon: '🏯', done: 8, total: 50, lastEdit: '2周前', progress: 16, color: '#1A1A0A' },
]

export default function NovelWorkspace() {
  const [activeFilter, setActiveFilter] = useState('全部')
  const [activeNav, setActiveNav] = useState('我的小说')
  const [search, setSearch] = useState('')

  return (
    <div style={{ minHeight: '100vh', background: '#0A0A0A', fontFamily: "'Inter', sans-serif", display: 'flex', flexDirection: 'column' }}>
      {/* Nav */}
      <nav style={{ display: 'flex', alignItems: 'center', padding: '0 40px', height: 64, borderBottom: '1px solid #141414', background: '#0A0A0A', position: 'sticky', top: 0, zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginRight: 'auto' }}>
          <div style={{ width: 32, height: 32, background: '#FFE500', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, color: '#000', fontSize: 16 }}>✦</div>
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, color: '#fff', fontSize: 16 }}>Arboris Novel</span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {NAV_ITEMS.map(item => (
            <button key={item} onClick={() => setActiveNav(item)}
              style={{ padding: '7px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500, background: activeNav === item ? '#141414' : 'transparent', color: activeNav === item ? '#FFE500' : '#888' }}>
              {item}
            </button>
          ))}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'linear-gradient(135deg, #FFE500, #e6ce00)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, color: '#000', fontSize: 15 }}>云</div>
          <span style={{ color: '#aaa', fontSize: 14 }}>云中君</span>
        </div>
      </nav>

      <div style={{ flex: 1, padding: '40px', maxWidth: 1280, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
        {/* Header row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32 }}>
          <div>
            <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 900, fontSize: 36, color: '#fff', margin: '0 0 6px', letterSpacing: -0.5 }}>我的小说库</h1>
            <p style={{ color: '#666', fontSize: 15, margin: 0 }}>共 {NOVELS.length} 部小说，{NOVELS.reduce((a,b)=>a+b.done,0)} 章已完成</p>
          </div>
          <button style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 22px', background: '#FFE500', color: '#000', border: 'none', borderRadius: 12, fontWeight: 800, fontSize: 14, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif" }}>
            <span style={{ fontSize: 18, lineHeight: 1 }}>+</span>
            新建小说
          </button>
        </div>

        {/* Search + filters */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
            <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: '#555', fontSize: 16 }}>🔍</span>
            <input
              readOnly
              value={search}
              placeholder="搜索小说标题..."
              style={{ width: '100%', padding: '10px 14px 10px 40px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}
            />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {FILTERS.map(f => (
              <button key={f} onClick={() => setActiveFilter(f)}
                style={{ padding: '9px 18px', borderRadius: 999, border: activeFilter===f ? '1px solid #FFE500' : '1px solid #2A2A2A', background: activeFilter===f ? '#FFE50015' : 'transparent', color: activeFilter===f ? '#FFE500' : '#888', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Novel card grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18, marginBottom: 20 }}>
          {NOVELS.map((novel, i) => (
            <div key={i} style={{ padding: '22px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 18, display: 'flex', flexDirection: 'column', gap: 16, cursor: 'pointer', transition: 'border-color 0.2s' }}>
              {/* Card header */}
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                <div style={{ width: 46, height: 46, borderRadius: 12, background: novel.color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0 }}>{novel.icon}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: '#fff', marginBottom: 4 }}>{novel.title}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ padding: '2px 9px', background: '#FFE50022', color: '#FFE500', borderRadius: 999, fontSize: 11, fontWeight: 700 }}>{novel.genre}</span>
                    {novel.progress === 100 && <span style={{ padding: '2px 9px', background: '#0A2A1A', color: '#2ED573', borderRadius: 999, fontSize: 11, fontWeight: 700 }}>已完成</span>}
                  </div>
                </div>
              </div>

              {/* Progress */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ color: '#666', fontSize: 12 }}>完成进度</span>
                  <span style={{ color: '#fff', fontSize: 12, fontWeight: 600 }}>{novel.done}/{novel.total} 章</span>
                </div>
                <div style={{ height: 5, background: '#1C1C1C', borderRadius: 999, overflow: 'hidden' }}>
                  <div style={{ width: `${novel.progress}%`, height: '100%', background: novel.progress === 100 ? '#2ED573' : '#FFE500', borderRadius: 999 }}/>
                </div>
              </div>

              <div style={{ color: '#555', fontSize: 12 }}>上次编辑：{novel.lastEdit}</div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 8 }}>
                <button style={{ flex: 1, padding: '9px', background: '#FFE500', color: '#000', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif" }}>
                  进入写作台
                </button>
                <button style={{ flex: 1, padding: '9px', background: 'transparent', color: '#888', border: '1px solid #2A2A2A', borderRadius: 10, fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
                  查看详情
                </button>
              </div>
            </div>
          ))}

          {/* Create new card */}
          <div style={{ padding: '22px', background: '#0D0D0D', border: '1px dashed #2A2A2A', borderRadius: 18, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, cursor: 'pointer', minHeight: 220 }}>
            <div style={{ width: 46, height: 46, borderRadius: 12, background: '#141414', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, color: '#FFE500' }}>+</div>
            <span style={{ color: '#555', fontSize: 14, fontWeight: 600 }}>创建新项目</span>
          </div>
        </div>
      </div>
    </div>
  )
}
