<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElButton } from 'element-plus'
import 'element-plus/es/components/button/style/css'

const status = ref('正在连接后端…')
const mode = ref('未知')
const loading = ref(false)
const names = ['文本编辑', '视觉分析', '网络检索', '图像生成']
async function refresh() {
  loading.value = true
  mode.value = '未知'
  try {
    const response = await fetch('/actuator/info', { signal: AbortSignal.timeout(5000) })
    if (!response.ok) throw new Error('unavailable')
    const data: unknown = await response.json()
    if (!data || typeof data !== 'object' || !('skeleton' in data)) throw new Error('invalid')
    const info = data.skeleton as Record<string, unknown>
    if (!['mock', 'dev', 'prod'].includes(String(info.mode)) || info.paidCallsEnabled !== false) throw new Error('invalid')
    mode.value = String(info.mode)
    status.value = '后端已连接 · 工程骨架'
  } catch {
    status.value = '后端不可用或响应不兼容，请检查服务后重试。'
  } finally { loading.value = false }
}
onMounted(refresh)
</script>

<template>
  <main>
    <p class="eyebrow">AI EDITORIAL AGENT</p>
    <h1>编辑工作台</h1>
    <p class="notice">内部编辑草稿，尚未完成事实与版权核查</p>
    <section aria-labelledby="connection">
      <h2 id="connection">工程连接状态</h2>
      <p role="status" aria-live="polite">{{ status }}</p>
      <p>运行模式：<strong>{{ mode }}</strong> · 契约：1.0.0-rc.3</p>
      <ElButton :loading="loading" @click="refresh">重新检查连接</ElButton>
    </section>
    <section aria-labelledby="capabilities">
      <h2 id="capabilities">能力尚未接入</h2>
      <ul><li v-for="name in names" :key="name"><strong>{{ name }}</strong><span>不可用 · 等待 Provider 与预算模块接入</span></li></ul>
      <p>本页仅用于验证启动。mock 模式不代表模型调用成功；当前没有收费调用，也不能创建、批准或正式导出文章。</p>
    </section>
  </main>
</template>

<style>
:root { font-family: system-ui, "Microsoft YaHei", sans-serif; color: #1e293b; background: #f5f7fa; line-height: 1.6; }
body { margin: 0; } main { max-width: 800px; margin: 48px auto; padding: 0 24px; }
h1 { font-size: 32px; margin: 8px 0 20px; } h2 { font-size: 19px; margin-top: 0; }
.eyebrow { font-size: 12px; letter-spacing: .16em; color: #475569; }
.notice { padding: 14px 18px; background: #fff5d6; border-left: 4px solid #a16207; }
section { background: white; border: 1px solid #dbe2ea; border-radius: 12px; padding: 24px; margin-top: 22px; }
ul { list-style: none; padding: 0; } li { display: flex; flex-wrap: wrap; gap: 8px 24px; padding: 12px 0; border-bottom: 1px solid #e2e8f0; }
li span { color: #475569; } button:focus-visible { outline: 3px solid #1d4ed8; outline-offset: 3px; }
</style>
