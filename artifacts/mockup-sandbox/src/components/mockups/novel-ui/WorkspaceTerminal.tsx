import React, { useState } from "react";
import { Search, Plus, BookOpen, Clock, Terminal, Library, Lightbulb, Settings, ChevronRight, Cpu } from "lucide-react";

const novels = [
  { id: "1", title: "星际穿越：黑暗森林的余烬", genre: "科幻", progress: 45, chaptersDone: 12, chaptersTotal: 30, lastEdited: "2小时前", status: "进行中" },
  { id: "2", title: "修仙纪元：从凡人到道祖", genre: "仙侠", progress: 80, chaptersDone: 80, chaptersTotal: 100, lastEdited: "1天前", status: "进行中" },
  { id: "3", title: "赛博朋克：霓虹雨下的武士", genre: "赛博朋克", progress: 100, chaptersDone: 50, chaptersTotal: 50, lastEdited: "3天前", status: "已完成" },
  { id: "4", title: "迷雾纪元", genre: "悬疑", progress: 15, chaptersDone: 3, chaptersTotal: 20, lastEdited: "1周前", status: "进行中" },
];

// Terminal green palette
const C = {
  bg: "#080C08",
  surface: "#0C110C",
  elevated: "#111811",
  border: "#1A2A1A",
  borderBright: "#2A4A2A",
  muted: "#4A6A4A",
  text: "#C8E6C8",
  textDim: "#6A946A",
  accent: "#4ADE80",      // terminal green
  accentDim: "#2A6A42",
  accentBright: "#86EFAC",
  warn: "#E8D44D",
  error: "#F87171",
  cursor: "#4ADE80",
};

const mono = { fontFamily: "'Roboto Mono', 'JetBrains Mono', 'Courier New', monospace" };

// ASCII progress bar
function AsciiBar({ value, width = 20 }: { value: number; width?: number }) {
  const filled = Math.round((value / 100) * width);
  const empty = width - filled;
  return (
    <span style={{ ...mono, fontSize: 11, color: value === 100 ? C.accentBright : C.accent }}>
      [{"█".repeat(filled)}{"░".repeat(empty)}] {value}%
    </span>
  );
}

function Prompt({ text }: { text: string }) {
  return (
    <span style={{ ...mono, fontSize: 11 }}>
      <span style={{ color: C.accentDim }}>~/arboris</span>
      <span style={{ color: C.muted }}>$</span>
      <span style={{ color: C.text }}> {text}</span>
    </span>
  );
}

