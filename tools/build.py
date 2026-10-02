#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""丢词大作战 · 内容仓构建脚本

把 poems/**/*.md（Markdown + YAML frontmatter）编译成 data/poems.json。

设计要点：
  * 纯标准库实现，不依赖 pyyaml —— 内容仓要做到 clone 即可跑
  * 所有文件读写显式 encoding='utf-8'（Windows 默认 GBK 会直接崩）
  * 正文段落 → lines[]（去标点，供地面贴花）+ linesPunct[]（保留标点，供显示）

用法：
    python tools/build.py            # 生成 data/poems.json + checksums.json
    python tools/build.py --check    # 只校验，不写文件（供CI 用）
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POEMS_DIR = ROOT / 'poems'
DATA_DIR = ROOT / 'data'

# 句末标点。中文诗词正文里的标点一律剥离，只保留汉字。
SENT_END = '。！？；，、：,.!?;:'
# 破折号与省略号在诗句内属内容还是标点？《江南》"鱼戏莲叶间，" 用逗号，
# 但诗句主体不含这些符号，剥离即可。
DASH = '——…'

# 去掉 Markdown 引用/标题/表格/列表等非正文标记
MD_NOISE = re.compile(r'^\s*(#|>|[-*+] |\d+\. |\|)')


def die(msg, *args):
    print('[build] ERROR: ' + (msg % args if args else msg), file=sys.stderr)
    sys.exit(1)


def parse_frontmatter(text, path):
    """切出 YAML frontmatter 与正文。

    不用 pyyaml：这里只需要支持我们自己写的那几种标量/行内结构，
    全量 YAML 会引入依赖，而内容仓必须零依赖可跑。
    """
    if not text.startswith('---'):
        die('%s: 缺少 frontmatter（首行应为 ---）', path.name)
    parts = text.split('---', 2)
    if len(parts) < 3:
        die('%s: frontmatter 未闭合', path.name)
    fm_text, body = parts[1], parts[2]

    fm = {}
    key = None
    for raw in fm_text.splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        m = re.match(r'^(\w+):\s*(.*)$', raw)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            fm[key] = val
        elif raw.lstrip().startswith('- ') and key:
            # 简写的行内列表（仅用于 tags 之类，本仓不依赖）
            fm.setdefault('_list_' + key, []).append(raw.lstrip()[2:].strip())
    return fm, body


def scalar(fm, key, default=None, required=False, path=''):
    v = fm.get(key, default)
    if v is None:
        if required:
            die('%s: 缺少必填字段 %s', path, key)
        return default
    if v == 'null' or v == '~':
        return None
    if v == 'true':
        return True
    if v == 'false':
        return False
    if isinstance(v, str) and v.startswith('[') and v.endswith(']'):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip('\'"') for x in inner.split(',')]
    if isinstance(v, str) and v.isdigit():
        return int(v)
    if isinstance(v, str) and re.match(r'^-?\d+\.\d+$', v):
        return float(v)
    return v


def extract_poem_lines(body):
    """从正文抽出正文段落（不含标题、注释、译文、赏析等章节）。

    约定：正文是文档里紧跟 H1 标题之后、第一个 H2 之前的段落。
    这样单篇文件既是人读的文章，也是机器的数据源。
    """
    lines = []
    started = False
    for raw in body.splitlines():
        s = raw.strip()
        if s.startswith('# '):
            started = True
            continue
        if s.startswith('##'):
            break                      # 到下一个章节就停
        if not started or not s or MD_NOISE.match(raw):
            continue
        lines.append(s)
    return lines


def strip_punct(s):
    out = []
    for ch in s:
        if ch in SENT_END or ch in DASH:
            continue
        out.append(ch)
    return ''.join(out)


def split_line_punct(s):
    """保留标点，但把句末标点规整为中文句读。"""
    return s.strip()


