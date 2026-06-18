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
        <span class="text-lg font-bold text-white" style="font-family:'Space Grotesk',sans-serif;">Octopus AI Novel</span>
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
        <h1 class="text-4xl font-bold text-white mb-3" style="font-family:'Space Grotesk',sans-serif;">隐私政策</h1>
        <p class="text-sm" style="color:#444;">最后更新：2025年1月1日</p>
      </div>

      <div class="space-y-10 text-sm leading-relaxed" style="color:#888;">

        <section>
          <h2 class="text-base font-semibold text-white mb-3">1. 概述</h2>
          <p>Octopus AI Novel 非常重视您的隐私。本隐私政策说明我们如何收集、使用、存储和保护您的个人信息。使用本平台即表示您同意本政策的内容。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">2. 我们收集的信息</h2>
          <p class="mb-3">我们可能收集以下类型的信息：</p>
          <ul class="space-y-3 pl-4">
            <li class="flex items-start gap-2">
              <span style="color:#FFE500; margin-top:5px;">•</span>
              <span><strong class="text-white">账户信息：</strong>注册时提供的用户名、邮箱地址及加密存储的密码。</span>
            </li>
            <li class="flex items-start gap-2">
              <span style="color:#FFE500; margin-top:5px;">•</span>
              <span><strong class="text-white">创作内容：</strong>您在平台上创建的小说、大纲、章节等内容，用于提供服务。</span>
            </li>
            <li class="flex items-start gap-2">
              <span style="color:#FFE500; margin-top:5px;">•</span>
              <span><strong class="text-white">使用数据：</strong>访问日志、功能使用情况、设备类型等，用于改善服务质量。</span>
            </li>
            <li class="flex items-start gap-2">
              <span style="color:#FFE500; margin-top:5px;">•</span>
              <span><strong class="text-white">支付信息：</strong>订阅时的支付信息由第三方支付平台处理，我们不存储完整的支付卡号。</span>
            </li>
          </ul>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">3. 信息的使用</h2>
          <p class="mb-3">我们使用收集的信息用于：</p>
          <ul class="space-y-2 pl-4">
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>提供、维护和改善平台服务</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>处理账户注册、登录和订阅</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>发送服务通知、安全提醒和更新信息</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>分析平台使用趋势以优化用户体验</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>防范欺诈和滥用行为</span></li>
          </ul>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">4. 信息共享</h2>
          <p>我们不会出售您的个人信息。仅在以下情况下可能与第三方共享：</p>
          <ul class="space-y-2 pl-4 mt-3">
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>经您明确授权</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>法律法规要求或政府机关的合法要求</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span>为提供服务而委托的技术服务商（如云存储、邮件服务）</span></li>
          </ul>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">5. 数据安全</h2>
          <p>我们采用行业标准的安全措施保护您的数据，包括数据加密传输（HTTPS）、密码加密存储（bcrypt）等。尽管如此，没有任何方式能保证绝对安全，请妥善保管您的账户信息。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">6. Cookie 与追踪技术</h2>
          <p>本平台使用 Cookie 和本地存储来维持您的登录状态和偏好设置。您可以通过浏览器设置禁用 Cookie，但这可能影响部分功能的正常使用。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">7. 您的权利</h2>
          <p class="mb-3">您对自己的个人数据享有以下权利：</p>
          <ul class="space-y-2 pl-4">
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span><strong class="text-white">访问权：</strong>查看我们持有的关于您的信息</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span><strong class="text-white">更正权：</strong>要求更正不准确的个人信息</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span><strong class="text-white">删除权：</strong>在特定情况下要求删除您的账户和数据</span></li>
            <li class="flex items-start gap-2"><span style="color:#FFE500; margin-top:5px;">•</span><span><strong class="text-white">可携带权：</strong>以通用格式导出您的创作数据</span></li>
          </ul>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">8. 未成年人</h2>
          <p>本平台不面向 18 周岁以下的未成年人。如果您是未成年人，请在监护人的监督下使用本平台。如我们发现未成年人在未经监护人同意的情况下提供个人信息，我们将予以删除。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">9. 政策更新</h2>
          <p>我们可能定期更新本隐私政策。重大变更时，我们将通过平台通知或邮件告知您。建议您定期查阅本页面以了解最新政策。</p>
        </section>

        <section>
          <h2 class="text-base font-semibold text-white mb-3">10. 联系我们</h2>
          <p>如对本隐私政策有任何疑问或行使您的数据权利，请联系：<br><span style="color:#FFE500;">privacy@octopusainovel.com</span></p>
        </section>

      </div>

      <div class="mt-16 pt-8 flex items-center justify-between border-t" style="border-color:#1A1A1A;">
        <router-link to="/terms" class="text-sm transition-colors" style="color:#555;"
          @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
          @mouseleave="($event.target as HTMLElement).style.color='#555'">
          ← 服务条款
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
