import React, { useState } from "react";
import { Sparkles, Library, Lightbulb, PenTool, Settings, Plus, Flame, Clock, TrendingUp, ChevronDown, ChevronRight, BookOpen, Zap, MoreHorizontal } from "lucide-react";

const novels = [
  {
    id: "1", title: "星际穿越：黑暗森林的余烬", genre: "科幻",
    progress: 45, chaptersDone: 12, chaptersTotal: 30, lastEdited: "2小时前",
    velocity: "+3章/周", momentum: 92, streak: 7,
    dotColor: "#4285F4", status: "active",
    summary: "在三体文明摧毁地球之后，人类的最后舰队在黑暗中前行，寻找一丝生机……",
  },
  {
    id: "2", title: "修仙纪元：从凡人到道祖", genre: "仙侠",
    progress: 80, chaptersDone: 80, chaptersTotal: 100, lastEdited: "1天前",
    velocity: "+2章/周", momentum: 74, streak: 4,
    dotColor: "#2ED573", status: "active",
    summary: "废柴少年意外得到上古道经，踏上漫漫修仙之路，终成一代道祖。",
  },
  {
    id: "3", title: "赛博朋克：霓虹雨下的武士", genre: "赛博朋克",
    progress: 100, chaptersDone: 50, chaptersTotal: 50, lastEdited: "3天前",
    velocity: "已完成", momentum: 100, streak: 0,
    dotColor: "#E040FB", status: "done",
    summary: "2089年的新东京，一名被改造的武士在霓虹与钢铁之间寻找自己失去的灵魂。",
  },
  {
    id: "4", title: "迷雾纪元", genre: "悬疑",
    progress: 15, chaptersDone: 3, chaptersTotal: 20, lastEdited: "1周前",
    velocity: "停滞", momentum: 12, streak: 0,
    dotColor: "#555555", status: "paused",
    summary: "小镇上连续发生的离奇失踪案，警探深入调查后发现了不可告人的秘密……",
  },
];

function MomentumBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 rounded-full bg-[#1C1C1C] overflow-hidden" style={{ width: 60 }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${value}%`, background: color }} />
      </div>
      <span className="text-[10px] text-[#555] w-6 text-right">{value}</span>
    </div>
  );
}

