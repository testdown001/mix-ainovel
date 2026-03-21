import { useState } from 'react'

const NAV = ['灵感模式','我的小说','写作台','设置']
const SIDEBAR_ITEMS = [
  { id:'llm', icon:'🤖', label:'LLM 配置' },
  { id:'writing', icon:'✍️', label:'写作偏好' },
  { id:'account', icon:'👤', label:'账号信息' },
  { id:'plan', icon:'💎', label:'会员套餐' },
]

function TopNav() {
  return (
    <div style={{ height:60, background:'#0A0A0A', borderBottom:'1px solid #1E1E1E', display:'flex', alignItems:'center', padding:'0 32px', gap:40, flexShrink:0 }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginRight:16 }}>
        <div style={{ width:34, height:34, background:'#FFE500', borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', fontSize:17, fontWeight:900, color:'#000' }}>✦</div>
        <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:15, color:'#fff' }}>Arboris Novel</span>
      </div>
      <div style={{ display:'flex', gap:4, flex:1 }}>
        {NAV.map(n=>(
          <div key={n} style={{ padding:'6px 16px', borderRadius:8, fontSize:14, fontWeight:n==='设置'?600:400, color:n==='设置'?'#FFE500':'#888', background:n==='设置'?'rgba(255,229,0,0.08)':'transparent', cursor:'pointer' }}>{n}</div>
        ))}
      </div>
      <div style={{ width:32, height:32, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FF9500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, fontWeight:700, color:'#000' }}>创</div>
    </div>
  )
}

function Field({ label, children }:{ label:string, children:React.ReactNode }) {
  return (
    <div style={{ marginBottom:22 }}>
      <label style={{ fontSize:12, color:'#888', fontWeight:600, display:'block', marginBottom:8, letterSpacing:'0.5px', textTransform:'uppercase' as const }}>{label}</label>
      {children}
    </div>
  )
}

const inputStyle = { width:'100%', padding:'12px 16px', background:'#1C1C1C', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' as const, fontFamily:'inherit' }

function LLMPanel() {
  const [temp, setTemp] = useState(70)
  return (
    <div>
      <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:800, color:'#fff', marginBottom:4 }}>LLM 配置</div>
      <p style={{ fontSize:14, color:'#666', marginBottom:28 }}>配置用于AI创作的大语言模型。</p>

      <Field label="模型 API 地址">
        <input style={inputStyle} placeholder="https://api.openai.com/v1" defaultValue="https://api.openai.com/v1"/>
      </Field>
      <Field label="API 密钥">
        <div style={{ position:'relative' }}>
          <input type="password" style={inputStyle} placeholder="sk-···" defaultValue="sk-proj-xxxxxxxxxxxxxxxxxxx"/>
          <button style={{ position:'absolute', right:12, top:'50%', transform:'translateY(-50%)', background:'none', border:'none', color:'#555', fontSize:12, cursor:'pointer' }}>显示</button>
        </div>
      </Field>
      <Field label="模型名称">
        <div style={{ position:'relative' }}>
          <select style={{ ...inputStyle, appearance:'none' as const, cursor:'pointer' }}>
            {['gpt-4o','gpt-4o-mini','gpt-4-turbo','claude-3-5-sonnet'].map(m=><option key={m}>{m}</option>)}
          </select>
          <span style={{ position:'absolute', right:14, top:'50%', transform:'translateY(-50%)', color:'#555', pointerEvents:'none' }}>▾</span>
        </div>
      </Field>
      <Field label={`创意温度 (Temperature)：${(temp/100).toFixed(2)}`}>
        <div style={{ display:'flex', alignItems:'center', gap:16 }}>
          <input type="range" min={0} max={100} value={temp} onChange={e=>setTemp(+e.target.value)}
            style={{ flex:1, accentColor:'#FFE500', cursor:'pointer' }}/>
          <div style={{ display:'flex', gap:4, fontSize:11, color:'#555' }}>
            <span>精确</span><span>···</span><span>创意</span>
          </div>
        </div>
      </Field>
      <Field label="搜索 API 密钥（可选）">
        <input type="password" style={inputStyle} placeholder="用于联网搜索小说信息（可留空）"/>
      </Field>

      <div style={{ display:'flex', gap:12, marginTop:8 }}>
        <button style={{ padding:'11px 24px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer' }}>
          保存配置
        </button>
        <button style={{ padding:'11px 24px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:10, fontSize:14, color:'#888', cursor:'pointer' }}>
          🔌 测试连接
        </button>
      </div>

      {/* Connection status */}
      <div style={{ marginTop:16, display:'flex', alignItems:'center', gap:8, padding:'12px 16px', background:'rgba(46,213,115,0.08)', border:'1px solid rgba(46,213,115,0.2)', borderRadius:10 }}>
        <div style={{ width:8, height:8, borderRadius:'50%', background:'#2ED573', boxShadow:'0 0 8px #2ED573' }}/>
        <span style={{ fontSize:13, color:'#2ED573' }}>连接正常 · gpt-4o · 响应 342ms</span>
      </div>

      {/* Membership card */}
      <div style={{ marginTop:32, padding:'24px 28px', background:'linear-gradient(135deg,#1A1700,#141414)', border:'1px solid rgba(255,229,0,0.2)', borderRadius:16, position:'relative', overflow:'hidden' }}>
        <div style={{ position:'absolute', top:-30, right:-30, width:120, height:120, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.1),transparent)' }}/>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:16 }}>
          <span style={{ fontSize:24 }}>💎</span>
          <div>
            <div style={{ fontSize:11, color:'#888', marginBottom:2 }}>当前套餐</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:16, fontWeight:800, color:'#FFE500' }}>免费版</div>
          </div>
        </div>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:20 }}>
          {[['小说限额','10部'],['章节配额','100章/月'],['AI生成','基础模型'],['导出','TXT 格式']].map(([k,v])=>(
            <div key={k} style={{ fontSize:12, color:'#666' }}>{k}：<span style={{ color:'#888' }}>{v}</span></div>
          ))}
        </div>
        <button style={{ padding:'11px 22px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:800, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>
          升级会员 ⚡
        </button>
      </div>
    </div>
  )
}

