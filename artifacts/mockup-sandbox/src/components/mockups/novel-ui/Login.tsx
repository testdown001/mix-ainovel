const S = {
  root: { display:'flex', height:'100vh', background:'#0A0A0A', fontFamily:"'Inter',sans-serif", overflow:'hidden' } as React.CSSProperties,
  left: { flex:'0 0 60%', position:'relative', display:'flex', flexDirection:'column' as const, justifyContent:'center', padding:'64px 72px', overflow:'hidden', background:'#0A0A0A' },
  right: { flex:'0 0 40%', display:'flex', alignItems:'center', justifyContent:'center', padding:'48px 52px', background:'#0D0D0D', borderLeft:'1px solid #1E1E1E' },
};

const dots = [[72,88],[210,160],[140,380],[360,300],[460,110],[510,460],[80,520],[300,440]];

export default function Login() {
  return (
    <div style={S.root}>
      {/* ── LEFT HERO ── */}
      <div style={S.left}>
        {/* Grid */}
        <svg style={{ position:'absolute', inset:0, width:'100%', height:'100%' }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="g" width="56" height="56" patternUnits="userSpaceOnUse">
              <path d="M56 0L0 0 0 56" fill="none" stroke="#FFE500" strokeWidth="0.35" opacity="0.09"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#g)"/>
          <line x1="-50" y1="750" x2="650" y2="-50" stroke="#FFE500" strokeWidth="0.8" opacity="0.08"/>
          <line x1="150" y1="750" x2="850" y2="-50" stroke="#FFE500" strokeWidth="0.8" opacity="0.06"/>
          <line x1="350" y1="750" x2="1050" y2="-50" stroke="#FFE500" strokeWidth="0.5" opacity="0.04"/>
          {/* Decorative diamond */}
          <polygon points="430,320 480,370 430,420 380,370" fill="none" stroke="#FFE500" strokeWidth="0.7" opacity="0.18"/>
          <polygon points="430,290 510,370 430,450 350,370" fill="none" stroke="#FFE500" strokeWidth="0.4" opacity="0.09"/>
        </svg>
        {/* Glow */}
        <div style={{ position:'absolute', bottom:-120, left:-80, width:500, height:500, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.07) 0%,transparent 70%)' }}/>
        <div style={{ position:'absolute', top:20, right:40, width:300, height:300, borderRadius:'50%', background:'radial-gradient(circle,rgba(255,229,0,0.04) 0%,transparent 70%)' }}/>
        {/* Dots */}
        {dots.map(([x,y],i)=>(
          <div key={i} style={{ position:'absolute', left:x, top:y, width:i%3===0?6:i%3===1?4:3, height:i%3===0?6:i%3===1?4:3, borderRadius:'50%', background:'#FFE500', opacity:[0.85,0.5,0.65,0.4,0.75,0.45,0.3,0.6][i] }}/>
        ))}

        <div style={{ position:'relative', zIndex:1 }}>
          {/* Logo */}
          <div style={{ display:'flex', alignItems:'center', gap:14, marginBottom:80 }}>
            <div style={{ width:48, height:48, background:'#FFE500', borderRadius:14, display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, fontWeight:900, color:'#000', fontFamily:"'Space Grotesk',sans-serif", flexShrink:0 }}>✦</div>
            <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:18, color:'#fff', letterSpacing:'-0.3px' }}>Arboris Novel</span>
          </div>

          {/* Headline */}
          <div style={{ marginBottom:40 }}>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:52, fontWeight:800, lineHeight:1.1, color:'#fff', letterSpacing:'-2px', marginBottom:4 }}>用AI，</div>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:52, fontWeight:800, lineHeight:1.1, letterSpacing:'-2px' }}>
              <span style={{ color:'#FFE500' }}>释放你的故事</span>
            </div>
          </div>
          <p style={{ fontSize:16, color:'#666', lineHeight:1.7, maxWidth:420, margin:0 }}>
            每一段对话，都是一个新的开始。让AI成为你的写作拍档，从灵感到成书，全程陪伴。
          </p>

          {/* Feature pills */}
          <div style={{ display:'flex', gap:12, marginTop:48, flexWrap:'wrap' as const }}>
            {['⚡ AI全程创作', '📖 章节自动生成', '🌍 世界观管理'].map(f=>(
              <div key={f} style={{ padding:'8px 16px', background:'rgba(255,229,0,0.06)', border:'1px solid rgba(255,229,0,0.15)', borderRadius:999, fontSize:13, color:'#FFE500', fontWeight:600 }}>{f}</div>
            ))}
          </div>

          {/* Social proof */}
          <div style={{ marginTop:56, display:'flex', alignItems:'center', gap:12 }}>
            <div style={{ display:'flex' }}>
              {['#F4A',  '#A4F', '#4AF', '#FA4'].map((c,i)=>(
                <div key={i} style={{ width:28, height:28, borderRadius:'50%', background:`linear-gradient(135deg,${c}88,${c}44)`, border:'2px solid #0A0A0A', marginLeft:i?-8:0, zIndex:4-i }}/>
              ))}
            </div>
            <span style={{ fontSize:13, color:'#666' }}>已有 <span style={{ color:'#FFE500', fontWeight:700 }}>2,400+</span> 位作者在使用</span>
          </div>
        </div>
      </div>

      {/* ── RIGHT FORM ── */}
      <div style={S.right}>
        <div style={{ width:'100%', maxWidth:380 }}>
          <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:26, fontWeight:800, color:'#fff', marginBottom:8, letterSpacing:'-0.5px' }}>欢迎回来</h2>
          <p style={{ fontSize:14, color:'#666', marginBottom:36 }}>登录以继续你的创作之旅</p>

          {/* LinuxDO OAuth */}
          <button style={{ width:'100%', padding:'13px 20px', background:'transparent', border:'1px solid #2A2A2A', borderRadius:12, color:'#fff', fontSize:14, fontWeight:600, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:10, marginBottom:28 }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FFE500" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M8 12h8M12 8v8"/></svg>
            使用 LinuxDO 登录
          </button>

          <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:28 }}>
            <div style={{ flex:1, height:1, background:'#1E1E1E' }}/>
            <span style={{ fontSize:12, color:'#444' }}>或使用账号密码</span>
            <div style={{ flex:1, height:1, background:'#1E1E1E' }}/>
          </div>

          {/* Username */}
          <div style={{ marginBottom:16 }}>
            <label style={{ fontSize:12, color:'#888', fontWeight:600, display:'block', marginBottom:8, letterSpacing:'0.5px', textTransform:'uppercase' as const }}>用户名</label>
            <div style={{ position:'relative' }}>
              <input placeholder="请输入用户名" style={{ width:'100%', padding:'13px 16px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:12, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' as const, fontFamily:'inherit' }}/>
            </div>
          </div>

          {/* Password */}
          <div style={{ marginBottom:28 }}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
              <label style={{ fontSize:12, color:'#888', fontWeight:600, letterSpacing:'0.5px', textTransform:'uppercase' as const }}>密码</label>
              <span style={{ fontSize:12, color:'#FFE500', cursor:'pointer' }}>忘记密码？</span>
            </div>
            <input type="password" placeholder="请输入密码" style={{ width:'100%', padding:'13px 16px', background:'#141414', border:'1px solid #2A2A2A', borderRadius:12, color:'#fff', fontSize:14, outline:'none', boxSizing:'border-box' as const, fontFamily:'inherit' }}/>
          </div>

          {/* CTA */}
          <button style={{ width:'100%', padding:'14px', background:'#FFE500', border:'none', borderRadius:12, color:'#000', fontSize:15, fontWeight:800, cursor:'pointer', fontFamily:"'Space Grotesk',sans-serif", letterSpacing:'-0.2px' }}>
            登录
          </button>

          <p style={{ textAlign:'center' as const, marginTop:24, fontSize:13, color:'#555' }}>
            还没有账号？{' '}
            <span style={{ color:'#FFE500', fontWeight:700, cursor:'pointer' }}>立即注册 →</span>
          </p>
        </div>
      </div>
    </div>
  );
}
