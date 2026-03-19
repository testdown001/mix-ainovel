import React, { useState } from "react";
import { 
  BookOpen, 
  Settings, 
  User, 
  ChevronLeft,
  Calendar,
  PenTool,
  BarChart2,
  List,
  Users,
  Globe,
  Map,
  Eye,
  TrendingUp,
  Database,
  Star,
  Clock,
  ChevronRight,
  Play
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function NovelDetail() {
  const [activeTab, setActiveTab] = useState("overview");

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-[#FFFFFF] font-sans selection:bg-[#FFE500] selection:text-black">
      {/* Top Navigation */}
      <header className="sticky top-0 z-50 w-full border-b border-[#2A2A2A] bg-[#0A0A0A]/80 backdrop-blur">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded bg-[#FFE500] flex items-center justify-center text-black font-bold text-xl">
                ✦
              </div>
              <span className="text-xl font-bold tracking-tight">Arboris Novel</span>
            </div>
            <nav className="hidden md:flex items-center gap-6 ml-6 text-sm font-medium text-[#888888]">
              <a href="#" className="hover:text-white transition-colors">灵感模式</a>
              <a href="#" className="text-white">我的小说</a>
              <a href="#" className="hover:text-white transition-colors">写作台</a>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" className="text-[#888888] hover:text-white">
              <Settings className="h-5 w-5" />
            </Button>
            <Avatar className="h-9 w-9 border border-[#2A2A2A]">
              <AvatarImage src="https://i.pravatar.cc/150?u=a042581f4e29026704d" />
              <AvatarFallback className="bg-[#141414] text-[#FFE500]">AX</AvatarFallback>
            </Avatar>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Back button */}
        <Button variant="ghost" className="mb-6 -ml-4 text-[#888888] hover:text-white">
          <ChevronLeft className="mr-2 h-4 w-4" />
          返回小说库
        </Button>

        {/* Hero Header */}
        <div className="bg-[#141414] border border-[#2A2A2A] rounded-2xl p-8 mb-8 relative overflow-hidden">
          {/* Decorative background element */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-[#FFE500]/5 rounded-full blur-3xl transform translate-x-1/2 -translate-y-1/2"></div>
          
          <div className="relative z-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <Badge className="bg-[#FFE500]/10 text-[#FFE500] hover:bg-[#FFE500]/20 border-[#FFE500]/20 rounded-md px-3 py-1">
                  赛博朋克
                </Badge>
                <Badge variant="outline" className="border-[#2A2A2A] text-[#888888] rounded-md px-3 py-1">
                  科幻
                </Badge>
                <span className="text-xs text-[#888888] flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#2ED573]"></span>
                  连载中
                </span>
              </div>
              
              <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-white">
                霓虹下的暗影
              </h1>
              
              <div className="flex flex-wrap items-center gap-6 text-sm text-[#888888]">
                <div className="flex items-center gap-2">
                  <PenTool className="h-4 w-4 text-[#FFE500]" />
                  <span>作者: Alex Chen</span>
                </div>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  <span>创建于 2024-03-15</span>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  <span>最后更新: 2小时前</span>
                </div>
              </div>
            </div>

            <div className="flex flex-col items-center gap-4 bg-[#1C1C1C] p-5 rounded-xl border border-[#2A2A2A] min-w-[200px]">
              <div className="relative w-20 h-20 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="45" fill="none" stroke="#2A2A2A" strokeWidth="10" />
                  <circle 
                    cx="50" cy="50" r="45" fill="none" stroke="#FFE500" strokeWidth="10" 
                    strokeDasharray="282.7" strokeDashoffset="113.1" // 60% completion
                    strokeLinecap="round" 
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-xl font-bold">60%</span>
                </div>
              </div>
              <div className="text-center">
                <div className="text-sm font-medium text-white">当前进度</div>
                <div className="text-xs text-[#888888]">18 / 30 章</div>
              </div>
              <Button className="w-full bg-[#FFE500] text-black hover:bg-[#FFE500]/90 font-bold mt-2">
                <Play className="mr-2 h-4 w-4 fill-black" /> 继续写作
              </Button>
            </div>
          </div>
        </div>

        {/* Horizontal Tab Bar */}
        <Tabs defaultValue="overview" className="w-full" onValueChange={setActiveTab}>
          <div className="border-b border-[#2A2A2A] mb-8">
            <TabsList className="bg-transparent h-12 p-0 space-x-8 overflow-x-auto flex-nowrap justify-start w-full border-none">
              <TabsTrigger 
                value="overview" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#FFE500] data-[state=active]:text-[#FFE500] rounded-none px-0 h-12 text-[#888888] hover:text-white"
              >
                <BarChart2 className="w-4 h-4 mr-2" />
                概览
              </TabsTrigger>
              <TabsTrigger value="chapters" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#FFE500] data-[state=active]:text-[#FFE500] rounded-none px-0 h-12 text-[#888888] hover:text-white">
                <List className="w-4 h-4 mr-2" /> 章节列表
              </TabsTrigger>
              <TabsTrigger value="characters" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#FFE500] data-[state=active]:text-[#FFE500] rounded-none px-0 h-12 text-[#888888] hover:text-white">
                <Users className="w-4 h-4 mr-2" /> 人物
              </TabsTrigger>
              <TabsTrigger value="world" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#FFE500] data-[state=active]:text-[#FFE500] rounded-none px-0 h-12 text-[#888888] hover:text-white">
                <Globe className="w-4 h-4 mr-2" /> 世界观
              </TabsTrigger>
              <TabsTrigger value="outline" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#FFE500] data-[state=active]:text-[#FFE500] rounded-none px-0 h-12 text-[#888888] hover:text-white">
                <Map className="w-4 h-4 mr-2" /> 大纲
              </TabsTrigger>
              <TabsTrigger value="foreshadowing" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#FFE500] data-[state=active]:text-[#FFE500] rounded-none px-0 h-12 text-[#888888] hover:text-white">
                <Eye className="w-4 h-4 mr-2" /> 伏笔
              </TabsTrigger>
              <TabsTrigger value="emotion" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#FFE500] data-[state=active]:text-[#FFE500] rounded-none px-0 h-12 text-[#888888] hover:text-white">
                <TrendingUp className="w-4 h-4 mr-2" /> 情感曲线
              </TabsTrigger>
              <TabsTrigger value="database" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#FFE500] data-[state=active]:text-[#FFE500] rounded-none px-0 h-12 text-[#888888] hover:text-white">
                <Database className="w-4 h-4 mr-2" /> 设定库
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="overview" className="mt-0 outline-none">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Column (Main Content) */}
              <div className="lg:col-span-2 space-y-8">
                {/* Stats Cards Row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card className="bg-[#141414] border-[#2A2A2A]">
                    <CardContent className="p-5">
                      <div className="text-[#888888] text-sm mb-2">总字数</div>
                      <div className="text-2xl font-bold text-white">54.2k</div>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#141414] border-[#2A2A2A]">
                    <CardContent className="p-5">
                      <div className="text-[#888888] text-sm mb-2">已完成章节</div>
                      <div className="text-2xl font-bold text-white">18 <span className="text-sm text-[#888888] font-normal">/ 30</span></div>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#141414] border-[#2A2A2A]">
                    <CardContent className="p-5">
                      <div className="text-[#888888] text-sm mb-2 flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-[#FFE500]"></div>
                        AI生成率
                      </div>
                      <div className="text-2xl font-bold text-white">92%</div>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#141414] border-[#2A2A2A]">
                    <CardContent className="p-5">
                      <div className="text-[#888888] text-sm mb-2 flex items-center gap-1">
                        <Star className="w-3 h-3 text-[#2ED573]" fill="#2ED573" />
                        平均质量分
                      </div>
                      <div className="text-2xl font-bold text-[#2ED573]">8.5</div>
                    </CardContent>
                  </Card>
                </div>

                {/* Recent Chapters */}
                <Card className="bg-[#141414] border-[#2A2A2A]">
                  <CardHeader className="flex flex-row items-center justify-between pb-4">
                    <CardTitle className="text-lg font-bold">最近更新章节</CardTitle>
                    <Button variant="ghost" size="sm" className="text-[#FFE500] hover:text-[#FFE500]/80 hover:bg-[#FFE500]/10">
                      查看全部 <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="divide-y divide-[#2A2A2A]">
                      {[
                        { num: 18, title: "觉醒与背叛", status: "completed", date: "2小时前", words: 3200, score: 8.8 },
                        { num: 17, title: "霓虹下的交易", status: "completed", date: "昨天", words: 2850, score: 8.5 },
                        { num: 16, title: "赛博精神病", status: "completed", date: "2天前", words: 3100, score: 8.2 },
                        { num: 19, title: "深渊凝视", status: "pending", date: "-", words: 0, score: 0 }
                      ].map((chapter) => (
                        <div key={chapter.num} className="p-4 flex items-center justify-between hover:bg-[#1C1C1C] transition-colors cursor-pointer group">
                          <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded bg-[#0A0A0A] border border-[#2A2A2A] flex items-center justify-center font-mono text-sm text-[#888888]">
                              第{chapter.num}章
                            </div>
                            <div>
                              <div className="font-medium text-white group-hover:text-[#FFE500] transition-colors">
                                {chapter.title}
                              </div>
                              <div className="text-xs text-[#888888] mt-1 flex items-center gap-3">
                                <span>{chapter.date}</span>
                                {chapter.words > 0 && <span>{chapter.words} 字</span>}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            {chapter.score > 0 && (
                              <Badge variant="outline" className="border-[#2A2A2A] bg-[#0A0A0A] text-[#888888]">
                                <Star className="w-3 h-3 text-[#2ED573] mr-1" fill="#2ED573" />
                                {chapter.score}
                              </Badge>
                            )}
                            {chapter.status === "completed" ? (
                              <Badge className="bg-[#2ED573]/10 text-[#2ED573] hover:bg-[#2ED573]/20 border-0">已完成</Badge>
                            ) : (
                              <Button size="sm" className="bg-[#2A2A2A] text-white hover:bg-[#FFE500] hover:text-black transition-colors">
                                生成本章
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Key Characters */}
                <Card className="bg-[#141414] border-[#2A2A2A]">
                  <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="text-lg font-bold">核心人物设定</CardTitle>
                    <Button variant="ghost" size="sm" className="text-[#888888] hover:text-white">
                      管理人物
                    </Button>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {[
                        { name: "Kael", role: "男主 · 赏金猎人", desc: "冷酷外表下的理想主义者" },
                        { name: "Nova", role: "女主 · 黑客", desc: "拥有能够直连底层网络的特异体质" },
                        { name: "Dr. Vance", role: "反派 · 财阀统领", desc: "试图通过义体控制全城" },
                        { name: "J-09", role: "AI伴侣", desc: "产生了自我意识的服务型仿生人" }
                      ].map((char, i) => (
                        <div key={i} className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-xl p-4 flex flex-col items-center text-center hover:border-[#FFE500]/50 transition-colors cursor-pointer">
                          <Avatar className="w-16 h-16 mb-3 border-2 border-[#1C1C1C]">
                            <AvatarImage src={`https://i.pravatar.cc/150?u=char${i}`} />
                            <AvatarFallback className="bg-[#1C1C1C] text-lg text-[#FFE500]">
                              {char.name.charAt(0)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="font-bold text-sm text-white">{char.name}</div>
                          <div className="text-xs text-[#FFE500] mt-1 mb-2">{char.role}</div>
                          <div className="text-xs text-[#888888] line-clamp-2">{char.desc}</div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Right Column (Sidebar) */}
              <div className="space-y-6">
                {/* AI Analysis Card */}
                <Card className="bg-[#141414] border-[#2A2A2A] overflow-hidden">
                  <div className="bg-gradient-to-r from-[#FFE500]/20 to-transparent p-1"></div>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-md flex items-center gap-2">
                      <div className="text-[#FFE500]">✦</div> AI 综合评估
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="text-sm text-[#888888] leading-relaxed">
                      当前故事节奏紧凑，第16-18章的情感爆发点处理得当。建议在后续章节适当放缓节奏，深入描写男女主的内心变化。
                    </div>
                    
                    <div className="space-y-3 pt-2">
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[#888888]">剧情张力</span>
                          <span className="text-white">85%</span>
                        </div>
                        <Progress value={85} className="h-1.5 bg-[#2A2A2A]" indicatorColor="bg-[#FFE500]" />
                      </div>
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[#888888]">人物塑造</span>
                          <span className="text-white">90%</span>
                        </div>
                        <Progress value={90} className="h-1.5 bg-[#2A2A2A]" indicatorColor="bg-[#FFE500]" />
                      </div>
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[#888888]">设定一致性</span>
                          <span className="text-white">78%</span>
                        </div>
                        <Progress value={78} className="h-1.5 bg-[#2A2A2A]" indicatorColor="bg-[#FF4757]" />
                        <div className="text-[10px] text-[#FF4757] mt-1 flex items-center">
                          注意：第17章中Nova的黑客能力设定存在轻微偏差。
                        </div>
                      </div>
                    </div>
                    
                    <Button variant="outline" className="w-full mt-4 border-[#2A2A2A] text-white hover:bg-[#1C1C1C]">
                      查看详细评估报告
                    </Button>
                  </CardContent>
                </Card>

                {/* Quick Actions */}
                <Card className="bg-[#141414] border-[#2A2A2A]">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-md font-bold">快捷操作</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <Button variant="ghost" className="w-full justify-start text-[#888888] hover:text-white hover:bg-[#1C1C1C]">
                      <PenTool className="mr-2 h-4 w-4" /> 修改小说设定
                    </Button>
                    <Button variant="ghost" className="w-full justify-start text-[#888888] hover:text-white hover:bg-[#1C1C1C]">
                      <Map className="mr-2 h-4 w-4" /> 导出当前大纲
                    </Button>
                    <Button variant="ghost" className="w-full justify-start text-[#888888] hover:text-white hover:bg-[#1C1C1C]">
                      <Settings className="mr-2 h-4 w-4" /> 项目专属设置
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Placeholders for other tabs */}
          {["chapters", "characters", "world", "outline", "foreshadowing", "emotion", "database"].map(tab => (
            <TabsContent key={tab} value={tab} className="mt-8 text-center py-20 border border-dashed border-[#2A2A2A] rounded-xl bg-[#141414]/50">
              <div className="text-[#888888]">内容开发中... ({tab})</div>
            </TabsContent>
          ))}
        </Tabs>
      </main>
    </div>
  );
}
