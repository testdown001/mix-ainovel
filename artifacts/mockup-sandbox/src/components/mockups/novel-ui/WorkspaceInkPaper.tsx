import React, { useState } from "react";
import { Search, Plus, BookOpen, Clock, MoreVertical, PenTool, Library, Lightbulb, Settings, Feather } from "lucide-react";

const novels = [
  { id: "1", title: "星际穿越：黑暗森林的余烬", genre: "科幻", progress: 45, chaptersDone: 12, chaptersTotal: 30, lastEdited: "2小时前", status: "进行中" },
  { id: "2", title: "修仙纪元：从凡人到道祖", genre: "仙侠", progress: 80, chaptersDone: 80, chaptersTotal: 100, lastEdited: "1天前", status: "进行中" },
  { id: "3", title: "赛博朋克：霓虹雨下的武士", genre: "赛博朋克", progress: 100, chaptersDone: 50, chaptersTotal: 50, lastEdited: "3天前", status: "已完成" },
  { id: "4", title: "迷雾纪元", genre: "悬疑", progress: 15, chaptersDone: 3, chaptersTotal: 20, lastEdited: "1周前", status: "进行中" },
];

// Warm sepia-amber palette
const C = {
  bg: "#0D0B09",
  surface: "#16120E",
  elevated: "#1E1912",
  border: "#2E2820",
  borderLight: "#3D3428",
  muted: "#7A6E5F",
  text: "#EDE4D4",
  textSub: "#9A8E7E",
  accent: "#D4A853",         // warm amber gold
  accentLight: "#E8C882",
  accentContainer: "#2A2010",
  success: "#6DBF87",
  successDim: "#1A2E1E",
  error: "#C97878",
};

const tag = { fontFamily: "Georgia, 'Times New Roman', serif" };

function NavLink({ icon: Icon, label, active }: { icon: any; label: string; active: boolean }) {
  return (
    <a href="#" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 500, color: active ? C.accent : C.muted, transition: "color .2s" }}>
      <Icon size={15} />
      {label}
    </a>
  );
}

