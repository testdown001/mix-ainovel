const FEATURES = [
  { icon:'🤖', title:'AI编辑团队，全程陪伴', desc:'从灵感到成书，AI在每个节点为你提供专业建议与内容生成' },
  { icon:'📖', title:'章节自动生成', desc:'输入大纲与风格，AI即刻生成高质量、符合剧情逻辑的章节内容' },
  { icon:'🌍', title:'角色 / 世界观管理', desc:'系统化管理人物、地点、势力等设定，保持故事高度一致性' },
];
const DOTS = [[60,70],[200,140],[100,360],[380,280],[500,100],[540,460],[110,490],[310,400],[460,220]];

export default function Register() {
  return (
    <div style={{ display:'flex', height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>

      {/* ── LEFT PANEL ── */}
      <div style={{ flex:'0 0 60%', position:'relative', display:'flex', flexDirection:'column', justifyContent:'center', padding:'64px 80px', overflow:'hidden' }}>
        <svg style={{ position:'absolute', inset:0, width:'100%', height:'100%' }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="rg" width="56" height="56" patternUnits="userSpaceOnUse">
              <path d="M56 0L0 0 0 56" fill="none" stroke="#FFE500" strokeWidth="0.3" opacity="0.07"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#rg)"/>
          <line x1="-50" y1="800" x2="700" y2="-50" stroke="#FFE500" strokeWidth="1" opacity="0.06"/>
          <line x1="300" y1="800" x2="1050" y2="-50" stroke="#FFE500" strokeWidth="0.6" opacity="0.04"/>
          <polygon points="500,200 570,270 500,340 430,270" fill="none" stroke="#FFE500" strokeWidth="0.7" opacity="0.15"/>
        </svg>
        <div style={{ position:'absolute', top:-60, right:-30, width:450, height:450, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.06) 0%,transparent 70%)', pointerEvents:'none' }}/>
        <div style={{ position:'absolute', bottom:-80, left:-50, width:380, height:380, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.04) 0%,transparent 70%)', pointerEvents:'none' }}/>
        {DOTS.map(([x,y],i)=>(
          <div key={i} style={{ position:'absolute', left:x, top:y, width:i%3===0?6:4, height:i%3===0?6:4, borderRadius:'50%', background:'#FFE500', opacity:[0.7,0.4,0.55,0.35,0.65,0.4,0.25,0.5,0.45][i] }}/>
        ))}

        <div style={{ position:'relative', zIndex:1 }}>
          <div style={{ display:'flex', alignItems:'center', gap:14, marginBottom:72 }}>
            <div style={{ width:44, height:44, background:'#FFE500', borderRadius:12, display:'flex', alignItems:'center', justifyContent:'center', fontSize:22, fontWeight:900, color:'#000', fontFamily:"'Space Grotesk',sans-serif" }}>✦</div>
            <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:17, color:'#fff', letterSpacing:'-0.3px' }}>Arboris Novel</span>
          </div>

          <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:42, fontWeight:800, color:'#fff', letterSpacing:'-1.5px', lineHeight:1.12, marginBottom:12 }}>
            开始你的<br/><span style={{ color:'#FFE500' }}>AI创作之旅</span>
          </div>
          <p style={{ fontSize:15, color:'#555', lineHeight:1.7, marginBottom:52, maxWidth:420 }}>
            加入数千位创作者，用AI的力量写出你的精彩故事。
          </p>

          <div style={{ display:'flex', flexDirection:'column', gap:28 }}>
            {FEATURES.map((f,i)=>(
              <div key={i} style={{ display:'flex', gap:20, alignItems:'flex-start' }}>
                <div style={{ width:44, height:44, background:'rgba(255,229,0,0.08)', border:'1px solid rgba(255,229,0,0.2)', borderRadius:12, display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, flexShrink:0 }}>{f.icon}</div>
                <div>
                  <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                    <span style={{ fontSize:15, fontWeight:600, color:'#fff' }}>{f.title}</span>
                    <div style={{ width:18, height:18, background:'#FFE500', borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2 2 4-4" stroke="#000" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    </div>
                  </div>
                  <p style={{ fontSize:13, color:'#555', margin:0, lineHeight:1.6 }}>{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── RIGHT FORM ── */}
      <div style={{ flex:'0 0 40%', display:'flex', alignItems:'center', justifyContent:'center', padding:'48px 56px', background:'#0D0D0D', borderLeft:'1px solid #1C1C1C' }}>
        <div style={{ width:'100%', maxWidth:380 }}>
          <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:28, fontWeight:700, color:'#fff', margin:'0 0 6px', letterSpacing:'-0.5px' }}>创建账号</h2>
          <p style={{ fontSize:14, color:'#555', margin:'0 0 32px' }}>免费开始，随时升级</p>

          <div style={{ marginBottom:16 }}>
            <label style={{ display:'block', fontSize:13, fontWeight:500, color:'#888', marginBottom:8 }}>用户名</label>
            <input readOnly placeholder="请输入用户名" style={{ width:'100%', padding:'12px 16px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' }}/>
          </div>

          <div style={{ marginBottom:16 }}>
            <label style={{ display:'block', fontSize:13, fontWeight:500, color:'#888', marginBottom:8 }}>密码</label>
            <input readOnly type="password" placeholder="至少8位字符" style={{ width:'100%', padding:'12px 16px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' }}/>
          </div>

          <div style={{ marginBottom:28 }}>
            <label style={{ display:'block', fontSize:13, fontWeight:500, color:'#888', marginBottom:8 }}>确认密码</label>
            <input readOnly type="password" placeholder="再次输入密码" style={{ width:'100%', padding:'12px 16px', background:'#141414', border:'1px solid #FFE500', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box', boxShadow:'0 0 0 3px rgba(255,229,0,0.08)' }}/>
          </div>

          <button style={{ width:'100%', padding:'14px', background:'#FFE500', border:'none', borderRadius:10, fontSize:15, fontWeight:700, color:'#000', fontFamily:"'Space Grotesk',sans-serif", cursor:'pointer', letterSpacing:'-0.2px', marginBottom:16 }}>创建账号</button>

          <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:16 }}>
            <div style={{ flex:1, height:1, background:'#222' }}/>
            <span style={{ fontSize:12, color:'#444' }}>或</span>
            <div style={{ flex:1, height:1, background:'#222' }}/>
          </div>

          <button style={{ width:'100%', padding:'13px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:10, fontSize:14, fontWeight:600, color:'#ccc', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:10, marginBottom:24 }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="#FFE500" strokeWidth="1.5"/>
              <path d="M8 12h8M12 8v8" stroke="#FFE500" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            使用 LinuxDO 账号注册
          </button>

          <p style={{ textAlign:'center', fontSize:12, color:'#444', margin:'0 0 14px', lineHeight:1.6 }}>
            注册即表示您同意<a href="#" style={{ color:'#FFE500', textDecoration:'none' }}>服务条款</a>和<a href="#" style={{ color:'#FFE500', textDecoration:'none' }}>隐私政策</a>
          </p>
          <p style={{ textAlign:'center', fontSize:13, color:'#555', margin:0 }}>
            已有账户？ <a href="#" style={{ color:'#FFE500', textDecoration:'none', fontWeight:600 }}>立即登录</a>
          </p>
        </div>
      </div>
    </div>
  );
}
