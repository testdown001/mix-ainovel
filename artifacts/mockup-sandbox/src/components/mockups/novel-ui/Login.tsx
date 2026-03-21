const dots = [[72,88],[210,160],[140,380],[360,300],[460,110],[510,460],[80,520],[300,440],[550,200],[420,530]];

export default function Login() {
  return (
    <div style={{ display:'flex', height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>

      {/* ── LEFT HERO ── */}
      <div style={{ flex:'0 0 60%', position:'relative', display:'flex', flexDirection:'column', justifyContent:'center', padding:'64px 80px', overflow:'hidden', background:'#0A0A0A' }}>
        {/* Grid + diagonals */}
        <svg style={{ position:'absolute', inset:0, width:'100%', height:'100%' }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="56" height="56" patternUnits="userSpaceOnUse">
              <path d="M56 0L0 0 0 56" fill="none" stroke="#FFE500" strokeWidth="0.3" opacity="0.08"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)"/>
          <line x1="-50" y1="800" x2="700" y2="-50" stroke="#FFE500" strokeWidth="1" opacity="0.07"/>
          <line x1="200" y1="800" x2="950" y2="-50" stroke="#FFE500" strokeWidth="1" opacity="0.05"/>
          <line x1="450" y1="800" x2="1200" y2="-50" stroke="#FFE500" strokeWidth="0.6" opacity="0.035"/>
          {/* Diamonds */}
          <polygon points="460,340 520,400 460,460 400,400" fill="none" stroke="#FFE500" strokeWidth="0.8" opacity="0.22"/>
          <polygon points="460,300 560,400 460,500 360,400" fill="none" stroke="#FFE500" strokeWidth="0.4" opacity="0.1"/>
          <polygon points="460,260 600,400 460,540 320,400" fill="none" stroke="#FFE500" strokeWidth="0.25" opacity="0.05"/>
          {/* Corner accent */}
          <circle cx="760" cy="80" r="120" fill="none" stroke="#FFE500" strokeWidth="0.4" opacity="0.06"/>
          <circle cx="760" cy="80" r="80" fill="none" stroke="#FFE500" strokeWidth="0.4" opacity="0.08"/>
        </svg>

        {/* Glows */}
        <div style={{ position:'absolute', bottom:-150, left:-100, width:600, height:600, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.08) 0%,transparent 70%)', pointerEvents:'none' }}/>
        <div style={{ position:'absolute', top:-40, right:20, width:400, height:400, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.05) 0%,transparent 70%)', pointerEvents:'none' }}/>

        {/* Dots */}
        {dots.map(([x,y],i)=>(
          <div key={i} style={{ position:'absolute', left:x, top:y, width:i%3===0?7:i%3===1?4:3, height:i%3===0?7:i%3===1?4:3, borderRadius:'50%', background:'#FFE500', opacity:[0.85,0.5,0.65,0.4,0.75,0.45,0.3,0.6,0.55,0.35][i] }}/>
        ))}

        <div style={{ position:'relative', zIndex:1 }}>
          {/* Logo */}
          <div style={{ display:'flex', alignItems:'center', gap:14, marginBottom:88 }}>
            <div style={{ width:44, height:44, background:'#FFE500', borderRadius:12, display:'flex', alignItems:'center', justifyContent:'center', fontSize:22, fontWeight:900, color:'#000', fontFamily:"'Space Grotesk',sans-serif", flexShrink:0 }}>✦</div>
            <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:17, color:'#fff', letterSpacing:'-0.3px' }}>Arboris Novel</span>
          </div>

          {/* Headline */}
          <div style={{ marginBottom:36 }}>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:56, fontWeight:800, lineHeight:1.08, color:'#fff', letterSpacing:'-2.5px', marginBottom:2 }}>用AI，</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:56, fontWeight:800, lineHeight:1.08, letterSpacing:'-2.5px', color:'#FFE500' }}>释放你的故事</div>
          </div>
          <p style={{ fontSize:16, color:'#666', lineHeight:1.75, maxWidth:440, margin:'0 0 52px' }}>
            每一段对话，都是一个新的开始。让AI成为你的写作拍档，从灵感到成书，全程陪伴。
          </p>

          {/* Feature pills */}
          <div style={{ display:'flex', gap:12, flexWrap:'wrap' }}>
            {['⚡ AI全程创作', '📖 章节自动生成', '🌍 世界观管理', '👥 角色管理'].map(f=>(
              <div key={f} style={{ padding:'8px 18px', background:'rgba(255,229,0,0.06)', border:'1px solid rgba(255,229,0,0.18)', borderRadius:999, fontSize:13, color:'#FFE500', fontWeight:600 }}>{f}</div>
            ))}
          </div>
        </div>
      </div>

      {/* ── RIGHT FORM ── */}
      <div style={{ flex:'0 0 40%', display:'flex', alignItems:'center', justifyContent:'center', padding:'48px 56px', background:'#0D0D0D', borderLeft:'1px solid #1C1C1C' }}>
        <div style={{ width:'100%', maxWidth:380 }}>
          <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:28, fontWeight:700, color:'#fff', margin:'0 0 6px', letterSpacing:'-0.5px' }}>欢迎回来</h2>
          <p style={{ fontSize:14, color:'#555', margin:'0 0 36px' }}>登录以继续您的创作之旅</p>

          {/* Username */}
          <div style={{ marginBottom:18 }}>
            <label style={{ display:'block', fontSize:13, fontWeight:500, color:'#888', marginBottom:8 }}>用户名</label>
            <input readOnly placeholder="请输入用户名" style={{ width:'100%', padding:'12px 16px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' }}/>
          </div>

          {/* Password */}
          <div style={{ marginBottom:28 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
              <label style={{ fontSize:13, fontWeight:500, color:'#888' }}>密码</label>
              <a href="#" style={{ fontSize:12, color:'#FFE500', textDecoration:'none', opacity:0.8 }}>忘记密码？</a>
            </div>
            <input readOnly type="password" placeholder="请输入密码" style={{ width:'100%', padding:'12px 16px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:10, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' }}/>
          </div>

          {/* Login button */}
          <button style={{ width:'100%', padding:'14px', background:'#FFE500', border:'none', borderRadius:10, fontSize:15, fontWeight:700, color:'#000', fontFamily:"'Space Grotesk',sans-serif", cursor:'pointer', letterSpacing:'-0.2px', marginBottom:16 }}>登录</button>

          {/* Divider */}
          <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:16 }}>
            <div style={{ flex:1, height:1, background:'#222' }}/>
            <span style={{ fontSize:12, color:'#444' }}>或</span>
            <div style={{ flex:1, height:1, background:'#222' }}/>
          </div>

          {/* LinuxDO OAuth */}
          <button style={{ width:'100%', padding:'13px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:10, fontSize:14, fontWeight:600, color:'#ccc', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:10, marginBottom:28, fontFamily:"'Inter',sans-serif" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="#FFE500" strokeWidth="1.5"/>
              <path d="M8 12h8M12 8v8" stroke="#FFE500" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            使用 LinuxDO 账号登录
          </button>

          {/* Register link */}
          <p style={{ textAlign:'center', fontSize:13, color:'#555', margin:0 }}>
            还没有账户？{' '}
            <a href="#" style={{ color:'#FFE500', textDecoration:'none', fontWeight:600 }}>立即注册</a>
          </p>
        </div>
      </div>
    </div>
  );
}
