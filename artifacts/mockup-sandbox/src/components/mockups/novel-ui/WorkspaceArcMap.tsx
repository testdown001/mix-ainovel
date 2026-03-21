import React, { useState } from "react";
import { Sparkles, Library, Lightbulb, PenTool, Settings, Plus, BookOpen, Clock } from "lucide-react";

const novels = [
  {
    id: "1", title: "星际穿越", subtitle: "黑暗森林的余烬", genre: "科幻",
    progress: 45, chaptersDone: 12, chaptersTotal: 30, lastEdited: "2小时前",
    color: "#4285F4", glow: "rgba(66,133,244,0.4)",
    arcPhase: "rising",
    summary: "三体文明的黑暗打击过后，人类舰队在虚空中的最后挣扎与救赎。",
  },
  {
    id: "2", title: "修仙纪元", subtitle: "从凡人到道祖", genre: "仙侠",
    progress: 80, chaptersDone: 80, chaptersTotal: 100, lastEdited: "1天前",
    color: "#2ED573", glow: "rgba(46,213,115,0.4)",
    arcPhase: "climax",
    summary: "废材少年得上古道经，历经千劫，终登道祖之位。",
  },
  {
    id: "3", title: "霓虹雨下的武士", subtitle: "赛博朋克", genre: "赛博朋克",
    progress: 100, chaptersDone: 50, chaptersTotal: 50, lastEdited: "3天前",
    color: "#E040FB", glow: "rgba(224,64,251,0.4)",
    arcPhase: "complete",
    summary: "2089年的新东京，被改造的武士在钢铁与霓虹中寻找失去的灵魂。",
  },
  {
    id: "4", title: "迷雾纪元", subtitle: "", genre: "悬疑",
    progress: 15, chaptersDone: 3, chaptersTotal: 20, lastEdited: "1周前",
    color: "#555555", glow: "rgba(85,85,85,0.3)",
    arcPhase: "opening",
    summary: "小镇连续离奇失踪案，深入调查后发现触目惊心的真相……",
  },
];

