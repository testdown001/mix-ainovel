import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Github, Mail, Lock } from "lucide-react";

export default function LoginMockup() {
  return (
    <div className="min-h-screen w-full flex bg-[#0A0A0A] text-white font-['Inter',sans-serif]">
      {/* Left Panel - Brand Hero (60%) */}
      <div className="hidden lg:flex w-[60%] relative overflow-hidden bg-[#0A0A0A] border-r border-[#2A2A2A] flex-col justify-between p-12">
        {/* Abstract Background Elements */}
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-[#FFE500]/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-[#FFE500]/5 rounded-full blur-[120px]" />
        
        {/* Diagonal Grid Pattern */}
        <div 
          className="absolute inset-0 opacity-10 pointer-events-none"
          style={{
            backgroundImage: `linear-gradient(45deg, #FFE500 1px, transparent 1px)`,
            backgroundSize: '40px 40px'
          }}
        />

        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-8">
            <span className="text-[#FFE500] text-4xl">✦</span>
            <h1 className="text-3xl font-bold font-['Space_Grotesk',sans-serif] tracking-tight">Arboris Novel</h1>
          </div>
          <div className="inline-block px-4 py-1.5 rounded-full border border-[#2A2A2A] bg-[#141414]/80 backdrop-blur-sm text-sm text-[#888888] mb-6">
            AI创作助手 · 下一代网文引擎
          </div>
        </div>

        <div className="relative z-10 max-w-xl">
          <h2 className="text-6xl font-black mb-6 leading-tight font-['Space_Grotesk',sans-serif]">
            用AI，<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#FFE500] to-[#FFB800]">
              释放你的故事
            </span>
          </h2>
          <p className="text-xl text-[#888888] leading-relaxed max-w-md">
            从灵感闪现到百万字巨著，AI全程陪伴你的创作旅程。打破写作瓶颈，让想象力不受拘束。
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-4 text-sm text-[#888888]">
          <div className="flex -space-x-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="w-8 h-8 rounded-full border-2 border-[#0A0A0A] bg-[#1C1C1C] flex items-center justify-center text-xs">
                {i}
              </div>
            ))}
          </div>
          <p>超过 <span className="text-[#FFE500] font-bold">10,000+</span> 创作者正在使用</p>
        </div>
      </div>

      {/* Right Panel - Login Form (40%) */}
      <div className="w-full lg:w-[40%] flex items-center justify-center p-8 bg-[#0A0A0A] relative">
        <div className="w-full max-w-[400px] bg-[#141414] p-8 rounded-2xl border border-[#2A2A2A] shadow-2xl relative z-10">
          
          <div className="mb-8">
            <h3 className="text-2xl font-bold mb-2 font-['Space_Grotesk',sans-serif]">欢迎回来</h3>
            <p className="text-[#888888] text-sm">登录以继续你的创作之旅</p>
          </div>

          <form className="space-y-5" onSubmit={(e) => e.preventDefault()}>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium text-[#888888]">账号</Label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[#888888]">
                  <Mail className="w-4 h-4" />
                </div>
                <Input 
                  id="email" 
                  placeholder="name@example.com" 
                  className="pl-10 bg-[#1C1C1C] border-[#2A2A2A] text-white focus-visible:ring-1 focus-visible:ring-[#FFE500] focus-visible:border-[#FFE500] h-11"
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm font-medium text-[#888888]">密码</Label>
                <a href="#" className="text-xs text-[#FFE500] hover:underline">忘记密码?</a>
              </div>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[#888888]">
                  <Lock className="w-4 h-4" />
                </div>
                <Input 
                  id="password" 
                  type="password"
                  placeholder="••••••••" 
                  className="pl-10 bg-[#1C1C1C] border-[#2A2A2A] text-white focus-visible:ring-1 focus-visible:ring-[#FFE500] focus-visible:border-[#FFE500] h-11"
                />
              </div>
            </div>

            <Button className="w-full h-11 bg-[#FFE500] hover:bg-[#FFE500]/90 text-black font-semibold text-base mt-2 transition-all">
              登录
            </Button>
          </form>

          <div className="mt-8 relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-[#2A2A2A]" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-[#141414] px-2 text-[#888888]">或者</span>
            </div>
          </div>

          <div className="mt-6">
            <Button 
              variant="outline" 
              className="w-full h-11 bg-transparent border-[#2A2A2A] text-white hover:bg-[#1C1C1C] hover:text-white transition-colors"
            >
              <Github className="mr-2 h-4 w-4" />
              使用 LinuxDO 账号登录
            </Button>
          </div>

          <p className="mt-8 text-center text-sm text-[#888888]">
            还没有账号？{' '}
            <a href="/register" className="text-[#FFE500] font-medium hover:underline transition-all">
              立即注册
            </a>
          </p>
        </div>
        
        {/* Subtle decorative glow for the form */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-gradient-to-tr from-[#FFE500]/5 to-transparent rounded-full blur-[100px] pointer-events-none" />
      </div>
    </div>
  );
}
