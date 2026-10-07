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

    约定：正文是文档里 H1 标题之后的**第一个内容章节**。该章节可能没有
    标题（小学：正文直接跟在 H1 与元信息引用行之后），也可能有标题
    （初中/高中：「## 必背全文」「## 必背名句」）。所以规则是——
    H1 之后的第一个 H2 若还没收集到任何正文段落，就当作正文的开始标记；
    一旦收集过内容，后续的 H2 就是章节结束。

    这样单篇文件既是人读的文章，也是机器的数据源。
    """
    lines = []
    started = False          # 已遇到 H1
    in_body = False           # 已进入正文区域
    for raw in body.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith('# '):
            started = True
            continue
        if not started:
            continue
        if s.startswith('## '):
            if in_body:
                break            # 已在正文里，遇到下一个 H2 即结束
            in_body = True        # 第一个 H2 = 正文开始标记
            continue
        if s.startswith('>'):
            continue             # 引用行是元信息（作者/朝代/册次）
        if MD_NOISE.match(raw):
            continue
        in_body = True            # 无标题的正文：内容行本身就是开始
        lines.append(s)
    return lines


def extract_full_lines(body):
    """抽「## 必背全文」/「## 全文」小节里的段落，作为背诵用的全文。

    为什么要单独抽：游戏单元要短（一句、一联），背诵要整篇。
    高中有 32 篇只有必背名句，全文小节里写的是「完整原文待补」——
    而课标把这些篇目列在默写范围里，只有名句等于没备齐。
    全文与游戏单元分开存，补全文就不会把游戏的句子单位撑长。
    """
    out = []
    in_sec = False
    for raw in body.splitlines():
        s = raw.strip()
        if s.startswith('## '):
            in_sec = s[3:].strip() in ('必背全文', '全文')
            continue
        if not in_sec or not s:
            continue
        if s.startswith('>'):
            continue
        if MD_NOISE.match(raw):
            continue
        out.append(s)
    return out


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


def body_section_names(body):
    """篇目文件里的 H2 小节名列表。

    「这篇到底收没收到全文」这件事只能按小节结构判断，而且必须只有一处实现：
    台账和校验器都读同一个字段，不许各自数一遍。
    """
    return [m.group(1).strip() for m in re.finditer(r'^##\s+(.+)$', body, re.M)]


# 正文起点只许是诗本身。
# 把「收录范围」这类说明小节写在最前面，会被 extract_poem_lines 当成正文开始标记，
# 于是说明文字被当成诗的句子。以前只有写了 render_split 的篇目才会暴露（对不上才报错），
# 没写的就静默把说明当正文——这种检查不能靠运气。
ALLOWED_BODY_SECTIONS = ('必背名句', '必背全文', '全文')


def body_start_section(body):
    """正文是从哪个小节名开始的；如果正文前面没有小节（短篇直接写在篇名下），返回 None。

    判据必须和 extract_poem_lines 一致：只有「第一个 H2 之前一行正文都没有」时，
    那个 H2 才是正文开始标记。满江红那种正文写在篇名下、第一个 H2 是「注释」的，
    不是问题——照第一个 H2 一刀切会把好样本误杀。
    """
    for raw in body.splitlines():
        s = raw.strip()
        if not s or s.startswith('# ') or s.startswith('>'):
            continue
        # 顺序必须和 extract_poem_lines 一致：先认 H2，再判噪声。
        # MD_NOISE 的 # 会把 H2 一起吞掉，先判噪声就等于这道护栏永远不触发。
        if s.startswith('## '):
            name = s[3:].strip()
            return name if name not in ALLOWED_BODY_SECTIONS else None
        if MD_NOISE.match(raw):
            continue
        return None
    return None


def has_full_text(body):
    """仓内是否收录了这篇的全文正文。口径：

      · 有「全文」或「必背全文」小节 → 有；
      · 没有「必背名句」小节 → 正文直接写在篇名下面，短篇的正文就是全文 → 有；
      · 只有「必背名句」小节 → 本篇收的是节选 → 没有。
    """
    secs = body_section_names(body)
    return ('全文' in secs) or ('必背全文' in secs) or ('必背名句' not in secs)


def build_record(md_path, fm, body):
    rel = md_path.relative_to(ROOT)
    poem_lines = extract_poem_lines(body)
    if not poem_lines:
        die('%s: 未找到正文段落', rel)

    lines = [strip_punct(x) for x in poem_lines]
    lines = [x for x in lines if x]
    if not lines:
        die('%s: 剥离标点后正文为空', rel)

    guard = body_start_section(body)
    if guard:
        die('%s: 正文起点是「%s」小节，说明文字会被当成诗的句子；把它挪到正文小节之后'
            % (rel, guard))

    # 背诵用的全文，与游戏单元分开存（见 extract_full_lines 的说明）
    full_body = extract_full_lines(body)
    full_lines = [strip_punct(x) for x in full_body]
    full_lines = [x for x in full_lines if x]

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

    # 公有领域证据：作者卒年，或佚名/乐府/民歌的年代上限。
    # 缺这个字段就不许构建——「这篇是公有领域」必须是可核验的事实，
    # 不能只是文档里的口头承诺。
    died_raw = fm.get('authorDied')
    era_raw = fm.get('authorEraEnd')
    if died_raw in (None, '') and era_raw in (None, ''):
        die('%s: 缺 authorDied / authorEraEnd，无法论证公有领域（跑 python tools/apply-author-years.py）', rel)
    author_died = int(died_raw) if died_raw not in (None, '') else None
    author_era = int(era_raw) if era_raw not in (None, '') else None

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
            % (rel, len(render_split), len(lines)))

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
        'authorDied': author_died,
        'authorEraEnd': author_era,
        'form': form,
        'stage': scalar(fm, 'stage'),
        'grade': scalar(fm, 'grade'),
        'volume': scalar(fm, 'volume'),
        'textbooks': scalar(fm, 'textbooks', ['统编']) or ['统编'],
        'textbookStatus': scalar(fm, 'textbookStatus'),
        'lines': lines,
        'linesPunct': [split_line_punct(x) for x in poem_lines],
        'fullLines': full_lines,
        'fullLinesPunct': [split_line_punct(x) for x in full_body],
        'pairs': pairs,
        'syllables': syllables,
        'render_split': render_split,
        'render_split_reason': scalar(fm, 'render_split_reason'),
        'hasFulltext': has_full_text(body),
        'theme': scalar(fm, 'theme', []) or [],
        'emotion': scalar(fm, 'emotion'),
        'technique': scalar(fm, 'technique', []) or [],
        'difficulty': scalar(fm, 'difficulty', 1),
        'examFreq': scalar(fm, 'exam_freq', 0),
        'tags': scalar(fm, 'tags', []) or [],
        'source': str(src),
        'license': scalar(fm, 'license', 'public-domain'),
        'copyright': scalar(fm, 'copyright', 'public-domain') or 'public-domain',
        'recite': scalar(fm, 'recite'),
        'gaokaoGroup': None,
        'gaokaoNo': None,
        'gaokaoSince': None,
        'irregular': scalar(fm, 'irregular'),
        '_path': str(rel).replace('\\', '/'),
    }


# ---------------------------------------------------------------- 高考默写范围
# 高中课标 72 篇分四组：必修 10 / 选择性必修 10 / 选修 12 / 诗词曲 40。
# 实际默写范围按届不同：2025 及以前 = 60 篇（不含选修 12），2026 起 = 72 篇全范围。
# 分组只从 docs/syllabus-2017.md 的表里读，不在篇目文件里手写——课标是唯一事实源。
GAOKAO_GROUPS = ('必修', '选择性必修', '选修', '诗词曲')
GAOKAO_SINCE = {'必修': 2023, '选择性必修': 2023, '诗词曲': 2023, '选修': 2026}


def load_gaokao_groups():
    """读 docs/syllabus-2017.md，返回 {规范化标题: (分组, 编号)}。"""
    sub = {'（一）必修（10 篇）': '必修', '（二）选择性必修（10 篇）': '选择性必修',
           '（三）选修（12 篇）': '选修'}
    out = {}
    group = None
    for line in (ROOT / 'docs' / 'syllabus-2017.md').read_text(encoding='utf-8').splitlines():
        if line.startswith('### '):
            group = sub.get(line[4:].strip(), group)
            continue
        if line.startswith('## 二、诗词曲'):
            group = '诗词曲'
            continue
        if line.startswith('## ') or line.startswith('# '):
            group = None
            continue
        m = re.match(r'^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$', line)
        if not m or not group:
            continue
        title = re.sub(r'（[^）]*）', '', m.group(2)).strip()
        out[title] = (group, int(m.group(1)))
    return out


def apply_gaokao_groups(records):
    """给高中篇目回填 gaokaoGroup / gaokaoNo / gaokaoSince。

    2025 及以前 = 必修 10 + 选择性必修 10 + 诗词曲 40 = 60 篇；2026 起加入选修 12 篇 = 72 篇。
    build.main 与 validate.load_poems 都调这一个函数，两边不许各写一份。
    """
    groups = load_gaokao_groups()
    unmatched = []
    for r in records:
        if r.get('stage') != '高中':
            continue
        keys = [r['title']]
        if r.get('subtitle'):
            keys.append(r['title'] + '·' + r['subtitle'])
            keys.append(r['title'] + r['subtitle'])
        hit = next((groups[k] for k in keys if k in groups), None)
        if hit is None:
            unmatched.append('%s（%s）' % (r['title'], r['_path']))
            continue
        r['gaokaoGroup'], r['gaokaoNo'] = hit
        r['gaokaoSince'] = GAOKAO_SINCE[hit[0]]
    if unmatched:
        die('高中篇目对不上课标分组：%s——课标表里没有同名条目，或篇目标题写歪了'
            % '、'.join(unmatched))


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

    apply_gaokao_groups(records)


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
        'contentVersion': '2026.10.03',
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