export default function WorkspaceTerminal() {
  const [activeTab, setActiveTab] = useState("全部");
  const [searchQuery, setSearchQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const filtered = novels.filter(n => {
    if (activeTab !== "全部" && n.status !== activeTab) return false;
    if (searchQuery && !n.title.includes(searchQuery)) return false;
    return true;
  });

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, ...mono }}>
      {/* Scanlines overlay */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0, opacity: 0.03,
        backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,0,0.5) 2px, rgba(0,255,0,0.5) 3px)",
        backgroundSize: "100% 3px" }} />

      {/* Nav */}
      <header style={{ position: "sticky", top: 0, zIndex: 50, borderBottom: `1px solid ${C.border}`, background: C.surface }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Cpu size={18} color={C.accent} />
            <span style={{ fontSize: 15, fontWeight: 700, color: C.accent, letterSpacing: "0.1em" }}>
              ARBORIS_NOVEL
            </span>
            <span style={{ fontSize: 10, color: C.muted, marginLeft: 4 }}>v2.4.1</span>
          </div>
          <nav style={{ display: "flex", gap: 0 }}>
            {[
              { label: "INSPIRATION", active: false },
              { label: "LIBRARY", active: true },
              { label: "DESK", active: false },
              { label: "CONFIG", active: false },
            ].map(({ label, active }) => (
              <a key={label} href="#"
                style={{ padding: "0 16px", height: 55, display: "flex", alignItems: "center", fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", cursor: "pointer", textDecoration: "none", transition: "color .15s",
                  color: active ? C.accent : C.muted,
                  borderBottom: active ? `2px solid ${C.accent}` : "2px solid transparent" }}>
                {label}
              </a>
            ))}
          </nav>
          <div style={{ fontSize: 11, color: C.muted }}>
            <span style={{ color: C.accentDim }}>USER:</span> AX
            <span style={{ display: "inline-block", width: 8, height: 14, background: C.cursor, marginLeft: 6, animation: "blink 1s step-end infinite", verticalAlign: "middle" }} />
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "28px 24px", position: "relative", zIndex: 1 }}>
        {/* Prompt-style header */}
        <div style={{ marginBottom: 24, paddingBottom: 20, borderBottom: `1px solid ${C.border}` }}>
          <div style={{ marginBottom: 6 }}><Prompt text="ls --filter=novels --sort=recent" /></div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
            <div>
              <h1 style={{ fontSize: 22, fontWeight: 700, color: C.accentBright, margin: "10px 0 4px", letterSpacing: "0.04em" }}>
                MY_NOVEL_LIBRARY
              </h1>
              <span style={{ fontSize: 11, color: C.muted }}>{novels.length} items found · sorted by last_modified</span>
            </div>
            <button style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 16px", border: `1px solid ${C.accentDim}`, borderRadius: 4, background: "transparent", color: C.accent, fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", letterSpacing: "0.08em" }}>
              <Plus size={13} />NEW_NOVEL
            </button>
          </div>
        </div>

        {/* Filters */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, gap: 16 }}>
          <div style={{ display: "flex", gap: 2 }}>
            {["全部", "进行中", "已完成"].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                style={{ padding: "5px 14px", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", cursor: "pointer", border: "none", fontFamily: "inherit", transition: "all .15s",
                  background: activeTab === tab ? C.accentDim : "transparent",
                  color: activeTab === tab ? C.accentBright : C.muted,
                  borderRadius: 3 }}>
                {tab.toUpperCase()}
              </button>
            ))}
          </div>
          <div style={{ position: "relative", width: 240 }}>
            <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", fontSize: 11, color: C.accentDim }}>/</span>
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="search novels..."
              style={{ width: "100%", paddingLeft: 22, paddingRight: 12, paddingTop: 7, paddingBottom: 7, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, fontSize: 12, fontFamily: "inherit", outline: "none", boxSizing: "border-box" }} />
          </div>
        </div>

        {/* Card grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          {filtered.map(novel => {
            const done = novel.progress === 100;
            return (
              <div key={novel.id}
                style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, overflow: "hidden", display: "flex", flexDirection: "column", transition: "border-color .15s", cursor: "pointer" }}
                onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = C.accentDim}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = C.border}
              >
                {/* Card header — like a terminal window title bar */}
                <div style={{ height: 28, background: C.elevated, borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 12px" }}>
                  <div style={{ display: "flex", gap: 5 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.error, opacity: 0.7 }} />
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.warn, opacity: 0.7 }} />
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: done ? C.accent : C.muted, opacity: done ? 1 : 0.5 }} />
                  </div>
                  <span style={{ fontSize: 10, color: C.muted, letterSpacing: "0.06em" }}>{novel.genre.toUpperCase()}</span>
                  <div style={{ position: "relative" }}>
                    <button onClick={() => setMenuOpen(menuOpen === novel.id ? null : novel.id)}
                      style={{ background: "transparent", border: "none", cursor: "pointer", color: C.muted, fontSize: 11, padding: 2, fontFamily: "inherit" }}>
                      ⋯
                    </button>
                    {menuOpen === novel.id && (
                      <div style={{ position: "absolute", right: 0, top: "100%", background: C.elevated, border: `1px solid ${C.borderBright}`, borderRadius: 4, minWidth: 110, zIndex: 10, padding: 4 }}>
                        {["rename()", "export_config()", "rm -rf"].map((item, i) => (
                          <button key={item} onClick={() => setMenuOpen(null)}
                            style={{ display: "block", width: "100%", padding: "7px 12px", background: "transparent", border: "none", color: i === 2 ? C.error : C.text, fontSize: 11, textAlign: "left", cursor: "pointer", fontFamily: "inherit" }}>
                            {item}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Card body */}
                <div style={{ padding: "14px 14px 10px", flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
                  <h3 style={{ fontSize: 13, fontWeight: 700, color: done ? C.accentBright : C.text, lineHeight: 1.45, margin: 0, letterSpacing: "0.01em" }}>
                    {novel.title}
                  </h3>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: C.muted, marginBottom: 2 }}>
                      <span>chapters</span>
                      <span style={{ color: C.textDim }}>{novel.chaptersDone}/{novel.chaptersTotal}</span>
                    </div>
                    <AsciiBar value={novel.progress} width={18} />
                  </div>

                  <div style={{ fontSize: 10, color: C.muted, display: "flex", alignItems: "center", gap: 6 }}>
                    <Clock size={10} />
                    <span>modified: {novel.lastEdited}</span>
                  </div>

                  {done && (
                    <div style={{ fontSize: 10, color: C.accent, display: "flex", alignItems: "center", gap: 4 }}>
                      <span>✓</span><span style={{ letterSpacing: "0.05em" }}>COMPLETED</span>
                    </div>
                  )}
                </div>

                {/* Card footer */}
                <div style={{ padding: "10px 14px 14px", display: "flex", gap: 8, borderTop: `1px solid ${C.border}` }}>
                  <button style={{ flex: 1, padding: "6px 0", borderRadius: 3, background: "transparent", border: `1px solid ${C.border}`, color: C.muted, fontSize: 11, cursor: "pointer", fontFamily: "inherit", letterSpacing: "0.05em" }}>
                    cat ./detail
                  </button>
                  <button style={{ flex: 1, padding: "6px 0", borderRadius: 3, background: C.accentDim, border: `1px solid ${C.accentDim}`, color: C.accentBright, fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", letterSpacing: "0.05em" }}>
                    vim ./write
                  </button>
                </div>
              </div>
            );
          })}

          {/* New slot */}
          <div style={{ border: `1px dashed ${C.border}`, borderRadius: 4, minHeight: 200, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10, cursor: "pointer", transition: "border-color .15s" }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = C.accentDim}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = C.border}>
            <Terminal size={18} color={C.muted} />
            <span style={{ fontSize: 11, color: C.muted, letterSpacing: "0.06em" }}>touch novel_new.md</span>
          </div>
        </div>

        {/* Status bar */}
        <div style={{ marginTop: 24, paddingTop: 14, borderTop: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", fontSize: 10, color: C.muted }}>
          <span><span style={{ color: C.accentDim }}>STATUS:</span> {filtered.length}/{novels.length} items displayed</span>
          <span><span style={{ color: C.accentDim }}>SESSION:</span> 3h 42m active</span>
          <span><span style={{ color: C.accentDim }}>AI_OPS:</span> ready</span>
        </div>
      </main>
    </div>
  );
}
