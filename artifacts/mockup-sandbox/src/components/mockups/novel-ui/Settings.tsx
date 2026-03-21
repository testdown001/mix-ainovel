import { useState } from 'react'

const NAV_BAR = ['灵感模式','我的小说','写作台','设置']
const SIDEBAR = [
  { id:'llm', icon:'🤖', label:'LLM 配置' },
  { id:'writing', icon:'✍️', label:'写作偏好' },
  { id:'account', icon:'👤', label:'账号信息' },
  { id:'plan', icon:'💎', label:'会员套餐' },
]
const MODELS = ['gpt-4o','gpt-4-turbo','claude-3-5-sonnet','gemini-1.5-pro','qwen-max','自定义']

export default function Settings() {
  const [activeNav, setActiveNav] = useState('设置')
  const [activeSection, setActiveSection] = useState('llm')
  const [model, setModel] = useState('gpt-4o')
  const [temp, setTemp] = useState(0.7)
  const [testStatus, setTestStatus] = useState<'idle'|'ok'|'fail'>('idle')

  return (
    <div style={{ minHeight:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", color:'#fff' }}>

      {/* ── NAV ── */}
      <nav style={{ height:60, borderBottom:'1px solid #1C1C1C', display:'flex', alignItems:'center', padding:'0 32px', background:'#0A0A0A', position:'sticky', top:0, zIndex:100 }}>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginRight:60 }}>
          <div style={{ width:32, height:32, background:'#FFE500', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', fontSize:16, fontWeight:900, color:'#000' }}>✦</div>
          <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:15, color:'#fff' }}>Arboris Novel</span>
        </div>
        <div style={{ display:'flex', gap:4, flex:1 }}>
          {NAV_BAR.map(n=>(
            <button key={n} onClick={()=>setActiveNav(n)} style={{ padding:'6px 16px', background:'none', border:'none', borderRadius:8, fontSize:14, color: activeNav===n ? '#FFE500' : '#666', fontWeight: activeNav===n ? 600 : 400, cursor:'pointer', fontFamily:"'Inter',sans-serif" }}>{n}</button>
          ))}
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ width:34, height:34, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FFA500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, fontWeight:700, color:'#000' }}>创</div>
          <span style={{ fontSize:14, color:'#888' }}>创作者_01</span>
        </div>
      </nav>

      <div style={{ maxWidth:1100, margin:'0 auto', padding:'40px 32px', display:'grid', gridTemplateColumns:'240px 1fr', gap:32 }}>

        {/* ── LEFT SIDEBAR ── */}
        <aside style={{ background:'#141414', border:'1px solid #1C1C1C', borderRadius:18, padding:'24px', height:'fit-content', position:'sticky', top:80 }}>
          {/* User card */}
          <div style={{ textAlign:'center', paddingBottom:20, marginBottom:20, borderBottom:'1px solid #1C1C1C' }}>
            <div style={{ width:60, height:60, borderRadius:'50%', background:'linear-gradient(135deg,#FFE500,#FFA500)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, fontWeight:700, color:'#000', margin:'0 auto 12px' }}>创</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:15, fontWeight:700, color:'#fff', marginBottom:4 }}>创作者_01</div>
            <div style={{ fontSize:12, color:'#555' }}>user_01@example.com</div>
            <div style={{ marginTop:10, padding:'4px 14px', background:'rgba(255,229,0,0.08)', border:'1px solid rgba(255,229,0,0.2)', borderRadius:999, fontSize:12, fontWeight:600, color:'#FFE500', display:'inline-block' }}>免费版</div>
          </div>
          {/* Nav items */}
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {SIDEBAR.map(s=>(
              <button key={s.id} onClick={()=>setActiveSection(s.id)} style={{ width:'100%', padding:'10px 16px', borderRadius:10, background: activeSection===s.id ? 'rgba(255,229,0,0.06)' : 'transparent', border: 'none', display:'flex', alignItems:'center', gap:12, cursor:'pointer', textAlign:'left', borderLeft: activeSection===s.id ? '2px solid #FFE500' : '2px solid transparent' }}>
                <span style={{ fontSize:16 }}>{s.icon}</span>
                <span style={{ fontSize:14, color: activeSection===s.id ? '#FFE500' : '#666', fontWeight: activeSection===s.id ? 600 : 400 }}>{s.label}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* ── RIGHT CONTENT ── */}
        <div style={{ display:'flex', flexDirection:'column', gap:24 }}>

          {activeSection === 'llm' && (
            <>
              <div style={{ background:'#141414', border:'1px solid #1C1C1C', borderRadius:18, padding:'32px' }}>
                <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:22, fontWeight:700, color:'#fff', margin:'0 0 6px', letterSpacing:'-0.5px' }}>LLM 配置</h2>
                <p style={{ fontSize:14, color:'#555', margin:'0 0 32px' }}>配置你的AI模型连接，支持 OpenAI 兼容接口</p>

                <div style={{ display:'flex', flexDirection:'column', gap:24 }}>
                  {/* Model URL */}
                  <div>
                    <label style={{ display:'block', fontSize:13, fontWeight:500, color:'#888', marginBottom:8 }}>API 端点地址</label>
                    <input readOnly defaultValue="https://api.openai.com/v1" style={{ width:'100%', padding:'12px 16px', background:'#0A0A0A', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box', fontFamily:'monospace' }}/>
                    <p style={{ fontSize:12, color:'#444', marginTop:6 }}>支持 OpenAI、Azure、Ollama 等兼容接口</p>
                  </div>

                  {/* API Key */}
                  <div>
                    <label style={{ display:'block', fontSize:13, fontWeight:500, color:'#888', marginBottom:8 }}>API 密钥</label>
                    <input readOnly type="password" defaultValue="sk-••••••••••••••••••••••••••••••••" style={{ width:'100%', padding:'12px 16px', background:'#0A0A0A', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box', fontFamily:'monospace' }}/>
                  </div>

                  {/* Model select */}
                  <div>
                    <label style={{ display:'block', fontSize:13, fontWeight:500, color:'#888', marginBottom:8 }}>模型名称</label>
                    <select value={model} onChange={e=>setModel(e.target.value)} style={{ width:'100%', padding:'12px 16px', background:'#0A0A0A', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box', cursor:'pointer' }}>
                      {MODELS.map(m=><option key={m} value={m} style={{ background:'#141414' }}>{m}</option>)}
                    </select>
                  </div>

                  {/* Temperature */}
                  <div>
                    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
                      <label style={{ fontSize:13, fontWeight:500, color:'#888' }}>创意温度 (Temperature)</label>
                      <span style={{ fontSize:13, fontWeight:700, color:'#FFE500', fontFamily:"'Space Grotesk',sans-serif" }}>{temp.toFixed(1)}</span>
                    </div>
                    <input type="range" min={0} max={1} step={0.1} value={temp} onChange={e=>setTemp(Number(e.target.value))} style={{ width:'100%', accentColor:'#FFE500', cursor:'pointer' }}/>
                    <div style={{ display:'flex', justifyContent:'space-between', marginTop:4 }}>
                      <span style={{ fontSize:11, color:'#444' }}>保守稳定</span>
                      <span style={{ fontSize:11, color:'#444' }}>充满创意</span>
                    </div>
                  </div>

                  {/* Test connection */}
                  <div style={{ display:'flex', gap:12, alignItems:'center' }}>
                    <button onClick={()=>setTestStatus('ok')} style={{ padding:'11px 24px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>
                      🔌 测试连接
                    </button>
                    {testStatus==='ok' && <span style={{ fontSize:13, color:'#2ED573', fontWeight:600 }}>✓ 连接成功</span>}
                    {testStatus==='fail' && <span style={{ fontSize:13, color:'#FF4757', fontWeight:600 }}>✕ 连接失败</span>}
                  </div>
                </div>
              </div>

              {/* Save button */}
              <button style={{ alignSelf:'flex-end', padding:'12px 32px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>保存配置</button>
            </>
          )}

          {activeSection !== 'llm' && (
            <div style={{ background:'#141414', border:'1px solid #1C1C1C', borderRadius:18, padding:'32px', textAlign:'center', paddingTop:80, paddingBottom:80 }}>
              <div style={{ fontSize:48, marginBottom:16 }}>{SIDEBAR.find(s=>s.id===activeSection)?.icon}</div>
              <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:700, color:'#333', marginBottom:8 }}>{SIDEBAR.find(s=>s.id===activeSection)?.label}</div>
              <p style={{ fontSize:14, color:'#444' }}>此功能正在开发中，敬请期待</p>
            </div>
          )}

          {/* ── MEMBERSHIP CARD ── */}
          <div style={{ background:'linear-gradient(135deg,#141414 0%,#1A1A0A 100%)', border:'1px solid rgba(255,229,0,0.2)', borderRadius:18, padding:'28px 32px', display:'flex', alignItems:'center', gap:28 }}>
            <div style={{ width:52, height:52, background:'rgba(255,229,0,0.1)', borderRadius:14, display:'flex', alignItems:'center', justifyContent:'center', fontSize:26, flexShrink:0 }}>💎</div>
            <div style={{ flex:1 }}>
              <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:6 }}>
                <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:17, fontWeight:700, color:'#fff' }}>当前套餐：免费版</span>
                <span style={{ padding:'3px 10px', background:'rgba(255,229,0,0.08)', border:'1px solid rgba(255,229,0,0.2)', borderRadius:999, fontSize:11, fontWeight:600, color:'#FFE500' }}>FREE</span>
              </div>
              <p style={{ fontSize:13, color:'#555', margin:'0 0 4px' }}>每月可生成 50,000 字 · 已使用 38,000 字</p>
              <div style={{ width:'100%', maxWidth:300, height:4, background:'#1C1C1C', borderRadius:999, marginTop:8 }}>
                <div style={{ width:'76%', height:'100%', background:'linear-gradient(90deg,#FFE500,#FFA500)', borderRadius:999 }}/>
              </div>
            </div>
            <button style={{ padding:'12px 24px', background:'#FFE500', border:'none', borderRadius:10, fontSize:14, fontWeight:700, color:'#000', cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif", flexShrink:0 }}>⬆ 升级会员</button>
          </div>
        </div>
      </div>
    </div>
  )
}
