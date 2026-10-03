#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 poems/*.md 转成 VitePress 站点页面。

单篇 .md 已经是「人读的文章」，但它缺少站点需要的东西：拼音、玩法标签、
面包屑导航。本脚本在不改动 poems/ 的前提下，生成 site/ 下的站点副本。

产出：
  site/.vitepress/catalog.json      篇目总目录（供筛选/搜索用）
  site/.vitepress/theme/*.css       样式（诗词排版、打印版）
  site/poems/<学段>/<册次>/<篇名>.md ← 站点页面
  site/index.md                首页（自动生成，含三轴筛选数据）
  site/print.md                    A4 打印版（全部篇目纯文本）

用法：
    python tools/build-site.py
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ.get('CONTENT_ROOT') or Path(__file__).resolve().parent.parent)
POEMS = ROOT / 'poems'
SITE = Path(__file__).resolve().parent.parent / 'site'
DATA = ROOT / 'data' / 'poems.json'

SITE_POEMS = SITE / 'poems'


def die(msg):
    print('[site] ERROR: ' + msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- 拼音
# 站点给孩子用，加拼音能显著降低阅读门槛。这里用「汉字 → 拼音」的小表，
# 只覆盖篇目里出现的字；查不到的留空（不报错），可后续补全。
#数据来源：GB/T 16159-2012《汉字拼音方案》常用字表
PINYIN = {}


def load_pinyin():
    """从 data/pinyin.txt 读「汉字 拼音」对照表（每行一个），缺失则跳过。"""
    p = ROOT / 'data' / 'pinyin.txt'
    if not p.exists():
        return 0
    n = 0
    for line in p.read_text(encoding='utf-8').splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 1:
            PINYIN[parts[0]] = parts[1]
            n += 1
    return n


def with_pinyin(text):
    """给一行汉字加拼音（HTML ruby 注音）。查不到的字不注，留原样。"""
    if not PINYIN:
        return text
    out = []
    for ch in text:
        if ch in PINYIN:
            out.append('<ruby>%s<rp>（</rp><rt>%s</rt><rp>）</rp></ruby>'
                       % (ch, PINYIN[ch]))
        else:
            out.append(ch)
    return ''.join(out)


# ---------------------------------------------------------------- 解析
def parse_poem(md_path):
    """读单篇 md，拆出 frontmatter 各字段与正文各节。"""
    text = md_path.read_text(encoding='utf-8')
    parts = text.split('---', 2)
    if len(parts) < 3:
        die('%s: frontmatter 未闭合' % md_path.name)
    fm_text, body = parts[1], parts[2]

    fm = {}
    key = None
    for raw in fm_text.splitlines():
        if not raw.strip():
            continue
        m = re.match(r'^(\w+):\s*(.*)$', raw)
        if m:
            key = m.group(1)
            v = m.group(2).strip()
            fm[key] = parse_scalar(v)
        elif raw.lstrip().startswith('- ') and key:
            fm.setdefault(key, [])
            if isinstance(fm[key], list):
                fm[key].append(raw.lstrip()[2:].strip())

    # 正文按 H2 分节。注意两种结构：
    #   小学：H1 之后**没有** H2 包裹，正文直接跟在元信息引用行后
    #   初中/高中：正文包在「## 必背全文」/「## 必背名句」里
    # 所以 H1 之后、首个 H2 之前的内容也要收集，作为无标题的正文段。
    sections = {}
    cur = None
    buf = []
    seen_h1 = False

    def flush():
        if cur is not None and buf:
            sections[cur] = '\n'.join(buf).strip()

    for raw in body.splitlines():
        s = raw.strip()
        if s.startswith('# '):
            flush()
            cur, buf = None, []
            seen_h1 = True
            continue
        if not seen_h1:
            continue
        if s.startswith('## '):
            flush()
            cur = s[3:].strip()
            buf = []
            continue
        if s.startswith('>'):
            continue                    # 元信息引用行
        if cur is None:
            # 首个 H2 之前的内容 = 正文（小学结构）
            cur = '正文'
        buf.append(raw)
    flush()

    title_line = ''
    m = re.search(r'^#\s+(.+)$', body, re.M)
    if m:
        title_line = m.group(1).strip()

    return fm, sections, title_line


def parse_scalar(v):
    if v in ('null', '~', ''):
        return None
    if v == 'true':
        return True
    if v == 'false':
        return False
    if v.startswith('[') and v.endswith(']'):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip('\'"') for x in inner.split(',')]
    if re.match(r'^-?\d+$', v):
        return int(v)
    if re.match(r'^-?\d+\.\d+$', v):
        return float(v)
    if v.startswith('{') and v.endswith('}'):
        out = {}
        for part in re.findall(r'(\w+):\s*([^,}]+)', v[1:-1]):
            out[part[0]] = part[1].strip().strip('\'"')
        return out
    return v


# ---------------------------------------------------------------- 渲染
RECITE_LABEL = {
    'full': '全文背诵',
    'section': '背诵段落',
    'line': '背诵名句',
    'none': '理解为主',
}

STAGE_ORDER = ['小学', '初中', '高中']


def render_page(fm, sections, title_line, catalog_entry):
    """生成单篇站点页面。"""
    sid = fm.get('id')
    title = fm.get('title')
    author = fm.get('author')
    dyn = fm.get('dynasty')
    form = fm.get('form')
    stage = fm.get('stage')
    volume = fm.get('volume')
    theme = fm.get('theme') or []
    tech = fm.get('technique') or []
    recite = fm.get('recite')

    L = []
    L.append('---')
    L.append('title: %s' % title)
    L.append('description: %s · %s · %s' % (author, dyn, title))
    L.append('outline: [2, 3]')
    L.append('---')
    L.append('')

    # ---- 题头信息卡
    L.append('<div class="poem-head">')
    L.append('  <h1 class="poem-title">%s</h1>' % title)
    L.append('  <div class="poem-meta">')
    L.append('    <span class="m-author">%s</span>' % author)
    L.append('    <span class="m-dyn">%s</span>' % dyn)
    L.append('    <span class="m-form">%s</span>' % form)
    L.append('    <span class="m-stage">%s</span>' % stage)
    L.append('    <span class="m-vol">%s</span>' % volume)
    L.append('  </div>')
    # 标签区：背诵要求（若有）+ 主题 + 手法，任一存在就渲染
    if recite or theme or tech:
        L.append('  <div class="poem-tags">')
        if recite:
            L.append('    <span class="tag tag-recite">%s</span>'
                     % RECITE_LABEL.get(recite, recite))
        for t in theme:
            L.append('    <span class="tag">%s</span>' % t)
        for t in tech:
            L.append('    <span class="tag tag-tech">%s</span>' % t)
        L.append('  </div>')
    L.append('</div>')
    L.append('')

    # ---- 正文（必背全文/名句，或小学的无标题正文）
    main_key = None
    for k in sections:
        if k.startswith('必背') or k == '正文':
            main_key = k
            break
    if main_key:
        L.append('<div class="poem-body">')
        L.append(with_pinyin(sections[main_key]))
        L.append('</div>')
        L.append('')

    # ---- 注释 / 译文 / 赏析
    plain = {
        '注释': 'note', '译文': 'trans', '赏析': 'appr',
    }
    for sec, css in plain.items():
        body_txt = sections.get(sec, '')
        if not body_txt:
            continue
        if '待补' in body_txt and len(body_txt.strip()) < 40:
            L.append('<div class="pending">')
            L.append('  <h2>%s</h2>' % sec)
            L.append('  <p class="pending-note">%s 正在编写中</p>' % sec)
            L.append('</div>')
            continue
        L.append('<div class="poem-%s">' % css)
        L.append('## %s' % sec)
        L.append('')
        L.append(body_txt)
        L.append('</div>')
        L.append('')

    # ---- 玩法数据
    game = sections.get('玩法数据', '')
    if game:
        L.append('<div class="poem-game">')
        L.append('## 玩法数据')
        L.append('')
        L.append(game)
        L.append('</div>')

    L.append('<div class="poem-foot">')
    L.append('  <a class="back" href="/">← 返回总览</a>')
    L.append('  <span class="src">来源：%s ｜ 许可：%s</span>'
             % (fm.get('source', ''), fm.get('license', '')))
    L.append('</div>')

    return '\n'.join(L) + '\n'


# ---------------------------------------------------------------- 主流程
def esc(s):
    return (str(s if s is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def render_print(catalog):
    """生成 A4 打印版：全部篇目纯文本，按学段分页。"""
    L = ['---', 'title: 打印版', '---', '']
    L.append('# K12 中文古诗文 · 打印版')
    L.append('')
    L.append('全部 %d 篇，按学段与册次排列。适合打印装订成册。' % len(catalog))
    L.append('')
    L.append('> 打印建议用 A4 纸。篇目页与本打印版都已适配打印样式。')
    L.append('')

    by_stage = {}
    for e in catalog:
        by_stage.setdefault(e['stage'], []).append(e)

    for stage in STAGE_ORDER:
        items = by_stage.get(stage)
        if not items:
            continue
        L.append('<div class="page-break"></div>')
        L.append('## %s（%d 篇）' % (stage, len(items)))
        L.append('')

        by_vol = {}
        for e in items:
            by_vol.setdefault(e['volume'], []).append(e)

        for vol in sorted(by_vol):
            L.append('### %s' % vol)
            L.append('')
            for e in sorted(by_vol[vol], key=lambda x: x['title']):
                L.append('<div class="print-item">')
                L.append('  <div class="p-title">%s<span class="p-author">%s · %s</span></div>'
                         % (esc(e['title']), esc(e['author']), esc(e['dynasty'])))
                if e.get('lines'):
                    L.append('  <div class="p-line">%s</div>' % esc(e['lines']))
                L.append('</div>')
                L.append('')
    return '\n'.join(L) + '\n'


def main():
    if not DATA.exists():
        die('缺少 data/poems.json，请先跑 python tools/build.py')
    n_pinyin = load_pinyin()

    # 清空旧的站点篇目（保留 .vitepress 与手写页面）
    if SITE_POEMS.exists():
        shutil.rmtree(SITE_POEMS)

    catalog = []
    for md in sorted(POEMS.rglob('*.md')):
        if md.name == '索引.md':
            continue
        fm, sections, title_line = parse_poem(md)
        rel = md.relative_to(POEMS)
        # 站点路径：保留 学段/册次 层级，但去掉可能含 Windows 保留名的目录
        parts = list(rel.parts[:-1]) + [md.stem + '.md']
        out = SITE_POEMS.joinpath(*parts)
        out.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            'id': fm.get('id'),
            'title': fm.get('title'),
            'subtitle': fm.get('subtitle'),
            'author': fm.get('author'),
            'dynasty': fm.get('dynasty'),
            'form': fm.get('form'),
            'stage': fm.get('stage'),
            'grade': fm.get('grade'),
            'volume': fm.get('volume'),
            'theme': fm.get('theme') or [],
            'tech': fm.get('technique') or [],
            'recite': fm.get('recite'),
            'freq': fm.get('exam_freq'),
            'difficulty': fm.get('difficulty'),
            'pairs': fm.get('pairs') or [],
            'lines': None,
            'url': '/poems/' + '/'.join(parts).replace('\\', '/'),
        }
        # 原文首句，供列表页展示
        main_key = next((k for k in sections
                         if k.startswith('必背') or k == '正文'), None)
        if main_key:
            first = next((x.strip() for x in sections[main_key].splitlines()
                          if x.strip()), '')
            entry['lines'] = re.sub(r'<[^>]+>', '', first)[:40]
        catalog.append(entry)

        out.write_text(render_page(fm, sections, title_line, entry),
                       encoding='utf-8')

    # ---- 目录 json（给首页筛选/搜索用）
    # 必须放 site/public/ —— VitePress 会把 public 下的文件原样复制到输出，
    # 而 .vitepress/ 是配置目录，其中的静态文件不会被拷贝（会404）。
    pub = SITE / 'public'
    pub.mkdir(parents=True, exist_ok=True)
    (pub / 'catalog.json').write_text(
        json.dumps(catalog, ensure_ascii=False, indent=1), encoding='utf-8')

    # ---- 打印版
    (SITE / 'print.md').write_text(render_print(catalog), encoding='utf-8')

    print('[site] 生成 %d 个篇目页面%s'
          % (len(catalog),
             '（拼音表 %d 字）' % n_pinyin if n_pinyin else '（无拼音表）'))
    print('[site] 目录：site/public/catalog.json')
    print('[site] 打印版：site/print.md')
    print('[site] 下一步：npm run dev 预览，npm run build 构建')


if __name__ == '__main__':
    main()