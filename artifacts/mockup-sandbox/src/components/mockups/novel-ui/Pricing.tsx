import React, { useState } from "react";
import { Check, X, Sparkles, Zap, Crown, Clock, ArrowRight, ChevronDown, ChevronUp, Library, Lightbulb, PenTool, Settings } from "lucide-react";

const PLANS = [
  {
    id: "free",
    name: "免费版",
    nameEn: "Free",
    price: 0,
    priceLabel: "¥0",
    period: "永久免费",
    desc: "轻度体验，够用就好",
    icon: Library,
    color: "#888888",
    bg: "#141414",
    border: "#2A2A2A",
    cta: "当前套餐",
    ctaStyle: "outline",
    badge: null,
    features: [
      { text: "1 个小说项目", ok: true },
      { text: "20次 AI章节生成 / 月", ok: true },
      { text: "基础角色管理", ok: true },
      { text: "标准生成队列", ok: true },
      { text: "TXT 导出", ok: true },
      { text: "无限小说项目", ok: false },
      { text: "世界观 / 伏笔 / 情感曲线", ok: false },
      { text: "优先生成队列", ok: false },
      { text: "自定义 LLM 接入", ok: false },
    ],
  },
  {
    id: "creator",
    name: "创作者版",
    nameEn: "Creator",
    price: 29,
    priceLabel: "¥29",
    period: "/ 月",
    desc: "认真写作的最佳选择",
    icon: Zap,
    color: "#FFE500",
    bg: "#141414",
    border: "#FFE500",
    cta: "免费试用 3 天",
    ctaStyle: "primary",
    badge: "最受欢迎",
    features: [
      { text: "无限 小说项目", ok: true },
      { text: "200次 AI章节生成 / 月", ok: true },
      { text: "完整角色 / 人物关系图", ok: true },
      { text: "世界观 / 伏笔 / 情感曲线", ok: true },
      { text: "优先生成队列（快 3×）", ok: true },
      { text: "章节大纲智能生成", ok: true },
      { text: "TXT / DOCX 导出", ok: true },
      { text: "自定义 LLM 接入", ok: false },
      { text: "专属客服支持", ok: false },
    ],
  },
  {
    id: "pro",
    name: "无限版",
    nameEn: "Pro",
    price: 69,
    priceLabel: "¥69",
    period: "/ 月",
    desc: "为重度创作者与团队打造",
    icon: Crown,
    color: "#C084FC",
    bg: "#141414",
    border: "#3D2A5E",
    cta: "免费试用 3 天",
    ctaStyle: "purple",
    badge: "全功能解锁",
    features: [
      { text: "无限 小说项目", ok: true },
      { text: "无限 AI章节生成", ok: true },
      { text: "完整角色 / 人物关系图", ok: true },
      { text: "世界观 / 伏笔 / 情感曲线", ok: true },
      { text: "最高优先队列（最快）", ok: true },
      { text: "章节大纲智能生成", ok: true },
      { text: "TXT / DOCX / EPUB 导出", ok: true },
      { text: "自定义 LLM 接入（自带 Key）", ok: true },
      { text: "专属客服支持", ok: true },
    ],
  },
];

const FAQS = [
  { q: "3天试用需要绑定信用卡吗？", a: "不需要。注册即可激活创作者版3天试用，无需填写任何支付信息。试用到期后自动降为免费版，不会产生任何扣费。" },
  { q: "试用期结束后数据会丢失吗？", a: "不会。你的所有小说项目和章节数据会完整保留。升级后即可继续使用所有内容。" },
  { q: "可以随时取消订阅吗？", a: "可以。订阅可在任意时间取消，取消后当前计费周期结束前仍可继续使用付费功能。" },
  { q: "「自定义LLM接入」是什么意思？", a: "无限版用户可以在设置中填写自己的 API Key（支持 OpenAI、DeepSeek、Qwen 等），使用自己的模型配额，不受平台生成次数限制。" },
];

