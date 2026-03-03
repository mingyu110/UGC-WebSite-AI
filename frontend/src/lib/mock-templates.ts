// =============================================================================
// UGC AI Demo - Mock Templates (Simplified)
// =============================================================================

export interface MockTemplate {
  name: string;
  keywords: string[];
  html: string;
  css: string;
  javascript?: string;
}

// Landing Page Template
const landingPageTemplate: MockTemplate = {
  name: '现代风格落地页',
  keywords: ['落地页', 'landing', '首页', '主页', '咖啡', '餐厅', '店铺'],
  html: `<div class="min-h-screen bg-gradient-to-b from-amber-50 to-white">
  <nav class="flex items-center justify-between px-8 py-4">
    <div class="text-2xl font-bold text-amber-800">CafeDemo</div>
    <div class="flex gap-6">
      <a href="#" class="text-gray-600 hover:text-amber-800">首页</a>
      <a href="#" class="text-gray-600 hover:text-amber-800">菜单</a>
      <a href="#" class="text-gray-600 hover:text-amber-800">关于</a>
      <a href="#" class="text-gray-600 hover:text-amber-800">联系</a>
    </div>
  </nav>
  <header class="text-center py-20 px-4">
    <h1 class="text-5xl font-bold text-gray-900 mb-6">品味生活的每一刻</h1>
    <p class="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">精选咖啡豆，匠心烘焙，为您带来最纯正的咖啡体验</p>
    <button class="bg-amber-600 text-white px-8 py-3 rounded-full text-lg hover:bg-amber-700">立即预约</button>
  </header>
  <section class="grid grid-cols-3 gap-8 px-8 py-16 max-w-6xl mx-auto">
    <div class="text-center p-6">
      <div class="w-16 h-16 bg-amber-100 rounded-full mx-auto mb-4 flex items-center justify-center">
        <span class="text-2xl">☕</span>
      </div>
      <h3 class="text-xl font-semibold mb-2">精选咖啡</h3>
      <p class="text-gray-600">来自世界各地的优质咖啡豆</p>
    </div>
    <div class="text-center p-6">
      <div class="w-16 h-16 bg-amber-100 rounded-full mx-auto mb-4 flex items-center justify-center">
        <span class="text-2xl">🍰</span>
      </div>
      <h3 class="text-xl font-semibold mb-2">精致甜点</h3>
      <p class="text-gray-600">每日新鲜制作的美味甜品</p>
    </div>
    <div class="text-center p-6">
      <div class="w-16 h-16 bg-amber-100 rounded-full mx-auto mb-4 flex items-center justify-center">
        <span class="text-2xl">🌿</span>
      </div>
      <h3 class="text-xl font-semibold mb-2">舒适环境</h3>
      <p class="text-gray-600">温馨雅致的休闲空间</p>
    </div>
  </section>
</div>`,
  css: '',
};

// Portfolio Template
const portfolioTemplate: MockTemplate = {
  name: '个人作品集',
  keywords: ['作品集', 'portfolio', '个人', '简历', '设计师', '开发者'],
  html: `<div class="min-h-screen bg-gray-900 text-white">
  <nav class="flex items-center justify-between px-8 py-6">
    <div class="text-xl font-bold">Portfolio</div>
    <div class="flex gap-6">
      <a href="#" class="text-gray-400 hover:text-white">作品</a>
      <a href="#" class="text-gray-400 hover:text-white">关于</a>
      <a href="#" class="text-gray-400 hover:text-white">联系</a>
    </div>
  </nav>
  <header class="text-center py-32 px-4">
    <p class="text-blue-400 mb-4">你好，我是</p>
    <h1 class="text-6xl font-bold mb-6">张小明</h1>
    <p class="text-xl text-gray-400 max-w-xl mx-auto">全栈开发者 / UI设计师</p>
  </header>
  <section class="px-8 py-16 max-w-5xl mx-auto">
    <h2 class="text-3xl font-bold mb-8 text-center">精选作品</h2>
    <div class="grid grid-cols-2 gap-6">
      <div class="bg-gray-800 rounded-lg p-6 hover:bg-gray-700 transition">
        <div class="h-40 bg-gradient-to-r from-blue-500 to-purple-500 rounded mb-4"></div>
        <h3 class="text-xl font-semibold mb-2">电商平台</h3>
        <p class="text-gray-400">React + Node.js 全栈项目</p>
      </div>
      <div class="bg-gray-800 rounded-lg p-6 hover:bg-gray-700 transition">
        <div class="h-40 bg-gradient-to-r from-green-500 to-teal-500 rounded mb-4"></div>
        <h3 class="text-xl font-semibold mb-2">数据可视化</h3>
        <p class="text-gray-400">D3.js 交互式图表</p>
      </div>
    </div>
  </section>
</div>`,
  css: '',
};

// Blog Template
const blogTemplate: MockTemplate = {
  name: '博客首页',
  keywords: ['博客', 'blog', '文章', '日记', '写作'],
  html: `<div class="min-h-screen bg-white">
  <nav class="border-b px-8 py-4 flex items-center justify-between">
    <div class="text-2xl font-serif font-bold">My Blog</div>
    <div class="flex gap-6">
      <a href="#" class="text-gray-600 hover:text-gray-900">首页</a>
      <a href="#" class="text-gray-600 hover:text-gray-900">归档</a>
      <a href="#" class="text-gray-600 hover:text-gray-900">关于</a>
    </div>
  </nav>
  <main class="max-w-3xl mx-auto px-4 py-12">
    <article class="mb-12 pb-12 border-b">
      <p class="text-sm text-gray-500 mb-2">2024年1月15日</p>
      <h2 class="text-3xl font-bold mb-4 hover:text-blue-600 cursor-pointer">探索现代前端开发的最佳实践</h2>
      <p class="text-gray-600 leading-relaxed mb-4">在这篇文章中，我们将探讨现代前端开发中的一些最佳实践，包括组件设计、状态管理和性能优化...</p>
      <a href="#" class="text-blue-600 hover:underline">阅读更多 →</a>
    </article>
    <article class="mb-12 pb-12 border-b">
      <p class="text-sm text-gray-500 mb-2">2024年1月10日</p>
      <h2 class="text-3xl font-bold mb-4 hover:text-blue-600 cursor-pointer">AI如何改变我们的工作方式</h2>
      <p class="text-gray-600 leading-relaxed mb-4">人工智能正在深刻地改变各行各业的工作方式。让我们看看AI带来的机遇与挑战...</p>
      <a href="#" class="text-blue-600 hover:underline">阅读更多 →</a>
    </article>
  </main>
</div>`,
  css: '',
};

// All templates
const templates: MockTemplate[] = [
  landingPageTemplate,
  portfolioTemplate,
  blogTemplate,
];

/**
 * Get mock template based on prompt keywords
 */
export function getMockTemplate(prompt: string): MockTemplate {
  const lowerPrompt = prompt.toLowerCase();

  for (const template of templates) {
    if (template.keywords.some(kw => lowerPrompt.includes(kw))) {
      return template;
    }
  }

  return landingPageTemplate; // Default
}
