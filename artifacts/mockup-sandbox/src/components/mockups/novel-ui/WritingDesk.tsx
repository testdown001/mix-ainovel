import { useState } from 'react'

type ChSt = 'done'|'pending'|'empty'
const CHAPTERS:{num:number,title:string,status:ChSt}[] = [
  {num:1,title:'序章·命运交织',status:'done'},{num:2,title:'第一次碰撞',status:'done'},
  {num:3,title:'风暴前夕',status:'done'},{num:4,title:'神秘来客',status:'done'},
  {num:5,title:'血月之夜',status:'done'},{num:6,title:'秘密曝光',status:'done'},
  {num:7,title:'追与逃',status:'done'},{num:8,title:'联盟破裂',status:'done'},
  {num:9,title:'真相一角',status:'done'},{num:10,title:'深渊之上',status:'done'},
  {num:11,title:'最后防线',status:'done'},{num:12,title:'新的危机',status:'done'},
  {num:13,title:'AI生成中...',status:'pending'},
  {num:14,title:'（空章节）',status:'empty'},{num:15,title:'（空章节）',status:'empty'},
]

const STATUS_DOT:Record<ChSt,string> = { done:'#2ED573', pending:'#FFE500', empty:'#333' }
const CH_CONTENT = `　　星河之上，剑光如练。

　　萧尘站在剑峰之巅，俯瞰着脚下云海翻涌，心中却无半分宁静。三年了，自从那场惊变之后，他便再也没有踏回过这片土地。

　　"师弟，你终于回来了。"

　　身后传来一声轻唤，萧尘缓缓转身。来人一身白衣胜雪，眉目如画，正是他阔别三年的师姐——李清歌。

　　"师姐。"萧尘点头，声音平静，却藏着说不清的情绪。

　　"宗门出事了。"李清歌走上前，神情凝重，"天魔宗已经确认了动向——他们盯上了藏剑阁的镇宗之宝，《山河决》。"`

