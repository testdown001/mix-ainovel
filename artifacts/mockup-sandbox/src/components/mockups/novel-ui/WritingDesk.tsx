import { useState } from 'react'

type ChSt = 'done'|'pending'|'empty'
const CHAPTERS:{num:number,title:string,status:ChSt}[] = [
  {num:1,title:'序章·命运交织',status:'done'},{num:2,title:'第一次碰撞',status:'done'},
  {num:3,title:'风暴前夕',status:'done'},{num:4,title:'神秘来客',status:'done'},
  {num:5,title:'血月之夜',status:'done'},{num:6,title:'秘密曝光',status:'done'},
  {num:7,title:'追与逃',status:'done'},{num:8,title:'联盟破裂',status:'done'},
  {num:9,title:'真相一角',status:'done'},{num:10,title:'深渊之上',status:'done'},
  {num:11,title:'最后防线',status:'done'},{num:12,title:'新的危机',status:'done'},
  {num:13,title:'(AI创作中...)',status:'pending'},{num:14,title:'(待生成)',status:'empty'},
  {num:15,title:'(待生成)',status:'empty'},{num:16,title:'(待生成)',status:'empty'},
]
const CHAPTER_CONTENT = `第12章　新的危机

繁星之下，剑与星河的世界在黎明前的黑暗中沉睡。

林远站在峭壁边缘，远处的灯火如星辰般点缀着山间村落。那封神秘的信笺已在他手中攥了整整三个昼夜，纸张的边缘微微泛黄，墨迹却依然清晰如初。

"你不该来的。"

身后传来熟悉的声音。林远没有回头，只是轻轻将信笺折好，收入袖中。

"我来，是因为别人都不敢来。"他说，语气平静如山间的夜风，"而且……我必须知道真相。"

剑气在他周身流转，将夜露蒸腾殆尽。青云山庄的旗帜在远处迎风招展，那象征着正道权威的符文如今在他眼中却透着几分讽刺的意味。

十二年。整整十二年的谎言。

身后的脚步声停住了。来人是凌霄，青云山庄大弟子，也是他曾经最信任的师兄。

"师父他……也是身不由己。"凌霄的声音低沉，带着说不清道不明的沉重。

林远终于转过身，月光将他的轮廓镀上一层清冷的银辉。`

const DOT_COLOR = {done:'#2ED573',pending:'#FFE500',empty:'#333'}

