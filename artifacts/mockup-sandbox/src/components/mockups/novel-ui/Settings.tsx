import React, { useState } from "react";
import { 
  Settings as SettingsIcon, 
  User, 
  Crown, 
  Key, 
  Sliders, 
  CheckCircle2, 
  LogOut, 
  Zap, 
  ChevronRight,
  BookOpen,
  PenTool,
  Lightbulb,
  Cpu
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function Settings() {
  const [activeTab, setActiveTab] = useState("llm");
  const [temperature, setTemperature] = useState([0.7]);
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");

  const handleTestConnection = () => {
    setTestStatus("testing");
    setTimeout(() => {
      setTestStatus("success");
      setTimeout(() => setTestStatus("idle"), 3000);
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white font-sans">
      {/* Top Navigation */}
      <nav className="h-16 border-b border-[#2A2A2A] bg-[#141414]/80 backdrop-blur-md sticky top-0 z-50 px-6 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2 text-xl font-bold font-display tracking-tight">
            <div className="w-8 h-8 rounded-lg bg-[#FFE500] flex items-center justify-center text-black">
              ✦
            </div>
            Arboris Novel
          </div>
          
          <div className="hidden md:flex items-center gap-6 text-sm">
            <a href="#" className="text-[#888888] hover:text-white transition-colors flex items-center gap-2">
              <Lightbulb className="w-4 h-4" /> 灵感模式
            </a>
            <a href="#" className="text-[#888888] hover:text-white transition-colors flex items-center gap-2">
              <BookOpen className="w-4 h-4" /> 我的小说
            </a>
            <a href="#" className="text-[#888888] hover:text-white transition-colors flex items-center gap-2">
              <PenTool className="w-4 h-4" /> 写作台
            </a>
            <a href="#" className="text-[#FFE500] flex items-center gap-2">
              <SettingsIcon className="w-4 h-4" /> 设置
            </a>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 pl-4 border-l border-[#2A2A2A]">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#FFE500] to-orange-500 p-[2px]">
              <div className="w-full h-full rounded-full bg-[#141414] border border-[#2A2A2A] overflow-hidden">
                <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix" alt="User" />
              </div>
            </div>
            <span className="text-sm font-medium hidden sm:block">林克创作中</span>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="text-3xl font-display font-bold">账号设置</h1>
          <p className="text-[#888888] mt-2">管理您的系统偏好、大模型配置与账号信息</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
          {/* Sidebar */}
          <div className="md:col-span-3 space-y-6">
            <div className="p-4 rounded-xl bg-[#141414] border border-[#2A2A2A] flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-[#2A2A2A] overflow-hidden flex-shrink-0">
                <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix" alt="User" />
              </div>
              <div className="min-w-0">
                <div className="font-medium truncate">林克创作中</div>
                <div className="text-xs text-[#888888] truncate mt-0.5">user@example.com</div>
                <Badge variant="outline" className="mt-1.5 border-[#FFE500]/30 text-[#FFE500] bg-[#FFE500]/10 text-[10px] px-1.5 py-0">
                  免费版
                </Badge>
              </div>
            </div>

            <nav className="space-y-1">
              {[
                { id: "llm", icon: Cpu, label: "LLM配置" },
                { id: "writing", icon: Sliders, label: "写作偏好" },
                { id: "account", icon: User, label: "账号信息" },
                { id: "billing", icon: Crown, label: "会员套餐" },
              ].map((item) => (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                    activeTab === item.id 
                      ? "bg-[#FFE500]/10 text-[#FFE500]" 
                      : "text-[#888888] hover:bg-[#1C1C1C] hover:text-white"
                  }`}
                >
                  <item.icon className="w-4 h-4" />
                  {item.label}
                  {activeTab === item.id && (
                    <ChevronRight className="w-4 h-4 ml-auto" />
                  )}
                </button>
              ))}
            </nav>

            <div className="pt-4 border-t border-[#2A2A2A]">
              <button className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-[#FF4757] hover:bg-[#FF4757]/10 transition-colors">
                <LogOut className="w-4 h-4" />
                退出登录
              </button>
            </div>
          </div>

          {/* Content Area */}
          <div className="md:col-span-9 space-y-6">
            {activeTab === "llm" && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <Card className="bg-[#141414] border-[#2A2A2A] text-white shadow-xl">
                  <CardHeader>
                    <CardTitle className="text-xl flex items-center gap-2">
                      <Cpu className="w-5 h-5 text-[#FFE500]" />
                      核心驱动配置
                    </CardTitle>
                    <CardDescription className="text-[#888888]">
                      设置 Arboris Novel 使用的大语言模型 API。支持 OpenAI 兼容格式。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="space-y-2">
                      <Label htmlFor="api-url" className="text-[#888888]">API 接口地址</Label>
                      <Input 
                        id="api-url" 
                        defaultValue="https://api.openai.com/v1" 
                        className="bg-[#0A0A0A] border-[#2A2A2A] focus-visible:ring-[#FFE500] text-white"
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="api-key" className="text-[#888888]">API Key</Label>
                      <div className="relative">
                        <Input 
                          id="api-key" 
                          type="password" 
                          defaultValue="sk-................................" 
                          className="bg-[#0A0A0A] border-[#2A2A2A] focus-visible:ring-[#FFE500] text-white pr-10"
                        />
                        <Key className="w-4 h-4 absolute right-3 top-3 text-[#888888]" />
                      </div>
                      <p className="text-xs text-[#888888]">您的密钥将安全地存储在本地，不会上传至我们的服务器。</p>
                    </div>

                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label className="text-[#888888]">默认推理模型</Label>
                        <Select defaultValue="gpt-4-turbo">
                          <SelectTrigger className="bg-[#0A0A0A] border-[#2A2A2A] focus:ring-[#FFE500]">
                            <SelectValue placeholder="选择模型" />
                          </SelectTrigger>
                          <SelectContent className="bg-[#1C1C1C] border-[#2A2A2A] text-white">
                            <SelectItem value="gpt-4-turbo">GPT-4 Turbo (推荐)</SelectItem>
                            <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                            <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
                            <SelectItem value="claude-3-sonnet">Claude 3.5 Sonnet</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <Label className="text-[#888888]">创造力 (Temperature)</Label>
                          <span className="text-sm font-mono text-[#FFE500]">{temperature[0]}</span>
                        </div>
                        <Slider 
                          defaultValue={[0.7]} 
                          max={2} 
                          step={0.1}
                          onValueChange={setTemperature}
                          className="py-1"
                        />
                        <div className="flex justify-between text-xs text-[#888888]">
                          <span>精确严谨</span>
                          <span>天马行空</span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                  <CardFooter className="bg-[#1C1C1C] border-t border-[#2A2A2A] flex justify-between rounded-b-xl">
                    <Button 
                      variant="outline" 
                      onClick={handleTestConnection}
                      disabled={testStatus === "testing"}
                      className="border-[#2A2A2A] bg-transparent hover:bg-[#2A2A2A] text-white"
                    >
                      {testStatus === "idle" && "测试连接"}
                      {testStatus === "testing" && "连接中..."}
                      {testStatus === "success" && <><CheckCircle2 className="w-4 h-4 mr-2 text-[#2ED573]" /> 测试成功</>}
                    </Button>
                    <Button className="bg-[#FFE500] hover:bg-[#FFE500]/90 text-black font-medium">
                      保存配置
                    </Button>
                  </CardFooter>
                </Card>

                <Card className="bg-gradient-to-br from-[#1C1C1C] to-[#0A0A0A] border-[#FFE500]/30 overflow-hidden relative shadow-2xl">
                  {/* Decorative element */}
                  <div className="absolute top-0 right-0 w-64 h-64 bg-[#FFE500] opacity-5 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>
                  
                  <CardContent className="p-8 flex flex-col sm:flex-row items-center justify-between gap-6 relative z-10">
                    <div className="flex items-center gap-5">
                      <div className="w-16 h-16 rounded-full bg-[#FFE500]/10 flex items-center justify-center border border-[#FFE500]/20 shrink-0">
                        <Crown className="w-8 h-8 text-[#FFE500]" />
                      </div>
                      <div>
                        <h3 className="text-xl font-bold text-white mb-1">当前套餐：免费版</h3>
                        <p className="text-[#888888] text-sm max-w-md">
                          享受基础 AI 创作辅助功能，每月 5 万字生成额度。升级专业版解锁无限创作潜力、高级模型权限与专属客服。
                        </p>
                      </div>
                    </div>
                    <Button className="bg-[#FFE500] hover:bg-[#FFE500]/90 text-black font-bold px-8 shadow-[0_0_15px_rgba(255,229,0,0.3)] shrink-0 group">
                      <Zap className="w-4 h-4 mr-2 group-hover:scale-110 transition-transform" />
                      升级会员
                    </Button>
                  </CardContent>
                </Card>
              </div>
            )}

            {activeTab !== "llm" && (
              <div className="h-64 flex flex-col items-center justify-center border border-dashed border-[#2A2A2A] rounded-xl bg-[#141414]/50 text-[#888888] animate-in fade-in">
                <Sliders className="w-8 h-8 mb-4 opacity-50" />
                <p>该模块设计正在赶工中...</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