def build_record(md_path, fm, body):
    rel = md_path.relative_to(ROOT)
    poem_lines = extract_poem_lines(body)
    if not poem_lines:
        die('%s: 未找到正文段落', rel)

    lines = [strip_punct(x) for x in poem_lines]
    lines = [x for x in lines if x]
    if not lines:
        die('%s: 剥离标点后正文为空', rel)

    # pairs 形如 "0-1,2-3"，用短横线避免 YAML 里的逗号歧义
    pairs = []
    raw_pairs = fm.get('pairs', '')
    if raw_pairs:
        for chunk in str(raw_pairs).replace('[', '').replace(']', '').split(','):
            chunk = chunk.strip().strip('\'"')
            if not chunk:
                continue
            mm = re.match(r'^(\d+)\s*-\s*(\d+)$', chunk)
            if mm:
                pairs.append([int(mm.group(1)), int(mm.group(2))])

    form = scalar(fm, 'form')
    # syllables：一联的字数（五言一联 10 字，七言一联 14 字）。
    # 词、曲、杂言、文言不适用，留None。
    syllables = None
    if form == '五言':
        syllables = 10
    elif form == '七言':
        syllables = 14

    # 渲染层拆分：每整句在地面按逗号拆成几行（游戏贴花层用）
    rs = scalar(fm, 'render_split')
    render_split = [int(x) for x in rs] if rs else [1] * len(lines)
    if len(render_split) != len(lines):
        die('%s: render_split %d 项与 lines %d 句不匹配'
            % (path.name, len(render_split), len(lines)))

    src = fm.get('source', '')
    crosscheck = ''
    if '+' in str(src):
        crosscheck = str(src).split('+', 1)[1]

    return {
        'id': scalar(fm, 'id', required=True, path=str(rel)),
        'title': scalar(fm, 'title', required=True, path=str(rel)),
        'subtitle': scalar(fm, 'subtitle'),
        'author': scalar(fm, 'author', required=True, path=str(rel)),
        'dynasty': scalar(fm, 'dynasty'),
        'form': form,
        'stage': scalar(fm, 'stage'),
        'grade': scalar(fm, 'grade'),
        'volume': scalar(fm, 'volume'),
        'textbooks': scalar(fm, 'textbooks', ['统编']) or ['统编'],
        'lines': lines,
        'linesPunct': [split_line_punct(x) for x in poem_lines],
        'pairs': pairs,
        'syllables': syllables,
        'render_split': render_split,
        'theme': scalar(fm, 'theme', []) or [],
        'emotion': scalar(fm, 'emotion'),
        'technique': scalar(fm, 'technique', []) or [],
        'difficulty': scalar(fm, 'difficulty', 1),
        'examFreq': scalar(fm, 'exam_freq', 0),
        'tags': scalar(fm, 'tags', []) or [],
        'source': str(src),
        'license': scalar(fm, 'license', 'public-domain'),
        'copyright': scalar(fm, 'copyright', 'public-domain') or 'public-domain',
        'irregular': scalar(fm, 'irregular'),
        '_path': str(rel).replace('\\', '/'),
    }


def main():
    check_only = '--check' in sys.argv

    if not POEMS_DIR.exists():
        die('找不到目录 %s', POEMS_DIR)

    md_files = sorted(p for p in POEMS_DIR.rglob('*.md')
                      # 索引.md 是自动生成的导航页，没有 frontmatter，跳过
                      if p.name != '索引.md')
    if not md_files:
        die('%s 下没有 .md 文件', POEMS_DIR)

    records = []
    for md in md_files:
        text = md.read_text(encoding='utf-8')
        fm, body = parse_frontmatter(text, md)
        records.append(build_record(md, fm, body))

    # 稳定排序：学段→ 年级 → 标题，保证每次构建产物一致
    records.sort(key=lambda r: (str(r.get('stage') or ''), r.get('grade') or 0, r['title']))

    # 索引
    by_id = {r['id']: r['id'] for r in records}
    by_grade = {}
    for r in records:
        k = str(r.get('stage') or '') + '-' + str(r.get('grade') or '')
        by_grade.setdefault(k, []).append(r['id'])
    by_theme = {}
    for r in records:
        for t in (r.get('theme') or []):
            by_theme.setdefault(t, []).append(r['id'])

    payload = {
        'contentVersion': '2026.10.02',
        'count': len(records),
        'byId': by_id,
        'byGrade': by_grade,
        'byTheme': by_theme,
        'poems': records,
    }

    blob = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / 'poems.json'
    out.write_text(blob, encoding='utf-8')

    # 内容哈希：游戏侧用来确认内容仓与本地快照是否一致
    sums = {
        r['id']: hashlib.sha256(
            json.dumps(r, ensure_ascii=False, sort_keys=True).encode('utf-8')
        ).hexdigest()[:16]
        for r in records
    }
    (DATA_DIR / 'checksums.json').write_text(
        json.dumps({'contentVersion': payload['contentVersion'], 'sums': sums},
                   ensure_ascii=False, indent=2, sort_keys=True),
        encoding='utf-8')

    print('[build] %d 篇→ %s' % (len(records), out.relative_to(ROOT)))
    print('[build] 索引：学段组%d / 主题 %d' % (len(by_grade), len(by_theme)))

    if check_only:
        print('[build] --check：仅校验，未写入')
        for r in records:
            print('  - %-22s %s' % (r['id'], r['title']))


if __name__ == '__main__':
    main()