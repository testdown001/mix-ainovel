import { useState } from 'react'

const NAV = ['灵感模式','我的小说','写作台','设置']
const TABS = ['概览','章节列表','人物','世界观','大纲','伏笔','情感曲线','设定库']
const STATS = [
  { label:'总字数', value:'48,200', unit:'字', icon:'📝', color:'#FFE500', bg:'rgba(255,229,0,0.08)' },
  { label:'章节数', value:'12', unit:'/30章', icon:'📖', color:'#A855F7', bg:'rgba(168,85,247,0.08)' },
  { label:'AI生成率', value:'94', unit:'%', icon:'🤖', color:'#06B6D4', bg:'rgba(6,182,212,0.08)' },
  { label:'平均质量', value:'88', unit:'/100', icon:'⭐', color:'#2ED573', bg:'rgba(46,213,115,0.08)' },
]
const RECENT_CHAPTERS = [
  { num:12, title:'新的危机', words:2847, quality:91, date:'今天' },
  { num:11, title:'最后防线', words:3102, quality:88, date:'昨天' },
  { num:10, title:'深渊之上', words:2690, quality:95, date:'2天前' },
]
const CHARS = [
  { name:'萧尘', role:'主角', emoji:'⚔️', color:'#FFE500' },
  { name:'李清歌', role:'女主', emoji:'🌸', color:'#A855F7' },
  { name:'天魔宗主', role:'反派', emoji:'👹', color:'#FF4757' },
  { name:'老掌门', role:'引导者', emoji:'🧙', color:'#06B6D4' },
]

