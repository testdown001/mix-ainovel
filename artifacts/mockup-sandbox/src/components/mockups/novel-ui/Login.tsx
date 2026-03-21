export default function Login() {
  return (
    <div style={{ display: 'flex', height: '100vh', background: '#0A0A0A', fontFamily: "'Inter', sans-serif", overflow: 'hidden' }}>
      {/* Left Hero Panel 60% */}
      <div style={{ flex: '0 0 60%', position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '64px 72px', overflow: 'hidden' }}>
        {/* Grid background */}
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#FFE500" strokeWidth="0.4" opacity="0.12"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
          {/* Diagonal accent lines */}
          <line x1="-100" y1="800" x2="600" y2="-100" stroke="#FFE500" strokeWidth="0.6" opacity="0.1"/>
          <line x1="100" y1="800" x2="800" y2="-100" stroke="#FFE500" strokeWidth="0.6" opacity="0.1"/>
          <line x1="300" y1="800" x2="1000" y2="-100" stroke="#FFE500" strokeWidth="0.6" opacity="0.07"/>
        </svg>
        {/* Glow blobs */}
        <div style={{ position: 'absolute', bottom: -100, left: -100, width: 400, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,229,0,0.06) 0%, transparent 70%)' }}/>
        <div style={{ position: 'absolute', top: 50, right: 50, width: 250, height: 250, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,229,0,0.04) 0%, transparent 70%)' }}/>
        {/* Floating dots */}
        {[[80,90],[200,180],[120,400],[350,320],[450,100],[500,450]].map(([x,y],i)=>(
          <div key={i} style={{ position: 'absolute', left: x, top: y, width: i%2===0?5:3, height: i%2===0?5:3, borderRadius: '50%', background: '#FFE500', opacity: [0.8,0.5,0.6,0.4,0.7,0.5][i] }}/>
        ))}

        <div style={{ position: 'relative', zIndex: 1 }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 72 }}>
            <div style={{ width: 44, height: 44, background: '#FFE500', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 900, color: '#000', fontFamily: "'Space Grotesk', sans-serif" }}>✦</div>
            <div>
              <div style={{ color: '#fff', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 18, lineHeight: 1 }}>Arboris Novel</div>
              <div style={{ color: '#FFE500', fontSize: 11, fontWeight: 600, letterSpacing: 1 }}>AI创作助手</div>
            </div>
          </div>

          {/* Hero text */}
          <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 900, fontSize: 62, lineHeight: 1.08, color: '#fff', margin: '0 0 20px', letterSpacing: -1 }}>
            用 <span style={{ color: '#FFE500' }}>AI</span>，<br/>释放你的<br/>故事
          </h1>
          <p style={{ color: '#777', fontSize: 17, lineHeight: 1.75, maxWidth: 420, margin: '0 0 52px' }}>
            从一个想法出发，让AI陪你完成一部属于自己的小说。灵感、蓝图、章节，全程守护。
          </p>

          {/* Feature list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {[
              ['✦', 'AI编辑团队，全程陪伴创作'],
              ['⚡', '章节自动生成，一键续写'],
              ['◎', '角色·世界观·大纲，全面管理'],
            ].map(([icon, text], i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <span style={{ color: '#FFE500', fontSize: 14, width: 20, textAlign: 'center', flexShrink: 0 }}>{icon}</span>
                <span style={{ color: '#aaa', fontSize: 15 }}>{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Login Panel 40% */}
      <div style={{ flex: '0 0 40%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '48px', background: '#0D0D0D', borderLeft: '1px solid #141414' }}>
        <div style={{ width: '100%', maxWidth: 360 }}>
          <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 26, color: '#fff', margin: '0 0 6px' }}>欢迎回来</h2>
          <p style={{ color: '#666', fontSize: 14, margin: '0 0 32px' }}>登录继续你的创作旅程</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 8 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 7, letterSpacing: 0.5, textTransform: 'uppercase' }}>用户名</label>
              <input readOnly placeholder="输入用户名" style={{ width: '100%', padding: '12px 14px', background: '#141414', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box', transition: 'border-color 0.2s' }}/>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 7, letterSpacing: 0.5, textTransform: 'uppercase' }}>密码</label>
              <input readOnly type="password" defaultValue="password" style={{ width: '100%', padding: '12px 14px', background: '#141414', border: '1px solid #FFE500', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box', boxShadow: '0 0 0 3px rgba(255,229,0,0.1)' }}/>
            </div>
            <div style={{ textAlign: 'right', marginTop: -6 }}>
              <a href="#" style={{ color: '#FFE500', fontSize: 13, textDecoration: 'none', fontWeight: 500 }}>忘记密码？</a>
            </div>
          </div>

          <button style={{ width: '100%', padding: '13px', background: '#FFE500', color: '#000', fontWeight: 800, fontSize: 15, borderRadius: 12, border: 'none', cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif", marginBottom: 20, letterSpacing: 0.3 }}>
            登 录
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '0 0 16px' }}>
            <div style={{ flex: 1, height: 1, background: '#1C1C1C' }}/>
            <span style={{ color: '#444', fontSize: 12 }}>或通过第三方登录</span>
            <div style={{ flex: 1, height: 1, background: '#1C1C1C' }}/>
          </div>

          <button style={{ width: '100%', padding: '12px 16px', background: 'transparent', border: '1px solid #2A2A2A', borderRadius: 12, color: '#ccc', fontSize: 14, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
            <span style={{ fontSize: 18 }}>🐧</span>
            通过 LinuxDO 登录
          </button>

          <p style={{ textAlign: 'center', marginTop: 28, color: '#666', fontSize: 14 }}>
            还没有账号？{' '}
            <a href="#" style={{ color: '#FFE500', fontWeight: 700, textDecoration: 'none' }}>立即注册 →</a>
          </p>
        </div>
      </div>
    </div>
  )
}
