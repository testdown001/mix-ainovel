import React, { useState } from "react";
import { Search, Plus, BookOpen, Clock, MoreVertical, PenTool, Library, Lightbulb, Settings, Sparkles } from "lucide-react";

const novels = [
  { id: "1", title: "星际穿越：黑暗森林的余烬", genre: "科幻", progress: 45, chaptersDone: 12, chaptersTotal: 30, lastEdited: "2小时前", status: "进行中", hue: "210" },
  { id: "2", title: "修仙纪元：从凡人到道祖", genre: "仙侠", progress: 80, chaptersDone: 80, chaptersTotal: 100, lastEdited: "1天前", status: "进行中", hue: "160" },
  { id: "3", title: "赛博朋克：霓虹雨下的武士", genre: "赛博朋克", progress: 100, chaptersDone: 50, chaptersTotal: 50, lastEdited: "3天前", status: "已完成", hue: "280" },
  { id: "4", title: "迷雾纪元", genre: "悬疑", progress: 15, chaptersDone: 3, chaptersTotal: 20, lastEdited: "1周前", status: "进行中", hue: "230" },
];

// Ethereal deep indigo-violet palette
const C = {
  bg: "#050814",          // near-black indigo
  orb1: "#1A0A3E",        // deep purple orb color
  orb2: "#051830",        // deep blue orb color
  surface: "rgba(255,255,255,0.04)",
  surfaceHover: "rgba(255,255,255,0.07)",
  border: "rgba(255,255,255,0.08)",
  borderHover: "rgba(180,150,255,0.35)",
  muted: "rgba(200,190,230,0.45)",
  text: "rgba(235,230,255,0.95)",
  textSub: "rgba(200,190,230,0.65)",
  accent: "#B794F4",       // soft lavender
  accentBright: "#D6BCFA",
  accentGlow: "rgba(183,148,244,0.2)",
  cyan: "#76E4F7",
  cyanGlow: "rgba(118,228,247,0.15)",
  success: "#68D391",
  successGlow: "rgba(104,211,145,0.2)",
  error: "#FC8181",
};

const sans = { fontFamily: "'Inter', system-ui, sans-serif" };

