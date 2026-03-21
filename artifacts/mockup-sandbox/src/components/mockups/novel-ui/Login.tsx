export default function Login() {
  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ background: '#0A0A0A', fontFamily: 'Inter, sans-serif' }}>
      {/* Left hero panel */}
      <div className="relative hidden lg:flex lg:w-3/5 flex-col justify-between p-14 overflow-hidden" style={{ background: '#0F0F0F' }}>
        {/* Grid background */}
        <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.07 }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#FFE500" strokeWidth="0.8"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)"/>
        </svg>
        {/* Diagonal accent */}
        <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.15 }} xmlns="http://www.w3.org/2000/svg">
          <line x1="0" y1="100%" x2="100%" y2="0" stroke="#FFE500" strokeWidth="1.5"/>
          <line x1="-5%" y1="85%" x2="85%" y2="-5%" stroke="#FFE500" strokeWidth="0.6"/>
        </svg>
        {/* Yellow glow */}
        <div className="absolute" style={{ top: '30%', left: '40%', width: 400, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, #FFE500 0%, transparent 70%)', opacity: 0.08, transform: 'translate(-50%, -50%)' }}/>
        {/* Floating dots */}
        {[
          { top: '12%', left: '8%', s: 9 }, { top: '22%', left: '78%', s: 5 },
          { top: '55%', left: '12%', s: 6 }, { top: '68%', left: '82%', s: 4 },
          { top: '82%', left: '48%', s: 7 }, { top: '38%', left: '65%', s: 5 },
          { top: '75%', left: '30%', s: 4 }, { top: '48%', left: '88%', s: 6 },
        ].map((d, i) => (
          <div key={i} className="absolute rounded-full" style={{ top: d.top, left: d.left, width: d.s, height: d.s, background: '#FFE500', opacity: 0.55 }}/>
        ))}

        {/* Brand */}
        <div className="relative z-10 flex items-center gap-3">
          <span style={{ color: '#FFE500', fontSize: 26, fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700 }}>✦</span>
          <span style={{ color: '#fff', fontSize: 20, fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700 }}>Arboris Novel</span>
        </div>

        {/* Hero */}
        <div className="relative z-10 flex-1 flex flex-col justify-center">
          <h1 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 900, fontSize: 68, lineHeight: 1.05, color: '#fff', marginBottom: 24 }}>
            用AI，<br/>
            <span style={{ color: '#FFE500' }}>释放你的</span><br/>
            故事
          </h1>
          <p style={{ color: '#888', fontSize: 17, maxWidth: 360, lineHeight: 1.7 }}>
            从灵感到完稿，Arboris Novel 陪你走过每一章节的创作旅程。
          </p>
          <div className="flex flex-wrap gap-3 mt-8">
            {['AI章节生成', '智能角色管理', '世界观构建', '伏笔追踪'].map(f => (
              <span key={f} style={{ background: '#1C1C1C', border: '1px solid #2A2A2A', color: '#888', fontSize: 13, fontWeight: 500, padding: '6px 14px', borderRadius: 999 }}>{f}</span>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="relative z-10 flex gap-10">
          {[['10,000+', '创作者'], ['500万+', '字数生成'], ['98%', '用户满意']].map(([n, l]) => (
            <div key={l}>
              <div style={{ color: '#FFE500', fontSize: 24, fontWeight: 700, fontFamily: 'Space Grotesk, sans-serif' }}>{n}</div>
              <div style={{ color: '#888', fontSize: 13 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right login panel */}
      <div className="flex flex-col justify-center w-full lg:w-2/5 px-10 lg:px-16">
        <div style={{ maxWidth: 360, width: '100%', margin: '0 auto' }}>
          {/* Mobile brand */}
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <span style={{ color: '#FFE500', fontSize: 22, fontWeight: 700 }}>✦</span>
            <span style={{ color: '#fff', fontSize: 18, fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700 }}>Arboris Novel</span>
          </div>

          <h2 style={{ color: '#fff', fontSize: 30, fontWeight: 700, fontFamily: 'Space Grotesk, sans-serif', marginBottom: 6 }}>欢迎回来</h2>
          <p style={{ color: '#888', marginBottom: 32 }}>登录以继续你的创作之旅</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ display: 'block', color: '#fff', fontSize: 14, fontWeight: 500, marginBottom: 8 }}>用户名</label>
              <input
                type="text" placeholder="请输入用户名"
                style={{ width: '100%', padding: '12px 16px', background: '#141414', border: '1px solid #2A2A2A', borderRadius: 12, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <div className="flex items-center justify-between" style={{ marginBottom: 8 }}>
                <label style={{ color: '#fff', fontSize: 14, fontWeight: 500 }}>密码</label>
                <span style={{ color: '#FFE500', fontSize: 13, cursor: 'pointer' }}>忘记密码？</span>
              </div>
              <input
                type="password" placeholder="请输入密码"
                style={{ width: '100%', padding: '12px 16px', background: '#141414', border: '1px solid #2A2A2A', borderRadius: 12, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}
              />
            </div>
            <button style={{ width: '100%', padding: '13px', background: '#FFE500', borderRadius: 12, fontWeight: 700, fontSize: 15, color: '#000', border: 'none', cursor: 'pointer', marginTop: 4 }}>
              登录
            </button>

            <div className="flex items-center gap-4">
              <div style={{ flex: 1, height: 1, background: '#2A2A2A' }}/>
              <span style={{ color: '#888', fontSize: 13 }}>或</span>
              <div style={{ flex: 1, height: 1, background: '#2A2A2A' }}/>
            </div>

            <button style={{ width: '100%', padding: '12px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 12, color: '#fff', fontSize: 14, fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>🐧</span>
              使用 LinuxDO 账号登录
            </button>
          </div>

          <p style={{ textAlign: 'center', marginTop: 32, color: '#888', fontSize: 14 }}>
            还没有账号？{' '}
            <span style={{ color: '#FFE500', fontWeight: 600, cursor: 'pointer' }}>立即注册</span>
          </p>
        </div>
      </div>
    </div>
  )
}