export default function WritingDesk() {
  const [sel, setSel] = useState(12)
  const [loading] = useState(false)

  return (
    <div style={{ display:'flex', flexDirection:'column' as const, height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>
      {/* Header */}
      <div style={{ height:56, background:'#0A0A0A', borderBottom:'1px solid #1E1E1E', display:'flex', alignItems:'center', padding:'0 24px', gap:16, flexShrink:0 }}>
        <button style={{ display:'flex', alignItems:'center', gap:8, padding:'6px 12px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, color:'#888', fontSize:13, cursor:'pointer' }}>
          ← 返回
        </button>
        <div style={{ flex:1 }}>
          <div style={{ display:'flex', alignItems:'center', gap:12 }}>
            <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:16, fontWeight:700, color:'#fff' }}>剑与星河</span>
            <div style={{ flex:1, maxWidth:200 }}>
              <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:'#666', marginBottom:3 }}>
                <span>第 12/30 章</span><span>40%</span>
              </div>
              <div style={{ height:3, background:'#2A2A2A', borderRadius:999 }}>
                <div style={{ height:'100%', width:'40%', background:'linear-gradient(90deg,#FFE500,#FF9500)', borderRadius:999 }}/>
              </div>
            </div>
          </div>
        </div>
        <button style={{ padding:'7px 16px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, fontSize:13, color:'#888', cursor:'pointer' }}>查看详情</button>
        <button style={{ padding:'7px 16px', background:'rgba(255,229,0,0.1)', border:'1px solid rgba(255,229,0,0.25)', borderRadius:8, fontSize:13, color:'#FFE500', fontWeight:600, cursor:'pointer' }}>⚡ 生成大纲</button>
      </div>

      <div style={{ flex:1, display:'flex', overflow:'hidden' }}>
        {/* Left Sidebar */}
        <div style={{ width:268, background:'#141414', borderRight:'1px solid #1E1E1E', display:'flex', flexDirection:'column' as const, overflow:'hidden', flexShrink:0 }}>
          <div style={{ padding:'16px 18px', borderBottom:'1px solid #1E1E1E' }}>
            <div style={{ fontSize:11, color:'#555', fontWeight:600, letterSpacing:'0.5px', textTransform:'uppercase' as const, marginBottom:2 }}>章节列表</div>
          </div>
          <div style={{ flex:1, overflowY:'auto' as const }}>
            {CHAPTERS.map(c=>(
              <div key={c.num} onClick={()=>setSel(c.num)} style={{ display:'flex', alignItems:'center', gap:12, padding:'11px 18px', cursor:'pointer', background:sel===c.num?'rgba(255,229,0,0.06)':'transparent', borderLeft:sel===c.num?'2px solid #FFE500':'2px solid transparent' }}>
                <div style={{ width:6, height:6, borderRadius:'50%', background:DOT_COLOR[c.status], flexShrink:0, boxShadow:c.status==='done'?'0 0 6px #2ED57344':c.status==='pending'?'0 0 6px #FFE50044':'none' }}/>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:11, color:'#555', marginBottom:1 }}>第 {c.num} 章</div>
                  <div style={{ fontSize:13, color:sel===c.num?'#FFE500':c.status==='empty'?'#444':'#CCC', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' as const }}>{c.title}</div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ padding:'16px 18px', borderTop:'1px solid #1E1E1E' }}>
            <button style={{ width:'100%', padding:'11px', background:'linear-gradient(135deg,#FFE500,#FF9500)', border:'none', borderRadius:10, fontSize:13, fontWeight:700, color:'#000', cursor:'pointer' }}>
              ⚡ 批量生成章节
            </button>
          </div>
        </div>

        {/* Main content */}
        <div style={{ flex:1, display:'flex', overflow:'hidden', position:'relative' }}>
          {loading ? (
            <div style={{ flex:1, display:'flex', flexDirection:'column' as const, alignItems:'center', justifyContent:'center', gap:24 }}>
              <div style={{ width:56, height:56, border:'3px solid #1E1E1E', borderTop:'3px solid #FFE500', borderRadius:'50%', animation:'spin 1s linear infinite' }}/>
              <div style={{ textAlign:'center' as const }}>
                <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:18, fontWeight:700, color:'#fff', marginBottom:8 }}>AI正在创作第13章...</div>
                <div style={{ fontSize:14, color:'#666' }}>追与逃，真相即将浮现</div>
              </div>
              {/* Skeleton lines */}
              <div style={{ width:480, display:'flex', flexDirection:'column' as const, gap:10, marginTop:8 }}>
                {[100,88,92,75,85].map((w,i)=>(
                  <div key={i} style={{ height:14, background:'#1C1C1C', borderRadius:6, width:`${w}%` }}/>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ flex:1, overflowY:'auto' as const, padding:'48px 64px', maxWidth:760, margin:'0 auto', width:'100%' }}>
              {/* Chapter tag */}
              <div style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'5px 14px', background:'rgba(46,213,115,0.1)', border:'1px solid rgba(46,213,115,0.2)', borderRadius:999, fontSize:12, color:'#2ED573', fontWeight:600, marginBottom:32 }}>
                <span style={{ width:6, height:6, borderRadius:'50%', background:'#2ED573', display:'inline-block' }}/>
                已生成 · 第 12 章
              </div>
              <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:26, fontWeight:800, color:'#fff', marginBottom:32, letterSpacing:'-0.5px', lineHeight:1.3 }}>
                新的危机
              </div>
              <div style={{ fontSize:16, color:'#CCCCCC', lineHeight:2, whiteSpace:'pre-wrap' as const, letterSpacing:'0.2px' }}>
                {CHAPTER_CONTENT}
              </div>
              {/* Word count */}
              <div style={{ marginTop:48, padding:'16px 20px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:12, display:'flex', gap:32 }}>
                {[['本章字数','2,847字'],['AI生成率','94%'],['质量评分','88/100']].map(([l,v])=>(
                  <div key={l}>
                    <div style={{ fontSize:11, color:'#555', marginBottom:3 }}>{l}</div>
                    <div style={{ fontSize:16, fontWeight:700, color:'#FFE500', fontFamily:"'Space Grotesk',sans-serif" }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Floating AI toolbar */}
          <div style={{ position:'absolute', right:24, top:'50%', transform:'translateY(-50%)', display:'flex', flexDirection:'column' as const, gap:8 }}>
            {[
              {icon:'⚡',label:'生成本章',primary:true},
              {icon:'📊',label:'评估质量',primary:false},
              {icon:'🕐',label:'版本历史',primary:false},
              {icon:'✏️',label:'编辑模式',primary:false},
            ].map(a=>(
              <button key={a.label} title={a.label} style={{ width:48, height:48, borderRadius:12, border:`1px solid ${a.primary?'#FFE500':'#2A2A2A'}`, background:a.primary?'#FFE500':'#141414', color:a.primary?'#000':'#888', fontSize:20, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', transition:'all 0.15s' }}>
                {a.icon}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
