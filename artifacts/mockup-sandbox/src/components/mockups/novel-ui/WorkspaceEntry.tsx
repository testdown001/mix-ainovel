import React from "react";
import { 
  Bell, 
  BookOpen, 
  ChevronRight, 
  Clock, 
  Lightbulb, 
  LogOut, 
  PenTool, 
  Settings, 
  User, 
  Plus
} from "lucide-react";
import { 
  Avatar, 
  AvatarFallback, 
  AvatarImage 
} from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function WorkspaceEntry() {
  return (
    <div className="min-h-screen bg-[#0A0A0A] text-[#FFFFFF] font-sans selection:bg-[#FFE500] selection:text-black">
      {/* Navigation Bar */}
      <header className="sticky top-0 z-50 w-full border-b border-[#2A2A2A] bg-[#0A0A0A]/80 backdrop-blur-md">
        <div className="container mx-auto flex h-16 items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#FFE500]">
              <PenTool className="h-5 w-5 text-black" />
            </div>
            <span className="text-xl font-bold tracking-tight text-white font-display">
              Arboris Novel
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-6">
            <a href="#" className="text-sm font-medium text-white hover:text-[#FFE500] transition-colors">
              灵感模式
            </a>
            <a href="#" className="text-sm font-medium text-[#888888] hover:text-[#FFE500] transition-colors">
              我的小说
            </a>
            <a href="#" className="text-sm font-medium text-[#888888] hover:text-[#FFE500] transition-colors">
              写作台
            </a>
            <a href="#" className="text-sm font-medium text-[#888888] hover:text-[#FFE500] transition-colors">
              设置
            </a>
          </nav>

          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" className="text-[#888888] hover:text-white hover:bg-[#141414]">
              <Bell className="h-5 w-5" />
            </Button>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-9 w-9 rounded-full">
                  <Avatar className="h-9 w-9 border border-[#2A2A2A]">
                    <AvatarImage src="https://i.pravatar.cc/150?u=a042581f4e29026024d" alt="@user" />
                    <AvatarFallback className="bg-[#1C1C1C] text-white">CN</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56 bg-[#141414] border-[#2A2A2A] text-white" align="end" forceMount>
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-1">
                    <p className="text-sm font-medium leading-none">Creator Name</p>
                    <p className="text-xs leading-none text-[#888888]">
                      creator@example.com
                    </p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-[#2A2A2A]" />
                <DropdownMenuItem className="hover:bg-[#1C1C1C] focus:bg-[#1C1C1C] cursor-pointer">
                  <User className="mr-2 h-4 w-4 text-[#888888]" />
                  <span>个人主页</span>
                </DropdownMenuItem>
                <DropdownMenuItem className="hover:bg-[#1C1C1C] focus:bg-[#1C1C1C] cursor-pointer">
                  <Settings className="mr-2 h-4 w-4 text-[#888888]" />
                  <span>账户设置</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-[#2A2A2A]" />
                <DropdownMenuItem className="hover:bg-[#1C1C1C] focus:bg-[#1C1C1C] text-[#FF4757] focus:text-[#FF4757] cursor-pointer">
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>退出登录</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 md:px-6 md:py-12">
        {/* Hero Section */}
        <div className="mb-12">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight font-display mb-4">
            下午好，<span className="text-transparent bg-clip-text bg-gradient-to-r from-[#FFE500] to-[#FFB000]">创作者</span> 👋
          </h1>
          <p className="text-[#888888] text-lg mb-8">
            准备好继续你的创作之旅了吗？
          </p>

          {/* Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl">
            <div className="bg-[#141414] border border-[#2A2A2A] rounded-xl p-4 flex flex-col justify-center">
              <span className="text-[#888888] text-sm font-medium mb-1">已建小说</span>
              <span className="text-3xl font-bold font-display">4</span>
            </div>
            <div className="bg-[#141414] border border-[#2A2A2A] rounded-xl p-4 flex flex-col justify-center">
              <span className="text-[#888888] text-sm font-medium mb-1">已写章节</span>
              <span className="text-3xl font-bold font-display">128</span>
            </div>
            <div className="bg-[#141414] border border-[#2A2A2A] rounded-xl p-4 flex flex-col justify-center">
              <span className="text-[#888888] text-sm font-medium mb-1">AI生成字数</span>
              <span className="text-3xl font-bold font-display text-[#FFE500]">34.2<span className="text-lg text-[#888888] ml-1">w</span></span>
            </div>
            <div className="bg-[#141414] border border-[#2A2A2A] rounded-xl p-4 flex flex-col justify-center">
              <span className="text-[#888888] text-sm font-medium mb-1">连续创作</span>
              <span className="text-3xl font-bold font-display">12<span className="text-lg text-[#888888] ml-1">天</span></span>
            </div>
          </div>
        </div>

        {/* Big Action Cards */}
        <div className="grid md:grid-cols-2 gap-6 mb-12">
          {/* Action Card 1 */}
          <Card className="bg-gradient-to-br from-[#1C1C0A] to-[#141414] border-[#FFE500]/30 hover:border-[#FFE500] transition-all group cursor-pointer relative overflow-hidden h-full">
            <div className="absolute right-0 top-0 w-64 h-64 bg-[#FFE500]/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 group-hover:bg-[#FFE500]/10 transition-colors"></div>
            <CardHeader>
              <div className="h-12 w-12 rounded-xl bg-[#FFE500]/10 flex items-center justify-center mb-4 text-[#FFE500] group-hover:scale-110 transition-transform">
                <Lightbulb className="h-6 w-6" />
              </div>
              <CardTitle className="text-2xl font-display text-white group-hover:text-[#FFE500] transition-colors">灵感模式</CardTitle>
              <CardDescription className="text-[#888888] text-base mt-2">
                还没有故事？让AI引导你从零开始。设定世界观、构建人物关系、生成完美大纲。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button className="bg-[#FFE500] text-black hover:bg-[#FFE500]/90 font-medium mt-2">
                开始探索 <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>

          {/* Action Card 2 */}
          <Card className="bg-[#141414] border-[#2A2A2A] hover:border-white transition-all group cursor-pointer h-full">
            <CardHeader>
              <div className="h-12 w-12 rounded-xl bg-[#1C1C1C] flex items-center justify-center mb-4 text-white group-hover:scale-110 transition-transform">
                <BookOpen className="h-6 w-6" />
              </div>
              <CardTitle className="text-2xl font-display text-white">我的小说库</CardTitle>
              <CardDescription className="text-[#888888] text-base mt-2">
                查看并管理你所有的小说项目。继续未完成的章节，或者调整已有的设定。
              </CardDescription>
            </CardHeader>
            <CardContent className="flex gap-3 mt-2">
              <Button variant="outline" className="border-[#2A2A2A] bg-transparent text-white hover:bg-[#1C1C1C] hover:text-white font-medium">
                进入书库 <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
              <Button variant="ghost" className="text-[#888888] hover:text-white hover:bg-[#1C1C1C]">
                <Plus className="mr-2 h-4 w-4" /> 新建小说
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Bottom Section: Recent Activity & Logs */}
        <div className="grid md:grid-cols-3 gap-8">
          {/* Recent Activity */}
          <div className="md:col-span-2 space-y-4">
            <h3 className="text-xl font-bold font-display flex items-center gap-2">
              <Clock className="h-5 w-5 text-[#888888]" /> 最近编辑
            </h3>
            <div className="space-y-3">
              {[
                { title: '赛博修仙传', chapter: '第42章：云端飞剑', time: '2小时前', progress: 85 },
                { title: '星际领航员', chapter: '第12章：跃迁失败', time: '昨天 15:30', progress: 100 },
                { title: '废土行者', chapter: '第3章：遗迹探索', time: '2天前', progress: 30 }
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between p-4 bg-[#141414] border border-[#2A2A2A] rounded-xl hover:border-[#888888] transition-colors cursor-pointer group">
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 rounded bg-[#1C1C1C] flex items-center justify-center border border-[#2A2A2A] group-hover:border-[#FFE500]/50 transition-colors">
                      <BookOpen className="h-5 w-5 text-[#888888] group-hover:text-[#FFE500] transition-colors" />
                    </div>
                    <div>
                      <h4 className="font-medium text-white group-hover:text-[#FFE500] transition-colors">{item.title}</h4>
                      <p className="text-sm text-[#888888]">{item.chapter}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="hidden sm:flex flex-col items-end">
                      <span className="text-xs font-medium text-[#888888] mb-1">完成度</span>
                      <div className="w-24 h-1.5 bg-[#1C1C1C] rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-[#FFE500]" 
                          style={{ width: `${item.progress}%` }}
                        ></div>
                      </div>
                    </div>
                    <div className="text-sm text-[#888888] w-20 text-right">
                      {item.time}
                    </div>
                    <ChevronRight className="h-4 w-4 text-[#888888] group-hover:text-white transition-colors" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Update Log */}
          <div className="space-y-4">
            <h3 className="text-xl font-bold font-display flex items-center gap-2">
              <Bell className="h-5 w-5 text-[#888888]" /> 系统更新
            </h3>
            <div className="bg-[#141414] border border-[#2A2A2A] rounded-xl p-5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-16 h-16 bg-[#FFE500]/5 rounded-bl-full"></div>
              
              <div className="mb-4">
                <span className="inline-block px-2 py-1 bg-[#2ED573]/10 text-[#2ED573] text-xs font-medium rounded mb-2">v2.4.0</span>
                <h4 className="font-medium text-white mb-1">更强大的世界观生成器</h4>
                <p className="text-sm text-[#888888] line-clamp-2">全新升级的世界观生成模型，支持更复杂的种族设定、力量体系和地理环境生成。</p>
              </div>
              
              <div className="mb-4 pt-4 border-t border-[#2A2A2A]">
                <span className="inline-block px-2 py-1 bg-[#1C1C1C] text-[#888888] text-xs font-medium rounded mb-2">v2.3.5</span>
                <h4 className="font-medium text-white mb-1">性能优化与Bug修复</h4>
                <p className="text-sm text-[#888888] line-clamp-1">修复了长篇幅小说加载缓慢的问题。</p>
              </div>

              <Button variant="link" className="text-[#FFE500] p-0 h-auto font-medium hover:text-[#FFE500]/80">
                查看全部更新日志
              </Button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
