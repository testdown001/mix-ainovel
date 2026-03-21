import { useState } from 'react'

const NAV_ITEMS = ['灵感模式', '我的小说', '写作台', '设置']
const TABS = ['概览', '章节列表', '人物', '世界观', '大纲', '伏笔', '情感曲线', '设定库']

const STATS = [
  { label: '总字数', value: '38.2万', unit: '字', icon: '📝', color: '#0A1A2A' },
  { label: '章节数', value: '12/30', unit: '章', icon: '📚', color: '#1A1800' },
  { label: 'AI生成率', value: '94', unit: '%', icon: '🤖', color: '#0A2A1A' },
  { label: '平均质量', value: '8.7', unit: '分', icon: '⭐', color: '#2A1A0A' },
]

const CHAPTERS = [
  { num: 1, title: '序章：启程', words: '3,200字', score: 9.1, status: 'done' },
  { num: 2, title: '异星信号', words: '3,450字', score: 8.8, status: 'done' },
  { num: 3, title: '星舰"曙光"号', words: '3,100字', score: 9.2, status: 'done' },
  { num: 12, title: '未知信号', words: '3,240字', score: 8.6, status: 'pending' },
]

const CHARACTERS = [
  { name: '林晓东', role: '主角·舰长', emoji: '👨‍✈️' },
  { name: '陈曦', role: '通讯官', emoji: '👩‍💻' },
  { name: '博士·欧文', role: '科学家', emoji: '🧑‍🔬' },
  { name: '阿尔法', role: '未知存在', emoji: '👁️' },
]