function WritingPanel() {
  return (
    <div>
      <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:800, color:'#fff', marginBottom:4 }}>写作偏好</div>
      <p style={{ fontSize:14, color:'#666', marginBottom:28 }}>自定义AI写作风格与行为。</p>
      <Field label="默认写作风格">
        <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10 }}>
          {['简洁明快','情节爽文','文艺感性','热血冒险','轻松幽默','沉浸深情'].map((s,i)=>(
            <div key={s} style={{ padding:'12px', background:i===1?'rgba(255,229,0,0.1)':'#1C1C1C', border:`1px solid ${i===1?'#FFE500':'#2A2A2A'}`, borderRadius:10, fontSize:13, color:i===1?'#FFE500':'#888', textAlign:'center' as const, cursor:'pointer' }}>{s}</div>
          ))}
        </div>
      </Field>
      <Field label="每章默认字数目标">
        <select style={{ ...inputStyle, appearance:'none' as const }}><option>2000-3000字（标准）</option><option>1000-2000字（短章）</option><option>3000-5000字（长章）</option></select>
      </Field>
      <Field label="章节末尾处理">
        <div style={{ display:'flex', flexDirection:'column' as const, gap:8 }}>
          {[['suspense','制造悬念（推荐）'],['summary','总结收尾'],['cliffhanger','强悬念结尾']].map(([v,l])=>(
            <label key={v} style={{ display:'flex', alignItems:'center', gap:10, cursor:'pointer' }}>
              <div style={{ width:16, height:16, borderRadius:'50%', border:`2px solid ${v==='suspense'?'#FFE500':'#2A2A2A'}`, display:'flex', alignItems:'center', justifyContent:'center' }}>
                {v==='suspense'&&<div style={{ width:6, height:6, borderRadius:'50%', background:'#FFE500' }}/>}
              </div>
              <span style={{ fontSize:14, color:'#888' }}>{l}</span>
            </label>
          ))}
        </div>
      </Field>
      <button style={{ padding:'11px 24px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer' }}>保存偏好</button>
    </div>
  )
}

function AccountPanel() {
  return (
    <div>
      <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:800, color:'#fff', marginBottom:4 }}>账号信息</div>
      <p style={{ fontSize:14, color:'#666', marginBottom:28 }}>管理你的账号设置。</p>
      <div style={{ display:'flex', alignItems:'center', gap:20, padding:'24px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:16, marginBottom:28 }}>
        <div style={{ width:72, height:72, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FF9500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:30, fontWeight:700, color:'#000' }}>创</div>
        <div style={{ flex:1 }}>
          <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:700, color:'#fff', marginBottom:2 }}>创作者</div>
          <div style={{ fontSize:13, color:'#666' }}>creator@example.com</div>
          <div style={{ fontSize:12, color:'#555', marginTop:4 }}>注册于 2024-01-01 · 免费版用户</div>
        </div>
        <button style={{ padding:'9px 18px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:8, fontSize:13, color:'#888', cursor:'pointer' }}>更换头像</button>
      </div>
      <Field label="用户名"><input style={inputStyle} defaultValue="创作者"/></Field>
      <Field label="邮箱地址"><input style={inputStyle} defaultValue="creator@example.com"/></Field>
      <Field label="新密码（留空则不修改）"><input type="password" style={inputStyle} placeholder="输入新密码"/></Field>
      <div style={{ display:'flex', gap:12, marginTop:8 }}>
        <button style={{ padding:'11px 24px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer' }}>保存修改</button>
        <button style={{ padding:'11px 24px', background:'rgba(255,71,87,0.1)', border:'1px solid rgba(255,71,87,0.25)', borderRadius:10, fontSize:14, color:'#FF4757', cursor:'pointer' }}>注销账号</button>
      </div>
    </div>
  )
}

