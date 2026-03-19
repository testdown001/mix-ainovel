import React, { useState } from 'react';
import { ArrowLeft, BookOpen, ChevronRight, FileText, List, Loader2, MoreVertical, Play, RefreshCw, Settings, Star, History, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';

const chapters = [
  { id: 1, title: '第一章 序幕：风起云涌', status: 'generated' },
  { id: 2, title: '第二章 命运的齿轮', status: 'generated' },
  { id: 3, title: '第三章 觉醒', status: 'generating' },
  { id: 4, title: '第四章 黑暗中的低语', status: 'pending' },
  { id: 5, title: '第五章 初入江湖', status: 'empty' },
  { id: 6, title: '第六章 神秘老者', status: 'empty' },
  { id: 7, title: '第七章 遗迹之谜', status: 'empty' },
  { id: 8, title: '第八章 险象环生', status: 'empty' },
  { id: 9, title: '第九章 突破', status: 'empty' },
  { id: 10, title: '第十章 新的征程', status: 'empty' },
];

export default function WritingDesk() {
  const [activeChapter, setActiveChapter] = useState(3);
  
  const currentChapter = chapters.find(c => c.id === activeChapter);

  return (
    <div className="flex h-screen w-full flex-col bg-[#0A0A0A] text-white overflow-hidden font-sans">
      {/* Header */}
      <header className="flex h-14 items-center justify-between border-b border-[#2A2A2A] bg-[#141414] px-4 shrink-0">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" className="text-[#888888] hover:text-white hover:bg-[#2A2A2A]">
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-lg font-bold">星辰变：起源</h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#1C1C1C] text-[#888888] border border-[#2A2A2A]">
              连载中
            </span>
          </div>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 w-48">
            <span className="text-xs text-[#888888]">进度 12/30章</span>
            <Progress value={40} className="h-1.5 flex-1 bg-[#1C1C1C]" indicatorClassName="bg-[#FFE500]" />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-8 border-[#2A2A2A] bg-transparent text-[#888888] hover:text-white hover:bg-[#1C1C1C]">
              查看详情
            </Button>
            <Button variant="outline" size="sm" className="h-8 border-[#2A2A2A] bg-transparent text-[#888888] hover:text-white hover:bg-[#1C1C1C]">
              生成大纲
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-[#888888] hover:text-white hover:bg-[#2A2A2A]">
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar - Chapter List */}
        <aside className="w-[280px] flex flex-col border-r border-[#2A2A2A] bg-[#141414] shrink-0">
          <div className="p-4 border-b border-[#2A2A2A] flex justify-between items-center">
            <h2 className="font-medium text-sm text-[#888888]">章节列表</h2>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-[#888888] hover:text-white">
              <List className="h-4 w-4" />
            </Button>
          </div>
          
          <ScrollArea className="flex-1">
            <div className="p-2 space-y-1">
              {chapters.map((chapter) => (
                <button
                  key={chapter.id}
                  onClick={() => setActiveChapter(chapter.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors text-left
                    ${activeChapter === chapter.id 
                      ? 'bg-[#1C1C1C] text-white' 
                      : 'text-[#888888] hover:bg-[#1C1C1C] hover:text-gray-300'
                    }`}
                >
                  <div className="relative flex items-center justify-center w-4 h-4 shrink-0">
                    {chapter.status === 'generated' && <div className="w-2 h-2 rounded-full bg-[#2ED573]" />}
                    {chapter.status === 'generating' && <Loader2 className="w-3.5 h-3.5 text-[#FFE500] animate-spin" />}
                    {chapter.status === 'pending' && <div className="w-2 h-2 rounded-full bg-[#FFE500]" />}
                    {chapter.status === 'empty' && <div className="w-2 h-2 rounded-full bg-[#2A2A2A]" />}
                  </div>
                  <span className="truncate flex-1">{chapter.title}</span>
                  {activeChapter === chapter.id && (
                    <ChevronRight className="w-4 h-4 text-[#888888] shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </ScrollArea>
          
          <div className="p-4 border-t border-[#2A2A2A] bg-[#141414]">
            <Button className="w-full bg-[#FFE500] text-black hover:bg-[#FFE500]/90 font-medium">
              <Sparkles className="w-4 h-4 mr-2" />
              批量生成章节
            </Button>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 relative flex bg-[#0A0A0A]">
          <div className="flex-1 flex flex-col items-center overflow-y-auto pt-12 pb-32 px-8">
            <div className="w-full max-w-3xl">
              <h1 className="text-3xl font-display font-bold mb-8 text-center">{currentChapter?.title}</h1>
              
              {currentChapter?.status === 'generating' ? (
                <div className="space-y-8 animate-pulse">
                  <div className="flex items-center justify-center py-12 flex-col gap-4">
                    <div className="w-12 h-12 rounded-full bg-[#1C1C1C] flex items-center justify-center">
                      <Loader2 className="w-6 h-6 text-[#FFE500] animate-spin" />
                    </div>
                    <p className="text-[#888888] text-sm">AI正在创作第3章，融入设定与伏笔...</p>
                  </div>
                  
                  <div className="space-y-4">
                    <Skeleton className="h-4 w-full bg-[#1C1C1C]" />
                    <Skeleton className="h-4 w-[90%] bg-[#1C1C1C]" />
                    <Skeleton className="h-4 w-[95%] bg-[#1C1C1C]" />
                    <Skeleton className="h-4 w-[80%] bg-[#1C1C1C]" />
                  </div>
                  <div className="space-y-4">
                    <Skeleton className="h-4 w-full bg-[#1C1C1C]" />
                    <Skeleton className="h-4 w-[85%] bg-[#1C1C1C]" />
                    <Skeleton className="h-4 w-[90%] bg-[#1C1C1C]" />
                  </div>
                </div>
              ) : currentChapter?.status === 'generated' ? (
                <div className="prose prose-invert prose-lg max-w-none text-gray-300 leading-relaxed">
                  <p>夜色如墨，繁星隐没在厚重的云层之后。林风站在悬崖边缘，任由凛冽的寒风如刀般刮过面颊。他的目光穿透重重黑暗，死死地盯着深渊下方那隐约闪烁的幽蓝光芒。</p>
                  <p>“这就是传说中的起源之地吗？”他喃喃自语，声音很快被风声吞噬。</p>
                  <p>根据那张残破羊皮纸上的记载，这里埋藏着足以颠覆整个修真界格局的秘密。但他知道，盯上这块肥肉的，绝不止他一个人。就在半个时辰前，他已经察觉到了三股若有若无的杀气，正从不同方向悄然逼近。</p>
                  <p>林风深吸一口气，体内的真气开始以一种奇异的韵律运转。这是他偶然得来的无名功法，虽然残缺不全，却能在关键时刻爆发出远超同阶修士的威力。</p>
                  <p>“既然来了，何必藏头露尾！”林风突然暴喝一声，右手猛地拔出身后的玄铁重剑，顺势向后方一记横扫。</p>
                  <p>铮——！</p>
                  <p>刺耳的金铁交加声在夜空中激荡开来，火花四溅。一个身穿黑袍的干瘦身影从阴影中跌退而出，眼中满是不可思议：“你区区一个筑基期，怎么可能看破我的匿影术？”</p>
                  <p>“死人不需要知道答案。”林风眼神冰冷，没有丝毫废话，提剑再次欺身而上。</p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-32 text-center">
                  <div className="w-16 h-16 rounded-full bg-[#1C1C1C] flex items-center justify-center mb-6 text-[#888888]">
                    <FileText className="w-8 h-8" />
                  </div>
                  <h3 className="text-xl font-medium mb-2">本章尚未生成</h3>
                  <p className="text-[#888888] text-sm mb-8 max-w-md">
                    你可以手动编写本章内容，或者让 AI 根据大纲和上下文自动生成。
                  </p>
                  <Button className="bg-[#FFE500] text-black hover:bg-[#FFE500]/90">
                    <Sparkles className="w-4 h-4 mr-2" />
                    立即生成本章
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* AI Action Toolbar - Right Edge */}
          <div className="absolute right-6 top-1/2 -translate-y-1/2 flex flex-col gap-3">
            <div className="bg-[#1C1C1C] border border-[#2A2A2A] rounded-2xl p-2 flex flex-col gap-2 shadow-2xl backdrop-blur-sm bg-opacity-90">
              <Button variant="ghost" size="icon" className="w-10 h-10 rounded-xl text-[#FFE500] hover:bg-[#FFE500]/10 hover:text-[#FFE500]" title="生成本章">
                <Sparkles className="w-5 h-5" />
              </Button>
              <div className="h-px w-6 bg-[#2A2A2A] mx-auto" />
              <Button variant="ghost" size="icon" className="w-10 h-10 rounded-xl text-[#888888] hover:text-white hover:bg-[#2A2A2A]" title="重写">
                <RefreshCw className="w-5 h-5" />
              </Button>
              <Button variant="ghost" size="icon" className="w-10 h-10 rounded-xl text-[#888888] hover:text-white hover:bg-[#2A2A2A]" title="评估质量">
                <Star className="w-5 h-5" />
              </Button>
              <Button variant="ghost" size="icon" className="w-10 h-10 rounded-xl text-[#888888] hover:text-white hover:bg-[#2A2A2A]" title="版本历史">
                <History className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
