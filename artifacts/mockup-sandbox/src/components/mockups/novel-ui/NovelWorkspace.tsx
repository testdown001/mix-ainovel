import React, { useState } from "react";
import { 
  Search, 
  Plus, 
  BookOpen, 
  Clock, 
  MoreVertical, 
  PenTool,
  Library,
  Lightbulb,
  Settings,
  Sparkles
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Mock data
const mockNovels = [
  {
    id: "1",
    title: "星际穿越：黑暗森林的余烬",
    genre: "科幻",
    progress: 45,
    chaptersDone: 12,
    chaptersTotal: 30,
    lastEdited: "2小时前",
    status: "进行中",
    coverColor: "from-blue-900 to-indigo-900",
  },
  {
    id: "2",
    title: "修仙纪元：从凡人到道祖",
    genre: "仙侠",
    progress: 80,
    chaptersDone: 80,
    chaptersTotal: 100,
    lastEdited: "1天前",
    status: "进行中",
    coverColor: "from-emerald-900 to-teal-900",
  },
  {
    id: "3",
    title: "赛博朋克：霓虹雨下的武士",
    genre: "赛博朋克",
    progress: 100,
    chaptersDone: 50,
    chaptersTotal: 50,
    lastEdited: "3天前",
    status: "已完成",
    coverColor: "from-purple-900 to-fuchsia-900",
  },
  {
    id: "4",
    title: "迷雾纪元",
    genre: "悬疑",
    progress: 15,
    chaptersDone: 3,
    chaptersTotal: 20,
    lastEdited: "1周前",
    status: "进行中",
    coverColor: "from-zinc-800 to-zinc-900",
  },
];

export default function NovelWorkspace() {
  const [activeTab, setActiveTab] = useState("全部");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredNovels = mockNovels.filter((novel) => {
    if (activeTab !== "全部" && novel.status !== activeTab) return false;
    if (searchQuery && !novel.title.includes(searchQuery)) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white font-['Inter'] flex flex-col">
      {/* Navigation Bar */}
      <header className="sticky top-0 z-50 w-full border-b border-[#2A2A2A] bg-[#141414]/80 backdrop-blur-md">
        <div className="container mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-[#FFE500] flex items-center justify-center text-black">
              <Sparkles className="w-5 h-5" />
            </div>
            <span className="font-['Space_Grotesk'] font-bold text-xl tracking-tight">
              Arboris Novel
            </span>
          </div>
          
          <nav className="hidden md:flex items-center gap-8">
            <a href="#" className="flex items-center gap-2 text-[#888888] hover:text-white transition-colors">
              <Lightbulb className="w-4 h-4" />
              <span className="text-sm font-medium">灵感模式</span>
            </a>
            <a href="#" className="flex items-center gap-2 text-[#FFE500] transition-colors">
              <Library className="w-4 h-4" />
              <span className="text-sm font-medium">我的小说</span>
            </a>
            <a href="#" className="flex items-center gap-2 text-[#888888] hover:text-white transition-colors">
              <PenTool className="w-4 h-4" />
              <span className="text-sm font-medium">写作台</span>
            </a>
            <a href="#" className="flex items-center gap-2 text-[#888888] hover:text-white transition-colors">
              <Settings className="w-4 h-4" />
              <span className="text-sm font-medium">设置</span>
            </a>
          </nav>
          
          <div className="flex items-center gap-4">
            <Avatar className="w-9 h-9 border border-[#2A2A2A]">
              <AvatarImage src="https://github.com/shadcn.png" />
              <AvatarFallback className="bg-[#1C1C1C] text-[#FFE500]">AX</AvatarFallback>
            </Avatar>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 container mx-auto px-6 py-8">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-['Space_Grotesk'] font-bold text-white mb-2">我的小说库</h1>
            <p className="text-[#888888]">查看并管理你所有的小说项目</p>
          </div>
          <Button className="bg-[#FFE500] text-black hover:bg-[#FFE500]/90 font-semibold gap-2">
            <Plus className="w-4 h-4" />
            新建小说
          </Button>
        </div>

        {/* Filters and Search */}
        <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
          <Tabs defaultValue="全部" className="w-full md:w-auto" onValueChange={setActiveTab}>
            <TabsList className="bg-[#141414] border border-[#2A2A2A]">
              <TabsTrigger 
                value="全部" 
                className="data-[state=active]:bg-[#1C1C1C] data-[state=active]:text-[#FFE500]"
              >
                全部
              </TabsTrigger>
              <TabsTrigger 
                value="进行中"
                className="data-[state=active]:bg-[#1C1C1C] data-[state=active]:text-[#FFE500]"
              >
                进行中
              </TabsTrigger>
              <TabsTrigger 
                value="已完成"
                className="data-[state=active]:bg-[#1C1C1C] data-[state=active]:text-[#FFE500]"
              >
                已完成
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="relative w-full md:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#888888]" />
            <Input 
              placeholder="搜索小说..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-[#141414] border-[#2A2A2A] text-white focus-visible:ring-[#FFE500] placeholder:text-[#888888]"
            />
          </div>
        </div>

        {/* Novel Grid */}
        {filteredNovels.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredNovels.map((novel) => (
              <Card key={novel.id} className="bg-[#141414] border-[#2A2A2A] overflow-hidden flex flex-col transition-all hover:border-[#FFE500]/50 hover:shadow-[0_0_15px_rgba(255,229,0,0.1)] group">
                {/* Card Top "Cover" area */}
                <div className={`h-24 bg-gradient-to-br ${novel.coverColor} relative p-4 flex flex-col justify-between`}>
                  <div className="flex justify-between items-start">
                    <Badge variant="secondary" className="bg-black/40 hover:bg-black/60 text-[#FFE500] border-none backdrop-blur-sm">
                      {novel.genre}
                    </Badge>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-white hover:bg-white/20">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="bg-[#1C1C1C] border-[#2A2A2A] text-white">
                        <DropdownMenuItem className="hover:bg-[#2A2A2A] hover:text-[#FFE500] focus:bg-[#2A2A2A] focus:text-[#FFE500] cursor-pointer">
                          重命名
                        </DropdownMenuItem>
                        <DropdownMenuItem className="hover:bg-[#2A2A2A] hover:text-[#FFE500] focus:bg-[#2A2A2A] focus:text-[#FFE500] cursor-pointer">
                          导出配置
                        </DropdownMenuItem>
                        <DropdownMenuItem className="text-[#FF4757] hover:bg-[#FF4757]/10 focus:bg-[#FF4757]/10 cursor-pointer">
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
                
                <CardHeader className="pt-4 pb-2">
                  <h3 className="font-['Space_Grotesk'] font-bold text-lg text-white group-hover:text-[#FFE500] transition-colors line-clamp-1">
                    {novel.title}
                  </h3>
                </CardHeader>
                
                <CardContent className="pb-4 flex-1">
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm text-[#888888]">
                      <Clock className="w-4 h-4" />
                      <span>上次编辑：{novel.lastEdited}</span>
                    </div>
                    
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-[#888888]">创作进度</span>
                        <span className="text-white font-medium">{novel.chaptersDone} / {novel.chaptersTotal} 章</span>
                      </div>
                      <Progress 
                        value={novel.progress} 
                        className="h-2 bg-[#1C1C1C]" 
                        indicatorClassName={novel.progress === 100 ? "bg-[#2ED573]" : "bg-[#FFE500]"}
                      />
                    </div>
                  </div>
                </CardContent>
                
                <CardFooter className="pt-0 pb-4 flex gap-3">
                  <Button className="flex-1 bg-[#1C1C1C] text-white hover:bg-[#2A2A2A] border border-[#2A2A2A]">
                    <BookOpen className="w-4 h-4 mr-2" />
                    查看详情
                  </Button>
                  <Button className="flex-1 bg-[#FFE500]/10 text-[#FFE500] hover:bg-[#FFE500]/20 border border-[#FFE500]/30">
                    <PenTool className="w-4 h-4 mr-2" />
                    进入写作台
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        ) : (
          /* Empty State */
          <div className="flex flex-col items-center justify-center py-20 px-4 border border-dashed border-[#2A2A2A] rounded-lg bg-[#141414]">
            <div className="w-24 h-24 bg-[#1C1C1C] rounded-full flex items-center justify-center mb-6">
              <Library className="w-10 h-10 text-[#888888]" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">没有找到相关小说</h3>
            <p className="text-[#888888] mb-8 text-center max-w-md">
              还没有小说，去灵感模式开始吧~ 让AI帮助你从零构建一个完整的世界。
            </p>
            <div className="flex gap-4">
              <Button className="bg-[#FFE500] text-black hover:bg-[#FFE500]/90 font-semibold gap-2">
                <Plus className="w-4 h-4" />
                新建小说
              </Button>
              <Button variant="outline" className="border-[#2A2A2A] text-white hover:bg-[#1C1C1C] hover:text-white gap-2">
                <Lightbulb className="w-4 h-4 text-[#FFE500]" />
                进入灵感模式
              </Button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
