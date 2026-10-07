#!/usr/bin/env node
/**
 * 丢词大作战 · 法律护栏
 *
 * 把「我们说过的法律话」变成可执行的断言。文档里写「公有领域」不算数，
 * 这条脚本逐篇核验作者卒年才算数。
 *
 * 五仓共用同一份逻辑，只有顶部的 CONFIG 不同。
 *
 * 用法：
 *   node tools/check-legal.mjs            校验
 *   node tools/check-legal.mjs --selftest 自检：坏样本必须被抓到
 */

import fs from 'node:fs'
import path from 'node:path'
import url from 'node:url'

const ROOT = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '..')

/** 本站版权行。每个仓的 LICENSE 都必须有这一行。 */
export const OUR_COPYRIGHT = '丢词大作战'

/** 绝对化表述。法律文本里出现这些词，等于替自己挖坑。 */
export const ABSOLUTE_PHRASES = [
  '零风险', '风险为 0', '风险为0', '风险为零', '绝无风险', '绝对保证', '万无一失',
  '100% 无风险', '100%无风险', '不会有任何纠纷', '版权无忧',
]

/** 全站不提某个第三方站名：玩法不受著作权保护，无需注明，提了反而生事。 */
export const FORBIDDEN_MENTIONS = ['poetrystrands', '古诗连词']

/** 自然人作品保护期：作者终生 + 死后第五十年的 12 月 31 日。 */
export const COPYRIGHT_YEARS = 50

export class LegalError extends Error {}

// ---------------------------------------------------------------- 纯检查

/** LICENSE：必须存在，必须有本站版权行；派生仓还必须保留上游版权行。 */
export function checkLicense(licenseText, cfg) {
  const problems = []
  if (licenseText === null)
    return ['缺少 LICENSE 文件']
  if (!licenseText.includes(OUR_COPYRIGHT))
    problems.push('LICENSE 里没有本站版权行（应含 "Copyright (c) ... ' + OUR_COPYRIGHT + '"）')
  for (const up of (cfg.upstreamCopyrights || [])) {
    if (!licenseText.includes(up))
      problems.push('LICENSE 丢了上游版权行：' + up)
  }
  return problems
}

/** vendor/ 下每一个装了第三方代码的目录都得带自己的 LICENSE。 */
export function checkVendor(dirsWithFiles, cfg) {
  const problems = []
  const vendorDirs = cfg.vendorDirs || []
  for (const dir of vendorDirs) {
    const hasLicense = dirsWithFiles.some(d => d.startsWith(dir + '/') || d === dir)
    if (!hasLicense)
      problems.push(dir + '/ 里有第三方代码，却没有 LICENSE')
  }
  return problems
}

/** 逐篇核验公有领域：卒年必须早于「当前年 − 50」。 */
export function checkCorpus(poems, thisYear) {
  const problems = []
  if (!Array.isArray(poems))
    return ['语料不是数组，无法核验公有领域']
  const cutoff = thisYear - COPYRIGHT_YEARS
  for (const p of poems) {
    const died = p.authorDied
    const era = p.authorEraEnd
    const year = Number.isInteger(died) ? died : (Number.isInteger(era) ? era : null)
    if (year === null) {
      problems.push((p.title || p.id || '?') + '：缺 authorDied / authorEraEnd，无法论证公有领域')
      continue
    }
    if (year > cutoff)
      problems.push((p.title || p.id || '?') + '：作者卒年 ' + year + ' 晚于 ' + cutoff + '，仍在保护期内')
  }
  return problems
}

/** 绝对化表述与不该出现的第三方站名。 */
/** 绝对化表述只查法律与文档文案——成语词库里「万无一失」是一个成语，不是我们在担保什么。 */
export function checkPhrasing(files, cfg) {
  const problems = []
  const scope = cfg && cfg.phraseScan
  const inScope = rel => !scope || scope.some(prefix => rel === prefix || rel.startsWith(prefix))
  for (const [name, text] of files) {
    if (inScope(name)) {
      for (const phrase of ABSOLUTE_PHRASES) {
        if (text.includes(phrase))
          problems.push(name + '：出现绝对化表述「' + phrase + '」——法律文本不做这种担保')
      }
    }
    for (const word of FORBIDDEN_MENTIONS) {
      if (text.toLowerCase().includes(word.toLowerCase()))
        problems.push(name + '：提到了「' + word + '」，本站不需要提及')
    }
  }
  return problems
}