export default function WorkspaceInkPaper() {
  const [activeTab, setActiveTab] = useState("全部");
  const [searchQuery, setSearchQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const filtered = novels.filter(n => {
    if (activeTab !== "全部" && n.status !== activeTab) return false;
    if (searchQuery && !n.title.includes(searchQuery)) return false;
    return true;
  });

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'Inter', Georgia, sans-serif" }}>
      {/* Nav */}
      <header style={{ position: "sticky", top: 0, zIndex: 50, borderBottom: `1px solid ${C.border}`, background: `${C.surface}E8`, backdropFilter: "blur(12px)" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px", height: 64, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {/* Logo — ink-pen mark */}
            <div style={{ width: 32, height: 32, borderRadius: 6, background: C.accentContainer, border: `1px solid ${C.borderLight}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Feather size={16} color={C.accent} />
            </div>
            <span style={{ ...tag, fontSize: 18, fontWeight: 700, color: C.text, letterSpacing: "0.02em" }}>
              Arboris Novel
            </span>
          </div>
          <nav style={{ display: "flex", gap: 32 }}>
            <NavLink icon={Lightbulb} label="灵感模式" active={false} />
            <NavLink icon={Library} label="我的小说" active={true} />
            <NavLink icon={PenTool} label="写作台" active={false} />
            <NavLink icon={Settings} label="设置" active={false} />
          </nav>
          <div style={{ width: 34, height: 34, borderRadius: "50%", border: `1px solid ${C.border}`, background: C.elevated, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, color: C.accent }}>
            AX
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "36px 24px" }}>
        {/* Page header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 32 }}>
          <div>
            <h1 style={{ ...tag, fontSize: 30, fontWeight: 700, color: C.text, marginBottom: 6, letterSpacing: "0.01em" }}>我的小说库</h1>
            <p style={{ fontSize: 14, color: C.muted, fontStyle: "italic" }}>查看并管理你所有的小说项目</p>
          </div>
          <button style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 18px", borderRadius: 6, background: C.accent, color: "#1A1208", fontWeight: 700, fontSize: 14, border: "none", cursor: "pointer", fontFamily: "inherit" }}>
            <Plus size={15} />新建小说
          </button>
        </div>

        {/* Filters + search */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28, gap: 16 }}>
          <div style={{ display: "flex", gap: 4, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: 4 }}>
            {["全部", "进行中", "已完成"].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                style={{ padding: "6px 16px", borderRadius: 6, fontSize: 13, fontWeight: 500, cursor: "pointer", border: "none", fontFamily: "inherit", transition: "all .2s",
                  background: activeTab === tab ? C.elevated : "transparent",
                  color: activeTab === tab ? C.accent : C.muted,
                  boxShadow: activeTab === tab ? `inset 0 0 0 1px ${C.borderLight}` : "none" }}>
                {tab}
              </button>
            ))}
          </div>
          <div style={{ position: "relative", width: 260 }}>
            <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: C.muted }} />
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="搜索小说..."
              style={{ width: "100%", paddingLeft: 36, paddingRight: 14, paddingTop: 9, paddingBottom: 9, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, fontSize: 13, fontFamily: "inherit", outline: "none", boxSizing: "border-box" }} />
          </div>
        </div>

        {/* Card grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
          {filtered.map(novel => {
            const done = novel.progress === 100;
            return (
              <div key={novel.id}
                style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, overflow: "hidden", display: "flex", flexDirection: "column", transition: "border-color .25s, box-shadow .25s", cursor: "pointer" }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = C.accentLight; (e.currentTarget as HTMLElement).style.boxShadow = `0 0 0 1px ${C.accentContainer}, 0 4px 20px rgba(0,0,0,0.4)` }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = C.border; (e.currentTarget as HTMLElement).style.boxShadow = "none" }}
              >
                {/* Card "cover" — textured warm dark band */}
                <div style={{ height: 88, background: `linear-gradient(135deg, ${C.elevated} 0%, ${C.accentContainer} 100%)`, position: "relative", padding: "14px 16px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  {/* Subtle diagonal lines texture */}
                  <div style={{ position: "absolute", inset: 0, opacity: 0.06, backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(255,255,255,0.5) 4px, rgba(255,255,255,0.5) 5px)" }} />
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", position: "relative" }}>
                    <span style={{ fontSize: 11, padding: "2px 10px", borderRadius: 20, fontWeight: 600, background: "rgba(0,0,0,0.35)", color: C.accentLight, backdropFilter: "blur(4px)", letterSpacing: "0.04em" }}>
                      {novel.genre}
                    </span>
                    <div style={{ position: "relative" }}>
                      <button onClick={() => setMenuOpen(menuOpen === novel.id ? null : novel.id)}
                        style={{ background: "transparent", border: "none", cursor: "pointer", color: C.muted, padding: 4, borderRadius: 4 }}>
                        <MoreVertical size={15} />
                      </button>
                      {menuOpen === novel.id && (
                        <div style={{ position: "absolute", right: 0, top: "100%", background: C.elevated, border: `1px solid ${C.border}`, borderRadius: 8, minWidth: 120, zIndex: 10, padding: 4 }}>
                          {["重命名", "导出配置"].map(item => (
                            <button key={item} onClick={() => setMenuOpen(null)}
                              style={{ display: "block", width: "100%", padding: "8px 14px", background: "transparent", border: "none", color: C.text, fontSize: 13, textAlign: "left", cursor: "pointer", fontFamily: "inherit", borderRadius: 4 }}>
                              {item}
                            </button>
                          ))}
                          <button onClick={() => setMenuOpen(null)}
                            style={{ display: "block", width: "100%", padding: "8px 14px", background: "transparent", border: "none", color: C.error, fontSize: 13, textAlign: "left", cursor: "pointer", fontFamily: "inherit", borderRadius: 4 }}>
                            删除
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Card body */}
                <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
                  <h3 style={{ ...tag, fontSize: 15, fontWeight: 700, color: C.text, lineHeight: 1.4, margin: 0 }}>
                    {novel.title}
                  </h3>

                  <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: C.muted }}>
                    <Clock size={12} />
                    <span>上次编辑：{novel.lastEdited}</span>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: C.muted }}>
                      <span style={{ fontStyle: "italic" }}>创作进度</span>
                      <span style={{ color: C.textSub, fontWeight: 600 }}>{novel.chaptersDone} / {novel.chaptersTotal} 章</span>
                    </div>
                    <div style={{ height: 3, borderRadius: 2, background: C.elevated, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${novel.progress}%`, background: done ? C.success : C.accent, borderRadius: 2, transition: "width .4s" }} />
                    </div>
                  </div>
                </div>

                {/* Card footer */}
                <div style={{ padding: "0 18px 16px", display: "flex", gap: 10 }}>
                  <button style={{ flex: 1, padding: "8px 0", borderRadius: 6, background: "transparent", border: `1px solid ${C.border}`, color: C.muted, fontSize: 13, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
                    <BookOpen size={13} />查看详情
                  </button>
                  <button style={{ flex: 1, padding: "8px 0", borderRadius: 6, background: C.accentContainer, border: `1px solid ${C.borderLight}`, color: C.accentLight, fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
                    <PenTool size={13} />进入写作台
                  </button>
                </div>
              </div>
            );
          })}

          {/* New project slot */}
          <div style={{ border: `2px dashed ${C.border}`, borderRadius: 10, minHeight: 220, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, cursor: "pointer", transition: "border-color .2s" }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = C.accentLight}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = C.border}>
            <div style={{ width: 42, height: 42, borderRadius: 8, background: C.accentContainer, border: `1px solid ${C.borderLight}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Plus size={18} color={C.accent} />
            </div>
            <span style={{ fontSize: 13, color: C.muted, fontStyle: "italic" }}>新建小说</span>
          </div>
        </div>
      </main>
    </div>
  );
}
