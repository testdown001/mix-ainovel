import { useState } from 'react'

type ChapterStatus = 'done' | 'pending' | 'empty'

const CHAPTERS: { num: number; title: string; status: ChapterStatus }[] = [
  { num: 1, title: '序章：命运的起点', status: 'done' },
  { num: 2, title: '初入江湖', status: 'done' },
  { num: 3, title: '师门危机', status: 'done' },
  { num: 4, title: '破境之路', status: 'done' },
  { num: 5, title: '山外有山', status: 'pending' },
  { num: 6, title: '古剑出世', status: 'pending' },
  { num: 7, title: '未命名章节', status: 'empty' },
  { num: 8, title: '未命名章节', status: 'empty' },
  { num: 9, title: '未命名章节', status: 'empty' },
  { num: 10, title: '未命名章节', status: 'empty' },
  { num: 11, title: '未命名章节', status: 'empty' },
  { num: 12, title: '未命名章节', status: 'empty' },
]

const STATUS_COLOR: Record<ChapterStatus, string> = { done: '#2ED573', pending: '#FFE500', empty: '#3A3A3A' }
const STATUS_LABEL: Record<ChapterStatus, string> = { done: '已生成', pending: '待生成', empty: '空白' }

const CHAPTER_CONTENT = `剑鸣山巅，云雾弥漫。

陆天远站在险峰之上，衣袂随风飘荡，眼神深邃而坚定。身后，千里江山如画卷般铺展，而眼前，却是一道横亘天地的剑气屏障。

"终于到了。"他喃喃自语，声音低沉，带着几分疲惫与期待。

三年。整整三年，他从一个名不见经传的山野小子，一路斩妖除魔，踏过无数尸山血海，终于站到了这里——传说中的剑域入口。

"小子，你真的准备好了吗？"

声音从虚空中传来，苍老而威严，如同天地之音。陆天远未曾转身，只是缓缓握紧了腰间那把历经岁月的古朴长剑。

"准备好了，没有？"他反问，嘴角微微上扬，"不重要。"

"不管准没准备好，我都要进去。"

静默片刻，虚空中爆发出一阵朗笑声。`