export default function NovelDetail() {
  const [activeNav, setActiveNav] = useState('我的小说')
  const [activeTab, setActiveTab] = useState('概览')

  return (
    <div style={{ minHeight:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", color:'#fff' }}>

      {/* ── NAV ── */}
      <nav style={{ height:60, borderBottom:'1px solid #1C1C1C', display:'flex', alignItems:'center', padding:'0 32px', background:'#0A0A0A', position:'sticky', top:0, zIndex:100 }}>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginRight:60 }}>
          <div style={{ width:32, height:32, background:'#FFE500', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', fontSize:16, fontWeight:900, color:'#000' }}>✦</div>
          <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:15, color:'#fff' }}>Arboris Novel</span>
        </div>
        <div style={{ display:'flex', gap:4, flex:1 }}>
          {NAV.map(n=>(
            <button key={n} onClick={()=>setActiveNav(n)} style={{ padding:'6px 16px', background:'none', border:'none', borderRadius:8, fontSize:14, color: activeNav===n ? '#FFE500' : '#666', fontWeight: activeNav===n ? 600 : 400, cursor:'pointer', fontFamily:"'Inter',sans-serif" }}>{n}</button>
          ))}
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ width:34, height:34, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FFA500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, fontWeight:700, color:'#000' }}>创</div>
          <span style={{ fontSize:14, color:'#888' }}>创作者_01</span>
        </div>
      </nav>

      {/* ── HERO ── */}
      <div style={{ padding:'40px 40px 0', borderBottom:'1px solid #1C1C1C', position:'relative', overflow:'hidden' }}>
        <div style={{ position:'absolute', inset:0, background:'radial-gradient(ellipse at 80% 50%, rgba(255,229,0,0.04) 0%, transparent 60%)', pointerEvents:'none' }}/>
        <div style={{ maxWidth:1200, margin:'0 auto', display:'flex', gap:40, alignItems:'flex-start', paddingBottom:32, position:'relative', zIndex:1 }}>
          <div style={{ flex:1 }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:16 }}>
              <a href="#" style={{ fontSize:13, color:'#555', textDecoration:'none' }}>我的小说</a>
              <span style={{ color:'#333', fontSize:13 }}>/</span>
              <span style={{ fontSize:13, color:'#888' }}>剑与星河</span>
            </div>
            <div style={{ display:'flex', alignItems:'center', gap:16, marginBottom:12 }}>
              <span style={{ width:56, height:56, background:'rgba(168,85,247,0.12)', border:'1px solid rgba(168,85,247,0.3)', borderRadius:14, display:'flex', alignItems:'center', justifyContent:'center', fontSize:28 }}>⚔️</span>
              <div>
                <h1 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:36, fontWeight:800, margin:'0 0 6px', letterSpacing:'-1px', color:'#fff' }}>剑与星河</h1>
                <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                  <span style={{ padding:'3px 12px', background:'rgba(168,85,247,0.1)', border:'1px solid rgba(168,85,247,0.25)', borderRadius:999, fontSize:12, fontWeight:600, color:'#A855F7' }}>仙侠</span>
                  <span style={{ fontSize:13, color:'#555' }}>by 创作者_01</span>
                  <span style={{ fontSize:13, color:'#444' }}>· 创建于 2026-01-10</span>
                </div>
              </div>
            </div>
            <p style={{ fontSize:14, color:'#555', lineHeight:1.7, maxWidth:600, margin:'0 0 24px' }}>
              少年萧尘机缘巧合，踏入修仙之路。在星河与剑意交织的世界里，他步步为营，直面命运的挑战，终走上传奇之路。
            </p>
          </div>
          {/* Progress ring */}
          <div style={{ textAlign:'center', flexShrink:0 }}>
            <div style={{ position:'relative', width:100, height:100, margin:'0 auto 8px' }}>
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="#1C1C1C" strokeWidth="8"/>
                <circle cx="50" cy="50" r="42" fill="none" stroke="#FFE500" strokeWidth="8" strokeLinecap="round" strokeDasharray={`${0.4*264} 264`} transform="rotate(-90 50 50)" opacity="0.9"/>
              </svg>
              <div style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center' }}>
                <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:22, fontWeight:800, color:'#FFE500' }}>40%</span>
              </div>
            </div>
            <div style={{ fontSize:12, color:'#555' }}>12 / 30章</div>
          </div>
        </div>

        {/* ── TABS ── */}
        <div style={{ maxWidth:1200, margin:'0 auto', display:'flex', gap:0, overflowX:'auto' }}>
          {TABS.map(t=>(
            <button key={t} onClick={()=>setActiveTab(t)} style={{ padding:'12px 20px', background:'none', border:'none', borderBottom: activeTab===t ? '2px solid #FFE500' : '2px solid transparent', fontSize:14, fontWeight: activeTab===t ? 600 : 400, color: activeTab===t ? '#FFE500' : '#555', cursor:'pointer', whiteSpace:'nowrap', fontFamily:"'Inter',sans-serif", transition:'color 0.15s' }}>{t}</button>
          ))}
        </div>
      </div>

      {/* ── CONTENT ── */}
      <div style={{ maxWidth:1200, margin:'0 auto', padding:'32px 40px', display:'grid', gridTemplateColumns:'1fr 280px', gap:32 }}>

        {/* LEFT */}
        <div>
          {/* Stats */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, marginBottom:32 }}>
            {STATS.map(s=>(
              <div key={s.label} style={{ padding:'20px', background:'#141414', border:'1px solid #1C1C1C', borderRadius:16 }}>
                <div style={{ width:36, height:36, background:s.bg, borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', fontSize:16, marginBottom:12 }}>{s.icon}</div>
                <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:24, fontWeight:800, color:s.color, marginBottom:2 }}>{s.value}<span style={{ fontSize:13, color:'#444', fontWeight:400, marginLeft:4 }}>{s.unit}</span></div>
                <div style={{ fontSize:12, color:'#555' }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Recent chapters */}
          <div style={{ marginBottom:32 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
              <h3 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:16, fontWeight:700, margin:0, color:'#fff' }}>最近章节</h3>
              <a href="#" style={{ fontSize:13, color:'#555', textDecoration:'none' }}>查看全部</a>
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
              {RECENT_CHAPTERS.map((c,i)=>(
                <div key={i} style={{ padding:'16px 20px', background:'#141414', border:'1px solid #1C1C1C', borderRadius:12, display:'flex', alignItems:'center', gap:16 }}>
                  <div style={{ width:36, height:36, background:'#1C1C1C', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, fontWeight:700, color:'#FFE500', fontFamily:"'Space Grotesk',sans-serif", flexShrink:0 }}>
                    {c.num}
                  </div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:14, fontWeight:600, color:'#fff', marginBottom:2 }}>{c.title}</div>
                    <div style={{ fontSize:12, color:'#555' }}>{c.words.toLocaleString()} 字 · {c.date}</div>
                  </div>
                  <div style={{ textAlign:'right', flexShrink:0 }}>
                    <div style={{ fontSize:18, fontWeight:800, fontFamily:"'Space Grotesk',sans-serif", color: c.quality>=90 ? '#2ED573' : '#FFE500' }}>{c.quality}</div>
                    <div style={{ fontSize:11, color:'#444' }}>质量分</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Characters */}
          <div>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
              <h3 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:16, fontWeight:700, margin:0, color:'#fff' }}>主要人物</h3>
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12 }}>
              {CHARS.map((c,i)=>(
                <div key={i} style={{ padding:'20px 16px', background:'#141414', border:'1px solid #1C1C1C', borderRadius:14, textAlign:'center', cursor:'pointer' }}>
                  <div style={{ width:52, height:52, background:`${c.color}15`, border:`1px solid ${c.color}30`, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, margin:'0 auto 12px' }}>{c.emoji}</div>
                  <div style={{ fontSize:14, fontWeight:600, color:'#fff', marginBottom:4 }}>{c.name}</div>
                  <span style={{ padding:'2px 10px', borderRadius:999, fontSize:11, background:`${c.color}15`, color:c.color, fontWeight:500 }}>{c.role}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT — AI Analysis */}
        <div>
          <div style={{ background:'#141414', border:'1px solid rgba(255,229,0,0.15)', borderRadius:18, padding:'24px', position:'sticky', top:80 }}>
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:20 }}>
              <div style={{ width:32, height:32, background:'rgba(255,229,0,0.1)', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', fontSize:16 }}>🤖</div>
              <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:14, fontWeight:700, color:'#fff' }}>AI分析摘要</span>
            </div>
            {[
              { label:'故事节奏', value:88, color:'#FFE500' },
              { label:'人物塑造', value:92, color:'#A855F7' },
              { label:'世界观构建', value:79, color:'#06B6D4' },
              { label:'情节张力', value:95, color:'#2ED573' },
            ].map((s,i)=>(
              <div key={i} style={{ marginBottom:14 }}>
                <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
                  <span style={{ fontSize:13, color:'#888' }}>{s.label}</span>
                  <span style={{ fontSize:13, fontWeight:600, color:s.color }}>{s.value}</span>
                </div>
                <div style={{ height:4, background:'#1C1C1C', borderRadius:999 }}>
                  <div style={{ height:'100%', background:s.color, borderRadius:999, width:`${s.value}%`, opacity:0.8 }}/>
                </div>
              </div>
            ))}
            <div style={{ marginTop:20, padding:'12px 16px', background:'rgba(255,229,0,0.05)', borderRadius:10, border:'1px solid rgba(255,229,0,0.1)' }}>
              <p style={{ fontSize:12, color:'#888', lineHeight:1.7, margin:0 }}>
                整体质量优秀。第9-12章情节张力突出，建议在第13章引入新的冲突支线以维持读者热情。
              </p>
            </div>
            <button style={{ width:'100%', marginTop:16, padding:'10px', background:'#FFE500', border:'none', borderRadius:8, fontSize:13, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>生成深度分析报告</button>
          </div>
        </div>
      </div>
    </div>
  )
}
