import { useState } from 'react'

const NAV = ['灵感模式','我的小说','写作台','设置']
const TABS = ['概览','章节列表','人物','世界观','大纲','伏笔','情感曲线','设定库']
const STATS = [
  { label:'总字数', value:'48,200', unit:'字', icon:'📝', color:'#FFE500' },
  { label:'章节数', value:'12', unit:'/30章', icon:'📖', color:'#A855F7' },
  { label:'AI生成率', value:'94', unit:'%', icon:'🤖', color:'#06B6D4' },
  { label:'平均质量', value:'88', unit:'/100', icon:'⭐', color:'#2ED573' },
]
const RECENT_CHAPTERS = [
  { num:12, title:'新的危机', words:'2,847', date:'2小时前', score:88 },
  { num:11, title:'最后防线', words:'3,102', date:'昨天', score:91 },
  { num:10, title:'深渊之上', words:'2,619', date:'2天前', score:85 },
  { num:9, title:'真相一角', words:'2,988', date:'3天前', score:87 },
]
const CHARACTERS = [
  { name:'林远', role:'主角', icon:'⚔️', color:'#FFE500', trait:'孤傲·坚韧' },
  { name:'凌霄', role:'师兄', icon:'🌊', color:'#06B6D4', trait:'沉稳·隐忍' },
  { name:'夜澜', role:'反派', icon:'🌑', color:'#FF4757', trait:'神秘·危险' },
  { name:'云笙', role:'导师', icon:'☁️', color:'#A855F7', trait:'睿智·慈悲' },
]

function TopNav({ active }:{ active:string }) {
  return (
    <div style={{ height:60, background:'#0A0A0A', borderBottom:'1px solid #1E1E1E', display:'flex', alignItems:'center', padding:'0 32px', gap:40, flexShrink:0 }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginRight:16 }}>
        <div style={{ width:34, height:34, background:'#FFE500', borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', fontSize:17, fontWeight:900, color:'#000' }}>✦</div>
        <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:15, color:'#fff' }}>Arboris Novel</span>
      </div>
      <div style={{ display:'flex', gap:4, flex:1 }}>
        {NAV.map(n=>(
          <div key={n} style={{ padding:'6px 16px', borderRadius:8, fontSize:14, fontWeight:n===active?600:400, color:n===active?'#FFE500':'#888', background:n===active?'rgba(255,229,0,0.08)':'transparent', cursor:'pointer' }}>{n}</div>
        ))}
      </div>
      <div style={{ width:32, height:32, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FF9500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, fontWeight:700, color:'#000' }}>创</div>
    </div>
  )
}

