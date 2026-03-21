export default function Register() {
  const features = [
    { icon: '🤖', check: true, title: 'AI编辑团队，全程陪伴', desc: '智能AI助手贯穿整个创作流程，随时提供灵感与建议' },
    { icon: '⚡', check: true, title: '章节自动生成', desc: '一键生成高质量章节内容，风格统一，逻辑连贯' },
    { icon: '🌍', check: true, title: '角色/世界观管理', desc: '结构化管理你的人物关系与世界设定，不再混乱' },
  ]
  return (
    <div style={{ display: 'flex', height: '100vh', background: '#0A0A0A', fontFamily: "'Inter', sans-serif", overflow: 'hidden' }}>
      {/* Left Features Panel 60% */}
      <div style={{ flex: '0 0 60%', position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '64px 72px', overflow: 'hidden' }}>
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid2" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#FFE500" strokeWidth="0.4" opacity="0.1"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid2)" />
        </svg>
        <div style={{ position: 'absolute', top: -80, right: -80, width: 350, height: 350, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,229,0,0.07) 0%, transparent 70%)' }}/>
        <div style={{ position: 'absolute', bottom: -60, left: -60, width: 280, height: 280, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,229,0,0.05) 0%, transparent 70%)' }}/>

        <div style={{ position: 'relative', zIndex: 1 }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 64 }}>
            <div style={{ width: 44, height: 44, background: '#FFE500', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 900, color: '#000', fontFamily: "'Space Grotesk', sans-serif" }}>✦</div>
            <div>
              <div style={{ color: '#fff', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 18, lineHeight: 1 }}>Arboris Novel</div>
              <div style={{ color: '#FFE500', fontSize: 11, fontWeight: 600, letterSpacing: 1 }}>AI创作助手</div>
            </div>
          </div>

          <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 900, fontSize: 52, lineHeight: 1.1, color: '#fff', margin: '0 0 16px', letterSpacing: -1 }}>
            开始你的<br/><span style={{ color: '#FFE500' }}>创作之旅</span>
          </h1>
          <p style={{ color: '#777', fontSize: 16, lineHeight: 1.7, margin: '0 0 48px', maxWidth: 400 }}>
            加入数千名创作者，用AI的力量让每个故事成真。注册即可免费开始。
          </p>

          {/* Feature cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {features.map((f, i) => (
              <div key={i} style={{ display: 'flex', gap: 16, alignItems: 'flex-start', padding: '20px 22px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16 }}>
                <div style={{ width: 42, height: 42, borderRadius: 12, background: '#1C1C1C', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>{f.icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ color: '#fff', fontWeight: 700, fontSize: 15, fontFamily: "'Space Grotesk', sans-serif" }}>{f.title}</span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, borderRadius: '50%', background: '#FFE500', color: '#000', fontSize: 10, fontWeight: 800 }}>✓</span>
                  </div>
                  <p style={{ color: '#666', fontSize: 13, lineHeight: 1.6, margin: 0 }}>{f.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Stats */}
          <div style={{ display: 'flex', gap: 32, marginTop: 36 }}>
            {[['5,000+','注册用户'],['120万+','AI生成字数'],['98%','用户满意度']].map(([num,label],i)=>(
              <div key={i}>
                <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 22, color: '#FFE500' }}>{num}</div>
                <div style={{ color: '#555', fontSize: 12, marginTop: 2 }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Register Panel 40% */}
      <div style={{ flex: '0 0 40%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '48px', background: '#0D0D0D', borderLeft: '1px solid #141414' }}>
        <div style={{ width: '100%', maxWidth: 360 }}>
          <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 26, color: '#fff', margin: '0 0 6px' }}>创建账号</h2>
          <p style={{ color: '#666', fontSize: 14, margin: '0 0 32px' }}>免费注册，立即开始创作</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 24 }}>
            {[
              { label: '用户名', placeholder: '设置你的用户名', type: 'text', active: false },
              { label: '密码', placeholder: '设置密码（至少8位）', type: 'password', active: true },
              { label: '确认密码', placeholder: '再次输入密码', type: 'password', active: false },
            ].map((field, i) => (
              <div key={i}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 7, letterSpacing: 0.5, textTransform: 'uppercase' }}>{field.label}</label>
                <input
                  readOnly
                  type={field.type}
                  placeholder={field.placeholder}
                  defaultValue={field.type === 'password' ? 'password' : ''}
                  style={{
                    width: '100%', padding: '12px 14px',
                    background: '#141414',
                    border: field.active ? '1px solid #FFE500' : '1px solid #2A2A2A',
                    borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none',
                    boxSizing: 'border-box',
                    boxShadow: field.active ? '0 0 0 3px rgba(255,229,0,0.1)' : 'none',
                  }}
                />
              </div>
            ))}
          </div>

          {/* Password strength */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ color: '#666', fontSize: 12 }}>密码强度</span>
              <span style={{ color: '#2ED573', fontSize: 12, fontWeight: 600 }}>强</span>
            </div>
            <div style={{ height: 4, background: '#1C1C1C', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ width: '75%', height: '100%', background: '#2ED573', borderRadius: 999 }}/>
            </div>
          </div>

          <button style={{ width: '100%', padding: '13px', background: '#FFE500', color: '#000', fontWeight: 800, fontSize: 15, borderRadius: 12, border: 'none', cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif", marginBottom: 16, letterSpacing: 0.3 }}>
            立即注册
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '0 0 16px' }}>
            <div style={{ flex: 1, height: 1, background: '#1C1C1C' }}/>
            <span style={{ color: '#444', fontSize: 12 }}>或通过第三方注册</span>
            <div style={{ flex: 1, height: 1, background: '#1C1C1C' }}/>
          </div>

          <button style={{ width: '100%', padding: '12px 16px', background: 'transparent', border: '1px solid #2A2A2A', borderRadius: 12, color: '#ccc', fontSize: 14, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
            <span style={{ fontSize: 18 }}>🐧</span>
            通过 LinuxDO 注册
          </button>

          <p style={{ textAlign: 'center', marginTop: 28, color: '#666', fontSize: 14 }}>
            已有账号？{' '}
            <a href="#" style={{ color: '#FFE500', fontWeight: 700, textDecoration: 'none' }}>立即登录 →</a>
          </p>
        </div>
      </div>
    </div>
  )
}
