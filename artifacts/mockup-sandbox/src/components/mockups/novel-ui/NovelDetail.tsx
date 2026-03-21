import { useState } from 'react'

const NAV_ITEMS = ['灵感模式', '我的小说', '写作台', '设置']
const TABS = ['概览', '章节列表', '人物', '世界观', '大纲', '伏笔', '情感曲线', '设定库']

const CHAPTERS = [
  { num: 1, title: '序章：命运的起点', words: 1240, quality: 92, status: '已生成' },
  { num: 2, title: '初入江湖', words: 1520, quality: 88, status: '已生成' },
  { num: 3, title: '师门危机', words: 1380, quality: 85, status: '已生成' },
  { num: 4, title: '破境之路', words: 1610, quality: 91, status: '已生成' },
  { num: 5, title: '山外有山', words: 1290, quality: 87, status: '已生成' },
]

const CHARACTERS = [
  { name: '陆天远', role: '主角', color: '#FFE500', desc: '天才剑修，性格坚毅' },
  { name: '苏晴雪', role: '女主', color: '#2ED573', desc: '冰雪宗传人，内敛温柔' },
  { name: '玄剑老人', role: '导师', color: '#888', desc: '神秘强者，身世成谜' },
  { name: '魔皇血炎', role: '反派', color: '#FF4757', desc: '千年魔修，野心勃勃' },
]