function NavLink({ icon: Icon, label, active }: { icon: any; label: string; active: boolean }) {
  return (
    <a href="#" className={`flex items-center gap-1.5 text-sm font-medium transition-colors ${active ? "text-[#FFE500]" : "text-[#888888] hover:text-white"}`}>
      <Icon className="w-4 h-4" />{label}
    </a>
  );
}

export default function Pricing() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [annual, setAnnual] = useState(false);

  const displayPrice = (p: number) => {
    if (p === 0) return "¥0";
    return annual ? `¥${Math.round(p * 0.8)}` : `¥${p}`;
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Nav */}
      <header className="sticky top-0 z-50 border-b border-[#2A2A2A] bg-[#141414]/90 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#FFE500] flex items-center justify-center text-black">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-bold text-lg tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              Arboris Novel
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-7">
            <NavLink icon={Lightbulb} label="灵感模式" active={false} />
            <NavLink icon={Library} label="我的小说" active={false} />
            <NavLink icon={PenTool} label="写作台" active={false} />
            <NavLink icon={Settings} label="设置" active={false} />
          </nav>
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#888888]">已登录</span>
            <div className="w-8 h-8 rounded-full border border-[#2A2A2A] bg-[#1C1C1C] flex items-center justify-center text-[#FFE500] text-xs font-bold">AX</div>
          </div>
        </div>
      </header>

      {/* Trial banner */}
      <div className="border-b border-[#2A2A2A]" style={{ background: "linear-gradient(90deg, #1A1600 0%, #141414 50%, #1A1600 100%)" }}>
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-center gap-3">
          <Clock className="w-4 h-4 text-[#FFE500] flex-shrink-0" />
          <span className="text-sm">
            <span className="text-[#FFE500] font-semibold">新用户专享：</span>
            <span className="text-[#CCCCCC]"> 注册即激活创作者版 </span>
            <span className="text-white font-bold">3天完整试用</span>
            <span className="text-[#888888]">，无需绑卡，到期自动降为免费版</span>
          </span>
          <ArrowRight className="w-4 h-4 text-[#FFE500] flex-shrink-0" />
        </div>
      </div>

      <main className="max-w-6xl mx-auto px-6 py-12">

        {/* Page header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold mb-3" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            选择你的创作套餐
          </h1>
          <p className="text-[#888888] text-lg mb-8">用 AI 加速你的小说创作之旅</p>

          {/* Annual toggle */}
          <div className="inline-flex items-center gap-3 bg-[#141414] border border-[#2A2A2A] rounded-full px-4 py-2">
            <span className={`text-sm font-medium transition-colors ${!annual ? "text-white" : "text-[#888888]"}`}>按月付费</span>
            <button
              onClick={() => setAnnual(!annual)}
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{ background: annual ? "#FFE500" : "#2A2A2A" }}>
              <span className="absolute top-0.5 w-4 h-4 rounded-full bg-black transition-all"
                style={{ left: annual ? "calc(100% - 18px)" : 2 }} />
            </button>
            <span className={`text-sm font-medium transition-colors ${annual ? "text-white" : "text-[#888888]"}`}>
              按年付费
              <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full bg-[#FFE500]/15 text-[#FFE500] font-semibold">省20%</span>
            </span>
          </div>
        </div>

        {/* Pricing cards */}
        <div className="grid grid-cols-3 gap-5 mb-14">
          {PLANS.map((plan) => {
            const Icon = plan.icon;
            const isCreator = plan.id === "creator";
            const isPro = plan.id === "pro";
            return (
              <div key={plan.id}
                className="relative rounded-2xl flex flex-col transition-all"
                style={{
                  background: isCreator
                    ? "linear-gradient(160deg, #1C1A00 0%, #141414 60%)"
                    : isPro
                    ? "linear-gradient(160deg, #1A0E2E 0%, #141414 60%)"
                    : "#141414",
                  border: `1px solid ${plan.border}`,
                  boxShadow: isCreator
                    ? "0 0 40px rgba(255,229,0,0.1), 0 0 0 1px rgba(255,229,0,0.2)"
                    : isPro
                    ? "0 0 40px rgba(192,132,252,0.08)"
                    : "none",
                }}>

                {/* Badge */}
                {plan.badge && (
                  <div className="absolute -top-3.5 left-0 right-0 flex justify-center">
                    <span className="text-xs font-bold px-4 py-1 rounded-full"
                      style={{
                        background: isCreator ? "#FFE500" : "#7C3AED",
                        color: isCreator ? "#000" : "#fff",
                      }}>
                      {plan.badge}
                    </span>
                  </div>
                )}

                <div className="p-7 flex-1 flex flex-col">
                  {/* Plan header */}
                  <div className="flex items-center gap-3 mb-5">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ background: `${plan.color}15`, border: `1px solid ${plan.color}30` }}>
                      <Icon className="w-5 h-5" style={{ color: plan.color }} />
                    </div>
                    <div>
                      <div className="font-bold text-white text-base">{plan.name}</div>
                      <div className="text-xs text-[#888888]">{plan.desc}</div>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="mb-6 pb-6 border-b border-[#2A2A2A]">
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-bold" style={{ fontFamily: "'Space Grotesk', sans-serif", color: plan.price === 0 ? "#888888" : "white" }}>
                        {displayPrice(plan.price)}
                      </span>
                      {plan.price > 0 && (
                        <span className="text-[#888888] text-sm">{annual ? "/ 月（年付）" : plan.period}</span>
                      )}
                    </div>
                    {plan.price === 0 && <div className="text-[#888888] text-sm mt-1">{plan.period}</div>}
                    {plan.price > 0 && annual && (
                      <div className="text-xs text-[#888888] mt-1">
                        即 <span style={{ color: plan.color }}>¥{Math.round(plan.price * 0.8 * 12)}</span> / 年
                        <span className="ml-1 line-through opacity-50">¥{plan.price * 12}</span>
                      </div>
                    )}
                  </div>

                  {/* Features */}
                  <ul className="space-y-3 flex-1 mb-7">
                    {plan.features.map((f, i) => (
                      <li key={i} className="flex items-center gap-2.5 text-sm">
                        {f.ok ? (
                          <div className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                            style={{ background: `${plan.color}20` }}>
                            <Check className="w-2.5 h-2.5" style={{ color: plan.color }} />
                          </div>
                        ) : (
                          <div className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 bg-[#1C1C1C]">
                            <X className="w-2.5 h-2.5 text-[#444444]" />
                          </div>
                        )}
                        <span style={{ color: f.ok ? "#DDDDDD" : "#555555" }}>{f.text}</span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  <button
                    className="w-full py-3 rounded-xl font-semibold text-sm transition-all"
                    style={
                      plan.ctaStyle === "primary"
                        ? { background: "#FFE500", color: "#000000" }
                        : plan.ctaStyle === "purple"
                        ? { background: "linear-gradient(135deg, #7C3AED, #4F46E5)", color: "#fff", boxShadow: "0 4px 16px rgba(124,58,237,0.3)" }
                        : { background: "transparent", color: "#888888", border: "1px solid #2A2A2A" }
                    }>
                    {plan.id === "free" ? plan.cta : (
                      <span className="flex items-center justify-center gap-2">
                        {plan.cta}
                        <ArrowRight className="w-4 h-4" />
                      </span>
                    )}
                  </button>

                  {plan.id !== "free" && (
                    <p className="text-center text-[10px] text-[#555555] mt-2.5">试用期结束自动降为免费版，无需绑卡</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Comparison table */}
        <div className="mb-14">
          <h2 className="text-xl font-bold text-white mb-5 text-center" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            详细功能对比
          </h2>
          <div className="rounded-xl border border-[#2A2A2A] overflow-hidden">
            {/* Header */}
            <div className="grid grid-cols-4 bg-[#141414] border-b border-[#2A2A2A]">
              <div className="p-4 text-[#888888] text-sm">功能</div>
              {PLANS.map(p => (
                <div key={p.id} className="p-4 text-center">
                  <div className="text-sm font-semibold" style={{ color: p.color === "#888888" ? "#aaa" : p.color }}>{p.name}</div>
                </div>
              ))}
            </div>
            {[
              { label: "小说项目数量", vals: ["1 个", "无限", "无限"] },
              { label: "AI章节生成", vals: ["20次/月", "200次/月", "无限次"] },
              { label: "优先生成队列", vals: [false, "快 3×", "最快"] },
              { label: "角色 / 人物关系", vals: ["基础", "完整", "完整"] },
              { label: "世界观 / 伏笔管理", vals: [false, true, true] },
              { label: "情感曲线分析", vals: [false, true, true] },
              { label: "章节大纲生成", vals: [false, true, true] },
              { label: "导出格式", vals: ["TXT", "TXT / DOCX", "TXT / DOCX / EPUB"] },
              { label: "自定义 LLM 接入", vals: [false, false, true] },
              { label: "专属客服", vals: [false, false, true] },
            ].map((row, i) => (
              <div key={i} className={`grid grid-cols-4 border-b border-[#1C1C1C] ${i % 2 === 0 ? "bg-[#0A0A0A]" : "bg-[#141414]"}`}>
                <div className="p-3.5 text-sm text-[#888888] flex items-center">{row.label}</div>
                {row.vals.map((v, j) => (
                  <div key={j} className="p-3.5 flex items-center justify-center">
                    {v === true ? (
                      <Check className="w-4 h-4 text-[#2ED573]" />
                    ) : v === false ? (
                      <X className="w-4 h-4 text-[#333333]" />
                    ) : (
                      <span className="text-xs text-center font-medium text-white">{v}</span>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* FAQ */}
        <div className="max-w-2xl mx-auto">
          <h2 className="text-xl font-bold text-white mb-6 text-center" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            常见问题
          </h2>
          <div className="space-y-3">
            {FAQS.map((faq, i) => (
              <div key={i} className="rounded-xl border border-[#2A2A2A] overflow-hidden">
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between gap-4 p-5 text-left bg-[#141414] hover:bg-[#1A1A1A] transition-colors">
                  <span className="text-sm font-medium text-white">{faq.q}</span>
                  {openFaq === i
                    ? <ChevronUp className="w-4 h-4 text-[#888888] flex-shrink-0" />
                    : <ChevronDown className="w-4 h-4 text-[#888888] flex-shrink-0" />}
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-5 bg-[#141414] border-t border-[#2A2A2A]">
                    <p className="text-sm text-[#888888] leading-relaxed pt-4">{faq.a}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Bottom CTA */}
        <div className="mt-14 text-center py-12 px-8 rounded-2xl border border-[#2A2A2A]"
          style={{ background: "linear-gradient(135deg, #1A1600 0%, #0A0A0A 50%, #1A1600 100%)" }}>
          <div className="inline-flex items-center gap-2 text-xs text-[#FFE500] font-semibold tracking-widest uppercase mb-4 px-3 py-1.5 rounded-full border border-[#FFE500]/20 bg-[#FFE500]/5">
            <Sparkles className="w-3.5 h-3.5" />
            新用户限时优惠
          </div>
          <h3 className="text-2xl font-bold text-white mb-2" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            现在注册，立享3天创作者版体验
          </h3>
          <p className="text-[#888888] mb-8 max-w-md mx-auto text-sm">无需信用卡 · 到期自动降级 · 数据永久保留</p>
          <button className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-[#FFE500] text-black font-bold text-sm hover:bg-[#FFF062] transition-colors">
            免费开始创作
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </main>
    </div>
  );
}
