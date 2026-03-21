import { useState } from 'react'

const NAV = ['灵感模式','我的小说','写作台','设置']
const FILTERS = ['全部','进行中','已完成','草稿']
const NOVELS = [
  { title:'剑与星河', genre:'仙侠', chapters:23, total:60, lastEdit:'2小时前', status:'active', progress:38, icon:'⚔️', color:'#A855F7' },
  { title:'都市仙途', genre:'都市', chapters:11, total:40, lastEdit:'昨天', status:'active', progress:27, icon:'🏙️', color:'#06B6D4' },
  { title:'赛博龙骑', genre:'科幻', chapters:5, total:50, lastEdit:'3天前', status:'draft', progress:10, icon:'🐉', color:'#FFE500' },
  { title:'星际旅者', genre:'星际', chapters:30, total:30, lastEdit:'上周', status:'done', progress:100, icon:'🚀', color:'#2ED573' },
  { title:'神魔戮天录', genre:'玄幻', chapters:0, total:80, lastEdit:'刚刚', status:'draft', progress:0, icon:'💀', color:'#FF4757' },
  { title:'花都少侠行', genre:'古风', chapters:18, total:45, lastEdit:'4天前', status:'active', progress:40, icon:'🌸', color:'#F97316' },
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
      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
        <div style={{ width:32, height:32, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FF9500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, fontWeight:700, color:'#000' }}>创</div>
      </div>
    </div>
  )
}

export default function NovelWorkspace() {
  const [filter, setFilter] = useState('全部')
  const filtered = filter==='全部' ? NOVELS
    : filter==='进行中' ? NOVELS.filter(n=>n.status==='active')
    : filter==='已完成' ? NOVELS.filter(n=>n.status==='done')
    : NOVELS.filter(n=>n.status==='draft')

  return (
    <div style={{ display:'flex', flexDirection:'column' as const, height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>
      <TopNav active="我的小说"/>
      <div style={{ flex:1, overflowY:'auto' as const, padding:'36px 48px' }}>
        {/* Page header */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:28 }}>
          <div>
            <h1 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:28, fontWeight:800, color:'#fff', margin:0, letterSpacing:'-0.8px' }}>我的小说库</h1>
            <p style={{ margin:'6px 0 0', fontSize:14, color:'#666' }}>共 {NOVELS.length} 部作品</p>
          </div>
          <button style={{ display:'flex', alignItems:'center', gap:8, padding:'11px 22px', background:'#FFE500', border:'none', borderRadius:12, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>
            <span style={{ fontSize:18 }}>＋</span> 新建小说
          </button>
        </div>

        {/* Search + filters */}
        <div style={{ display:'flex', gap:12, marginBottom:28, alignItems:'center' }}>
          <div style={{ position:'relative', flex:1, maxWidth:360 }}>
            <svg style={{ position:'absolute', left:14, top:'50%', transform:'translateY(-50%)', width:16, height:16, color:'#555' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            <input placeholder="搜索小说标题..." style={{ width:'100%', padding:'10px 16px 10px 42px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' as const, fontFamily:'inherit' }}/>
          </div>
          <div style={{ display:'flex', gap:6 }}>
            {FILTERS.map(f=>(
              <button key={f} onClick={()=>setFilter(f)} style={{ padding:'8px 16px', background:f===filter?'#FFE500':'#141414', border:`1px solid ${f===filter?'#FFE500':'#2A2A2A'}`, borderRadius:999, fontSize:13, fontWeight:f===filter?700:400, color:f===filter?'#000':'#888', cursor:'pointer' }}>{f}</button>
            ))}
          </div>
        </div>

        {/* Novel grid */}
        {filtered.length === 0 ? (
          <div style={{ display:'flex', flexDirection:'column' as const, alignItems:'center', justifyContent:'center', padding:'80px 20px', gap:16 }}>
            <div style={{ fontSize:64 }}>📝</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:700, color:'#fff' }}>还没有小说</div>
            <p style={{ fontSize:14, color:'#666', textAlign:'center' as const }}>去灵感模式开始你的第一个故事吧~</p>
            <button style={{ padding:'11px 22px', background:'#FFE500', border:'none', borderRadius:12, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer' }}>去灵感模式</button>
          </div>
        ) : (
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:18 }}>
            {filtered.map((n,i)=>(
              <div key={i} style={{ background:'#141414', border:'1px solid #2A2A2A', borderRadius:16, overflow:'hidden', cursor:'pointer', transition:'border-color 0.2s' }}>
                {/* Color bar */}
                <div style={{ height:4, background:`linear-gradient(90deg,${n.color},${n.color}44)` }}/>
                <div style={{ padding:'20px 22px' }}>
                  {/* Header */}
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:14 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:12 }}>
                      <div style={{ width:40, height:40, background:`${n.color}18`, border:`1px solid ${n.color}33`, borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', fontSize:20 }}>{n.icon}</div>
                      <div>
                        <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:16, fontWeight:700, color:'#fff', marginBottom:2 }}>{n.title}</div>
                        <div style={{ display:'inline-block', padding:'2px 10px', background:`${n.color}18`, border:`1px solid ${n.color}33`, borderRadius:999, fontSize:11, color:n.color, fontWeight:600 }}>{n.genre}</div>
                      </div>
                    </div>
                    <div style={{ fontSize:11, padding:'3px 9px', borderRadius:999, background:n.status==='done'?'rgba(46,213,115,0.12)':n.status==='active'?'rgba(255,229,0,0.1)':'rgba(136,136,136,0.1)', color:n.status==='done'?'#2ED573':n.status==='active'?'#FFE500':'#888' }}>
                      {n.status==='done'?'已完成':n.status==='active'?'进行中':'草稿'}
                    </div>
                  </div>

                  {/* Progress */}
                  <div style={{ marginBottom:16 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
                      <span style={{ fontSize:12, color:'#888' }}>{n.chapters}/{n.total} 章</span>
                      <span style={{ fontSize:12, color:n.color, fontWeight:600 }}>{n.progress}%</span>
                    </div>
                    <div style={{ height:4, background:'#2A2A2A', borderRadius:999 }}>
                      <div style={{ height:'100%', width:`${n.progress}%`, background:`linear-gradient(90deg,${n.color},${n.color}99)`, borderRadius:999 }}/>
                    </div>
                  </div>

                  <div style={{ fontSize:12, color:'#555', marginBottom:18 }}>上次编辑：{n.lastEdit}</div>

                  {/* Actions */}
                  <div style={{ display:'flex', gap:8 }}>
                    <button style={{ flex:1, padding:'9px', background:'#FFE500', border:'none', borderRadius:8, fontSize:12, fontWeight:700, color:'#000', cursor:'pointer' }}>进入写作台</button>
                    <button style={{ padding:'9px 14px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, fontSize:12, color:'#888', cursor:'pointer' }}>详情</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
