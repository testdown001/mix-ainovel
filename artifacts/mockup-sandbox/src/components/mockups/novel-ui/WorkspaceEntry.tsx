import { useState } from 'react'

const NAV = ['灵感模式','我的小说','写作台','设置']
const RECENT = [
  { title:'剑与星河', chapter:'第23章 · 繁星之下', time:'2小时前', status:'done', icon:'⚔️' },
  { title:'都市仙途', chapter:'第11章 · 修仙觉醒', time:'昨天', status:'done', icon:'🏙️' },
  { title:'赛博龙骑', chapter:'第5章（草稿）', time:'3天前', status:'draft', icon:'🐉' },
]

export default function WorkspaceEntry() {
  const [active, setActive] = useState('我的小说')
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

      <div style={{ maxWidth:1200, margin:'0 auto', padding:'48px 32px' }}>

        {/* ── HERO ── */}
        <div style={{ marginBottom:48 }}>
          <div style={{ position:'relative', display:'inline-block' }}>
            <h1 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:40, fontWeight:800, margin:'0 0 12px', letterSpacing:'-1.5px', background:'linear-gradient(90deg,#fff 0%,#FFE500 60%)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', backgroundClip:'text' }}>
              下午好，创作者 👋
            </h1>
          </div>
          <p style={{ fontSize:15, color:'#555', margin:'0 0 28px' }}>今天想继续哪部作品的旅程？</p>

          {/* Stats row */}
          <div style={{ display:'flex', gap:20 }}>
            {[
              { label:'创作小说', value:'5', unit:'部', icon:'📚', color:'#FFE500' },
              { label:'累计章节', value:'82', unit:'章', icon:'📖', color:'#A855F7' },
              { label:'生成字数', value:'12.4万', unit:'字', icon:'⚡', color:'#2ED573' },
            ].map(s=>(
              <div key={s.label} style={{ padding:'16px 24px', background:'#141414', border:'1px solid #1C1C1C', borderRadius:14, display:'flex', alignItems:'center', gap:14 }}>
                <div style={{ width:40, height:40, background:`rgba(255,255,255,0.04)`, borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', fontSize:18 }}>{s.icon}</div>
                <div>
                  <div style={{ fontSize:22, fontWeight:700, fontFamily:"'Space Grotesk',sans-serif", color:s.color }}>{s.value}<span style={{ fontSize:13, color:'#555', fontWeight:400, marginLeft:4 }}>{s.unit}</span></div>
                  <div style={{ fontSize:12, color:'#555', marginTop:1 }}>{s.label}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── ACTION CARDS ── */}
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:52 }}>
          {/* 灵感模式 */}
          <div style={{ padding:'32px', background:'linear-gradient(135deg,rgba(255,229,0,0.1) 0%,rgba(255,229,0,0.04) 100%)', border:'1px solid rgba(255,229,0,0.25)', borderRadius:20, cursor:'pointer', position:'relative', overflow:'hidden' }}>
            <div style={{ position:'absolute', top:-20, right:-20, fontSize:80, opacity:0.06 }}>💡</div>
            <div style={{ width:52, height:52, background:'#FFE500', borderRadius:14, display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, marginBottom:20 }}>💡</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:22, fontWeight:700, color:'#fff', marginBottom:8 }}>灵感模式</div>
            <p style={{ fontSize:14, color:'#888', lineHeight:1.6, margin:'0 0 24px', maxWidth:320 }}>还没有故事？让AI引导你从零开始，一步步构建独一无二的故事世界。</p>
            <button style={{ padding:'10px 22px', background:'#FFE500', border:'none', borderRadius:8, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>⚡ 开启灵感模式</button>
          </div>

          {/* 我的小说库 */}
          <div style={{ padding:'32px', background:'#141414', border:'1px solid #1C1C1C', borderRadius:20, cursor:'pointer', position:'relative', overflow:'hidden' }}>
            <div style={{ position:'absolute', top:-20, right:-20, fontSize:80, opacity:0.04 }}>📚</div>
            <div style={{ width:52, height:52, background:'#1C1C1C', border:'1px solid #2A2A2A', borderRadius:14, display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, marginBottom:20 }}>📚</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:22, fontWeight:700, color:'#fff', marginBottom:8 }}>我的小说库</div>
            <p style={{ fontSize:14, color:'#555', lineHeight:1.6, margin:'0 0 24px', maxWidth:320 }}>查看并管理你所有的小说项目，进入写作台继续创作或查看详细分析。</p>
            <button style={{ padding:'10px 22px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, fontSize:14, fontWeight:600, color:'#ccc', cursor:'pointer' }}>查看全部小说 →</button>
          </div>
        </div>

        {/* ── RECENT ACTIVITY ── */}
        <div style={{ display:'grid', gridTemplateColumns:'1fr auto', gap:40, alignItems:'start' }}>
          <div>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
              <h3 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:18, fontWeight:700, margin:0, color:'#fff' }}>最近活动</h3>
              <a href="#" style={{ fontSize:13, color:'#555', textDecoration:'none' }}>查看全部</a>
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
              {RECENT.map((r,i)=>(
                <div key={i} style={{ padding:'16px 20px', background:'#141414', border:'1px solid #1C1C1C', borderRadius:14, display:'flex', alignItems:'center', gap:16, cursor:'pointer' }}>
                  <div style={{ width:40, height:40, background:'#1C1C1C', borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', fontSize:18, flexShrink:0 }}>{r.icon}</div>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontSize:14, fontWeight:600, color:'#fff', marginBottom:2 }}>{r.title}</div>
                    <div style={{ fontSize:12, color:'#555', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{r.chapter}</div>
                  </div>
                  <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:6, flexShrink:0 }}>
                    <span style={{ fontSize:11, color:'#444' }}>{r.time}</span>
                    <span style={{ padding:'2px 10px', borderRadius:999, fontSize:11, fontWeight:600, background: r.status==='done' ? 'rgba(46,213,115,0.12)' : 'rgba(255,229,0,0.08)', color: r.status==='done' ? '#2ED573' : '#FFE500' }}>{r.status==='done' ? '已生成' : '草稿'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Update log */}
          <div style={{ width:260, background:'#141414', border:'1px solid #1C1C1C', borderRadius:16, padding:'20px' }}>
            <h4 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:14, fontWeight:700, color:'#fff', margin:'0 0 16px' }}>更新日志</h4>
            {[
              { ver:'v2.4.1', date:'2026-03-20', note:'新增情感曲线分析' },
              { ver:'v2.4.0', date:'2026-03-15', note:'灵感模式全面升级' },
              { ver:'v2.3.5', date:'2026-03-01', note:'写作台性能优化' },
            ].map((u,i)=>(
              <div key={i} style={{ paddingBottom:12, marginBottom:12, borderBottom: i<2 ? '1px solid #1C1C1C' : 'none' }}>
                <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                  <span style={{ padding:'2px 8px', background:'rgba(255,229,0,0.1)', borderRadius:4, fontSize:11, fontWeight:600, color:'#FFE500' }}>{u.ver}</span>
                  <span style={{ fontSize:11, color:'#444' }}>{u.date}</span>
                </div>
                <p style={{ fontSize:12, color:'#666', margin:0 }}>{u.note}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
