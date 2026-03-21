import { useState } from 'react'

const NAV_ITEMS = ['灵感模式', '我的小说', '写作台', '设置']

const RECENT_NOVELS = [
  { title: '剑域苍穹', genre: '玄幻', chapters: 12, total: 30, updated: '2小时前', pct: 40 },
  { title: '都市修真记', genre: '都市', chapters: 8, total: 20, updated: '昨天', pct: 40 },
  { title: '星际迷途', genre: '科幻', chapters: 5, total: 25, updated: '3天前', pct: 20 },
  { title: '锦绣山河', genre: '历史', chapters: 18, total: 40, updated: '1周前', pct: 45 },
]

const UPDATES = [
  { tag: '更新', text: 'v2.1 上线：批量生成模式效率提升 40%', time: '今天' },
  { tag: '活动', text: '限时活动：高级版免费体验7天，立即领取', time: '昨天' },
  { tag: '提示', text: '新功能：伏笔追踪器已支持跨章节分析', time: '3天前' },
]

export default function WorkspaceEntry() {
  const [activeNav, setActiveNav] = useState('灵感模式')

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
            <button key={item} onClick={() => setActiveNav(item)} style={{ padding: '6px 16px', borderRadius: 8, fontSize: 14, fontWeight: 500, border: 'none', cursor: 'pointer', background: activeNav === item ? '#1C1C1C' : 'transparent', color: activeNav === item ? '#FFE500' : '#888' }}>
              {item}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#FFE500', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#000', fontSize: 15, cursor: 'pointer' }}>创</div>
        </div>
      </nav>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 32px' }}>
        {/* Greeting */}
        <div style={{ marginBottom: 48 }}>
          <h1 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 900, fontSize: 48, marginBottom: 8 }}>
            下午好，<span style={{ color: '#FFE500' }}>创作者</span> 👋
          </h1>
          <p style={{ color: '#888', fontSize: 16 }}>今天想写点什么？你的故事正在等待。</p>

          {/* Stats row */}
          <div style={{ display: 'flex', gap: 32, marginTop: 28 }}>
            {[['4', '部小说'], ['43', '章节'], ['8.6万', '字数']].map(([n, l]) => (
              <div key={l} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 28, color: '#FFE500' }}>{n}</span>
                <span style={{ color: '#888', fontSize: 14 }}>{l}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Action cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 48 }}>
          {/* Inspiration card */}
          <div style={{ background: '#FFE500', borderRadius: 20, padding: 32, cursor: 'pointer', position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', top: -20, right: -20, width: 120, height: 120, background: 'rgba(0,0,0,0.08)', borderRadius: '50%' }}/>
            <div style={{ position: 'absolute', bottom: -30, right: 20, width: 80, height: 80, background: 'rgba(0,0,0,0.05)', borderRadius: '50%' }}/>
            <div style={{ fontSize: 36, marginBottom: 16 }}>💡</div>
            <h3 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 800, fontSize: 24, color: '#000', marginBottom: 8 }}>灵感模式</h3>
            <p style={{ color: '#333', fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>还没有故事？让AI引导你从零开始，一步步构建你的世界。</p>
            <button style={{ background: '#000', color: '#FFE500', border: 'none', borderRadius: 10, padding: '10px 20px', fontWeight: 700, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              开始创作 →
            </button>
          </div>

          {/* Library card */}
          <div style={{ background: '#141414', borderRadius: 20, padding: 32, cursor: 'pointer', border: '1px solid #2A2A2A', position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', top: -20, right: -20, width: 120, height: 120, background: '#1C1C1C', borderRadius: '50%' }}/>
            <div style={{ fontSize: 36, marginBottom: 16 }}>📚</div>
            <h3 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 800, fontSize: 24, color: '#fff', marginBottom: 8 }}>我的小说库</h3>
            <p style={{ color: '#888', fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>查看并管理你所有的小说项目，随时继续上次的创作。</p>
            <button style={{ background: '#2A2A2A', color: '#fff', border: '1px solid #3A3A3A', borderRadius: 10, padding: '10px 20px', fontWeight: 600, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              进入书库 →
            </button>
          </div>
        </div>

        {/* Bottom row: Recent + Updates */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24 }}>
          {/* Recent novels */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <h2 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 18 }}>最近创作</h2>
              <span style={{ color: '#888', fontSize: 13, cursor: 'pointer' }}>查看全部 →</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {RECENT_NOVELS.map((n, i) => (
                <div key={i} style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 14, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 10, background: '#1C1C1C', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <span style={{ fontSize: 20 }}>📖</span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                      <span style={{ fontWeight: 600, fontSize: 15 }}>{n.title}</span>
                      <span style={{ background: '#FFE500', color: '#000', fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 999 }}>{n.genre}</span>
                    </div>
                    <div style={{ height: 4, background: '#2A2A2A', borderRadius: 999, marginBottom: 4 }}>
                      <div style={{ height: '100%', width: `${n.pct}%`, background: '#FFE500', borderRadius: 999 }}/>
                    </div>
                    <span style={{ color: '#888', fontSize: 12 }}>{n.chapters}/{n.total} 章 · {n.updated}</span>
                  </div>
                  <span style={{ color: '#888', fontSize: 18 }}>›</span>
                </div>
              ))}
            </div>
          </div>

          {/* Update log */}
          <div>
            <h2 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 18, marginBottom: 20 }}>平台动态</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {UPDATES.map((u, i) => (
                <div key={i} style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 12, padding: '14px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ background: u.tag === '活动' ? '#FFE500' : '#2A2A2A', color: u.tag === '活动' ? '#000' : '#888', fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 999 }}>{u.tag}</span>
                    <span style={{ color: '#888', fontSize: 12 }}>{u.time}</span>
                  </div>
                  <p style={{ color: '#ccc', fontSize: 13, lineHeight: 1.5 }}>{u.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