export default function WorkspaceMomentum() {
  const [pausedOpen, setPausedOpen] = useState(false);

  const featured = novels[0];
  const active = novels.filter(n => n.status === "active" && n.id !== featured.id);
  const done = novels.filter(n => n.status === "done");
  const paused = novels.filter(n => n.status === "paused");

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white flex flex-col" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Nav */}
      <header className="sticky top-0 z-50 w-full border-b border-[#2A2A2A] bg-[#141414]/90 backdrop-blur-md">
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

      <main className="flex-1 container mx-auto px-6 py-8 max-w-4xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-2xl font-bold text-white">创作中心</h1>
            <p className="text-[#888888] text-sm mt-0.5">按动力排序 · 今日写作连续 7 天</p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FFE500] text-black font-semibold text-sm">
            <Plus className="w-4 h-4" />新建小说
          </button>
        </div>

        {/* Featured card — most active novel */}
        <div className="mb-6 rounded-xl border border-[#2A2A2A] overflow-hidden"
          style={{ background: "linear-gradient(135deg, #141414 0%, #0F1A2E 100%)", boxShadow: "0 0 40px rgba(66,133,244,0.1)" }}>
          <div className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <Flame className="w-4 h-4 text-[#FFE500]" />
              <span className="text-xs font-semibold text-[#FFE500] uppercase tracking-widest">最高动力</span>
            </div>
            <div className="flex items-start justify-between gap-6">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ background: "rgba(66,133,244,0.15)", color: "#82B1FF" }}>{featured.genre}</span>
                  <span className="flex items-center gap-1 text-xs text-[#2ED573]">
                    <Flame className="w-3 h-3" />{featured.streak}天连续写作
                  </span>
                </div>
                <h2 style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-2xl font-bold text-white mb-2">{featured.title}</h2>
                <p className="text-[#888888] text-sm mb-4 leading-relaxed">{featured.summary}</p>
                <div className="flex items-center gap-4 text-sm text-[#888888]">
                  <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{featured.lastEdited}</span>
                  <span className="flex items-center gap-1"><TrendingUp className="w-3.5 h-3.5 text-[#2ED573]" />{featured.velocity}</span>
                  <span>{featured.chaptersDone} / {featured.chaptersTotal} 章</span>
                </div>
              </div>
              <div className="flex-shrink-0 text-right">
                <div className="text-5xl font-bold text-[#4285F4] mb-1" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>{featured.momentum}</div>
                <div className="text-xs text-[#888888]">动力分</div>
                <div className="mt-4 flex flex-col gap-2">
                  <button className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#FFE500] text-black text-sm font-semibold">
                    <PenTool className="w-3.5 h-3.5" />继续写作
                  </button>
                  <button className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[#2A2A2A] text-[#888888] text-sm hover:text-white">
                    <BookOpen className="w-3.5 h-3.5" />查看详情
                  </button>
                </div>
              </div>
            </div>
            {/* Progress bar */}
            <div className="mt-5 h-1.5 rounded-full bg-[#1C1C1C] overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${featured.progress}%`, background: "linear-gradient(90deg, #4285F4, #82B1FF)" }} />
            </div>
          </div>
        </div>

        {/* Active + done list */}
        <div className="mb-3">
          <span className="text-xs font-semibold text-[#888888] uppercase tracking-widest">进行中 & 已完成</span>
        </div>
        <div className="rounded-xl border border-[#2A2A2A] overflow-hidden divide-y divide-[#1C1C1C] mb-4">
          {[...active, ...done].map((novel) => (
            <div key={novel.id}
              className="flex items-center gap-4 px-5 py-4 bg-[#141414] hover:bg-[#1A1A1A] transition-colors group cursor-pointer">
              {/* Color dot */}
              <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: novel.dotColor }} />
              {/* Title */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white text-sm truncate group-hover:text-[#FFE500] transition-colors">{novel.title}</span>
                  {novel.status === "done" && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#2ED573]/10 text-[#2ED573] flex-shrink-0">已完成</span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-0.5">
                  <span className="text-xs text-[#555]">{novel.genre}</span>
                  <span className="text-xs text-[#555]">{novel.chaptersDone}/{novel.chaptersTotal}章</span>
                </div>
              </div>
              {/* Velocity */}
              <div className="hidden md:flex items-center gap-1 w-24 text-xs text-[#888888] flex-shrink-0">
                <Zap className="w-3 h-3 text-[#FFE500]" />{novel.velocity}
              </div>
              {/* Momentum bar */}
              <div className="hidden sm:block w-20 flex-shrink-0">
                <MomentumBar value={novel.momentum} color={novel.dotColor} />
              </div>
              {/* Last edited */}
              <span className="text-xs text-[#555] flex-shrink-0 hidden md:block w-16 text-right">{novel.lastEdited}</span>
              {/* Actions */}
              <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                <button className="p-1.5 rounded hover:bg-[#2A2A2A]">
                  <PenTool className="w-3.5 h-3.5 text-[#888888]" />
                </button>
                <button className="p-1.5 rounded hover:bg-[#2A2A2A]">
                  <MoreHorizontal className="w-3.5 h-3.5 text-[#888888]" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Paused accordion */}
        <button
          className="flex items-center gap-2 text-xs text-[#555] mb-2 hover:text-[#888] transition-colors"
          onClick={() => setPausedOpen(!pausedOpen)}>
          {pausedOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          <span className="uppercase tracking-widest font-semibold">搁置中 ({paused.length})</span>
        </button>
        {pausedOpen && (
          <div className="rounded-xl border border-[#2A2A2A] overflow-hidden divide-y divide-[#1C1C1C]">
            {paused.map((novel) => (
              <div key={novel.id}
                className="flex items-center gap-4 px-5 py-4 bg-[#0F0F0F] hover:bg-[#141414] transition-colors group cursor-pointer opacity-60 hover:opacity-100">
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: novel.dotColor }} />
                <div className="flex-1 min-w-0">
                  <span className="font-medium text-white text-sm truncate">{novel.title}</span>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs text-[#555]">{novel.genre}</span>
                    <span className="text-xs text-[#555]">{novel.chaptersDone}/{novel.chaptersTotal}章</span>
                  </div>
                </div>
                <span className="text-xs text-[#555]">{novel.lastEdited}</span>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button className="p-1.5 rounded hover:bg-[#2A2A2A]">
                    <PenTool className="w-3.5 h-3.5 text-[#888888]" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Stats footer */}
        <div className="mt-8 grid grid-cols-3 gap-4">
          {[
            { label: "本周新增", value: "+5章", icon: TrendingUp, color: "#2ED573" },
            { label: "连续写作", value: "7天", icon: Flame, color: "#FFE500" },
            { label: "AI协助率", value: "87%", icon: Zap, color: "#4285F4" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="flex items-center gap-3 p-4 rounded-xl border border-[#2A2A2A] bg-[#141414]">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: `${color}15` }}>
                <Icon className="w-4 h-4" style={{ color }} />
              </div>
              <div>
                <div style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-lg font-bold text-white">{value}</div>
                <div className="text-xs text-[#888888]">{label}</div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