export default function NovelDetail() {
  const [activeTab, setActiveTab] = useState('概览')
  const [activeNav] = useState('我的小说')

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

      {/* Hero header */}
      <div style={{ background: '#0D0D0D', borderBottom: '1px solid #1C1C1C', padding: '40px 32px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', gap: 40, alignItems: 'center' }}>
          {/* Novel icon */}
          <div style={{ width: 100, height: 100, borderRadius: 20, background: '#1C1C1C', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48, flexShrink: 0 }}>⚔️</div>

          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <h1 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 900, fontSize: 36 }}>剑域苍穹</h1>
              <span style={{ background: '#FFE500', color: '#000', fontSize: 12, fontWeight: 700, padding: '3px 12px', borderRadius: 999 }}>玄幻</span>
              <span style={{ background: '#1C1C1C', color: '#888', fontSize: 12, padding: '3px 12px', borderRadius: 999, border: '1px solid #2A2A2A' }}>进行中</span>
            </div>
            <div style={{ display: 'flex', gap: 20, color: '#888', fontSize: 14, marginBottom: 20 }}>
              <span>作者：创作者</span>
              <span>创建于：2024年1月15日</span>
              <span>上次编辑：2小时前</span>
            </div>
            <div style={{ display: 'flex', gap: 16 }}>
              <button style={{ background: '#FFE500', color: '#000', border: 'none', borderRadius: 10, padding: '10px 24px', fontWeight: 700, fontSize: 14, cursor: 'pointer' }}>进入写作台</button>
              <button style={{ background: '#1C1C1C', color: '#fff', border: '1px solid #2A2A2A', borderRadius: 10, padding: '10px 24px', fontWeight: 500, fontSize: 14, cursor: 'pointer' }}>生成大纲</button>
              <button style={{ background: 'transparent', color: '#888', border: '1px solid #2A2A2A', borderRadius: 10, padding: '10px 16px', cursor: 'pointer' }}>⋮</button>
            </div>
          </div>

          {/* Progress ring */}
          <div style={{ flexShrink: 0, textAlign: 'center' }}>
            <svg width="100" height="100" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="#1C1C1C" strokeWidth="8"/>
              <circle cx="50" cy="50" r="42" fill="none" stroke="#FFE500" strokeWidth="8" strokeDasharray={`${2 * Math.PI * 42 * 0.4} ${2 * Math.PI * 42 * 0.6}`} strokeLinecap="round" strokeDashoffset={2 * Math.PI * 42 * 0.25} style={{ transform: 'rotate(-90deg)', transformOrigin: '50px 50px' }}/>
              <text x="50" y="46" textAnchor="middle" fill="#FFE500" fontSize="18" fontWeight="700" fontFamily="Space Grotesk, sans-serif">40%</text>
              <text x="50" y="62" textAnchor="middle" fill="#888" fontSize="10">完成率</text>
            </svg>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ borderBottom: '1px solid #1C1C1C', padding: '0 32px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', gap: 0 }}>
          {TABS.map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{ padding: '16px 20px', fontSize: 14, fontWeight: 500, border: 'none', cursor: 'pointer', background: 'transparent', color: activeTab === tab ? '#FFE500' : '#888', borderBottom: activeTab === tab ? '2px solid #FFE500' : '2px solid transparent' }}>
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Main content */}
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '36px 32px', display: 'grid', gridTemplateColumns: '1fr 280px', gap: 32 }}>
        <div>
          {/* Stats row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 36 }}>
            {[
              { label: '总字数', value: '1.5万', icon: '📝', color: '#FFE500' },
              { label: '章节数', value: '12', icon: '📚', color: '#2ED573' },
              { label: 'AI生成率', value: '95%', icon: '🤖', color: '#888' },
              { label: '平均质量', value: '88', icon: '⭐', color: '#FFE500' },
            ].map((s, i) => (
              <div key={i} style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16, padding: '20px 20px' }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>{s.icon}</div>
                <div style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 28, color: s.color, marginBottom: 4 }}>{s.value}</div>
                <div style={{ color: '#888', fontSize: 13 }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Recent chapters */}
          <div style={{ marginBottom: 32 }}>
            <h3 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 16, marginBottom: 16 }}>最近章节</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {CHAPTERS.map(ch => (
                <div key={ch.num} style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 12, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer' }}>
                  <span style={{ color: '#888', fontWeight: 600, fontSize: 13, width: 28 }}>#{ch.num}</span>
                  <span style={{ flex: 1, fontWeight: 500, fontSize: 14 }}>{ch.title}</span>
                  <span style={{ color: '#888', fontSize: 13 }}>{ch.words.toLocaleString()} 字</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ color: '#FFE500', fontSize: 13 }}>★</span>
                    <span style={{ color: '#fff', fontSize: 13, fontWeight: 600 }}>{ch.quality}</span>
                  </div>
                  <span style={{ background: '#2ED57322', color: '#2ED573', fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999 }}>{ch.status}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Characters grid */}
          <div>
            <h3 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 16, marginBottom: 16 }}>关键人物</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
              {CHARACTERS.map(c => (
                <div key={c.name} style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 14, padding: '18px 14px', textAlign: 'center', cursor: 'pointer' }}>
                  <div style={{ width: 52, height: 52, borderRadius: '50%', background: c.color + '22', border: `2px solid ${c.color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 10px', fontSize: 20, fontWeight: 700, color: c.color }}>
                    {c.name[0]}
                  </div>
                  <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{c.name}</div>
                  <div style={{ color: c.color, fontSize: 11, fontWeight: 600, marginBottom: 6 }}>{c.role}</div>
                  <div style={{ color: '#888', fontSize: 12, lineHeight: 1.4 }}>{c.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right AI analysis column */}
        <div>
          <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16, padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <span style={{ fontSize: 16 }}>🤖</span>
              <span style={{ fontWeight: 600, fontSize: 14 }}>AI 分析摘要</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                { label: '剧情节奏', score: 82, color: '#FFE500' },
                { label: '人物塑造', score: 88, color: '#2ED573' },
                { label: '世界观丰富度', score: 75, color: '#888' },
                { label: '文笔质量', score: 91, color: '#FFE500' },
              ].map(m => (
                <div key={m.label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ color: '#aaa', fontSize: 13 }}>{m.label}</span>
                    <span style={{ color: m.color, fontWeight: 700, fontSize: 13 }}>{m.score}</span>
                  </div>
                  <div style={{ height: 4, background: '#2A2A2A', borderRadius: 999 }}>
                    <div style={{ width: `${m.score}%`, height: '100%', background: m.color, borderRadius: 999 }}/>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 20, padding: 14, background: '#1C1C1C', borderRadius: 12 }}>
              <p style={{ color: '#aaa', fontSize: 13, lineHeight: 1.7 }}>整体质量优秀。建议在第6章加强反派的动机描写，以增强冲突张力。伏笔"玄剑传承"需要在后续章节中及时回收。</p>
            </div>
            <button style={{ width: '100%', marginTop: 16, padding: '10px', background: '#FFE500', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 13, color: '#000', cursor: 'pointer' }}>深度分析报告</button>
          </div>
        </div>
      </div>
    </div>
  )
}