export default function WritingDesk() {
  const [activeChapter, setActiveChapter] = useState(4)
  const [generating, setGenerating] = useState(false)

  const handleGenerate = () => {
    setGenerating(true)
    setTimeout(() => setGenerating(false), 2000)
  }

  return (
    <div style={{ height: '100vh', background: '#0A0A0A', fontFamily: 'Inter, sans-serif', color: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <header style={{ height: 56, background: '#0A0A0A', borderBottom: '1px solid #1C1C1C', display: 'flex', alignItems: 'center', padding: '0 20px', gap: 16, flexShrink: 0, zIndex: 20 }}>
        <button style={{ width: 34, height: 34, borderRadius: 8, background: '#141414', border: '1px solid #2A2A2A', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff', fontSize: 16 }}>←</button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
          <span style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 16 }}>剑域苍穹</span>
          <span style={{ color: '#2A2A2A' }}>·</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, maxWidth: 300 }}>
            <div style={{ flex: 1, height: 4, background: '#1C1C1C', borderRadius: 999 }}>
              <div style={{ width: '40%', height: '100%', background: '#FFE500', borderRadius: 999 }}/>
            </div>
            <span style={{ color: '#888', fontSize: 12, whiteSpace: 'nowrap' }}>12/30 章</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button style={{ padding: '7px 16px', background: '#141414', border: '1px solid #2A2A2A', borderRadius: 8, color: '#fff', fontSize: 13, cursor: 'pointer' }}>查看详情</button>
          <button style={{ padding: '7px 16px', background: '#FFE500', border: 'none', borderRadius: 8, color: '#000', fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>生成大纲</button>
        </div>
      </header>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left sidebar */}
        <aside style={{ width: 260, background: '#0D0D0D', borderRight: '1px solid #1C1C1C', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
          <div style={{ padding: '16px 16px 8px' }}>
            <p style={{ color: '#888', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>章节列表</p>
            <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
              {Object.entries(STATUS_LABEL).map(([s, l]) => (
                <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: 7, height: 7, borderRadius: '50%', background: STATUS_COLOR[s as ChapterStatus] }}/>
                  <span style={{ color: '#888', fontSize: 11 }}>{l}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
            {CHAPTERS.map(ch => (
              <div key={ch.num} onClick={() => setActiveChapter(ch.num)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 10px', borderRadius: 10, marginBottom: 2, cursor: 'pointer', background: activeChapter === ch.num ? '#1C1C1C' : 'transparent' }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: STATUS_COLOR[ch.status], flexShrink: 0 }}/>
                <span style={{ color: '#888', fontSize: 12, flexShrink: 0, fontWeight: 600, width: 24 }}>{String(ch.num).padStart(2, '0')}</span>
                <span style={{ color: activeChapter === ch.num ? '#fff' : (ch.status === 'empty' ? '#555' : '#aaa'), fontSize: 13, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ch.title}</span>
              </div>
            ))}
          </div>

          <div style={{ padding: 12, borderTop: '1px solid #1C1C1C' }}>
            <button style={{ width: '100%', padding: '10px', background: '#FFE500', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 13, color: '#000', cursor: 'pointer' }}>
              ⚡ 批量生成章节
            </button>
          </div>
        </aside>

        {/* Main content area */}
        <main style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
          {generating ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24, padding: 40 }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', border: '3px solid #2A2A2A', borderTopColor: '#FFE500', animation: 'spin 1s linear infinite' }}/>
              <div style={{ textAlign: 'center' }}>
                <p style={{ color: '#FFE500', fontWeight: 600, fontSize: 16, marginBottom: 8 }}>AI 正在创作第 {activeChapter} 章...</p>
                <p style={{ color: '#888', fontSize: 14 }}>正在分析上下文，保持风格一致性</p>
              </div>
              <div style={{ width: '100%', maxWidth: 480, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[100, 85, 70, 55].map((w, i) => (
                  <div key={i} style={{ height: 14, background: '#1C1C1C', borderRadius: 999, width: `${w}%`, opacity: 0.4 + i * 0.15 }}/>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ flex: 1, overflowY: 'auto', padding: '48px 64px' }}>
              <div style={{ maxWidth: 680, margin: '0 auto' }}>
                <h2 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 22, marginBottom: 8 }}>
                  第 {activeChapter} 章 · {CHAPTERS[activeChapter - 1]?.title}
                </h2>
                <p style={{ color: '#888', fontSize: 13, marginBottom: 40 }}>约 1,240 字 · 质量评分 88</p>
                <div style={{ color: '#ddd', fontSize: 16, lineHeight: 2.1, whiteSpace: 'pre-line' }}>{CHAPTER_CONTENT}</div>
              </div>
            </div>
          )}

          {/* Right AI action panel */}
          <div style={{ width: 64, background: '#0D0D0D', borderLeft: '1px solid #1C1C1C', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px 0', gap: 12, flexShrink: 0 }}>
            {[
              { icon: '⚡', label: '生成本章', yellow: true, onClick: handleGenerate },
              { icon: '⭐', label: '质量评估', yellow: false },
              { icon: '🕐', label: '版本历史', yellow: false },
              { icon: '✏️', label: '编辑模式', yellow: false },
            ].map((btn, i) => (
              <button key={i} onClick={btn.onClick} title={btn.label} style={{ width: 44, height: 44, borderRadius: 12, background: btn.yellow ? '#FFE500' : '#1C1C1C', border: btn.yellow ? 'none' : '1px solid #2A2A2A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, cursor: 'pointer' }}>
                {btn.icon}
              </button>
            ))}
          </div>
        </main>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
