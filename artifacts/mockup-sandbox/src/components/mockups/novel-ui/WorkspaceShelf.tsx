import React, { useState } from "react";
import { Plus, Sparkles, BookOpen, PenTool, Settings, Library, Lightbulb } from "lucide-react";

const books = [
  {
    id: "1", title: "星际穿越：黑暗森林的余烬", genre: "科幻", shortGenre: "SF",
    progress: 45, chaptersDone: 12, chaptersTotal: 30, lastEdited: "2小时前",
    heightFactor: 1.0,
    spineGradient: "linear-gradient(180deg, #1a237e 0%, #283593 40%, #1565c0 100%)",
    glowColor: "#4285F4",
    accentColor: "#82B1FF",
  },
  {
    id: "2", title: "修仙纪元：从凡人到道祖", genre: "仙侠", shortGenre: "仙",
    progress: 80, chaptersDone: 80, chaptersTotal: 100, lastEdited: "1天前",
    heightFactor: 1.3,
    spineGradient: "linear-gradient(180deg, #0a3d2e 0%, #1b5e20 40%, #2e7d32 100%)",
    glowColor: "#2ED573",
    accentColor: "#69F0AE",
  },
  {
    id: "3", title: "赛博朋克：霓虹雨下的武士", genre: "赛博朋克", shortGenre: "CP",
    progress: 100, chaptersDone: 50, chaptersTotal: 50, lastEdited: "3天前",
    heightFactor: 0.85,
    spineGradient: "linear-gradient(180deg, #4a148c 0%, #6a1b9a 40%, #7b1fa2 100%)",
    glowColor: "#E040FB",
    accentColor: "#CE93D8",
  },
  {
    id: "4", title: "迷雾纪元", genre: "悬疑", shortGenre: "悬",
    progress: 15, chaptersDone: 3, chaptersTotal: 20, lastEdited: "1周前",
    heightFactor: 0.65,
    spineGradient: "linear-gradient(180deg, #1a1a1a 0%, #212121 40%, #2c2c2c 100%)",
    glowColor: "#888888",
    accentColor: "#BDBDBD",
  },
];