export default function NovelDetail() {
  const [tab, setTab] = useState('概览')

  return (
    <div style={{ display:'flex', flexDirection:'column' as const, height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>
      <TopNav active="我的小说"/>

      {/* Hero header */}
      <div style={{ padding:'28px 48px 0', background:'#0A0A0A', borderBottom:'1px solid #1E1E1E', flexShrink:0 }}>
        <div style={{ display:'flex', alignItems:'flex-start', gap:28, marginBottom:24 }}>
          {/* Cover placeholder */}
          <div style={{ width:80, height:80, background:'linear-gradient(135deg,#A855F722,#FFE50022)', border:'1px solid #A855F733', borderRadius:16, display:'flex', alignItems:'center', justifyContent:'center', fontSize:36, flexShrink:0 }}>⚔️</div>
          <div style={{ flex:1 }}>
            <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:6 }}>
              <h1 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:30, fontWeight:800, color:'#fff', margin:0, letterSpacing:'-1px' }}>剑与星河</h1>
              <div style={{ padding:'3px 12px', background:'rgba(168,85,247,0.15)', border:'1px solid rgba(168,85,247,0.3)', borderRadius:999, fontSize:12, color:'#A855F7', fontWeight:600 }}>仙侠</div>
              <div style={{ padding:'3px 12px', background:'rgba(46,213,115,0.12)', border:'1px solid rgba(46,213,115,0.25)', borderRadius:999, fontSize:12, color:'#2ED573', fontWeight:600 }}>进行中</div>
            </div>
            <div style={{ display:'flex', gap:20, fontSize:13, color:'#666' }}>
              <span>作者：创作者</span>
              <span>创建于 2024-01-01</span>
              <span>最近更新：2小时前</span>
            </div>
          </div>
          {/* Progress ring */}
          <div style={{ textAlign:'center' as const, flexShrink:0 }}>
            <svg width="80" height="80" viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="32" fill="none" stroke="#1E1E1E" strokeWidth="6"/>
              <circle cx="40" cy="40" r="32" fill="none" stroke="#FFE500" strokeWidth="6" strokeDasharray={`${0.4*2*Math.PI*32} ${2*Math.PI*32}`} strokeLinecap="round" transform="rotate(-90 40 40)"/>
              <text x="40" y="45" textAnchor="middle" fontSize="16" fontWeight="800" fill="#FFE500" fontFamily="Space Grotesk">40%</text>
            </svg>
            <div style={{ fontSize:11, color:'#666', marginTop:2 }}>12/30 章</div>
          </div>
        </div>

        {/* Tab bar */}
        <div style={{ display:'flex', gap:0, overflowX:'auto' as const }}>
          {TABS.map(t=>(
            <button key={t} onClick={()=>setTab(t)} style={{ padding:'10px 20px', background:'transparent', border:'none', borderBottom:t===tab?'2px solid #FFE500':'2px solid transparent', fontSize:14, fontWeight:t===tab?600:400, color:t===tab?'#FFE500':'#666', cursor:'pointer', whiteSpace:'nowrap' as const, transition:'color 0.15s' }}>{t}</button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div style={{ flex:1, overflowY:'auto' as const, padding:'28px 48px' }}>
        {tab==='概览' && (
          <div style={{ display:'grid', gridTemplateColumns:'1fr 320px', gap:24 }}>
            <div>
              {/* Stats */}
              <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:14, marginBottom:28 }}>
                {STATS.map(s=>(
                  <div key={s.label} style={{ background:'#141414', border:'1px solid #2A2A2A', borderRadius:14, padding:'18px 20px' }}>
                    <div style={{ fontSize:24, marginBottom:10 }}>{s.icon}</div>
                    <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:26, fontWeight:800, color:s.color, letterSpacing:'-1px' }}>
                      {s.value}<span style={{ fontSize:14, color:'#666', fontWeight:500 }}>{s.unit}</span>
                    </div>
                    <div style={{ fontSize:12, color:'#666', marginTop:4 }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {/* Recent chapters */}
              <div style={{ background:'#141414', border:'1px solid #2A2A2A', borderRadius:16, overflow:'hidden', marginBottom:24 }}>
                <div style={{ padding:'18px 22px', borderBottom:'1px solid #1E1E1E', display:'flex', justifyContent:'space-between' }}>
                  <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:14, fontWeight:700, color:'#fff' }}>最近章节</span>
                  <span style={{ fontSize:12, color:'#FFE500', cursor:'pointer' }}>查看全部 →</span>
                </div>
                {RECENT_CHAPTERS.map((c,i)=>(
                  <div key={i} style={{ display:'flex', alignItems:'center', gap:16, padding:'14px 22px', borderBottom:i<RECENT_CHAPTERS.length-1?'1px solid #1A1A1A':'none' }}>
                    <div style={{ width:36, height:36, background:'rgba(255,229,0,0.08)', border:'1px solid rgba(255,229,0,0.15)', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, fontWeight:700, color:'#FFE500', fontFamily:"'Space Grotesk',sans-serif", flexShrink:0 }}>
                      {c.num}
                    </div>
                    <div style={{ flex:1 }}>
                      <div style={{ fontSize:14, fontWeight:600, color:'#fff', marginBottom:2 }}>第{c.num}章 · {c.title}</div>
                      <div style={{ fontSize:12, color:'#555' }}>{c.words} 字 · {c.date}</div>
                    </div>
                    <div style={{ textAlign:'right' as const }}>
                      <div style={{ fontSize:13, fontWeight:700, color:c.score>=90?'#2ED573':c.score>=80?'#FFE500':'#FF4757' }}>{c.score}分</div>
                      <div style={{ fontSize:11, color:'#555' }}>质量评分</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Characters */}
              <div style={{ background:'#141414', border:'1px solid #2A2A2A', borderRadius:16, overflow:'hidden' }}>
                <div style={{ padding:'18px 22px', borderBottom:'1px solid #1E1E1E' }}>
                  <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:14, fontWeight:700, color:'#fff' }}>核心人物</span>
                </div>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, padding:'20px 22px' }}>
                  {CHARACTERS.map((c,i)=>(
                    <div key={i} style={{ textAlign:'center' as const, cursor:'pointer' }}>
                      <div style={{ width:56, height:56, borderRadius:'50%', background:`${c.color}18`, border:`2px solid ${c.color}44`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:26, margin:'0 auto 10px' }}>{c.icon}</div>
                      <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:2 }}>{c.name}</div>
                      <div style={{ fontSize:11, color:c.color, marginBottom:4 }}>{c.role}</div>
                      <div style={{ fontSize:11, color:'#555' }}>{c.trait}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right: AI analysis card */}
            <div style={{ display:'flex', flexDirection:'column' as const, gap:16 }}>
              <div style={{ background:'#141414', border:'1px solid rgba(255,229,0,0.2)', borderRadius:16, padding:'20px 22px' }}>
                <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:16 }}>
                  <span style={{ fontSize:18 }}>🤖</span>
                  <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:14, fontWeight:700, color:'#FFE500' }}>AI 综合分析</span>
                </div>
                {[
                  { label:'人物塑造', score:89, color:'#A855F7' },
                  { label:'情节节奏', score:82, color:'#06B6D4' },
                  { label:'世界观深度', score:91, color:'#2ED573' },
                  { label:'对话自然度', score:85, color:'#FF9500' },
                ].map(m=>(
                  <div key={m.label} style={{ marginBottom:14 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:5 }}>
                      <span style={{ fontSize:12, color:'#888' }}>{m.label}</span>
                      <span style={{ fontSize:12, fontWeight:700, color:m.color }}>{m.score}</span>
                    </div>
                    <div style={{ height:4, background:'#2A2A2A', borderRadius:999 }}>
                      <div style={{ height:'100%', width:`${m.score}%`, background:m.color, borderRadius:999 }}/>
                    </div>
                  </div>
                ))}
                <div style={{ marginTop:16, padding:'12px 14px', background:'rgba(255,229,0,0.05)', borderRadius:10, fontSize:12, color:'#999', lineHeight:1.6 }}>
                  💡 建议在第13章增加林远与凌霄的内心冲突描写，情感层次将更加丰富。
                </div>
              </div>

              <div style={{ background:'#141414', border:'1px solid #2A2A2A', borderRadius:16, padding:'20px 22px' }}>
                <div style={{ fontSize:13, fontWeight:700, color:'#fff', marginBottom:14 }}>快速操作</div>
                {['⚡ 生成下一章','📊 生成质量报告','🌍 更新世界观设定','📋 导出全文'].map(a=>(
                  <button key={a} style={{ width:'100%', padding:'10px 14px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, color:'#888', fontSize:13, cursor:'pointer', textAlign:'left' as const, marginBottom:8 }}>{a}</button>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab!=='概览' && (
          <div style={{ display:'flex', flexDirection:'column' as const, alignItems:'center', justifyContent:'center', padding:'80px 20px', gap:12 }}>
            <div style={{ fontSize:48 }}>🚧</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:18, fontWeight:700, color:'#fff' }}>{tab}</div>
            <p style={{ fontSize:14, color:'#666' }}>此标签页内容建设中</p>
          </div>
        )}
      </div>
    </div>
  )
}
