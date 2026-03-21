export default function Register() {
  const features = [
    { icon: '🤖', title: 'AI编辑团队，全程陪伴', desc: '智能AI助手贯穿整个创作流程，随时提供灵感与建议' },
    { icon: '⚡', title: '章节自动生成', desc: '一键生成高质量章节内容，保持风格一致性' },
    { icon: '🌍', title: '角色/世界观管理', desc: '结构化管理你的人物关系与世界设定，不再混乱' },
  ]

  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ background: '#0A0A0A', fontFamily: 'Inter, sans-serif' }}>
      {/* Left feature panel */}
      <div className="relative hidden lg:flex lg:w-3/5 flex-col justify-between p-14 overflow-hidden" style={{ background: '#0F0F0F' }}>
        {/* Grid */}
        <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.07 }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid2" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#FFE500" strokeWidth="0.8"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid2)"/>
        </svg>
        <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.12 }} xmlns="http://www.w3.org/2000/svg">
          <line x1="100%" y1="100%" x2="0" y2="0" stroke="#FFE500" strokeWidth="1.5"/>
          <line x1="110%" y1="80%" x2="20%" y2="-10%" stroke="#FFE500" strokeWidth="0.6"/>
        </svg>
        <div className="absolute" style={{ top: '35%', left: '55%', width: 360, height: 360, borderRadius: '50%', background: 'radial-gradient(circle, #FFE500 0%, transparent 70%)', opacity: 0.07, transform: 'translate(-50%, -50%)' }}/>

        {/* Brand */}
        <div className="relative z-10 flex items-center gap-3">
          <span style={{ color: '#FFE500', fontSize: 26, fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700 }}>✦</span>
          <span style={{ color: '#fff', fontSize: 20, fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700 }}>Arboris Novel</span>
        </div>

        {/* Heading */}
        <div className="relative z-10 flex-1 flex flex-col justify-center">
          <h1 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 900, fontSize: 52, lineHeight: 1.1, color: '#fff', marginBottom: 12 }}>
            开始你的<br/>
            <span style={{ color: '#FFE500' }}>创作之旅</span>
          </h1>
          <p style={{ color: '#888', fontSize: 16, marginBottom: 48, maxWidth: 380, lineHeight: 1.7 }}>
            加入 10,000+ 创作者，用 AI 的力量让故事鲜活起来。
          </p>

          {/* Feature list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
            {features.map((f, i) => (
              <div key={i} className="flex items-start gap-5">
                {/* Yellow check */}
                <div style={{ width: 44, height: 44, borderRadius: 12, background: '#FFE500', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <span style={{ fontSize: 20 }}>{f.icon}</span>
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span style={{ color: '#FFE500', fontSize: 14, fontWeight: 700 }}>✓</span>
                    <span style={{ color: '#fff', fontSize: 16, fontWeight: 600 }}>{f.title}</span>
                  </div>
                  <p style={{ color: '#888', fontSize: 14, lineHeight: 1.6 }}>{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Testimonial */}
        <div className="relative z-10 p-5 rounded-2xl" style={{ background: '#1C1C1C', border: '1px solid #2A2A2A' }}>
          <p style={{ color: '#ccc', fontSize: 14, lineHeight: 1.7, fontStyle: 'italic', marginBottom: 12 }}>
            "用了Arboris Novel之后，我终于完成了拖延了三年的玄幻小说。AI真的能理解我想写什么。"
          </p>
          <div className="flex items-center gap-3">
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#FFE500', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#000', fontSize: 14 }}>李</div>
            <div>
              <div style={{ color: '#fff', fontSize: 13, fontWeight: 600 }}>李晓明</div>
              <div style={{ color: '#888', fontSize: 12 }}>玄幻小说作者 · 已完成2部作品</div>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 2 }}>
              {[1,2,3,4,5].map(s => <span key={s} style={{ color: '#FFE500', fontSize: 14 }}>★</span>)}
            </div>
          </div>
        </div>
      </div>

      {/* Right register panel */}
      <div className="flex flex-col justify-center w-full lg:w-2/5 px-10 lg:px-16">
        <div style={{ maxWidth: 360, width: '100%', margin: '0 auto' }}>
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <span style={{ color: '#FFE500', fontSize: 22, fontWeight: 700 }}>✦</span>
            <span style={{ color: '#fff', fontSize: 18, fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700 }}>Arboris Novel</span>
          </div>

          <h2 style={{ color: '#fff', fontSize: 30, fontWeight: 700, fontFamily: 'Space Grotesk, sans-serif', marginBottom: 6 }}>创建账号</h2>
          <p style={{ color: '#888', marginBottom: 32 }}>免费开始，无需信用卡</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ display: 'block', color: '#fff', fontSize: 14, fontWeight: 500, marginBottom: 8 }}>用户名</label>
              <input type="text" placeholder="请设置用户名" style={{ width: '100%', padding: '12px 16px', background: '#141414', border: '1px solid #2A2A2A', borderRadius: 12, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}/>
            </div>
            <div>
              <label style={{ display: 'block', color: '#fff', fontSize: 14, fontWeight: 500, marginBottom: 8 }}>密码</label>
              <input type="password" placeholder="请设置密码（至少8位）" style={{ width: '100%', padding: '12px 16px', background: '#141414', border: '1px solid #2A2A2A', borderRadius: 12, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}/>
            </div>
            <div>
              <label style={{ display: 'block', color: '#fff', fontSize: 14, fontWeight: 500, marginBottom: 8 }}>确认密码</label>
              <input type="password" placeholder="再次输入密码" style={{ width: '100%', padding: '12px 16px', background: '#141414', border: '1px solid #2A2A2A', borderRadius: 12, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}/>
            </div>

            {/* Agreement */}
            <div className="flex items-start gap-3">
              <div style={{ width: 18, height: 18, border: '2px solid #FFE500', borderRadius: 4, flexShrink: 0, marginTop: 2, background: '#FFE500', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: '#000', fontSize: 11, fontWeight: 700 }}>✓</span>
              </div>
              <p style={{ color: '#888', fontSize: 13, lineHeight: 1.5 }}>
                我已阅读并同意 <span style={{ color: '#FFE500' }}>服务条款</span> 与 <span style={{ color: '#FFE500' }}>隐私政策</span>
              </p>
            </div>

            <button style={{ width: '100%', padding: '13px', background: '#FFE500', borderRadius: 12, fontWeight: 700, fontSize: 15, color: '#000', border: 'none', cursor: 'pointer', marginTop: 4 }}>
              注册账号
            </button>

            <div className="flex items-center gap-4">
              <div style={{ flex: 1, height: 1, background: '#2A2A2A' }}/>
              <span style={{ color: '#888', fontSize: 13 }}>或</span>
              <div style={{ flex: 1, height: 1, background: '#2A2A2A' }}/>
            </div>

            <button style={{ width: '100%', padding: '12px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 12, color: '#fff', fontSize: 14, fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>🐧</span>
              使用 LinuxDO 账号注册
            </button>
          </div>

          <p style={{ textAlign: 'center', marginTop: 28, color: '#888', fontSize: 14 }}>
            已有账号？{' '}
            <span style={{ color: '#FFE500', fontWeight: 600, cursor: 'pointer' }}>立即登录</span>
          </p>
        </div>
      </div>
    </div>
  )
}
