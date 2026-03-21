import { useState } from 'react'

const NAV = ['灵感模式','我的小说','写作台','设置']
const FILTERS = ['全部','进行中','已完成','草稿']
const NOVELS = [
  { title:'剑与星河', genre:'仙侠', chapters:23, total:60, lastEdit:'2小时前', status:'active', progress:38, icon:'⚔️', accentColor:'#A855F7' },
  { title:'都市仙途', genre:'都市', chapters:11, total:40, lastEdit:'昨天', status:'active', progress:27, icon:'🏙️', accentColor:'#06B6D4' },
  { title:'赛博龙骑', genre:'科幻', chapters:5, total:50, lastEdit:'3天前', status:'draft', progress:10, icon:'🐉', accentColor:'#FFE500' },
  { title:'星际旅者', genre:'星际', chapters:30, total:30, lastEdit:'上周', status:'done', progress:100, icon:'🚀', accentColor:'#2ED573' },
  { title:'神魔戮天录', genre:'玄幻', chapters:8, total:80, lastEdit:'昨天', status:'active', progress:10, icon:'⚡', accentColor:'#FF4757' },
  { title:'末日余辉', genre:'末日', chapters:0, total:30, lastEdit:'刚刚', status:'draft', progress:0, icon:'☢️', accentColor:'#FF8C00' },
]

const statusLabel = (s:string) => s==='done' ? '已完成' : s==='draft' ? '草稿' : '进行中'
const statusColor = (s:string) => s==='done' ? '#2ED573' : s==='draft' ? '#FFE500' : '#06B6D4'
const statusBg = (s:string) => s==='done' ? 'rgba(46,213,115,0.1)' : s==='draft' ? 'rgba(255,229,0,0.1)' : 'rgba(6,182,212,0.1)'

export default function NovelWorkspace() {
  const [active, setActive] = useState('我的小说')
  const [filter, setFilter] = useState('全部')
  const [query, setQuery] = useState('')

  const filtered = NOVELS.filter(n=>{
    const matchFilter = filter==='全部' || (filter==='进行中'&&n.status==='active') || (filter==='已完成'&&n.status==='done') || (filter==='草稿'&&n.status==='draft')
    const matchQuery = !query || n.title.includes(query) || n.genre.includes(query)
    return matchFilter && matchQuery
  })

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
            <button key={n} onClick={()=>setActive(n)} style={{ padding:'6px 16px', background:'none', border:'none', borderRadius:8, fontSize:14, color: active===n ? '#FFE500' : '#666', fontWeight: active===n ? 600 : 400, cursor:'pointer', fontFamily:"'Inter',sans-serif" }}>{n}</button>
          ))}
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ width:34, height:34, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FFA500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, fontWeight:700, color:'#000' }}>创</div>
          <span style={{ fontSize:14, color:'#888' }}>创作者_01</span>
        </div>
      </nav>

      <div style={{ maxWidth:1200, margin:'0 auto', padding:'40px 32px' }}>

        {/* ── HEADER ── */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:32 }}>
          <div>
            <h1 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:32, fontWeight:800, margin:'0 0 4px', letterSpacing:'-1px', color:'#fff' }}>我的小说库</h1>
            <p style={{ fontSize:14, color:'#555', margin:0 }}>{NOVELS.length} 部作品</p>
          </div>
          <button style={{ padding:'11px 24px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif", display:'flex', alignItems:'center', gap:8 }}>
            <span style={{ fontSize:18, lineHeight:1 }}>+</span> 新建小说
          </button>
        </div>

        {/* ── SEARCH + FILTERS ── */}
        <div style={{ display:'flex', gap:12, marginBottom:32, alignItems:'center' }}>
          <div style={{ position:'relative', flex:1, maxWidth:360 }}>
            <svg style={{ position:'absolute', left:14, top:'50%', transform:'translateY(-50%)', opacity:0.4 }} width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="#fff" strokeWidth="2"/><path d="M20 20l-3-3" stroke="#fff" strokeWidth="2" strokeLinecap="round"/></svg>
            <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索小说标题、类型..." style={{ width:'100%', padding:'10px 16px 10px 42px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' }}/>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            {FILTERS.map(f=>(
              <button key={f} onClick={()=>setFilter(f)} style={{ padding:'8px 18px', borderRadius:999, fontSize:13, border: filter===f ? 'none' : '1px solid #2A2A2A', background: filter===f ? '#FFE500' : 'transparent', color: filter===f ? '#000' : '#666', cursor:'pointer', fontFamily:"'Inter',sans-serif", fontWeight: filter===f ? 700 : 400 }}>{f}</button>
            ))}
          </div>
        </div>

        {/* ── NOVEL GRID ── */}
        {filtered.length > 0 ? (
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:20 }}>
            {filtered.map((n,i)=>(
              <div key={i} style={{ background:'#141414', border:'1px solid #1C1C1C', borderRadius:18, padding:'24px', cursor:'pointer', position:'relative', overflow:'hidden', transition:'border-color 0.2s' }}>
                {/* Accent line */}
                <div style={{ position:'absolute', top:0, left:0, right:0, height:3, background:n.accentColor, borderRadius:'18px 18px 0 0', opacity:0.8 }}/>

                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:16 }}>
                  <div style={{ display:'flex', alignItems:'center', gap:12 }}>
                    <div style={{ width:44, height:44, background:'#1C1C1C', borderRadius:12, display:'flex', alignItems:'center', justifyContent:'center', fontSize:22 }}>{n.icon}</div>
                    <div>
                      <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:16, fontWeight:700, color:'#fff', marginBottom:4 }}>{n.title}</div>
                      <span style={{ padding:'2px 10px', borderRadius:999, fontSize:11, fontWeight:600, background:`${n.accentColor}18`, color:n.accentColor, border:`1px solid ${n.accentColor}30` }}>{n.genre}</span>
                    </div>
                  </div>
                  <span style={{ padding:'4px 10px', borderRadius:999, fontSize:11, fontWeight:600, background:statusBg(n.status), color:statusColor(n.status) }}>{statusLabel(n.status)}</span>
                </div>

                {/* Progress */}
                <div style={{ marginBottom:16 }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
                    <span style={{ fontSize:12, color:'#555' }}>章节进度</span>
                    <span style={{ fontSize:12, color:'#888', fontWeight:600 }}>{n.chapters}/{n.total}章</span>
                  </div>
                  <div style={{ height:4, background:'#1C1C1C', borderRadius:999 }}>
                    <div style={{ height:'100%', background:n.accentColor, borderRadius:999, width:`${n.progress}%`, opacity:0.8 }}/>
                  </div>
                </div>

                <div style={{ fontSize:12, color:'#444', marginBottom:20 }}>上次编辑：{n.lastEdit}</div>

                {/* Actions */}
                <div style={{ display:'flex', gap:8 }}>
                  <button style={{ flex:1, padding:'9px', background:'#FFE500', border:'none', borderRadius:8, fontSize:12, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>进入写作台</button>
                  <button style={{ padding:'9px 14px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, fontSize:12, color:'#666', cursor:'pointer' }}>详情</button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign:'center', padding:'100px 0' }}>
            <div style={{ fontSize:64, marginBottom:20 }}>📭</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:700, color:'#333', marginBottom:8 }}>还没有小说</div>
            <p style={{ fontSize:14, color:'#444', marginBottom:28 }}>去灵感模式开始你的第一个故事吧~</p>
            <button style={{ padding:'12px 28px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>⚡ 开启灵感模式</button>
          </div>
        )}
      </div>
    </div>
  )
}
