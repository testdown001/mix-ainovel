import { useState } from 'react'

const NAV = ['灵感模式','我的小说','写作台','设置']
const RECENT = [
  { title:'剑与星河', chapter:'第23章 · 繁星之下', time:'2小时前', status:'done' },
  { title:'都市仙途', chapter:'第11章 · 修仙觉醒', time:'昨天', status:'done' },
  { title:'赛博龙骑', chapter:'第5章（草稿）', time:'3天前', status:'draft' },
]
const UPDATES = [
  { ver:'v2.4.1', date:'2024-01-15', note:'新增情感曲线分析功能' },
  { ver:'v2.4.0', date:'2024-01-10', note:'优化章节生成速度提升40%' },
  { ver:'v2.3.5', date:'2024-01-03', note:'修复伏笔追踪显示异常' },
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
        <span style={{ fontSize:13, color:'#888' }}>创作者</span>
      </div>
    </div>
  )
}

export default function WorkspaceEntry() {
  const [activeNav] = useState('灵感模式')
  return (
    <div style={{ display:'flex', flexDirection:'column' as const, height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>
      <TopNav active={activeNav}/>

      <div style={{ flex:1, overflowY:'auto' as const, padding:'40px 48px' }}>
        {/* Hero greeting */}
        <div style={{ marginBottom:48 }}>
          <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:36, fontWeight:800, color:'#fff', letterSpacing:'-1px', marginBottom:4 }}>
            下午好，<span style={{ background:'linear-gradient(90deg,#FFE500,#FF9500)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>创作者</span> 👋
          </div>
          <p style={{ fontSize:15, color:'#666', marginBottom:32 }}>继续你未完成的故事，或开启全新的篇章。</p>

          {/* Stats row */}
          <div style={{ display:'flex', gap:20 }}>
            {[['3','部小说'],['23','章已生成'],['48,200','字创作量']].map(([v,l])=>(
              <div key={l} style={{ padding:'16px 24px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:14, display:'flex', flexDirection:'column' as const, gap:2 }}>
                <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:26, fontWeight:800, color:'#FFE500', letterSpacing:'-1px' }}>{v}</span>
                <span style={{ fontSize:12, color:'#666' }}>{l}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Action cards */}
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:40 }}>
          {/* Inspiration mode */}
          <div style={{ padding:'36px 32px', background:'linear-gradient(135deg,#1A1700,#141414)', border:'1px solid rgba(255,229,0,0.2)', borderRadius:20, cursor:'pointer', position:'relative', overflow:'hidden' }}>
            <div style={{ position:'absolute', top:-30, right:-30, width:120, height:120, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.12),transparent 70%)' }}/>
            <div style={{ fontSize:40, marginBottom:16 }}>💡</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:22, fontWeight:800, color:'#FFE500', marginBottom:8, letterSpacing:'-0.5px' }}>灵感模式</div>
            <p style={{ fontSize:14, color:'#888', lineHeight:1.6, marginBottom:24 }}>还没有故事？让AI引导你从零开始，对话式构建你的宇宙。</p>
            <div style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'10px 20px', background:'#FFE500', borderRadius:10, fontSize:13, fontWeight:700, color:'#000', cursor:'pointer' }}>
              开始创作 →
            </div>
          </div>

          {/* Novel library */}
          <div style={{ padding:'36px 32px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:20, cursor:'pointer', position:'relative', overflow:'hidden' }}>
            <div style={{ position:'absolute', top:-30, right:-30, width:120, height:120, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,255,255,0.03),transparent 70%)' }}/>
            <div style={{ fontSize:40, marginBottom:16 }}>📚</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:22, fontWeight:800, color:'#fff', marginBottom:8, letterSpacing:'-0.5px' }}>我的小说库</div>
            <p style={{ fontSize:14, color:'#888', lineHeight:1.6, marginBottom:24 }}>查看并管理你所有的小说项目，继续上次的创作进度。</p>
            <div style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'10px 20px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:10, fontSize:13, fontWeight:600, color:'#fff', cursor:'pointer' }}>
              进入小说库 →
            </div>
          </div>
        </div>

        {/* Bottom row: recent + updates */}
        <div style={{ display:'grid', gridTemplateColumns:'3fr 2fr', gap:20 }}>
          {/* Recent activity */}
          <div style={{ background:'#141414', border:'1px solid #2A2A2A', borderRadius:16, overflow:'hidden' }}>
            <div style={{ padding:'20px 24px', borderBottom:'1px solid #1E1E1E', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:14, fontWeight:700, color:'#fff' }}>最近创作</span>
              <span style={{ fontSize:12, color:'#FFE500', cursor:'pointer' }}>全部 →</span>
            </div>
            {RECENT.map((r,i)=>(
              <div key={i} style={{ padding:'16px 24px', borderBottom:i<RECENT.length-1?'1px solid #1A1A1A':'none', display:'flex', alignItems:'center', gap:16, cursor:'pointer' }}>
                <div style={{ width:40, height:40, background:`linear-gradient(135deg,${['#FFE500','#A855F7','#06B6D4'][i]}22,${['#FFE500','#A855F7','#06B6D4'][i]}11)`, border:`1px solid ${['#FFE500','#A855F7','#06B6D4'][i]}33`, borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', fontSize:18 }}>
                  {['📖','🏙️','🐉'][i]}
                </div>
                <div style={{ flex:1 }}>
                  <div style={{ fontSize:14, fontWeight:600, color:'#fff', marginBottom:2 }}>{r.title}</div>
                  <div style={{ fontSize:12, color:'#666' }}>{r.chapter}</div>
                </div>
                <div style={{ textAlign:'right' as const }}>
                  <div style={{ fontSize:11, color:'#555', marginBottom:4 }}>{r.time}</div>
                  <div style={{ fontSize:11, padding:'2px 8px', borderRadius:999, background:r.status==='done'?'rgba(46,213,115,0.12)':'rgba(136,136,136,0.12)', color:r.status==='done'?'#2ED573':'#888' }}>
                    {r.status==='done'?'已保存':'草稿'}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Update log */}
          <div style={{ background:'#141414', border:'1px solid #2A2A2A', borderRadius:16, overflow:'hidden' }}>
            <div style={{ padding:'20px 24px', borderBottom:'1px solid #1E1E1E' }}>
              <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:14, fontWeight:700, color:'#fff' }}>更新日志</span>
            </div>
            {UPDATES.map((u,i)=>(
              <div key={i} style={{ padding:'14px 24px', borderBottom:i<UPDATES.length-1?'1px solid #1A1A1A':'none' }}>
                <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:4 }}>
                  <span style={{ fontSize:12, fontWeight:700, color:'#FFE500', fontFamily:"'Space Grotesk',sans-serif" }}>{u.ver}</span>
                  <span style={{ fontSize:11, color:'#555' }}>{u.date}</span>
                </div>
                <p style={{ margin:0, fontSize:12, color:'#888', lineHeight:1.5 }}>{u.note}</p>
              </div>
            ))}
            <div style={{ padding:'14px 24px' }}>
              <span style={{ fontSize:12, color:'#FFE500', cursor:'pointer' }}>查看全部更新 →</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