function StoryArcSVG({ phase, color, width = 120, height = 44 }: { phase: string; color: string; width?: number; height?: number }) {
  const w = width, h = height, pad = 8;
  const cx = w / 2, cy = h / 2;

  const getPath = () => {
    if (phase === "opening") {
      return `M ${pad} ${h - pad} C ${cx * 0.4} ${h - pad}, ${cx * 0.8} ${cy + 4}, ${cx} ${cy + 4}`;
    }
    if (phase === "rising") {
      return `M ${pad} ${h - pad} C ${cx * 0.5} ${h - pad}, ${cx * 0.7} ${pad + 4}, ${w * 0.65} ${pad + 4} L ${w - pad} ${pad + 4}`;
    }
    if (phase === "climax") {
      return `M ${pad} ${h - pad} C ${cx * 0.5} ${h - pad}, ${cx * 0.6} ${pad}, ${cx} ${pad} C ${cx * 1.4} ${pad}, ${cx * 1.5} ${cy}, ${w - pad} ${cy}`;
    }
    if (phase === "complete") {
      return `M ${pad} ${h - pad} C ${cx * 0.5} ${h - pad}, ${cx * 0.6} ${pad}, ${cx} ${pad} C ${cx * 1.4} ${pad}, ${w * 1.4} ${cy}, ${w - pad} ${h - pad}`;
    }
    return `M ${pad} ${cy} L ${w - pad} ${cy}`;
  };

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none">
      <defs>
        <linearGradient id={`arc-grad-${phase}-${color.replace("#","")}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="1" />
        </linearGradient>
      </defs>
      <path d={getPath()} stroke={`url(#arc-grad-${phase}-${color.replace("#","")})`} strokeWidth="2.5" strokeLinecap="round" />
      {phase === "complete" && (
        <circle cx={w - pad} cy={h - pad} r="3" fill={color} />
      )}
    </svg>
  );
}

export default function WorkspaceArcMap() {
  const [selected, setSelected] = useState<string>("1");
  const selectedNovel = novels.find(n => n.id === selected)!;

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white flex flex-col" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Subtle grid background */}
      <div className="fixed inset-0 pointer-events-none" style={{
        backgroundImage: "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)",
        backgroundSize: "48px 48px",
        zIndex: 0,
      }} />

      {/* Nav */}
      <header className="sticky top-0 z-50 w-full border-b border-[#2A2A2A] bg-[#0A0A0A]/90 backdrop-blur-md">
        <div className="container mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-[#FFE500] flex items-center justify-center text-black">
              <Sparkles className="w-5 h-5" />
            </div>
            <span style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="font-bold text-xl tracking-tight">Arboris Novel</span>
          </div>
          <nav className="hidden md:flex items-center gap-8">
            {[
              { icon: Lightbulb, label: "灵感模式", active: false },
              { icon: Library, label: "我的小说", active: true },
              { icon: PenTool, label: "写作台", active: false },
              { icon: Settings, label: "设置", active: false },
            ].map(({ icon: Icon, label, active }) => (
              <a key={label} href="#" className={`flex items-center gap-2 transition-colors text-sm font-medium ${active ? "text-[#FFE500]" : "text-[#888888] hover:text-white"}`}>
                <Icon className="w-4 h-4" />{label}
              </a>
            ))}
          </nav>
          <div className="w-9 h-9 rounded-full border border-[#2A2A2A] bg-[#1C1C1C] flex items-center justify-center text-[#FFE500] text-sm font-bold">AX</div>
        </div>
      </header>

      <main className="flex-1 container mx-auto px-6 py-10 relative z-10">
        {/* Title */}
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-2xl font-bold text-white">创作旅程</h1>
            <p className="text-[#888888] text-sm mt-0.5">每一部作品都是一段独特的故事弧线</p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FFE500] text-black font-semibold text-sm">
            <Plus className="w-4 h-4" />新建小说
          </button>
        </div>

        {/* Arc legend */}
        <div className="flex items-center gap-6 mb-12 mt-6">
          {[
            { phase: "opening", label: "起始", color: "#555" },
            { phase: "rising", label: "上升", color: "#4285F4" },
            { phase: "climax", label: "高潮", color: "#2ED573" },
            { phase: "complete", label: "完结", color: "#E040FB" },
          ].map(({ phase, label, color }) => (
            <div key={phase} className="flex items-center gap-2">
              <StoryArcSVG phase={phase} color={color} width={48} height={22} />
              <span className="text-xs text-[#555]">{label}</span>
            </div>
          ))}
        </div>

        {/* Main arc map area */}
        <div className="relative">
          {/* Horizontal connecting line / "the creative river" */}
          <div className="absolute top-[72px] left-0 right-0 flex items-center px-8" style={{ zIndex: 0 }}>
            <div className="flex-1 h-px" style={{
              background: "linear-gradient(90deg, transparent, #2A2A2A 10%, #2A2A2A 90%, transparent)",
            }} />
          </div>

          {/* Novel nodes */}
          <div className="flex items-start gap-0">
            {novels.map((novel, i) => {
              const isSelected = selected === novel.id;
              return (
                <div key={novel.id}
                  className="flex-1 flex flex-col items-center cursor-pointer group"
                  onClick={() => setSelected(novel.id)}
                  style={{ zIndex: isSelected ? 10 : 1 }}>

                  {/* Arc preview above node */}
                  <div className="mb-3 opacity-60 group-hover:opacity-100 transition-opacity">
                    <StoryArcSVG phase={novel.arcPhase} color={novel.color} />
                  </div>

                  {/* Node circle */}
                  <div className="relative mb-3">
                    <div className="w-14 h-14 rounded-full border-2 flex items-center justify-center transition-all"
                      style={{
                        background: isSelected ? `${novel.color}22` : "#141414",
                        borderColor: isSelected ? novel.color : "#2A2A2A",
                        boxShadow: isSelected ? `0 0 24px ${novel.glow}` : "none",
                        transform: isSelected ? "scale(1.15)" : "scale(1)",
                        transition: "all 0.25s ease",
                      }}>
                      <span style={{ fontFamily: "'Space Grotesk', sans-serif", color: isSelected ? novel.color : "#555", fontSize: 13, fontWeight: 700 }}>
                        {novel.progress === 100 ? "✓" : `${novel.progress}%`}
                      </span>
                    </div>
                    {/* Pulsing ring for active */}
                    {isSelected && (
                      <div className="absolute inset-0 rounded-full animate-ping opacity-20"
                        style={{ border: `2px solid ${novel.color}` }} />
                    )}
                    {/* Chapter number tag */}
                    <div className="absolute -top-2 -right-2 text-[9px] px-1.5 py-0.5 rounded-full font-bold"
                      style={{ background: novel.color, color: "#000" }}>
                      {novel.chaptersDone}章
                    </div>
                  </div>

                  {/* Title below node */}
                  <div className="text-center px-2">
                    <div className="text-xs font-semibold text-white truncate max-w-[110px] group-hover:text-[#FFE500] transition-colors"
                      style={{ color: isSelected ? novel.color : undefined }}>
                      {novel.title}
                    </div>
                    <div className="text-[10px] text-[#555] mt-0.5">{novel.genre}</div>
                  </div>
                </div>
              );
            })}

            {/* Add new node */}
            <div className="flex flex-col items-center" style={{ flex: "0 0 80px" }}>
              <div className="mb-3 h-[44px] flex items-end justify-center opacity-30">
                <div className="w-12 border-t border-dashed border-[#2A2A2A]" />
              </div>
              <div className="w-14 h-14 rounded-full border-2 border-dashed border-[#2A2A2A] flex items-center justify-center hover:border-[#FFE500]/50 hover:bg-[#FFE500]/5 transition-all cursor-pointer mb-3">
                <Plus className="w-5 h-5 text-[#2A2A2A]" />
              </div>
              <span className="text-[10px] text-[#2A2A2A]">新建</span>
            </div>
          </div>
        </div>

        {/* Expanded detail panel */}
        <div className="mt-10 rounded-xl border overflow-hidden transition-all"
          style={{ borderColor: `${selectedNovel.color}40`, background: `linear-gradient(135deg, #141414 0%, #0F0F0F 100%)`, boxShadow: `0 0 40px ${selectedNovel.glow}` }}>
          <div className="h-1 w-full" style={{ background: `linear-gradient(90deg, ${selectedNovel.color}, transparent)` }} />
          <div className="p-6">
            <div className="flex items-start justify-between gap-6">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ background: `${selectedNovel.color}22`, color: selectedNovel.color }}>
                    {selectedNovel.genre}
                  </span>
                  <span className="text-xs text-[#888888] flex items-center gap-1">
                    <Clock className="w-3 h-3" />{selectedNovel.lastEdited}
                  </span>
                  <span className="text-xs" style={{ color: selectedNovel.color }}>
                    弧线阶段：{
                      { opening: "序章", rising: "上升期", climax: "高潮期", complete: "完结" }[selectedNovel.arcPhase]
                    }
                  </span>
                </div>
                <h2 style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-2xl font-bold text-white mb-1">{selectedNovel.title}</h2>
                {selectedNovel.subtitle && <p className="text-[#888888] text-sm mb-3">{selectedNovel.subtitle}</p>}
                <p className="text-[#888888] text-sm leading-relaxed mb-5">{selectedNovel.summary}</p>

                {/* Mini stats */}
                <div className="flex items-center gap-6 text-sm">
                  <div>
                    <div style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-xl font-bold text-white">{selectedNovel.chaptersDone}</div>
                    <div className="text-xs text-[#555]">已完成章节</div>
                  </div>
                  <div>
                    <div style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-xl font-bold text-white">{selectedNovel.chaptersTotal}</div>
                    <div className="text-xs text-[#555]">计划章节</div>
                  </div>
                  <div>
                    <div style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-xl font-bold"
                      style={{ color: selectedNovel.color }}>{selectedNovel.progress}%</div>
                    <div className="text-xs text-[#555]">完成度</div>
                  </div>
                </div>

                {/* Progress arc mini */}
                <div className="mt-4 flex items-center gap-3">
                  <div className="flex-1 h-1.5 rounded-full bg-[#1C1C1C] overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${selectedNovel.progress}%`, background: selectedNovel.color }} />
                  </div>
                  <span className="text-xs text-[#555]">{selectedNovel.chaptersDone}/{selectedNovel.chaptersTotal}章</span>
                </div>
              </div>

              {/* Story arc visual — large */}
              <div className="flex-shrink-0 hidden md:flex flex-col items-center gap-3">
                <div className="p-4 rounded-lg" style={{ background: `${selectedNovel.color}0A`, border: `1px solid ${selectedNovel.color}20` }}>
                  <StoryArcSVG phase={selectedNovel.arcPhase} color={selectedNovel.color} width={200} height={80} />
                </div>
                <span className="text-xs text-[#555]">故事弧线</span>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-3 mt-6 pt-5 border-t border-[#1C1C1C]">
              <button className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-black transition-colors"
                style={{ background: selectedNovel.color }}>
                <PenTool className="w-4 h-4" />进入写作台
              </button>
              <button className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-[#2A2A2A] text-[#888888] text-sm hover:text-white hover:border-[#444] transition-colors">
                <BookOpen className="w-4 h-4" />查看详情
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
