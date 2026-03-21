import { useState } from 'react'

const NAV_ITEMS = ['灵感模式', '我的小说', '写作台', '设置']
const SIDEBAR_ITEMS = [
  { id: 'llm', icon: '🤖', label: 'LLM 配置' },
  { id: 'writing', icon: '✍️', label: '写作偏好' },
  { id: 'account', icon: '👤', label: '账号信息' },
  { id: 'membership', icon: '👑', label: '会员套餐' },
]

const PLANS = [
  { name: '免费版', price: '¥0', period: '/月', current: true, features: ['每月 10 次AI生成', '最多 3 部小说', '基础角色管理'] },
  { name: '专业版', price: '¥29', period: '/月', current: false, features: ['无限 AI 生成', '无限小说数量', '高级角色/世界观管理', '伏笔追踪', '优先客服'] },
  { name: '旗舰版', price: '¥69', period: '/月', current: false, features: ['所有专业版功能', '多模型支持', '批量章节生成', '情感曲线分析', '专属客服'] },
]

export default function Settings() {
  const [activeNav] = useState('设置')
  const [activeSection, setActiveSection] = useState('llm')
  const [temp, setTemp] = useState(0.7)
  const [apiKey, setApiKey] = useState('')

  return (
    <div style={{ minHeight: '100vh', background: '#0A0A0A', fontFamily: 'Inter, sans-serif', color: '#fff' }}>
      {/* Nav */}
      <nav style={{ background: '#0A0A0A', borderBottom: '1px solid #1C1C1C', padding: '0 32px', height: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#FFE500', fontSize: 22, fontWeight: 700 }}>✦</span>
          <span style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 18 }}>Arboris Novel</span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {NAV_ITEMS.map(item => (
            <button key={item} style={{ padding: '6px 16px', borderRadius: 8, fontSize: 14, fontWeight: 500, border: 'none', cursor: 'pointer', background: activeNav === item ? '#1C1C1C' : 'transparent', color: activeNav === item ? '#FFE500' : '#888' }}>
              {item}
            </button>
          ))}
        </div>
        <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#FFE500', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#000', fontSize: 15, cursor: 'pointer' }}>创</div>
      </nav>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '48px 32px', display: 'grid', gridTemplateColumns: '240px 1fr', gap: 32 }}>
        {/* Left sidebar */}
        <aside>
          {/* User card */}
          <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16, padding: 20, marginBottom: 16, textAlign: 'center' }}>
            <div style={{ width: 60, height: 60, borderRadius: '50%', background: '#FFE500', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#000', fontSize: 22, margin: '0 auto 12px' }}>创</div>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>创作者</div>
            <div style={{ color: '#888', fontSize: 12, marginBottom: 10 }}>creator@example.com</div>
            <span style={{ background: '#2A2A2A', color: '#888', fontSize: 11, padding: '3px 10px', borderRadius: 999 }}>免费版</span>
          </div>

          {/* Nav items */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {SIDEBAR_ITEMS.map(item => (
              <button key={item.id} onClick={() => setActiveSection(item.id)} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderRadius: 12, border: 'none', cursor: 'pointer', background: activeSection === item.id ? '#1C1C1C' : 'transparent', color: activeSection === item.id ? '#FFE500' : '#888', textAlign: 'left', fontWeight: activeSection === item.id ? 600 : 400, fontSize: 14 }}>
                <span style={{ fontSize: 16 }}>{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        </aside>

        {/* Right content */}
        <div>
          {activeSection === 'llm' && (
            <div>
              <h2 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 24, marginBottom: 8 }}>LLM 配置</h2>
              <p style={{ color: '#888', fontSize: 14, marginBottom: 32 }}>配置你的 AI 语言模型接入参数</p>

              <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 18, padding: 28 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  <div>
                    <label style={{ display: 'block', color: '#aaa', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>模型 API 地址</label>
                    <input type="url" defaultValue="https://api.openai.com/v1" style={{ width: '100%', padding: '12px 16px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}/>
                  </div>
                  <div>
                    <label style={{ display: 'block', color: '#aaa', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>API Key</label>
                    <div style={{ position: 'relative' }}>
                      <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="sk-••••••••••••••••••••" style={{ width: '100%', padding: '12px 16px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}/>
                    </div>
                    <p style={{ color: '#888', fontSize: 12, marginTop: 6 }}>API Key 经过加密存储，不会明文传输</p>
                  </div>
                  <div>
                    <label style={{ display: 'block', color: '#aaa', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>模型名称</label>
                    <select style={{ width: '100%', padding: '12px 16px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none' }}>
                      <option>gpt-4o</option>
                      <option>gpt-4-turbo</option>
                      <option>gpt-3.5-turbo</option>
                      <option>claude-3-5-sonnet</option>
                      <option>deepseek-chat</option>
                    </select>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                      <label style={{ color: '#aaa', fontSize: 13, fontWeight: 500 }}>Temperature（创意度）</label>
                      <span style={{ color: '#FFE500', fontWeight: 700, fontFamily: 'Space Grotesk, sans-serif' }}>{temp.toFixed(1)}</span>
                    </div>
                    <input type="range" min="0" max="1" step="0.1" value={temp} onChange={e => setTemp(Number(e.target.value))} style={{ width: '100%', accentColor: '#FFE500' }}/>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                      <span style={{ color: '#888', fontSize: 11 }}>保守 (0.0)</span>
                      <span style={{ color: '#888', fontSize: 11 }}>创意 (1.0)</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 14 }}>
                    <button style={{ flex: 1, padding: '12px', background: '#FFE500', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 14, color: '#000', cursor: 'pointer' }}>保存配置</button>
                    <button style={{ padding: '12px 20px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, cursor: 'pointer' }}>测试连接</button>
                  </div>
                </div>
              </div>

              {/* Membership upsell card */}
              <div style={{ marginTop: 24, background: 'linear-gradient(135deg, #1A1800 0%, #141414 100%)', border: '1px solid #FFE50033', borderRadius: 18, padding: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: 18 }}>👑</span>
                    <span style={{ fontWeight: 600, fontSize: 15 }}>当前套餐：<span style={{ color: '#888' }}>免费版</span></span>
                  </div>
                  <p style={{ color: '#888', fontSize: 13 }}>升级后可使用更强的模型与无限生成次数</p>
                </div>
                <button onClick={() => setActiveSection('membership')} style={{ background: '#FFE500', color: '#000', border: 'none', borderRadius: 10, padding: '10px 22px', fontWeight: 700, fontSize: 14, cursor: 'pointer', whiteSpace: 'nowrap' }}>升级会员 →</button>
              </div>
            </div>
          )}

          {activeSection === 'writing' && (
            <div>
              <h2 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 24, marginBottom: 8 }}>写作偏好</h2>
              <p style={{ color: '#888', fontSize: 14, marginBottom: 32 }}>配置 AI 的写作风格与生成偏好</p>
              <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 18, padding: 28 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  {[
                    { label: '默认写作风格', options: ['玄幻武侠', '都市现代', '科幻奇幻', '历史言情'], type: 'select' },
                    { label: '每章字数目标', options: ['1000字', '1500字', '2000字', '3000字'], type: 'select' },
                    { label: '叙事视角', options: ['第一人称', '第三人称全知', '第三人称有限'], type: 'select' },
                  ].map(field => (
                    <div key={field.label}>
                      <label style={{ display: 'block', color: '#aaa', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>{field.label}</label>
                      <select style={{ width: '100%', padding: '12px 16px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none' }}>
                        {field.options.map(o => <option key={o}>{o}</option>)}
                      </select>
                    </div>
                  ))}
                  <div>
                    <label style={{ display: 'block', color: '#aaa', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>写作风格备注</label>
                    <textarea placeholder="描述你期望的写作风格..." rows={4} style={{ width: '100%', padding: '12px 16px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', resize: 'vertical', boxSizing: 'border-box' }}/>
                  </div>
                  <button style={{ padding: '12px', background: '#FFE500', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 14, color: '#000', cursor: 'pointer' }}>保存偏好</button>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'account' && (
            <div>
              <h2 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 24, marginBottom: 8 }}>账号信息</h2>
              <p style={{ color: '#888', fontSize: 14, marginBottom: 32 }}>管理你的个人信息与安全设置</p>
              <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 18, padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}>
                {[['用户名', '创作者', 'text'], ['邮箱地址', 'creator@example.com', 'email']].map(([l, v, t]) => (
                  <div key={l as string}>
                    <label style={{ display: 'block', color: '#aaa', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>{l}</label>
                    <input type={t as string} defaultValue={v as string} style={{ width: '100%', padding: '12px 16px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}/>
                  </div>
                ))}
                <div style={{ borderTop: '1px solid #2A2A2A', paddingTop: 20 }}>
                  <label style={{ display: 'block', color: '#aaa', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>修改密码</label>
                  <input type="password" placeholder="输入新密码" style={{ width: '100%', padding: '12px 16px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box', marginBottom: 12 }}/>
                  <input type="password" placeholder="确认新密码" style={{ width: '100%', padding: '12px 16px', background: '#1C1C1C', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}/>
                </div>
                <button style={{ padding: '12px', background: '#FFE500', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 14, color: '#000', cursor: 'pointer' }}>保存更改</button>
              </div>
            </div>
          )}

          {activeSection === 'membership' && (
            <div>
              <h2 style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 700, fontSize: 24, marginBottom: 8 }}>会员套餐</h2>
              <p style={{ color: '#888', fontSize: 14, marginBottom: 32 }}>选择适合你的创作计划</p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                {PLANS.map((plan, i) => (
                  <div key={plan.name} style={{ background: i === 1 ? '#1A1800' : '#141414', border: `1px solid ${i === 1 ? '#FFE50055' : '#1C1C1C'}`, borderRadius: 18, padding: 24, position: 'relative' }}>
                    {i === 1 && <div style={{ position: 'absolute', top: -12, left: '50%', transform: 'translateX(-50%)', background: '#FFE500', color: '#000', fontSize: 11, fontWeight: 700, padding: '3px 14px', borderRadius: 999 }}>推荐</div>}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ color: '#888', fontSize: 13, marginBottom: 4 }}>{plan.name}</div>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                        <span style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 900, fontSize: 36, color: i === 1 ? '#FFE500' : '#fff' }}>{plan.price}</span>
                        <span style={{ color: '#888', fontSize: 13 }}>{plan.period}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
                      {plan.features.map(f => (
                        <div key={f} style={{ display: 'flex', gap: 8 }}>
                          <span style={{ color: '#FFE500', fontSize: 14 }}>✓</span>
                          <span style={{ color: '#aaa', fontSize: 13 }}>{f}</span>
                        </div>
                      ))}
                    </div>
                    <button style={{ width: '100%', padding: '11px', background: plan.current ? '#2A2A2A' : (i === 1 ? '#FFE500' : '#1C1C1C'), border: plan.current ? 'none' : (i === 1 ? 'none' : '1px solid #2A2A2A'), borderRadius: 10, fontWeight: 700, fontSize: 13, color: plan.current ? '#888' : (i === 1 ? '#000' : '#fff'), cursor: plan.current ? 'default' : 'pointer' }}>
                      {plan.current ? '当前套餐' : '升级'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
