import { useState } from 'react'

const NAV_ITEMS = ['灵感模式', '我的小说', '写作台', '设置']
const SIDEBAR_ITEMS = [
  { id: 'llm', icon: '🤖', label: 'LLM 配置' },
  { id: 'writing', icon: '✍️', label: '写作偏好' },
  { id: 'account', icon: '👤', label: '账号信息' },
  { id: 'subscription', icon: '💎', label: '会员套餐' },
]

export default function Settings() {
  const [activeSection, setActiveSection] = useState('llm')
  const [activeNav, setActiveNav] = useState('设置')
  const [showKey, setShowKey] = useState(false)
  const [temperature, setTemperature] = useState(0.7)
  const [testStatus, setTestStatus] = useState<'idle'|'testing'|'success'|'error'>('idle')

  const handleTest = () => {
    setTestStatus('testing')
    setTimeout(() => setTestStatus('success'), 1500)
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0A0A0A', fontFamily: "'Inter', sans-serif", display: 'flex', flexDirection: 'column' }}>
      {/* Nav */}
      <nav style={{ display: 'flex', alignItems: 'center', padding: '0 40px', height: 64, borderBottom: '1px solid #141414', background: '#0A0A0A', position: 'sticky', top: 0, zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginRight: 'auto' }}>
          <div style={{ width: 32, height: 32, background: '#FFE500', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, color: '#000', fontSize: 16 }}>✦</div>
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, color: '#fff', fontSize: 16 }}>Arboris Novel</span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {NAV_ITEMS.map(item => (
            <button key={item} onClick={() => setActiveNav(item)}
              style={{ padding: '7px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500, background: activeNav === item ? '#141414' : 'transparent', color: activeNav === item ? '#FFE500' : '#888' }}>
              {item}
            </button>
          ))}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'linear-gradient(135deg, #FFE500, #e6ce00)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, color: '#000', fontSize: 15 }}>云</div>
        </div>
      </nav>

      <div style={{ flex: 1, display: 'flex', maxWidth: 1100, margin: '0 auto', width: '100%', padding: '40px', gap: 24, boxSizing: 'border-box' }}>
        {/* Left sidebar */}
        <div style={{ width: 220, flexShrink: 0 }}>
          {/* User info */}
          <div style={{ padding: '20px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16, marginBottom: 16, textAlign: 'center' }}>
            <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'linear-gradient(135deg, #FFE500, #e6ce00)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, color: '#000', fontSize: 28, margin: '0 auto 12px' }}>云</div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, color: '#fff', fontSize: 15, marginBottom: 3 }}>云中君</div>
            <div style={{ color: '#666', fontSize: 12 }}>免费版会员</div>
          </div>

          {/* Section nav */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {SIDEBAR_ITEMS.map(item => (
              <button key={item.id} onClick={() => setActiveSection(item.id)}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px', borderRadius: 10, border: 'none', cursor: 'pointer', background: activeSection === item.id ? '#141414' : 'transparent', color: activeSection === item.id ? '#FFE500' : '#888', borderLeft: activeSection === item.id ? '2px solid #FFE500' : '2px solid transparent', fontWeight: activeSection === item.id ? 600 : 400, fontSize: 14, textAlign: 'left' }}>
                <span>{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Right content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {activeSection === 'llm' && (
            <div>
              <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 24, color: '#fff', margin: '0 0 6px' }}>LLM 配置</h2>
              <p style={{ color: '#666', fontSize: 14, margin: '0 0 28px' }}>配置你的AI模型连接，影响全局创作质量</p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {/* Model URL */}
                <div style={{ padding: '24px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#888', marginBottom: 8, letterSpacing: 0.6, textTransform: 'uppercase' }}>API 地址</label>
                  <input readOnly defaultValue="https://api.openai.com/v1"
                    style={{ width: '100%', padding: '12px 14px', background: '#0A0A0A', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}/>
                  <p style={{ color: '#555', fontSize: 12, marginTop: 6 }}>支持 OpenAI 兼容格式的 API 端点</p>
                </div>

                {/* API Key */}
                <div style={{ padding: '24px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#888', marginBottom: 8, letterSpacing: 0.6, textTransform: 'uppercase' }}>API Key</label>
                  <div style={{ position: 'relative' }}>
                    <input readOnly type={showKey ? 'text' : 'password'} defaultValue="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                      style={{ width: '100%', padding: '12px 46px 12px 14px', background: '#0A0A0A', border: '1px solid #FFE500', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box', boxShadow: '0 0 0 3px rgba(255,229,0,0.08)' }}/>
                    <button onClick={() => setShowKey(!showKey)}
                      style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 16 }}>
                      {showKey ? '🙈' : '👁️'}
                    </button>
                  </div>
                </div>

                {/* Model name */}
                <div style={{ padding: '24px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#888', marginBottom: 8, letterSpacing: 0.6, textTransform: 'uppercase' }}>模型名称</label>
                  <select style={{ width: '100%', padding: '12px 14px', background: '#0A0A0A', border: '1px solid #2A2A2A', borderRadius: 10, color: '#fff', fontSize: 14, outline: 'none', cursor: 'pointer', appearance: 'none' }}>
                    <option value="gpt-4o">GPT-4o（推荐）</option>
                    <option value="gpt-4-turbo">GPT-4 Turbo</option>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo（经济）</option>
                    <option value="claude-3-opus">Claude 3 Opus</option>
                    <option value="custom">自定义模型</option>
                  </select>
                </div>

                {/* Temperature */}
                <div style={{ padding: '24px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#888', marginBottom: 3, letterSpacing: 0.6, textTransform: 'uppercase' }}>创意温度</label>
                      <p style={{ color: '#555', fontSize: 12, margin: 0 }}>数值越高，生成内容越有创意</p>
                    </div>
                    <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: 22, color: '#FFE500' }}>{temperature.toFixed(1)}</span>
                  </div>
                  <input type="range" min="0" max="1" step="0.1" value={temperature} onChange={e => setTemperature(+e.target.value)}
                    style={{ width: '100%', accentColor: '#FFE500', cursor: 'pointer' }}/>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                    <span style={{ color: '#444', fontSize: 11 }}>精确 (0.0)</span>
                    <span style={{ color: '#444', fontSize: 11 }}>创意 (1.0)</span>
                  </div>
                </div>

                {/* Test connection */}
                <div style={{ display: 'flex', gap: 12 }}>
                  <button onClick={handleTest}
                    style={{ padding: '12px 28px', background: '#FFE500', color: '#000', border: 'none', borderRadius: 12, fontWeight: 800, fontSize: 14, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif", display: 'flex', alignItems: 'center', gap: 8 }}>
                    {testStatus === 'testing' ? '⏳ 测试中...' : '⚡ 测试连接'}
                  </button>
                  {testStatus === 'success' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 18px', background: '#0A2A1A', border: '1px solid #2ED57333', borderRadius: 12 }}>
                      <span style={{ color: '#2ED573', fontSize: 16 }}>✓</span>
                      <span style={{ color: '#2ED573', fontWeight: 600, fontSize: 14 }}>连接成功！响应时间 342ms</span>
                    </div>
                  )}
                  {testStatus === 'error' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 18px', background: '#3D0A0A', border: '1px solid #FF475733', borderRadius: 12 }}>
                      <span style={{ color: '#FF4757', fontSize: 16 }}>✗</span>
                      <span style={{ color: '#FF4757', fontWeight: 600, fontSize: 14 }}>连接失败，请检查配置</span>
                    </div>
                  )}
                </div>

                {/* Membership card */}
                <div style={{ padding: '24px', background: 'linear-gradient(135deg, #1A1800 0%, #141414 100%)', border: '1px solid #FFE50033', borderRadius: 16, position: 'relative', overflow: 'hidden' }}>
                  <div style={{ position: 'absolute', top: -20, right: -20, width: 100, height: 100, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,229,0,0.12) 0%, transparent 70%)' }}/>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 20 }}>💎</span>
                        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, color: '#fff', fontSize: 16 }}>当前套餐</span>
                      </div>
                      <div style={{ display: 'inline-block', padding: '4px 12px', background: '#1C1C1C', color: '#888', borderRadius: 999, fontSize: 13, fontWeight: 600, marginBottom: 12 }}>免费版</div>
                      <div style={{ color: '#666', fontSize: 13, lineHeight: 1.6 }}>
                        <div>✗ 每月 20 次AI生成上限</div>
                        <div>✗ 不支持参考小说功能</div>
                        <div>✗ 无法批量生成章节</div>
                      </div>
                    </div>
                    <button style={{ padding: '11px 22px', background: '#FFE500', color: '#000', border: 'none', borderRadius: 12, fontWeight: 800, fontSize: 14, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif", flexShrink: 0 }}>
                      升级会员 →
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeSection !== 'llm' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 400, gap: 16 }}>
              <div style={{ fontSize: 48 }}>🔧</div>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, color: '#fff', fontSize: 18 }}>
                {SIDEBAR_ITEMS.find(s=>s.id===activeSection)?.label}
              </div>
              <p style={{ color: '#666', fontSize: 14 }}>点击左侧 LLM 配置查看完整设置示例</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