export default function NovelDetail() {
  const [activeTab, setActiveTab] = useState('概览')
  const [activeNav, setActiveNav] = useState('我的小说')

  return (
    <div style={{ minHeight: '100vh', background: '#0A0A0A', fontFamily: "'Inter', sans-serif", display: 'flex', flexDirection: 'column' }}>
      {/* Nav */}
      <nav style={{ display: 'flex', alignItems: 'center', padding: '0 40px', height: 64, borderBottom: '1px solid #141414', background: '#0A0A0A', position: 'sticky', top: 0, zIndex: 10, flexShrink: 0 }}>
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
        </div>
      </nav>

      {/* Hero header */}
      <div style={{ background: '#0D0D0D', borderBottom: '1px solid #141414', padding: '40px 40px 0' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start', marginBottom: 32 }}>
            {/* Book cover placeholder */}
            <div style={{ width: 100, height: 140, background: '#0A1A2A', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40, flexShrink: 0, border: '1px solid #1C1C1C' }}>🚀</div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <span style={{ padding: '3px 12px', background: '#FFE50022', color: '#FFE500', borderRadius: 999, fontSize: 12, fontWeight: 700 }}>科幻</span>
                <span style={{ padding: '3px 12px', background: '#0A2A1A', color: '#2ED573', borderRadius: 999, fontSize: 12, fontWeight: 600 }}>进行中</span>
              </div>
              <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 900, fontSize: 40, color: '#fff', margin: '0 0 10px', letterSpacing: -1 }}>星际边疆</h1>
              <div style={{ display: 'flex', gap: 24, color: '#666', fontSize: 14, marginBottom: 16 }}>
                <span>作者：云中君</span>
                <span>创建于：2025年11月12日</span>
                <span>最近更新：2小时前</span>
              </div>
              <p style={{ color: '#888', fontSize: 15, lineHeight: 1.7, maxWidth: 600, margin: '0 0 20px' }}>
                在遥远的未来，人类已经踏足星际，但宇宙的黑暗深处隐藏着远超人类认知的存在……
              </p>
              <div style={{ display: 'flex', gap: 10 }}>
                <button style={{ padding: '10px 22px', background: '#FFE500', color: '#000', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 14, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif" }}>进入写作台</button>
                <button style={{ padding: '10px 22px', background: 'transparent', color: '#888', border: '1px solid #2A2A2A', borderRadius: 10, fontWeight: 600, fontSize: 14, cursor: 'pointer' }}>编辑设定</button>
              </div>
            </div>
            {/* Progress ring */}
            <div style={{ flexShrink: 0, textAlign: 'center' }}>
              <svg width="90" height="90" viewBox="0 0 90 90">
                <circle cx="45" cy="45" r="38" fill="none" stroke="#1C1C1C" strokeWidth="7"/>
                <circle cx="45" cy="45" r="38" fill="none" stroke="#FFE500" strokeWidth="7" strokeLinecap="round" strokeDasharray={`${0.4 * 2 * Math.PI * 38} ${2 * Math.PI * 38}`} transform="rotate(-90 45 45)"/>
                <text x="45" y="48" textAnchor="middle" fill="#fff" fontSize="16" fontFamily="Space Grotesk" fontWeight="800">40%</text>
              </svg>
              <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>完成进度</div>
            </div>
          </div>

          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 0, overflowX: 'auto' }}>
            {TABS.map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                style={{ padding: '12px 18px', border: 'none', borderBottom: activeTab === tab ? '2px solid #FFE500' : '2px solid transparent', background: 'transparent', color: activeTab === tab ? '#FFE500' : '#666', fontSize: 14, fontWeight: activeTab === tab ? 700 : 500, cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.15s' }}>
                {tab}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content area */}
      <div style={{ flex: 1, padding: '32px 40px', maxWidth: 1200, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 }}>
          {/* Main */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
              {STATS.map((s, i) => (
                <div key={i} style={{ padding: '20px 18px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 14 }}>
                  <div style={{ width: 38, height: 38, borderRadius: 10, background: s.color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, marginBottom: 12 }}>{s.icon}</div>
                  <div style={{ color: '#666', fontSize: 12, marginBottom: 4 }}>{s.label}</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
                    <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 22, color: '#FFE500' }}>{s.value}</span>
                    <span style={{ color: '#555', fontSize: 12 }}>{s.unit}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Recent chapters */}
            <div>
              <h3 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: '#fff', margin: '0 0 14px' }}>章节列表</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {CHAPTERS.map((ch, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 18px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 12, cursor: 'pointer' }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: ch.status === 'done' ? '#2ED573' : '#FFE500', flexShrink: 0 }}/>
                    <span style={{ color: '#555', fontSize: 12, width: 32 }}>#{ch.num}</span>
                    <span style={{ flex: 1, color: '#fff', fontWeight: 600, fontSize: 14 }}>{ch.title}</span>
                    <span style={{ color: '#555', fontSize: 12 }}>{ch.words}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ color: '#FFE500', fontSize: 12 }}>★</span>
                      <span style={{ color: '#888', fontSize: 12, fontWeight: 600 }}>{ch.score}</span>
                    </div>
                    <span style={{ color: '#FFE500', fontSize: 14 }}>→</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Characters */}
            <div>
              <h3 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: '#fff', margin: '0 0 14px' }}>主要人物</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {CHARACTERS.map((ch, i) => (
                  <div key={i} style={{ padding: '18px 14px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 12, textAlign: 'center', cursor: 'pointer' }}>
                    <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#1C1C1C', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, margin: '0 auto 10px' }}>{ch.emoji}</div>
                    <div style={{ fontWeight: 700, color: '#fff', fontSize: 13, marginBottom: 3 }}>{ch.name}</div>
                    <div style={{ color: '#666', fontSize: 11 }}>{ch.role}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: AI analysis */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ padding: '22px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <span style={{ fontSize: 18 }}>🤖</span>
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, color: '#fff', fontSize: 15 }}>AI 分析摘要</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[
                  { label: '叙事节奏', score: 88, color: '#2ED573' },
                  { label: '人物塑造', score: 82, color: '#FFE500' },
                  { label: '世界构建', score: 91, color: '#2ED573' },
                  { label: '情节张力', score: 76, color: '#FFE500' },
                ].map((item, i) => (
                  <div key={i}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                      <span style={{ color: '#888', fontSize: 13 }}>{item.label}</span>
                      <span style={{ color: '#fff', fontSize: 13, fontWeight: 700 }}>{item.score}</span>
                    </div>
                    <div style={{ height: 4, background: '#1C1C1C', borderRadius: 999, overflow: 'hidden' }}>
                      <div style={{ width: `${item.score}%`, height: '100%', background: item.color, borderRadius: 999 }}/>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 18, padding: '12px', background: '#0A0A0A', borderRadius: 10, border: '1px solid #1C1C1C' }}>
                <p style={{ color: '#888', fontSize: 12, lineHeight: 1.7, margin: 0 }}>
                  整体质量优秀，科幻世界观构建扎实。建议在第10-15章增加角色内心戏，丰富人物层次。
                </p>
              </div>
            </div>

            {/* Quick actions */}
            <div style={{ padding: '20px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16 }}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, color: '#fff', fontSize: 15, marginBottom: 14 }}>快速操作</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {['生成下一章', '更新世界观设定', '角色关系图谱', '情感曲线分析'].map((action, i) => (
                  <button key={i} style={{ padding: '10px 14px', background: i === 0 ? '#FFE500' : 'transparent', color: i === 0 ? '#000' : '#888', border: i === 0 ? 'none' : '1px solid #2A2A2A', borderRadius: 10, fontWeight: i === 0 ? 700 : 500, fontSize: 13, cursor: 'pointer', textAlign: 'left', fontFamily: i === 0 ? "'Space Grotesk', sans-serif" : 'inherit' }}>
                    {action}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
