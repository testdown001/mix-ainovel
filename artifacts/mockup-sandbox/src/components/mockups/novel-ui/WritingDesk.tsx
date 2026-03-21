import { useState } from 'react'

type ChapterStatus = 'done' | 'pending' | 'empty'

const CHAPTERS: { num: number; title: string; status: ChapterStatus }[] = [
  { num: 1, title: '序章：启程', status: 'done' },
  { num: 2, title: '异星信号', status: 'done' },
  { num: 3, title: '星舰"曙光"号', status: 'done' },
  { num: 4, title: '未知坐标', status: 'done' },
  { num: 5, title: '接触', status: 'done' },
  { num: 6, title: '第一次接触', status: 'done' },
  { num: 7, title: '深渊之眼', status: 'done' },
  { num: 8, title: '同行者', status: 'done' },
  { num: 9, title: '裂缝', status: 'done' },
  { num: 10, title: '边界线', status: 'done' },
  { num: 11, title: '沉默的星系', status: 'done' },
  { num: 12, title: '未知信号', status: 'pending' },
  { num: 13, title: '第十三章', status: 'empty' },
  { num: 14, title: '第十四章', status: 'empty' },
  { num: 15, title: '第十五章', status: 'empty' },
]

const STATUS_DOT = { done: '#2ED573', pending: '#FFE500', empty: '#333' }
const STATUS_LABEL = { done: '已生成', pending: '生成中', empty: '待生成' }

const CHAPTER_12_CONTENT = `夜幕低垂，星舰"曙光"号在虚空中缓缓漂移。导航屏上，一连串密集的数据流如同电流涌动，让值班的通讯官陈曦不得不揉了揉眼睛，再次确认自己没有眼花。

**信号强度：9.7/10**
**来源坐标：Sector 7-G，距离当前位置约 0.3 光年**
**信号类型：未知——既不属于已知文明，亦不在数据库范围内**

"舰长。"陈曦的声音透过舰内通讯系统穿向指挥舱，带着一丝压抑不住的颤意，"我们收到了一段……很奇怪的信号。"

片刻之后，舰长林晓东踱步走来，面容沉静如旧，但眉心的那道浅皱已经出卖了他。他俯身看向屏幕，沉默良久。

"解析出来了吗？"

"只解析了前半段。"陈曦摇摇头，"这不像是普通的机械噪声，也不像是某种自然天体的辐射模式——它……有某种结构性的重复。像是在说话。"

**像是在说话。**

那四个字落在指挥舱里，像一颗石子投入深潭，荡起层层涟漪。所有人都屏住了呼吸。`

