---
layout: page
title: 总览
description: K12 必背古诗文总览，按学段、主题、体裁筛选。
---

<div class="hero">
  <h1 class="hero-t">K12 中文古诗文</h1>
  <p class="hero-s">小学到高中必背古诗文，按教育部课程标准收录</p>
  <p class="hero-meta">
    <span id="stat-total">—</span> 篇 ｜ 诗经 · 乐府 · 五言 · 七言 · 词 · 曲 · 文言
  </p>
</div>

## 收录范围

| 学段 | 课标要求 | 说明 |
|---|---|---|
| 小学 1–6 年级 | 75 篇 | 全部为诗歌 |
| 初中 7–9 年级 | 60 篇 | 含短篇文言 |
| 高中 | 72 篇 | 文言 32 + 诗词曲 40 |
| **合计** | **207 篇** | 另收教材拓展篇目 |

课文用字以**人教社统编教材**为准。诗文原文属**公有领域**；注释、译文、赏析与选篇编排采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。

## 全部篇目

<div class="filters">
  <h3>学段 / 年级</h3>
  <div class="chips" id="f-stage"></div>

  <h3>主题</h3>
  <div class="chips" id="f-theme"></div>

  <h3>体裁</h3>
  <div class="chips" id="f-form"></div>

  <p class="count" id="count"></p>
</div>

<div class="grid" id="grid"></div>

<p class="count" style="margin-top:20px">
  提示：按 <kbd>Ctrl</kbd>+<kbd>K</kbd>（macOS <kbd>⌘</kbd>+<kbd>K</kbd>）可全文搜索 poems、作者、诗句。
</p>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useData } from 'vitepress'

// 用 siteData.base 拼路径：部署到 /<repo>/ 子路径时，
// 绝对路径 /catalog.json 会 404
const { site } = useData()
const RECITE = { full: '全文背', section: '背段落', line: '背名句', none: '理解' }

const all = ref([])
const fStage = ref('')
const fTheme = ref('')
const fForm = ref('')

const STAGES = ['小学', '初中', '高中']

onMounted(async () => {
  const res = await fetch(site.value.base + 'catalog.json')
  all.value = await res.json()

  // 统计
  const t = document.getElementById('stat-total')
  if (t) t.textContent = all.value.length

  // 筛选器：学段按固定顺序，主题与体裁按出现频次
  buildChips('f-stage', STAGES, () => fStage.value, v => (fStage.value = v))
  const themes = countBy(p => p.theme)
  const forms = countBy(p => [p.form])
  buildChips('f-theme', themes, () => fTheme.value, v => (fTheme.value = v))
  buildChips('f-form', forms, () => fForm.value, v => (fForm.value = v))
  render()
})

function countBy(fn) {
  const m = new Map()
  for (const p of all.value) {
    for (const k of [].concat(fn(p))) {
      if (k) m.set(k, (m.get(k) || 0) + 1)
    }
  }
  return [...m.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k)
}

function buildChips(id, keys, get, set) {
  const box = document.getElementById(id)
  if (!box) return
  const mk = (label, val, on) => {
    const s = document.createElement('span')
    s.className = 'chip' + (on ? ' on' : '')
    s.textContent = label
    s.onclick = () => {
      set(val)
      ;[...box.children].forEach(c => c.classList.remove('on'))
      if (val) s.classList.add('on')
      render()
    }
    return s
  }
  box.appendChild(mk('全部', '', false))
  for (const k of keys) box.appendChild(mk(k, k, false))
}

const shown = computed(() =>
  all.value.filter(
    p =>
      (!fStage.value || p.stage === fStage.value) &&
      (!fForm.value || p.form === fForm.value) &&
      (!fTheme.value || (p.theme || []).includes(fTheme.value))
  )
)

function render() {
  const grid = document.getElementById('grid')
  const cnt = document.getElementById('count')
  if (!grid) return
  grid.innerHTML = ''
  for (const p of shown.value) {
    const a = document.createElement('a')
    a.className = 'card'
    a.href = p.url
    const badge = p.recite && RECITE[p.recite] && p.recite !== 'none'
      ? `<span class="badge badge-recite">${RECITE[p.recite]}</span>` : ''
    a.innerHTML =
      `<div class="card-t">${esc(p.title)}${badge}</div>` +
      `<div class="card-a">${esc(p.author)} · ${esc(p.dynasty || '')}</div>` +
      (p.lines ? `<div class="card-l">${esc(p.lines)}</div>` : '')
    grid.appendChild(a)
  }
  if (cnt) {
    cnt.textContent = shown.value.length === all.value.length
      ? `共 ${all.value.length} 篇`
      : `筛选出 ${shown.value.length} / ${all.value.length} 篇`
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
}
</script>

<style>
.hero {
  padding: 30px 0 22px;
  margin-bottom: 10px;
  border-bottom: 2px solid var(--rule);
}
.hero-t {
  margin: 0 0 8px;
  font-family: var(--font-serif);
  font-size: 2.3rem;
  font-weight: 600;
  letter-spacing: 0.08em;
}
.hero-s {
  margin: 0 0 10px;
  font-size: 1.05rem;
  color: var(--vp-c-text-2);
}
.hero-meta { margin: 0; font-size: 0.88rem; color: var(--vp-c-text-3); }
</style>
