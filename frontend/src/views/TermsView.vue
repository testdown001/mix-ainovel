<template>
  <div class="min-h-screen" style="background:#0A0A0A; font-family:'Inter',sans-serif; color:#ccc;">

    <div class="fixed inset-0 pointer-events-none" style="background-image:linear-gradient(#161616 1px,transparent 1px),linear-gradient(90deg,#161616 1px,transparent 1px);background-size:48px 48px;opacity:0.5;"></div>

    <!-- Navbar -->
    <nav class="sticky top-0 z-50 flex items-center justify-between px-6 py-4 border-b" style="background:rgba(10,10,10,0.95); backdrop-filter:blur(12px); border-color:#1A1A1A;">
      <div class="flex items-center gap-2.5 cursor-pointer" @click="router.push('/')">
        <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:#FFE500;">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
          </svg>
        </div>
        <span class="text-lg font-bold text-white" style="font-family:'Space Grotesk',sans-serif;">Arboris Novel</span>
      </div>
      <button @click="router.go(-1)" class="flex items-center gap-1.5 text-sm transition-colors" style="color:#666;"
        @mouseenter="($event.currentTarget as HTMLElement).style.color='#fff'"
        @mouseleave="($event.currentTarget as HTMLElement).style.color='#666'">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18"/></svg>
        返回
      </button>
    </nav>

    <!-- Content -->
    <div class="relative max-w-3xl mx-auto px-6 py-16">

      <div class="mb-10">
        <div class="text-xs font-medium mb-3 px-3 py-1 rounded-full inline-block" style="background:#1A1A1A; color:#666; border:1px solid #222;">法律文件</div>
        <h1 class="text-4xl font-bold text-white mb-3" style="font-family:'Space Grotesk',sans-serif;">服务条款</h1>
        <p class="text-sm" style="color:#444;">最后更新：2025年1月1日</p>
      </div>

      <div class="space-y-10 text-sm leading-relaxed" style="color:#888;">

        <section>
          <h2 class="text-base font-semibold text-white mb-3">1. 接受条款</h2>
          <p>欢迎使用 Arboris Novel（以下简称"本平台"）。访问或使用本平台，即表示您同意受本服务条款约束。如您不同意任何条款，请停止使用本平台。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">2. 服务说明</h2>
          <p class="mb-3">Arboris Novel 是一个 AI 驱动的中文网络小说创作平台，提供以下核心服务：</p>
          <ul class="space-y-2 pl-4">
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>基于自创先进多 Agent 架构的 AI 辅助创作</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>灵感生成、大纲规划、章节写作等创作工具</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>小说项目管理与存储</span></li>
          </ul>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">3. 用户账户</h2>
          <p class="mb-3">注册账户时，您需要提供真实、准确、完整的信息，并对账户下的所有活动负责。您有义务：</p>
          <ul class="space-y-2 pl-4">
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>妥善保管账户密码，不与他人共享</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>及时通知我们任何账户被盗用的情况</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>年满 18 周岁，或在法定监护人监督下使用</span></li>
          </ul>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">4. 内容规范</h2>
          <p class="mb-3">使用本平台创作时，您同意不生成、传播以下内容：</p>
          <ul class="space-y-2 pl-4">
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>违反中华人民共和国法律法规的内容</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>侵犯他人知识产权的内容</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>淫秽、色情、暴力等违法有害内容</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>虚假信息、诈骗或恶意软件</span></li>
          </ul>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">5. 知识产权</h2>
          <p>您使用本平台创作的内容，其著作权归您所有。本平台对您创作的内容不主张任何所有权。但您授予本平台在提供服务所必要范围内使用、存储、处理您内容的权利。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">6. 付费服务与退款</h2>
          <p>订阅高级套餐即视为您同意支付相应费用。订阅费用按周期预付且不可退款，除非适用法律另有规定。免费试用期结束后将自动转为付费套餐，如不需要请在到期前取消。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">7. 服务变更与终止</h2>
          <p>我们保留随时修改、暂停或终止部分或全部服务的权利，并会提前通知重大变更。如您违反本条款，我们有权暂停或终止您的账户而不承担任何责任。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">8. 免责声明</h2>
          <p>本平台按"现状"提供服务，不对 AI 生成内容的准确性、完整性或适用性作出任何保证。在法律允许的最大范围内，我们不对任何间接、偶发或后果性损失承担责任。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">9. 联系我们</h2>
          <p>如对本服务条款有任何疑问，请通过以下方式联系我们：<br><span style="color:#FFE500;">support@arborisnovel.com</span></p>
        </section>

      </div>

      <div class="mt-16 pt-8 flex items-center justify-between border-t" style="border-color:#1A1A1A;">
        <router-link to="/privacy" class="text-sm transition-colors" style="color:#555;"
          @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
          @mouseleave="($event.target as HTMLElement).style.color='#555'">
          隐私政策 →
        </router-link>
        <button @click="router.push('/')" class="text-sm font-medium transition-colors" style="color:#FFE500;">
          返回首页
        </button>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
</script>