export default function WritingDesk() {
  const [selectedChapter, setSelectedChapter] = useState(12)
  const [generating, setGenerating] = useState(false)

  const chapter = CHAPTERS.find(c => c.num === selectedChapter)

  return (
    <div style={{ height: '100vh', background: '#0A0A0A', fontFamily: "'Inter', sans-serif", display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', height: 56, padding: '0 20px', borderBottom: '1px solid #141414', background: '#0A0A0A', flexShrink: 0, gap: 16 }}>
        <button style={{ color: '#888', background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, padding: '4px 8px', display: 'flex', alignItems: 'center' }}>←</button>
        <div style={{ width: 1, height: 24, background: '#1C1C1C' }}/>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, color: '#fff', fontSize: 15 }}>星际边疆</div>
        </div>
        {/* Progress */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#888', fontSize: 13 }}>12/30 章</span>
          <div style={{ width: 120, height: 5, background: '#1C1C1C', borderRadius: 999, overflow: 'hidden' }}>
            <div style={{ width: '40%', height: '100%', background: '#FFE500', borderRadius: 999 }}/>
          </div>
          <span style={{ color: '#FFE500', fontSize: 13, fontWeight: 700 }}>40%</span>
        </div>
        <div style={{ width: 1, height: 24, background: '#1C1C1C' }}/>
        <button style={{ padding: '7px 14px', border: '1px solid #2A2A2A', borderRadius: 8, background: 'transparent', color: '#aaa', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>查看详情</button>
        <button style={{ padding: '7px 14px', border: 'none', borderRadius: 8, background: '#FFE500', color: '#000', fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif" }}>生成大纲</button>
      </div>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left Sidebar */}
        <div style={{ width: 264, background: '#0D0D0D', borderRight: '1px solid #141414', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>
          {/* Novel info */}
          <div style={{ padding: '20px 18px 14px', borderBottom: '1px solid #141414' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: '#0A1A2A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>🚀</div>
              <div>
                <div style={{ fontWeight: 700, color: '#fff', fontSize: 14 }}>星际边疆</div>
                <div style={{ color: '#555', fontSize: 12 }}>科幻 · 30章</div>
              </div>
            </div>
          </div>

          {/* Chapter list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
            {CHAPTERS.map(ch => (
              <div key={ch.num} onClick={() => setSelectedChapter(ch.num)}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 16px', cursor: 'pointer', background: selectedChapter === ch.num ? '#141414' : 'transparent', borderLeft: selectedChapter === ch.num ? '2px solid #FFE500' : '2px solid transparent' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_DOT[ch.status], flexShrink: 0 }}/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: selectedChapter === ch.num ? '#fff' : '#777', fontSize: 13, fontWeight: selectedChapter === ch.num ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {`第${ch.num}章 · ${ch.title}`}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Batch generate button */}
          <div style={{ padding: '14px 16px', borderTop: '1px solid #141414' }}>
            <button style={{ width: '100%', padding: '11px', background: '#FFE500', color: '#000', border: 'none', borderRadius: 10, fontWeight: 800, fontSize: 13, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif" }}>
              ⚡ 批量生成剩余章节
            </button>
          </div>
        </div>

        {/* Main content area */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {generating ? (
            /* Generating state */
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24, padding: 40 }}>
              <div style={{ position: 'relative', width: 72, height: 72 }}>
                <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '3px solid #1C1C1C' }}/>
                <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '3px solid transparent', borderTopColor: '#FFE500', animation: 'spin 1s linear infinite' }}/>
                <div style={{ position: 'absolute', inset: '18px', borderRadius: '50%', background: '#FFE50020', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>✦</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, color: '#fff', fontSize: 18, marginBottom: 8 }}>AI 正在创作第12章…</div>
                <div style={{ color: '#666', fontSize: 14 }}>正在生成章节内容，请稍候</div>
              </div>
              {/* Skeleton lines */}
              <div style={{ width: '100%', maxWidth: 600, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[100, 90, 100, 75, 100, 85].map((w, i) => (
                  <div key={i} style={{ height: 14, background: 'linear-gradient(90deg, #1C1C1C 25%, #242424 50%, #1C1C1C 75%)', backgroundSize: '200% 100%', borderRadius: 7, width: `${w}%` }}/>
                ))}
              </div>
            </div>
          ) : chapter?.status === 'empty' ? (
            /* Empty chapter */
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
              <div style={{ fontSize: 48 }}>📄</div>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, color: '#fff', fontSize: 20 }}>第{selectedChapter}章尚未生成</div>
              <p style={{ color: '#666', fontSize: 14, textAlign: 'center', maxWidth: 340, lineHeight: 1.7 }}>让AI根据大纲自动生成本章内容，保持与前文风格一致。</p>
              <button onClick={() => setGenerating(true)} style={{ padding: '12px 32px', background: '#FFE500', color: '#000', border: 'none', borderRadius: 12, fontWeight: 800, fontSize: 15, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif" }}>
                ⚡ 生成本章
              </button>
            </div>
          ) : (
            /* Chapter content */
            <div style={{ flex: 1, overflowY: 'auto', padding: '48px 64px' }}>
              <div style={{ maxWidth: 720, margin: '0 auto' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{ color: '#555', fontSize: 14 }}>第12章</span>
                  {chapter?.status === 'pending' && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 10px', background: '#2A2600', color: '#FFE500', borderRadius: 999, fontSize: 12, fontWeight: 600 }}>
                      <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#FFE500', display: 'inline-block' }}/>
                      生成中
                    </span>
                  )}
                  {chapter?.status === 'done' && (
                    <span style={{ padding: '3px 10px', background: '#0A2A1A', color: '#2ED573', borderRadius: 999, fontSize: 12, fontWeight: 600 }}>已生成</span>
                  )}
                </div>
                <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 900, fontSize: 28, color: '#fff', margin: '0 0 36px', letterSpacing: -0.5 }}>未知信号</h2>
                <div style={{ fontSize: 16, lineHeight: 1.95, color: '#bbb', whiteSpace: 'pre-line' }}>
                  {CHAPTER_12_CONTENT.split('\n').map((line, i) => {
                    if (line.startsWith('**') && line.endsWith('**')) {
                      return <p key={i} style={{ fontWeight: 700, color: '#fff', fontFamily: "'Space Grotesk', sans-serif", padding: '8px 16px', background: '#141414', borderLeft: '3px solid #FFE500', borderRadius: '0 8px 8px 0', margin: '16px 0' }}>{line.replace(/\*\*/g, '')}</p>
                    }
                    return line ? <p key={i} style={{ margin: '0 0 16px' }}>{line}</p> : <br key={i}/>
                  })}
                </div>

                {/* Word count */}
                <div style={{ marginTop: 40, paddingTop: 20, borderTop: '1px solid #141414', display: 'flex', alignItems: 'center', gap: 20 }}>
                  <span style={{ color: '#444', fontSize: 13 }}>本章字数：3,240字</span>
                  <span style={{ color: '#444', fontSize: 13 }}>AI生成</span>
                </div>
              </div>
            </div>
          )}

          {/* Right AI toolbar */}
          <div style={{ width: 56, background: '#0D0D0D', borderLeft: '1px solid #141414', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px 0', gap: 8, flexShrink: 0 }}>
            {[
              { icon: '⚡', label: '生成本章', active: true },
              { icon: '★', label: '评估质量', active: false },
              { icon: '🕐', label: '版本历史', active: false },
              { icon: '✏️', label: '编辑模式', active: false },
              { icon: '📋', label: '章节大纲', active: false },
            ].map((tool, i) => (
              <button key={i} title={tool.label}
                style={{ width: 40, height: 40, borderRadius: 10, border: tool.active ? '1px solid #FFE500' : '1px solid transparent', background: tool.active ? '#FFE50015' : 'transparent', color: tool.active ? '#FFE500' : '#555', fontSize: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {tool.icon}
              </button>
            ))}
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