function PlanPanel() {
  return (
    <div>
      <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:800, color:'#fff', marginBottom:4 }}>会员套餐</div>
      <p style={{ fontSize:14, color:'#666', marginBottom:28 }}>选择最适合你的创作方案。</p>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:16, marginBottom:32 }}>
        {[
          { name:'免费版', price:'¥0', period:'永久', current:true, color:'#888', features:['10部小说','100章/月','基础模型','TXT导出'] },
          { name:'专业版', price:'¥39', period:'/月', current:false, color:'#FFE500', features:['无限小说','1000章/月','GPT-4o','多格式导出','优先客服'] },
          { name:'旗舰版', price:'¥99', period:'/月', current:false, color:'#A855F7', features:['无限一切','自定义模型','专属训练','API接入','团队协作'] },
        ].map(p=>(
          <div key={p.name} style={{ background:p.current?'#141414':'#141414', border:`1px solid ${p.current?'#2A2A2A':p.color+'55'}`, borderRadius:16, padding:'24px 22px', position:'relative', overflow:'hidden' }}>
            {!p.current && <div style={{ position:'absolute', top:0, left:0, right:0, height:3, background:`linear-gradient(90deg,${p.color},${p.color}66)` }}/>}
            {p.current && <div style={{ position:'absolute', top:12, right:12, padding:'3px 10px', background:'rgba(136,136,136,0.1)', borderRadius:999, fontSize:11, color:'#888' }}>当前套餐</div>}
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:16, fontWeight:700, color:p.current?'#888':p.color, marginBottom:8 }}>{p.name}</div>
            <div style={{ marginBottom:20 }}>
              <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:32, fontWeight:900, color:'#fff' }}>{p.price}</span>
              <span style={{ fontSize:13, color:'#666' }}>{p.period}</span>
            </div>
            <div style={{ display:'flex', flexDirection:'column' as const, gap:8, marginBottom:20 }}>
              {p.features.map(f=>(
                <div key={f} style={{ display:'flex', gap:8, alignItems:'center', fontSize:13, color:'#888' }}>
                  <span style={{ color:p.color }}>✓</span>{f}
                </div>
              ))}
            </div>
            <button style={{ width:'100%', padding:'11px', background:p.current?'transparent':p.color, border:p.current?'1px solid #2A2A2A':'none', borderRadius:10, fontSize:13, fontWeight:700, color:p.current?'#555':'#000', cursor:p.current?'default':'pointer' }}>
              {p.current?'当前方案':'立即升级'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

const PANELS:Record<string,React.ReactNode> = {
  llm: <LLMPanel/>, writing: <WritingPanel/>, account: <AccountPanel/>, plan: <PlanPanel/>
}

export default function Settings() {
  const [active, setActive] = useState('llm')

  return (
    <div style={{ display:'flex', flexDirection:'column' as const, height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>
      <TopNav/>
      <div style={{ flex:1, display:'flex', overflow:'hidden' }}>
        {/* Left sidebar */}
        <div style={{ width:260, background:'#141414', borderRight:'1px solid #1E1E1E', display:'flex', flexDirection:'column' as const, padding:'24px 0', flexShrink:0 }}>
          {/* User card */}
          <div style={{ padding:'0 20px 24px', borderBottom:'1px solid #1E1E1E', marginBottom:16 }}>
            <div style={{ display:'flex', alignItems:'center', gap:12 }}>
              <div style={{ width:44, height:44, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FF9500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, fontWeight:700, color:'#000', flexShrink:0 }}>创</div>
              <div>
                <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:1 }}>创作者</div>
                <div style={{ fontSize:12, color:'#666' }}>免费版用户</div>
              </div>
            </div>
          </div>

          {/* Nav items */}
          {SIDEBAR_ITEMS.map(item=>(
            <button key={item.id} onClick={()=>setActive(item.id)} style={{ display:'flex', alignItems:'center', gap:14, padding:'13px 20px', background:active===item.id?'rgba(255,229,0,0.07)':'transparent', borderLeft:active===item.id?'2px solid #FFE500':'2px solid transparent', border:'none', width:'100%', cursor:'pointer', textAlign:'left' as const }}>
              <span style={{ fontSize:18 }}>{item.icon}</span>
              <span style={{ fontSize:14, fontWeight:active===item.id?600:400, color:active===item.id?'#FFE500':'#888' }}>{item.label}</span>
            </button>
          ))}
        </div>

        {/* Right content */}
        <div style={{ flex:1, overflowY:'auto' as const, padding:'36px 48px' }}>
          {PANELS[active]}
        </div>
      </div>
    </div>
  )
}
