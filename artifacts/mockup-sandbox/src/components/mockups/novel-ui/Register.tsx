const REG_FEATURES = [
  { icon:'🤝', title:'AI编辑团队，全程陪伴', desc:'从灵感到成书，AI在每个节点助力' },
  { icon:'⚡', title:'章节自动生成', desc:'一键生成符合剧情逻辑的精彩章节' },
  { icon:'🌍', title:'角色 & 世界观管理', desc:'完整的设定档案系统，永不失忆' },
];
const REG_DOTS = [[60,70],[200,140],[100,360],[380,280],[500,100],[540,460],[110,490],[310,400]];

export default function Register() {
  return (
    <div style={{ display:'flex', height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>
      {/* ── LEFT FEATURE PANEL ── */}
      <div style={{ flex:'0 0 60%', position:'relative', display:'flex', flexDirection:'column' as const, justifyContent:'center', padding:'64px 72px', overflow:'hidden' }}>
        <svg style={{ position:'absolute', inset:0, width:'100%', height:'100%' }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="g2" width="56" height="56" patternUnits="userSpaceOnUse">
              <path d="M56 0L0 0 0 56" fill="none" stroke="#FFE500" strokeWidth="0.35" opacity="0.09"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#g2)"/>
          <line x1="-50" y1="750" x2="650" y2="-50" stroke="#FFE500" strokeWidth="0.8" opacity="0.07"/>
          <line x1="250" y1="750" x2="950" y2="-50" stroke="#FFE500" strokeWidth="0.5" opacity="0.04"/>
          <circle cx="520" cy="200" r="140" fill="none" stroke="#FFE500" strokeWidth="0.5" opacity="0.1"/>
          <circle cx="520" cy="200" r="80" fill="none" stroke="#FFE500" strokeWidth="0.5" opacity="0.07"/>
        </svg>
        <div style={{ position:'absolute', top:-80, right:-80, width:400, height:400, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.06) 0%,transparent 70%)' }}/>
        <div style={{ position:'absolute', bottom:-80, left:-80, width:350, height:350, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.04) 0%,transparent 70%)' }}/>
        {REG_DOTS.map(([x,y],i)=>(
          <div key={i} style={{ position:'absolute', left:x, top:y, width:i%2===0?5:3, height:i%2===0?5:3, borderRadius:'50%', background:'#FFE500', opacity:[0.8,0.45,0.6,0.35,0.7,0.4,0.25,0.55][i] }}/>
        ))}

        <div style={{ position:'relative', zIndex:1 }}>
          <div style={{ display:'flex', alignItems:'center', gap:14, marginBottom:72 }}>
            <div style={{ width:48, height:48, background:'#FFE500', borderRadius:14, display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, fontWeight:900, color:'#000', fontFamily:"'Space Grotesk',sans-serif" }}>✦</div>
            <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:18, color:'#fff' }}>Arboris Novel</span>
          </div>

          <div style={{ marginBottom:56 }}>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:46, fontWeight:800, lineHeight:1.1, color:'#fff', letterSpacing:'-1.5px', marginBottom:16 }}>
              开启你的<br/><span style={{ color:'#FFE500' }}>AI创作之旅</span>
            </div>
            <p style={{ fontSize:15, color:'#555', lineHeight:1.7, maxWidth:400 }}>注册即可免费使用所有核心功能，无需信用卡。</p>
          </div>

          <div style={{ display:'flex', flexDirection:'column' as const, gap:28 }}>
            {REG_FEATURES.map((f,i)=>(
              <div key={i} style={{ display:'flex', alignItems:'flex-start', gap:18 }}>
                <div style={{ width:44, height:44, background:'rgba(255,229,0,0.08)', border:'1px solid rgba(255,229,0,0.15)', borderRadius:12, display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, flexShrink:0 }}>{f.icon}</div>
                <div>
                  <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:4 }}>
                    <span style={{ fontSize:15, fontWeight:700, color:'#fff' }}>{f.title}</span>
                    <span style={{ fontSize:16, color:'#2ED573', fontWeight:700 }}>✓</span>
                  </div>
                  <span style={{ fontSize:13, color:'#666' }}>{f.desc}</span>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop:52, padding:'20px 24px', background:'rgba(255,229,0,0.04)', border:'1px solid rgba(255,229,0,0.1)', borderRadius:14 }}>
            <div style={{ fontSize:12, color:'#888', marginBottom:4 }}>注册后即享</div>
            <div style={{ fontSize:15, fontWeight:700, color:'#FFE500' }}>免费版 · 永久有效</div>
            <div style={{ fontSize:12, color:'#555', marginTop:4 }}>10部小说 · 100章生成配额/月</div>
          </div>
        </div>
      </div>

      {/* ── RIGHT FORM ── */}
      <div style={{ flex:'0 0 40%', display:'flex', alignItems:'center', justifyContent:'center', padding:'48px 52px', background:'#0D0D0D', borderLeft:'1px solid #1E1E1E' }}>
        <div style={{ width:'100%', maxWidth:380 }}>
          <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:26, fontWeight:800, color:'#fff', marginBottom:8, letterSpacing:'-0.5px' }}>创建账号</h2>
          <p style={{ fontSize:14, color:'#666', marginBottom:36 }}>填写以下信息，免费开始创作</p>

          <button style={{ width:'100%', padding:'13px 20px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:12, color:'#fff', fontSize:14, fontWeight:600, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:10, marginBottom:28 }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FFE500" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M8 12h8M12 8v8"/></svg>
            使用 LinuxDO 注册
          </button>

          <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:24 }}>
            <div style={{ flex:1, height:1, background:'#1E1E1E' }}/>
            <span style={{ fontSize:12, color:'#444' }}>或创建账号</span>
            <div style={{ flex:1, height:1, background:'#1E1E1E' }}/>
          </div>

          {[['用户名','请设置用户名','text'],['密码','至少8位字符','password'],['确认密码','再次输入密码','password']].map(([label,ph,type])=>(
            <div key={label as string} style={{ marginBottom:14 }}>
              <label style={{ fontSize:12, color:'#888', fontWeight:600, display:'block', marginBottom:7, letterSpacing:'0.5px', textTransform:'uppercase' as const }}>{label}</label>
              <input type={type as string} placeholder={ph as string} style={{ width:'100%', padding:'12px 16px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:12, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' as const, fontFamily:'inherit' }}/>
            </div>
          ))}

          <div style={{ display:'flex', alignItems:'flex-start', gap:10, margin:'16px 0 24px' }}>
            <div style={{ width:16, height:16, border:'1px solid #FFE500', borderRadius:4, marginTop:2, background:'rgba(255,229,0,0.1)', flexShrink:0, display:'flex', alignItems:'center', justifyContent:'center', fontSize:10, color:'#FFE500' }}>✓</div>
            <span style={{ fontSize:12, color:'#555', lineHeight:1.6 }}>我已阅读并同意 <span style={{ color:'#FFE500', cursor:'pointer' }}>服务条款</span> 和 <span style={{ color:'#FFE500', cursor:'pointer' }}>隐私政策</span></span>
          </div>

          <button style={{ width:'100%', padding:'14px', background:'#FFE500', border:'none', borderRadius:12, color:'#000', fontSize:15, fontWeight:800, cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif" }}>
            立即注册
          </button>
          <p style={{ textAlign:'center' as const, marginTop:24, fontSize:13, color:'#555' }}>
            已有账号？ <span style={{ color:'#FFE500', fontWeight:700, cursor:'pointer' }}>登录 →</span>
          </p>
        </div>
      </div>
    </div>
  );
}