/** 页面必须留一个能联系我们的入口（侵权通知）。 */
export function checkContact(texts, cfg) {
  const problems = []
  if (!cfg.contactEmail)
    return problems
  const joined = texts.map(([, t]) => t).join('\n')
  if (!joined.includes(cfg.contactEmail))
    problems.push('全站找不到侵权联系入口 ' + cfg.contactEmail)
  if (cfg.legalLink && !texts.some(([, t]) => t.includes(cfg.legalLink)))
    problems.push('页面里没有指向 ' + cfg.legalLink + ' 的法律页链接')
  return problems
}

// ---------------------------------------------------------------- 取数

const SKIP_DIRS = new Set(['.git', 'node_modules', 'dist', '.vitepress', '.baseline-handle', '__pycache__'])
const TEXT_EXT = new Set(['.md', '.txt', '.mjs', '.js', '.cjs', '.ts', '.vue', '.html', '.yml', '.yaml', '.json', '.css'])
// 检查器自己必然写着那些被禁的词——那是词表本身，不是文案。
// 不止本站那一份：k12-site 的 CI 会把内容仓检出到 content/，
// 于是 content/tools/check-legal.mjs 也被扫到，护栏因为「词表里写着那些词」而红。
// 凡是路径以 tools/check-legal.mjs 结尾的都跳过——文案照抓。
const SELF = 'tools/check-legal.mjs'
export const isChecker = rel => rel === SELF || rel.endsWith('/' + SELF)
const SKIP_FILES = new Set(['package-lock.json'])
/** 第三方原始数据不扫：那是 Unicode 的原文，改不了也不该改。 */
const SKIP_PATH_HINTS = ['data/unihan', 'vendor/']

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue
      walk(path.join(dir, entry.name), out)
      continue
    }
    if (!entry.isFile()) continue
    const rel = path.relative(ROOT, path.join(dir, entry.name)).split(path.sep).join('/')
    if (SKIP_FILES.has(entry.name)) continue
    if (SKIP_PATH_HINTS.some(h => rel.includes(h))) continue
    if (!TEXT_EXT.has(path.extname(entry.name))) continue
    out.push(rel)
  }
  return out
}

function readText(rel) {
  try {
    return fs.readFileSync(path.join(ROOT, rel), 'utf8')
  }
  catch {
    return null
  }
}

export function collect(cfg) {
  const files = walk(ROOT).filter(rel => !isChecker(rel)).map(rel => [rel, readText(rel)]).filter(([, t]) => t !== null)
  const licenseText = fs.existsSync(path.join(ROOT, 'LICENSE')) ? readText('LICENSE') : null
  const vendorDirs = []
  for (const dir of (cfg.vendorDirs || [])) {
    const abs = path.join(ROOT, dir)
    if (!fs.existsSync(abs)) continue
    for (const e of fs.readdirSync(abs, { withFileTypes: true })) {
      if (e.isFile() && /^licen[cs]e/i.test(e.name)) vendorDirs.push(dir)
    }
  }
  const poems = []
  for (const rel of (cfg.corpusFiles || [])) {
    const abs = path.join(ROOT, rel)
    if (!fs.existsSync(abs)) continue
    const parsed = JSON.parse(readText(rel))
    if (Array.isArray(parsed)) poems.push(...parsed)
    else if (Array.isArray(parsed.poems)) poems.push(...parsed.poems)
    else if (Array.isArray(parsed.items)) poems.push(...parsed.items)
  }
  return { files, licenseText, vendorDirs, poems }
}

export function runAll(cfg, thisYear) {
  const data = collect(cfg)
  const problems = [
    ...checkLicense(data.licenseText, cfg),
    ...checkVendor(data.vendorDirs, cfg),
    ...(data.poems.length ? checkCorpus(data.poems, thisYear) : []),
    ...checkPhrasing(data.files, cfg),
    ...checkContact(data.files, cfg),
  ]
  return { problems, data }
}

// ---------------------------------------------------------------- 自检