export default function WorkspaceShelf() {
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>("1");

  const activeBook = books.find(b => b.id === (hovered || selected));
  const BASE_HEIGHT = 220;

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white font-['Inter'] flex flex-col"
      style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Nav */}
      <header className="sticky top-0 z-50 w-full border-b border-[#2A2A2A] bg-[#141414]/90 backdrop-blur-md">
        <div className="container mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-[#FFE500] flex items-center justify-center text-black">
              <Sparkles className="w-5 h-5" />
            </div>
            <span style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="font-bold text-xl tracking-tight">
              Arboris Novel
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-8">
            {[
              { icon: Lightbulb, label: "灵感模式", active: false },
              { icon: Library, label: "我的小说", active: true },
              { icon: PenTool, label: "写作台", active: false },
              { icon: Settings, label: "设置", active: false },
            ].map(({ icon: Icon, label, active }) => (
              <a key={label} href="#"
                className={`flex items-center gap-2 transition-colors text-sm font-medium ${active ? "text-[#FFE500]" : "text-[#888888] hover:text-white"}`}>
                <Icon className="w-4 h-4" />{label}
              </a>
            ))}
          </nav>
          <div className="w-9 h-9 rounded-full border border-[#2A2A2A] bg-[#1C1C1C] flex items-center justify-center text-[#FFE500] text-sm font-bold">AX</div>
        </div>
      </header>

      <main className="flex-1 container mx-auto px-6 py-10 flex flex-col">
        {/* Title row */}
        <div className="flex items-center justify-between mb-12">
          <div>
            <h1 style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-3xl font-bold text-white mb-1">我的书架</h1>
            <p className="text-[#888888] text-sm">悬停书脊预览，点击进入写作台</p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FFE500] text-black font-semibold text-sm hover:bg-[#FFF062] transition-colors">
            <Plus className="w-4 h-4" />新建小说
          </button>
        </div>

        {/* Shelf */}
        <div className="relative flex flex-col items-center">
          {/* Detail panel floats above shelf */}
          <div className="w-full mb-8" style={{ minHeight: 120 }}>
            {activeBook ? (
              <div className="flex gap-6 p-6 rounded-xl border border-[#2A2A2A] bg-[#141414] transition-all"
                style={{ boxShadow: `0 0 30px ${activeBook.glowColor}18` }}>
                <div className="w-1 rounded-full flex-shrink-0" style={{ background: activeBook.glowColor }}></div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div>
                      <span className="text-xs px-2 py-0.5 rounded-full font-medium mb-2 inline-block"
                        style={{ background: `${activeBook.glowColor}22`, color: activeBook.accentColor }}>
                        {activeBook.genre}
                      </span>
                      <h2 style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-xl font-bold text-white mt-1">{activeBook.title}</h2>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-[#2A2A2A] text-[#888888] hover:text-white hover:border-[#444] transition-colors">
                        <BookOpen className="w-3.5 h-3.5" />查看详情
                      </button>
                      <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg font-semibold transition-colors"
                        style={{ background: `${activeBook.glowColor}22`, color: activeBook.accentColor, border: `1px solid ${activeBook.glowColor}40` }}>
                        <PenTool className="w-3.5 h-3.5" />进入写作台
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-sm text-[#888888]">
                    <span>{activeBook.chaptersDone} / {activeBook.chaptersTotal} 章</span>
                    <span>上次编辑：{activeBook.lastEdited}</span>
                    <span style={{ color: activeBook.progress === 100 ? "#2ED573" : "#888" }}>
                      {activeBook.progress === 100 ? "✓ 已完成" : `${activeBook.progress}% 完成`}
                    </span>
                  </div>
                  <div className="mt-3 h-1.5 rounded-full bg-[#1C1C1C] overflow-hidden">
                    <div className="h-full rounded-full transition-all"
                      style={{ width: `${activeBook.progress}%`, background: activeBook.progress === 100 ? "#2ED573" : activeBook.glowColor }} />
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-[120px] rounded-xl border border-dashed border-[#2A2A2A] flex items-center justify-center text-[#888888] text-sm">
                悬停书脊查看详情
              </div>
            )}
          </div>

          {/* The actual shelf */}
          <div className="w-full rounded-2xl overflow-hidden" style={{ background: "#0F0F0F", border: "1px solid #1C1C1C" }}>
            {/* Books row */}
            <div className="flex items-end justify-center gap-1 px-16 pt-12 pb-0"
              style={{ minHeight: BASE_HEIGHT + 80 }}>
              {books.map((book) => {
                const isActive = hovered === book.id || (!hovered && selected === book.id);
                const bookH = Math.round(BASE_HEIGHT * book.heightFactor);
                return (
                  <div key={book.id}
                    className="relative cursor-pointer flex-shrink-0"
                    style={{
                      width: 52,
                      height: bookH,
                      transform: isActive ? "translateY(-16px) scaleX(1.04)" : "translateY(0) scaleX(1)",
                      transition: "all 0.25s cubic-bezier(0.34,1.56,0.64,1)",
                      filter: isActive ? `drop-shadow(0 0 16px ${book.glowColor}80)` : "none",
                      zIndex: isActive ? 10 : 1,
                    }}
                    onMouseEnter={() => setHovered(book.id)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => setSelected(book.id)}
                  >
                    {/* Book body */}
                    <div className="absolute inset-0 rounded-sm" style={{ background: book.spineGradient }}>
                      {/* Spine texture lines */}
                      <div className="absolute inset-0 opacity-20"
                        style={{ background: "repeating-linear-gradient(90deg, transparent, transparent 3px, rgba(255,255,255,0.05) 3px, rgba(255,255,255,0.05) 4px)" }} />
                      {/* Top edge highlight */}
                      <div className="absolute top-0 inset-x-0 h-px" style={{ background: "rgba(255,255,255,0.3)" }} />
                      {/* Right edge shadow */}
                      <div className="absolute right-0 inset-y-0 w-1.5" style={{ background: "rgba(0,0,0,0.4)" }} />
                      {/* Genre initial at top */}
                      <div className="absolute top-3 inset-x-0 flex justify-center">
                        <span className="text-xs font-bold" style={{ color: book.accentColor, fontFamily: "'Space Grotesk', sans-serif" }}>
                          {book.shortGenre}
                        </span>
                      </div>
                      {/* Vertical title */}
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-[9px] font-medium text-white/70 leading-tight text-center px-1"
                          style={{ writingMode: "vertical-rl", textOrientation: "mixed", maxHeight: bookH - 40, overflow: "hidden", letterSpacing: "0.05em" }}>
                          {book.title.length > 14 ? book.title.slice(0, 14) + "…" : book.title}
                        </span>
                      </div>
                      {/* Progress strip at bottom */}
                      <div className="absolute bottom-0 inset-x-0 rounded-b-sm overflow-hidden" style={{ height: Math.round(bookH * book.progress / 100 * 0.15) + "px" }}>
                        <div className="w-full h-full" style={{ background: book.progress === 100 ? "#2ED573" : book.glowColor, opacity: 0.7 }} />
                      </div>
                      {/* Active indicator dot */}
                      {isActive && (
                        <div className="absolute bottom-2 inset-x-0 flex justify-center">
                          <div className="w-1.5 h-1.5 rounded-full" style={{ background: book.glowColor }} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* "Add new" slot */}
              <div className="flex-shrink-0 flex items-end" style={{ height: BASE_HEIGHT }}>
                <div className="w-12 border-2 border-dashed border-[#2A2A2A] rounded-sm flex items-center justify-center hover:border-[#FFE500]/50 transition-colors cursor-pointer"
                  style={{ height: BASE_HEIGHT * 0.75 }}>
                  <Plus className="w-4 h-4 text-[#2A2A2A]" />
                </div>
              </div>
            </div>

            {/* Shelf board */}
            <div className="mx-8 h-4 rounded-b-sm" style={{ background: "linear-gradient(180deg, #2A2A2A 0%, #1C1C1C 100%)", boxShadow: "0 4px 12px rgba(0,0,0,0.8)" }} />
            {/* Shelf legs */}
            <div className="flex justify-between px-16 pb-6 pt-2">
              <div className="w-2 h-5 rounded-b" style={{ background: "#1A1A1A" }} />
              <div className="w-2 h-5 rounded-b" style={{ background: "#1A1A1A" }} />
            </div>
          </div>
        </div>

        {/* Bottom stats */}
        <div className="grid grid-cols-4 gap-4 mt-8">
          {[
            { label: "小说总数", value: "4", sub: "部作品" },
            { label: "章节总数", value: "145", sub: "章已完成" },
            { label: "AI生成率", value: "87%", sub: "章节由AI协助" },
            { label: "写作天数", value: "23", sub: "天创作历程" },
          ].map(({ label, value, sub }) => (
            <div key={label} className="p-4 rounded-xl border border-[#2A2A2A] bg-[#141414] text-center">
              <div style={{ fontFamily: "'Space Grotesk', sans-serif" }} className="text-2xl font-bold text-[#FFE500]">{value}</div>
              <div className="text-xs text-[#888888] mt-1">{label}</div>
              <div className="text-[10px] text-[#555] mt-0.5">{sub}</div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
