import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle2, Bot, Sparkles, BookOpen } from "lucide-react";

export default function Register() {
  return (
    <div className="flex min-h-screen bg-[#0A0A0A] text-white selection:bg-[#FFE500] selection:text-black font-sans">
      {/* Left Panel - Branding & Features */}
      <div className="relative hidden w-[60%] lg:flex flex-col justify-between overflow-hidden bg-[#141414] p-12">
        {/* Abstract Background Elements */}
        <div className="absolute inset-0 z-0">
          <div className="absolute -left-1/4 -top-1/4 h-[800px] w-[800px] rounded-full bg-[#FFE500]/5 blur-[120px]"></div>
          <div className="absolute -bottom-1/4 -right-1/4 h-[600px] w-[600px] rounded-full bg-white/5 blur-[100px]"></div>
          
          {/* Diagonal Lines Pattern */}
          <svg className="absolute inset-0 h-full w-full opacity-10" width="100%" height="100%">
            <defs>
              <pattern id="diagonal-lines" width="40" height="40" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="40" stroke="#FFE500" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#diagonal-lines)" />
          </svg>
        </div>

        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FFE500] text-black">
              <Sparkles className="h-6 w-6" />
            </div>
            <span className="text-2xl font-bold tracking-tight font-display">Arboris Novel</span>
          </div>
          
          <h1 className="text-5xl font-bold leading-tight font-display mb-6">
            开启你的<br />
            <span className="text-[#FFE500]">智能创作之旅</span>
          </h1>
          <p className="text-xl text-[#888888] font-light">Arboris Novel · AI创作助手</p>
        </div>

        <div className="relative z-10 space-y-8 max-w-md">
          <div className="flex items-start gap-4 p-4 rounded-2xl bg-[#1C1C1C]/50 border border-[#2A2A2A] backdrop-blur-sm">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#FFE500]/10 text-[#FFE500]">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-lg mb-1 flex items-center gap-2">
                AI编辑团队, 全程陪伴
                <CheckCircle2 className="h-4 w-4 text-[#FFE500]" />
              </h3>
              <p className="text-[#888888] text-sm leading-relaxed">提供专业的设定指导、大纲规划和内容润色，让创作不再孤单。</p>
            </div>
          </div>

          <div className="flex items-start gap-4 p-4 rounded-2xl bg-[#1C1C1C]/50 border border-[#2A2A2A] backdrop-blur-sm">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#FFE500]/10 text-[#FFE500]">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-lg mb-1 flex items-center gap-2">
                章节自动生成
                <CheckCircle2 className="h-4 w-4 text-[#FFE500]" />
              </h3>
              <p className="text-[#888888] text-sm leading-relaxed">基于设定和大纲，一键生成高质量正文，突破创作瓶颈。</p>
            </div>
          </div>

          <div className="flex items-start gap-4 p-4 rounded-2xl bg-[#1C1C1C]/50 border border-[#2A2A2A] backdrop-blur-sm">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#FFE500]/10 text-[#FFE500]">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-lg mb-1 flex items-center gap-2">
                角色/世界观管理
                <CheckCircle2 className="h-4 w-4 text-[#FFE500]" />
              </h3>
              <p className="text-[#888888] text-sm leading-relaxed">系统化管理小说设定，保持逻辑严密，避免前后矛盾。</p>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-sm text-[#888888]">
          &copy; {new Date().getFullYear()} Arboris Novel. All rights reserved.
        </div>
      </div>

      {/* Right Panel - Register Form */}
      <div className="flex w-full lg:w-[40%] flex-col items-center justify-center px-8 sm:px-16 lg:px-24 xl:px-32 relative">
        {/* Mobile Logo */}
        <div className="absolute top-8 left-8 flex lg:hidden items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#FFE500] text-black">
            <Sparkles className="h-5 w-5" />
          </div>
          <span className="font-bold tracking-tight">Arboris</span>
        </div>

        <div className="w-full max-w-[400px] space-y-8">
          <div className="space-y-2 text-center lg:text-left">
            <h2 className="text-3xl font-bold tracking-tight font-display">创建账号</h2>
            <p className="text-[#888888]">加入我们，开始你的AI创作之旅</p>
          </div>

          <div className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username" className="text-sm font-medium text-gray-300">用户名</Label>
                <Input 
                  id="username" 
                  placeholder="请输入您的用户名" 
                  className="h-12 bg-[#1C1C1C] border-[#2A2A2A] text-white placeholder:text-[#888888] focus-visible:ring-[#FFE500] focus-visible:border-[#FFE500] transition-colors"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium text-gray-300">密码</Label>
                <Input 
                  id="password" 
                  type="password"
                  placeholder="至少8位字符" 
                  className="h-12 bg-[#1C1C1C] border-[#2A2A2A] text-white placeholder:text-[#888888] focus-visible:ring-[#FFE500] focus-visible:border-[#FFE500] transition-colors"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password" className="text-sm font-medium text-gray-300">确认密码</Label>
                <Input 
                  id="confirm-password" 
                  type="password"
                  placeholder="再次输入密码" 
                  className="h-12 bg-[#1C1C1C] border-[#2A2A2A] text-white placeholder:text-[#888888] focus-visible:ring-[#FFE500] focus-visible:border-[#FFE500] transition-colors"
                />
              </div>
            </div>

            <Button className="w-full h-12 bg-[#FFE500] hover:bg-[#FFE500]/90 text-black font-semibold text-base transition-all active:scale-[0.98]">
              注册
            </Button>
            
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-[#2A2A2A]" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-[#0A0A0A] px-2 text-[#888888]">或者</span>
              </div>
            </div>

            <Button variant="outline" className="w-full h-12 bg-transparent border-[#2A2A2A] text-white hover:bg-[#1C1C1C] hover:text-white transition-colors">
              <svg className="mr-2 h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" />
                <path d="M12 6v6l4 2" />
              </svg>
              使用 LinuxDO 账号登录
            </Button>
          </div>

          <p className="text-center text-sm text-[#888888]">
            已有账号？{" "}
            <a href="/__mockup/preview/novel-ui/Login" className="font-medium text-[#FFE500] hover:underline underline-offset-4 transition-colors">
              立即登录
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