function selftest() {
  const problems = []
  const year = 2026
  const goodLicense = 'Copyright (c) 2026 ' + OUR_COPYRIGHT + '\nMIT'

  // 1) 没有 LICENSE 必须报
  if (checkLicense(null, { upstreamCopyrights: [] }).length === 0)
    problems.push('缺 LICENSE 应当报错，却放行了')
  // 2) 缺本站版权行必须报
  if (checkLicense('MIT License\n', { upstreamCopyrights: [] }).length === 0)
    problems.push('LICENSE 缺本站版权行应当报错，却放行了')
  // 3) 派生仓丢上游版权行必须报
  const derived = { upstreamCopyrights: ['Anthony Fu'] }
  if (checkLicense(goodLicense, derived).length === 0)
    problems.push('派生仓丢了上游版权行应当报错，却放行了')
  if (checkLicense(goodLicense + '\nCopyright (c) 2021 Anthony Fu', derived).length !== 0)
    problems.push('上游版权行齐全时不该报错，却误报')
  // 4) vendor 缺 LICENSE 必须报
  if (checkVendor(['three/README.md'], { vendorDirs: ['vendor/three'] }).length === 0)
    problems.push('vendor 缺 LICENSE 应当报错，却放行了')
  if (checkVendor(['vendor/three/LICENSE'], { vendorDirs: ['vendor/three'] }).length !== 0)
    problems.push('vendor 有 LICENSE 时不该报错，却误报')
  // 5) 卒年核验：保护期内必须报，恰好届满必须放行
  if (checkCorpus([{ title: '假作', authorDied: 1999 }], year).length === 0)
    problems.push('1999 年卒的作者应当报错，却放行了')
  if (checkCorpus([{ title: '假作', authorEraEnd: null, authorDied: null }], year).length === 0)
    problems.push('没有卒年证据的篇目应当报错，却放行了')
  if (checkCorpus([{ title: '假作', authorDied: year - COPYRIGHT_YEARS }], year).length !== 0)
    problems.push('恰好届满的应当放行，却误报')
  if (checkCorpus([{ title: '假作', authorEraEnd: 220 }], year).length !== 0)
    problems.push('佚名走年代上限应当放行，却误报')
  // 6) 绝对化表述必须被抓到
  if (checkPhrasing([['a.md', '本站版权零风险。']]).length === 0)
    problems.push('「零风险」这种绝对化表述应当报错，却放行了')
  // 7) 第三方站名必须被抓到
  if (checkPhrasing([['a.md', '玩法参考自 PoetryStrands。']]).length === 0)
    problems.push('提到不该提的站名应当报错，却放行了')
  // 8) 侵权联系入口缺失必须被抓到
  if (checkContact([['a.md', '没有邮箱']], { contactEmail: 'hi@diuci.com', legalLink: null }).length === 0)
    problems.push('缺侵权联系入口应当报错，却放行了')
  // 9) 检查器自身（包括内容仓那一份）不该被自己的词表绊倒；普通文案要照抓
  if (!isChecker('tools/check-legal.mjs') || !isChecker('content/tools/check-legal.mjs'))
    problems.push('检查器自身（含内容仓那一份）应当跳过，却没跳过')
  if (isChecker('site/legal.md'))
    problems.push('普通文案不该被跳过，却被跳过了')
  if (checkPhrasing([['content/site/x.md', '玩法参考自 古诗连词。']]).length === 0)
    problems.push('内容仓的文案提到禁词应当报错，却放行了')
  // 10) 全好的样本必须零问题——否则这条检查就是摆设
  if (checkLicense(goodLicense, { upstreamCopyrights: [] }).length !== 0)
    problems.push('正常 LICENSE 不该报错，却误报')

  if (problems.length) {
    console.error('[!!] check-legal --selftest 失败：')
    for (const p of problems) console.error('  - ' + p)
    process.exit(1)
  }
  console.log('[ok] check-legal --selftest 通过（缺 LICENSE、缺本站版权行、丢上游版权行、'
    + 'vendor 缺 LICENSE、卒年越界、缺卒年证据、绝对化表述、第三方站名、缺联系入口、检查器自身不误伤都试到了）')
  process.exit(0)
}

const isEntry = process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(url.fileURLToPath(import.meta.url))

if (isEntry) {
  const args = process.argv.slice(2)
  if (args.includes('--selftest'))
    selftest()

  const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'tools', 'check-legal.config.json'), 'utf8'))
  const { problems, data } = runAll(cfg, new Date().getFullYear())
  if (problems.length) {
    console.error('[!!] 法律护栏 ' + cfg.name + '：' + problems.length + ' 处问题')
    for (const p of problems.slice(0, 40)) console.error('  - ' + p)
    process.exit(1)
  }
  console.log('[ok] 法律护栏 ' + cfg.name + '：LICENSE 齐、vendor 许可齐、'
    + (data.poems.length ? data.poems.length + ' 篇公有领域可核验、' : '')
    + data.files.length + ' 个文本文件无绝对化表述')
}