export default function WorkspaceGlass() {
  const [activeTab, setActiveTab] = useState("全部");
  const [searchQuery, setSearchQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const filtered = novels.filter(n => {
    if (activeTab !== "全部" && n.status !== activeTab) return false;
    if (searchQuery && !n.title.includes(searchQuery)) return false;
    return true;
  });

  const getProgressColor = (n: typeof novels[0]) => {
    if (n.progress === 100) return `linear-gradient(90deg, ${C.success}, ${C.cyan})`;
    return `linear-gradient(90deg, hsla(${n.hue}, 70%, 65%, 0.9), hsla(${parseInt(n.hue) + 40}, 75%, 75%, 0.9))`;
  };

  const getCardGlow = (n: typeof novels[0]) => {
    return `0 0 30px hsla(${n.hue}, 70%, 55%, 0.12), 0 0 0 1px hsla(${n.hue}, 60%, 55%, 0.25)`;
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, ...sans, position: "relative", overflow: "hidden" }}>
      {/* Ambient background orbs */}
      <div style={{ position: "fixed", top: "-20%", left: "-10%", width: 500, height: 500, borderRadius: "50%", background: "radial-gradient(circle, rgba(88,28,135,0.25) 0%, transparent 70%)", pointerEvents: "none", zIndex: 0 }} />
      <div style={{ position: "fixed", top: "30%", right: "-15%", width: 600, height: 600, borderRadius: "50%", background: "radial-gradient(circle, rgba(17,24,95,0.35) 0%, transparent 70%)", pointerEvents: "none", zIndex: 0 }} />
      <div style={{ position: "fixed", bottom: "-20%", left: "30%", width: 400, height: 400, borderRadius: "50%", background: "radial-gradient(circle, rgba(6,78,59,0.15) 0%, transparent 70%)", pointerEvents: "none", zIndex: 0 }} />

      {/* Nav */}
      <header style={{ position: "sticky", top: 0, zIndex: 50, borderBottom: `1px solid ${C.border}`, background: "rgba(5,8,20,0.7)", backdropFilter: "blur(20px) saturate(180%)", WebkitBackdropFilter: "blur(20px)" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 28px", height: 64, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg, #7C3AED, #4F46E5)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 16px rgba(124,58,237,0.5)" }}>
              <Sparkles size={15} color="white" />
            </div>
            <span style={{ fontSize: 17, fontWeight: 700, background: "linear-gradient(90deg, #D6BCFA, #76E4F7)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", letterSpacing: "0.01em" }}>
              Arboris Novel
            </span>
          </div>
          <nav style={{ display: "flex", gap: 6 }}>
            {[
              { icon: Lightbulb, label: "灵感模式", active: false },
              { icon: Library, label: "我的小说", active: true },
              { icon: PenTool, label: "写作台", active: false },
              { icon: Settings, label: "设置", active: false },
            ].map(({ icon: Icon, label, active }) => (
              <a key={label} href="#"
                style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer", textDecoration: "none", transition: "all .2s",
                  color: active ? C.accentBright : C.muted,
                  background: active ? C.accentGlow : "transparent",
                  border: active ? `1px solid rgba(183,148,244,0.2)` : "1px solid transparent" }}>
                <Icon size={14} />{label}
              </a>
            ))}
          </nav>
          <div style={{ width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg, rgba(124,58,237,0.3), rgba(79,70,229,0.2))", border: `1px solid rgba(183,148,244,0.25)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: C.accentBright }}>
            AX
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "40px 28px", position: "relative", zIndex: 1 }}>
        {/* Page header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 36 }}>
          <div>
            <h1 style={{ fontSize: 32, fontWeight: 700, margin: "0 0 8px", lineHeight: 1.2, background: "linear-gradient(135deg, #E9D5FF 0%, #A5F3FC 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              我的小说库
            </h1>
            <p style={{ fontSize: 14, color: C.muted, margin: 0 }}>查看并管理你所有的小说项目</p>
          </div>
          <button style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 22px", borderRadius: 10, background: "linear-gradient(135deg, #7C3AED, #4F46E5)", color: "white", fontWeight: 600, fontSize: 14, border: "none", cursor: "pointer", fontFamily: "inherit", boxShadow: "0 4px 20px rgba(124,58,237,0.4), inset 0 1px 0 rgba(255,255,255,0.15)" }}>
            <Plus size={15} />新建小说
          </button>
        </div>

        {/* Filters + search */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28, gap: 16 }}>
          <div style={{ display: "flex", gap: 6, padding: "4px", background: "rgba(255,255,255,0.03)", borderRadius: 12, border: `1px solid ${C.border}` }}>
            {["全部", "进行中", "已完成"].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                style={{ padding: "7px 20px", borderRadius: 9, fontSize: 13, fontWeight: 500, cursor: "pointer", border: "none", fontFamily: "inherit", transition: "all .25s",
                  background: activeTab === tab ? "rgba(124,58,237,0.25)" : "transparent",
                  color: activeTab === tab ? C.accentBright : C.muted,
                  boxShadow: activeTab === tab ? `0 0 0 1px rgba(183,148,244,0.3), inset 0 1px 0 rgba(255,255,255,0.08)` : "none" }}>
                {tab}
              </button>
            ))}
          </div>
          <div style={{ position: "relative", width: 280 }}>
            <Search size={14} style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: C.muted }} />
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="搜索小说..."
              style={{ width: "100%", paddingLeft: 40, paddingRight: 16, paddingTop: 10, paddingBottom: 10, background: "rgba(255,255,255,0.04)", border: `1px solid ${C.border}`, borderRadius: 10, color: C.text, fontSize: 13, fontFamily: "inherit", outline: "none", boxSizing: "border-box", backdropFilter: "blur(8px)" }} />
          </div>
        </div>

        {/* Card grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 18 }}>
          {filtered.map(novel => {
            const isHovered = hovered === novel.id;
            const done = novel.progress === 100;
            return (
              <div key={novel.id}
                style={{ background: isHovered ? C.surfaceHover : C.surface, border: isHovered ? `1px solid hsla(${novel.hue}, 60%, 60%, 0.3)` : `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden", display: "flex", flexDirection: "column", transition: "all .3s cubic-bezier(0.34,1.56,0.64,1)", cursor: "pointer", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)",
                  boxShadow: isHovered ? getCardGlow(novel) : "none",
                  transform: isHovered ? "translateY(-3px)" : "none" }}
                onMouseEnter={() => setHovered(novel.id)}
                onMouseLeave={() => setHovered(null)}
              >
                {/* Card header — gradient shimmer */}
                <div style={{ height: 88, background: `linear-gradient(135deg, hsla(${novel.hue}, 70%, 20%, 0.4) 0%, hsla(${parseInt(novel.hue) + 40}, 65%, 15%, 0.3) 100%)`, position: "relative", padding: "14px 16px", display: "flex", flexDirection: "column", justifyContent: "space-between", overflow: "hidden" }}>
                  {/* Inner glow */}
                  <div style={{ position: "absolute", top: -20, right: -20, width: 80, height: 80, borderRadius: "50%", background: `radial-gradient(circle, hsla(${novel.hue}, 80%, 65%, 0.2) 0%, transparent 70%)`, pointerEvents: "none" }} />
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", position: "relative" }}>
                    <span style={{ fontSize: 11, padding: "3px 12px", borderRadius: 20, fontWeight: 600, background: `hsla(${novel.hue}, 60%, 50%, 0.2)`, color: `hsla(${novel.hue}, 90%, 80%, 1)`, border: `1px solid hsla(${novel.hue}, 60%, 60%, 0.25)`, backdropFilter: "blur(8px)" }}>
                      {novel.genre}
                    </span>
                    <div style={{ position: "relative" }}>
                      <button onClick={() => setMenuOpen(menuOpen === novel.id ? null : novel.id)}
                        style={{ background: "rgba(255,255,255,0.1)", border: "none", cursor: "pointer", color: C.muted, padding: 5, borderRadius: 6, backdropFilter: "blur(8px)" }}>
                        <MoreVertical size={13} />
                      </button>
                      {menuOpen === novel.id && (
                        <div style={{ position: "absolute", right: 0, top: "100%", background: "rgba(15,10,35,0.95)", border: `1px solid ${C.border}`, borderRadius: 10, minWidth: 130, zIndex: 10, padding: 6, backdropFilter: "blur(20px)" }}>
                          {["重命名", "导出配置"].map(item => (
                            <button key={item} onClick={() => setMenuOpen(null)}
                              style={{ display: "block", width: "100%", padding: "9px 14px", background: "transparent", border: "none", color: C.text, fontSize: 13, textAlign: "left", cursor: "pointer", fontFamily: "inherit", borderRadius: 6 }}>
                              {item}
                            </button>
                          ))}
                          <button onClick={() => setMenuOpen(null)}
                            style={{ display: "block", width: "100%", padding: "9px 14px", background: "transparent", border: "none", color: C.error, fontSize: 13, textAlign: "left", cursor: "pointer", fontFamily: "inherit", borderRadius: 6 }}>
                            删除
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Body */}
                <div style={{ padding: "18px 18px 14px", flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, lineHeight: 1.45, margin: 0 }}>
                    {novel.title}
                  </h3>

                  <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: C.muted }}>
                    <Clock size={11} />
                    <span>上次编辑：{novel.lastEdited}</span>
                  </div>

                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 7 }}>
                      <span style={{ color: C.muted }}>创作进度</span>
                      <span style={{ color: C.textSub, fontWeight: 600 }}>{novel.chaptersDone} / {novel.chaptersTotal} 章</span>
                    </div>
                    <div style={{ height: 3, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${novel.progress}%`, background: getProgressColor(novel), borderRadius: 2, boxShadow: done ? `0 0 8px ${C.success}` : `0 0 8px hsla(${novel.hue}, 70%, 65%, 0.5)`, transition: "width .5s" }} />
                    </div>
                  </div>
                </div>

                {/* Footer */}
                <div style={{ padding: "0 18px 18px", display: "flex", gap: 10 }}>
                  <button style={{ flex: 1, padding: "9px 0", borderRadius: 8, background: "rgba(255,255,255,0.04)", border: `1px solid ${C.border}`, color: C.muted, fontSize: 13, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", justifyContent: "center", gap: 6, backdropFilter: "blur(8px)", transition: "all .2s" }}>
                    <BookOpen size={13} />查看详情
                  </button>
                  <button style={{ flex: 1, padding: "9px 0", borderRadius: 8, background: `linear-gradient(135deg, hsla(${novel.hue}, 60%, 30%, 0.5), hsla(${parseInt(novel.hue)+30}, 60%, 25%, 0.5))`, border: `1px solid hsla(${novel.hue}, 60%, 55%, 0.25)`, color: `hsla(${novel.hue}, 90%, 80%, 1)`, fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", justifyContent: "center", gap: 6, backdropFilter: "blur(8px)", transition: "all .2s" }}>
                    <PenTool size={13} />进入写作台
                  </button>
                </div>
              </div>
            );
          })}

          {/* Add new slot */}
          <div style={{ border: `1.5px dashed rgba(255,255,255,0.1)`, borderRadius: 14, minHeight: 230, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, cursor: "pointer", transition: "all .3s", backdropFilter: "blur(8px)" }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "rgba(183,148,244,0.35)"; (e.currentTarget as HTMLElement).style.background = "rgba(124,58,237,0.06)" }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.1)"; (e.currentTarget as HTMLElement).style.background = "transparent" }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: "rgba(124,58,237,0.15)", border: "1px solid rgba(183,148,244,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Plus size={18} color={C.accent} />
            </div>
            <span style={{ fontSize: 13, color: C.muted }}>新建小说</span>
          </div>
        </div>
      </main>
    </div>
  );
}