export default function WritingDesk() {
  const [selected, setSelected] = useState(5)
  const [generating] = useState(false)

  const ch = CHAPTERS[selected]

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", color:'#fff', overflow:'hidden' }}>

      {/* ── HEADER ── */}
      <header style={{ height:56, borderBottom:'1px solid #1C1C1C', display:'flex', alignItems:'center', padding:'0 24px', gap:16, flexShrink:0, background:'#0A0A0A' }}>
        <button style={{ width:32, height:32, borderRadius:8, background:'#141414', border:'1px solid #1C1C1C', display:'flex', alignItems:'center', justifyContent:'center', cursor:'pointer', color:'#888', fontSize:16 }}>←</button>
        <div style={{ width:1, height:20, background:'#1C1C1C' }}/>
        <div style={{ display:'flex', alignItems:'center', gap:10, flex:1 }}>
          <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:15, fontWeight:700, color:'#fff' }}>剑与星河</span>
          {/* Progress */}
          <div style={{ display:'flex', alignItems:'center', gap:8, marginLeft:8 }}>
            <div style={{ width:120, height:5, background:'#1C1C1C', borderRadius:999 }}>
              <div style={{ width:'40%', height:'100%', background:'#FFE500', borderRadius:999 }}/>
            </div>
            <span style={{ fontSize:12, color:'#555' }}>12/30章</span>
          </div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button style={{ padding:'7px 16px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, fontSize:13, color:'#888', cursor:'pointer' }}>查看详情</button>
          <button style={{ padding:'7px 16px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, fontSize:13, color:'#888', cursor:'pointer' }}>生成大纲</button>
        </div>
      </header>

      <div style={{ display:'flex', flex:1, overflow:'hidden' }}>

        {/* ── LEFT SIDEBAR ── */}
        <aside style={{ width:260, background:'#141414', borderRight:'1px solid #1C1C1C', display:'flex', flexDirection:'column', overflow:'hidden', flexShrink:0 }}>
          <div style={{ padding:'16px 16px 12px', borderBottom:'1px solid #1C1C1C' }}>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color:'#fff', marginBottom:4 }}>剑与星河</div>
            <div style={{ fontSize:11, color:'#555' }}>仙侠 · 60章计划</div>
          </div>
          <div style={{ flex:1, overflowY:'auto', padding:'8px 0' }}>
            {CHAPTERS.map((c,i)=>(
              <button key={i} onClick={()=>setSelected(i)} style={{ width:'100%', padding:'9px 16px', background: selected===i ? 'rgba(255,229,0,0.06)' : 'transparent', border:'none', display:'flex', alignItems:'center', gap:10, cursor:'pointer', textAlign:'left', borderLeft: selected===i ? '2px solid #FFE500' : '2px solid transparent' }}>
                <div style={{ width:7, height:7, borderRadius:'50%', background:STATUS_DOT[c.status], flexShrink:0 }}/>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:12, color: selected===i ? '#FFE500' : c.status==='empty' ? '#333' : '#888', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>第{c.num}章</div>
                  <div style={{ fontSize:11, color: selected===i ? '#bbb' : c.status==='empty' ? '#2A2A2A' : '#555', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', marginTop:1 }}>{c.title}</div>
                </div>
              </button>
            ))}
          </div>
          {/* Batch generate */}
          <div style={{ padding:'16px', borderTop:'1px solid #1C1C1C' }}>
            <button style={{ width:'100%', padding:'10px', background:'#FFE500', border:'none', borderRadius:10, fontSize:13, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>⚡ 批量生成章节</button>
          </div>
        </aside>

        {/* ── MAIN AREA ── */}
        <main style={{ flex:1, display:'flex', overflow:'hidden', position:'relative' }}>
          <div style={{ flex:1, overflowY:'auto', padding:'48px 64px', maxWidth:760, margin:'0 auto', width:'100%' }}>

            {generating ? (
              <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100%', gap:24 }}>
                <div style={{ width:64, height:64, border:'3px solid #1C1C1C', borderTop:'3px solid #FFE500', borderRadius:'50%', animation:'spin 1s linear infinite' }}/>
                <div style={{ textAlign:'center' }}>
                  <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:18, fontWeight:700, color:'#fff', marginBottom:8 }}>AI正在创作第13章...</div>
                  <div style={{ fontSize:14, color:'#555' }}>正在生成高质量内容，请稍等片刻</div>
                </div>
                <div style={{ width:360, height:8, background:'#141414', borderRadius:999, overflow:'hidden' }}>
                  <div style={{ height:'100%', background:'linear-gradient(90deg,#FFE500,#FFA500)', borderRadius:999, width:'65%', animation:'progress 2s ease infinite' }}/>
                </div>
              </div>
            ) : ch.status === 'empty' ? (
              <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100%', gap:20 }}>
                <div style={{ fontSize:48 }}>✦</div>
                <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:700, color:'#333' }}>空章节</div>
                <p style={{ fontSize:14, color:'#444', textAlign:'center', maxWidth:360, lineHeight:1.6 }}>这个章节还没有内容，点击下方按钮让AI为您生成精彩章节。</p>
                <button style={{ padding:'12px 28px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>⚡ 生成本章</button>
              </div>
            ) : (
              <>
                <div style={{ marginBottom:32 }}>
                  <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:8 }}>
                    <span style={{ fontSize:12, color:'#555' }}>第{ch.num}章</span>
                    <span style={{ padding:'2px 8px', background:'rgba(46,213,115,0.1)', borderRadius:4, fontSize:11, color:'#2ED573', fontWeight:600 }}>已生成</span>
                    <span style={{ fontSize:12, color:'#444' }}>2,847字</span>
                  </div>
                  <h1 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:26, fontWeight:800, color:'#fff', margin:0, letterSpacing:'-0.5px' }}>{ch.title}</h1>
                </div>
                <div style={{ fontSize:16, lineHeight:2, color:'#ccc', whiteSpace:'pre-line', fontFamily:"'Noto Sans SC', 'Inter', sans-serif" }}>
                  {CH_CONTENT}
                </div>
                <div style={{ height:80 }}/>
              </>
            )}
          </div>

          {/* ── FLOATING AI TOOLBAR ── */}
          {ch.status !== 'empty' && (
            <div style={{ position:'absolute', right:24, top:'50%', transform:'translateY(-50%)', display:'flex', flexDirection:'column', gap:8, zIndex:10 }}>
              {[
                { icon:'⚡', label:'生成本章', primary:true },
                { icon:'🔍', label:'评估质量', primary:false },
                { icon:'🕐', label:'版本历史', primary:false },
              ].map((a,i)=>(
                <button key={i} title={a.label} style={{ width:48, height:48, borderRadius:14, background: a.primary ? '#FFE500' : '#141414', border: a.primary ? 'none' : '1px solid #2A2A2A', display:'flex', alignItems:'center', justifyContent:'center', fontSize:18, cursor:'pointer', boxShadow:'0 4px 16px rgba(0,0,0,0.4)' }}>{a.icon}</button>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
