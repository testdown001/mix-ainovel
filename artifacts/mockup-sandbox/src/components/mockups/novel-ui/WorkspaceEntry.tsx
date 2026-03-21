import { useState } from 'react'

const NAV_ITEMS = ['灵感模式', '我的小说', '写作台', '设置']

const RECENT = [
  { title: '星际边疆', chapter: '第12章：未知信号', time: '2小时前', genre: '科幻', icon: '🚀' },
  { title: '剑破九霄', chapter: '第28章：破境', time: '昨天', genre: '仙侠', icon: '⚔️' },
  { title: '都市修仙录', chapter: '第5章：初入师门', time: '3天前', genre: '都市', icon: '🏙️' },
]

const UPDATES = [
  { text: 'AI模型升级至 GPT-4o，写作质量大幅提升', time: '今天', tag: '升级' },
  { text: '新增情感曲线分析功能', time: '2天前', tag: '新功能' },
  { text: '参考小说库新增300+热门网文', time: '1周前', tag: '内容' },
]

export default function WorkspaceEntry() {
  const [activeNav, setActiveNav] = useState('灵感模式')
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
              style={{ padding: '7px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500, background: activeNav === item ? '#141414' : 'transparent', color: activeNav === item ? '#FFE500' : '#888', transition: 'all 0.15s' }}>
              {item}
            </button>
          ))}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'linear-gradient(135deg, #FFE500, #e6ce00)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, color: '#000', fontSize: 15 }}>云</div>
          <span style={{ color: '#aaa', fontSize: 14 }}>云中君</span>
        </div>
      </nav>

      <div style={{ flex: 1, padding: '48px 40px', maxWidth: 1200, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
        {/* Hero greeting */}
        <div style={{ marginBottom: 48 }}>
          <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 900, fontSize: 44, color: '#fff', margin: '0 0 12px', letterSpacing: -1 }}>
            下午好，<span style={{ color: '#FFE500' }}>创作者</span> 👋
          </h1>
          <p style={{ color: '#666', fontSize: 16, margin: '0 0 28px' }}>你的故事在等待，今天继续写几章？</p>

          {/* Stats row */}
          <div style={{ display: 'flex', gap: 20 }}>
            {[
              { label: '创建小说', value: '3', unit: '部' },
              { label: '已写章节', value: '47', unit: '章' },
              { label: 'AI生成字数', value: '23.4万', unit: '字' },
              { label: '今日写作', value: '2,840', unit: '字' },
            ].map((stat, i) => (
              <div key={i} style={{ padding: '16px 24px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 14, display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
                <span style={{ color: '#555', fontSize: 12, fontWeight: 500 }}>{stat.label}</span>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                  <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 26, color: '#FFE500' }}>{stat.value}</span>
                  <span style={{ color: '#555', fontSize: 13 }}>{stat.unit}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Action cards 2-col */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 44 }}>
          {/* Inspiration mode */}
          <div style={{ padding: '36px', background: 'linear-gradient(135deg, #1A1800 0%, #141414 100%)', border: '1px solid #FFE50033', borderRadius: 20, position: 'relative', overflow: 'hidden', cursor: 'pointer' }}>
            <div style={{ position: 'absolute', top: -30, right: -30, width: 120, height: 120, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,229,0,0.12) 0%, transparent 70%)' }}/>
            <div style={{ width: 52, height: 52, borderRadius: 14, background: '#FFE500', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, marginBottom: 20 }}>💡</div>
            <h3 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 22, color: '#fff', margin: '0 0 8px' }}>灵感模式</h3>
            <p style={{ color: '#888', fontSize: 14, lineHeight: 1.6, margin: '0 0 24px' }}>还没有故事？让AI引导你从零开始，一步步构建你的小说世界。</p>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 22px', background: '#FFE500', color: '#000', borderRadius: 999, fontWeight: 700, fontSize: 14, fontFamily: "'Space Grotesk', sans-serif" }}>
              ⚡ 开启灵感模式
            </div>
          </div>

          {/* Novel library */}
          <div style={{ padding: '36px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 20, cursor: 'pointer', position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', top: -20, right: -20, width: 100, height: 100, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,255,255,0.03) 0%, transparent 70%)' }}/>
            <div style={{ width: 52, height: 52, borderRadius: 14, background: '#1C1C1C', border: '1px solid #2A2A2A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, marginBottom: 20 }}>📚</div>
            <h3 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 22, color: '#fff', margin: '0 0 8px' }}>我的小说库</h3>
            <p style={{ color: '#888', fontSize: 14, lineHeight: 1.6, margin: '0 0 24px' }}>查看并管理你所有的小说项目，章节进度一目了然。</p>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 22px', background: 'transparent', color: '#fff', border: '1px solid #2A2A2A', borderRadius: 999, fontWeight: 600, fontSize: 14 }}>
              📖 进入小说库
            </div>
          </div>
        </div>

        {/* Bottom: Recent + Updates */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 20 }}>
          {/* Recent activity */}
          <div>
            <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: '#fff', margin: '0 0 16px' }}>最近创作</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {RECENT.map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 14, cursor: 'pointer' }}>
                  <div style={{ width: 42, height: 42, borderRadius: 12, background: '#1C1C1C', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>{item.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                      <span style={{ fontWeight: 700, color: '#fff', fontSize: 14 }}>{item.title}</span>
                      <span style={{ padding: '1px 7px', background: '#FFE50022', color: '#FFE500', borderRadius: 999, fontSize: 11, fontWeight: 600 }}>{item.genre}</span>
                    </div>
                    <span style={{ color: '#666', fontSize: 13 }}>{item.chapter}</span>
                  </div>
                  <span style={{ color: '#444', fontSize: 12, flexShrink: 0 }}>{item.time}</span>
                  <span style={{ color: '#FFE500', fontSize: 16 }}>→</span>
                </div>
              ))}
            </div>
          </div>

          {/* Updates */}
          <div>
            <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: '#fff', margin: '0 0 16px' }}>更新日志</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {UPDATES.map((u, i) => (
                <div key={i} style={{ padding: '14px 18px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ padding: '2px 8px', background: i === 0 ? '#0A2A1A' : '#1C1C1C', color: i === 0 ? '#2ED573' : '#888', borderRadius: 6, fontSize: 11, fontWeight: 600 }}>{u.tag}</span>
                    <span style={{ color: '#444', fontSize: 11 }}>{u.time}</span>
                  </div>
                  <p style={{ color: '#aaa', fontSize: 13, lineHeight: 1.5, margin: 0 }}>{u.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
