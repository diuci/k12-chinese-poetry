#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""丢词大作战 · 内容仓校验脚本

沿用主仓"文档即契约"的传统（tools/audio-test.mjs 直接解析 CONTRACTS.md
生成测试项），把 docs/syllabus-2022.md 当作可执行的契约：

    课标 135 篇  ⇄  poems/ 实际篇目  →  逐条比对

八项校验（任何一项失败即 exit 1）：
    1. 课标完整性     —— 漏收 / 多收
    2. id 唯一性      —— 全库 id 不重复
    3. pairs 索引     —— 下标必须在 lines 范围内
    4. 字数匹配       —— form 声明与实际句长一致
    5. 台账完整       —— 缺 source / license 的篇目
    6. 版权核验       —— 非公有领域的内容不得混入 poems/
    7. frontmatter    —— 必填字段齐全
    8. 公有领域证据   —— 每篇都有可核验的作者卒年（卒年 + 50 年保护期）

用法：
    python tools/validate.py            # 完整校验（要求 135 篇齐）
    python tools/validate.py --partial  # 增量期校验：跳过"课标完整性"
"""

import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POEMS_DIR = ROOT / 'poems'
PENDING_DIR = ROOT / 'pending'
SYLLABUS = ROOT / 'docs' / 'syllabus-2022.md'
SYLLABUS_HS = ROOT / 'docs' / 'syllabus-2017.md'
DATA_JSON = ROOT / 'data' / 'poems.json'
KNOWN_DEFECTS = ROOT / 'data' / 'known-defects.json'

sys.path.insert(0, str(Path(__file__).resolve().parent))
import match  # noqa: E402  课标 ⇄ 仓内 匹配器（与 build-ledger.py 共用一份）

# 我国《著作权法》：自然人作品的保护期为作者终生及其死亡后第五十年的 12 月 31 日。
# 即作者卒年 <= 当前年 - 50 才算进入公有领域。这不是文档里的说法，是下面要跑的规则。
COPYRIGHT_YEARS = 50

# 调色：仅在支持 ANSI 的终端着色
class C:
    OK, FAIL, WARN = '\033[32m', '\033[31m', '\033[33m'
    BOLD, DIM, END = '\033[1m', '\033[2m', '\033[0m'
    @classmethod
    def off(cls):
        for k in ('OK','FAIL','WARN','BOLD','DIM','END'):
            setattr(cls, k, '')


if not sys.stdout.isatty():
    C.off()

errors, warnings, notes = [], [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load_known_defects():
    """已知未修的登记表。

    容忍必须写下来：每一条都要有 key、理由、负责阶段。校验器对登记过的缺陷降级为提示，
    对没登记的直接报错；登记过但问题已经消失的也报错——防止这张表变成永久垃圾桶。
    """
    if not KNOWN_DEFECTS.exists():
        return {}
    data = json.loads(KNOWN_DEFECTS.read_text(encoding='utf-8'))
    out = {}
    for d in data.get('defects', []):
        if not d.get('key') or not d.get('reason') or not d.get('phase'):
            err('已知未修登记不完整（缺 key/reason/phase）：%s' % json.dumps(d, ensure_ascii=False))
            continue
        out[d['key']] = d
    return out


# ---------------------------------------------------------------- 课标解析
def parse_syllabus(path):
    """从一份课标文档抽出 (分组, 编号, 标题, 作者) 列表。

    义务教育（syllabus-2022.md）与高中（syllabus-2017.md）用同一套表格格式：
        | 1 | 江南（江南可采莲） | 汉乐府 |
        | 1 | 劝学（学不可以已……用心躁也） | 《荀子》 |
    高中文档没有「教材拓展」附表，故extra 恒为空集。
    """
    text = path.read_text(encoding='utf-8')
    section = None
    rows = []
    extra = set()
    in_wenyan_table = False        # 文言文分节表（必修/选择性必修/选修）
    for line in text.splitlines():
        if line.startswith('## '):
            if '1–6 年级' in line:
                section = '小学'
            elif '7–9 年级' in line:
                section = '初中'
            elif '教材内但不在课标' in line:
                section = 'extra'
            elif '文言文（32 篇）' in line:
                section = '高中'
                in_wenyan_table = True
            elif '诗词曲（40 首）' in line:
                section = '高中'
                in_wenyan_table = False
            else:
                section = None
            continue
        if not section:
            continue
        if section == 'extra':
            m = re.match(r'^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$', line)
            if m and m.group(1).strip() not in ('篇目', '---'):
                extra.add(canon_title(m.group(1)))
            continue
        # 高中表头：| # | 篇目 | 作者/ 出处 |
        m = re.match(r'^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$', line)
        if not m:
            continue
        title, author = m.group(2).strip(), m.group(3).strip()
        # 跳过表头与分节行
        if title.startswith('#') or set(title) <= set('-: '):
            continue
        if title in ('篇目', '段落'):
            continue
        rows.append((section, int(m.group(1)), title, author))
    return rows, extra


# ---------------------------------------------------------------- 读篇目
def load_poems():
    """复用 build.py 的解析逻辑，避免两处对frontmatter 的理解不一致。"""
    sys.path.insert(0, str(ROOT / 'tools'))
    import build  # noqa: E402
    poems = []
    for md in sorted(POEMS_DIR.rglob('*.md')):
        if md.name == '索引.md':      # 自动生成的导航页，无 frontmatter
            continue
        text = md.read_text(encoding='utf-8')
        fm, body = build.parse_frontmatter(text, md)
        poems.append(build.build_record(md, fm, body))
    return poems


def normalize_title(s):
    """归一标题用于匹配，去掉一切不影响指称的成分。

    课标与篇目文件的写法差异很大，要都能对上：
      「江南（江南可采莲）」 ↔「江南」        —— 去括号
      「悯农（春种一粒粟）」 ↔「悯农其一」    —— 去序号后缀
      「西江月·夜行黄沙道中」 ↔「西江月」     —— 词牌只留牌名
      「清平乐·村居」       ↔「清平乐」      —— 同上
      「渔歌子（西塞山前…）」 ↔「渔歌子」     —— 去括号
    """
    s = re.sub(r'[（(].*?[）)]', '', s)      # 去括号内容
    s = re.sub(r'[·・].*$', '', s)            # 词牌副题：西江月·夜行… → 西江月
    s = re.sub(r'[\s]', '', s)                # 去空白
    s = re.sub(r'[《》「」]', '', s)          # 去书名号
    s = re.sub(r'其[一二三四五六七八九十]$', '', s)      # 去「其一」
    s = re.sub(r'第[一二三四五六七八九十]$', '', s)      # 去「其一」异写
    s = re.sub(r'[（(][一二三四五六七八九十][）)]$', '', s)
    return s

# 同一篇作品的两种通行标题。课标与教材用字不同，按别名对照而非强行改标题。
TITLE_ALIAS = {
    '凉州词': '凉州',          # 课标作「凉州」，教材作「凉州词（王翰）」
}


def canon_title(s):
    """归一后再套用别名表。"""
    n = normalize_title(s)
    return TITLE_ALIAS.get(n, n)


REQUIRED = ['id', 'title', 'author', 'lines', 'linesPunct',
            'theme', 'form', 'dynasty', 'stage',
            'source', 'license', 'difficulty']

# 高中篇目不用 grade（1-9），改用 volume 表达册次，故单独校验
REQUIRED_BY_STAGE = {
    '小学': ['grade', 'volume'],
    '初中': ['grade', 'volume'],
    '高中': ['volume'],
}


def check_public_domain(poems, this_year):
    """逐篇核验公有领域证据，返回问题列表（不直接报错，便于自检单独调用）。

    卒年不详的（佚名、汉乐府、北朝民歌等）用 authorEraEnd —— 作品活动年代的上限，
    按同一条 50 年规则判：上限也远在保护期外，才允许放行。
    """
    cutoff = this_year - COPYRIGHT_YEARS
    problems = []
    for p in poems:
        died = p.get('authorDied')
        era = p.get('authorEraEnd')
        if not isinstance(died, int) and not isinstance(era, int):
            problems.append('%s: 缺 authorDied / authorEraEnd，无法论证公有领域'
                            '（跑 python tools/apply-author-years.py）' % p.get('title'))
            continue
        year = died if isinstance(died, int) else era
        if year > cutoff:
            problems.append('版权风险：%s 的作者卒年 %d 距今年未满 %d 年，仍在保护期内，'
                            '不得收录（应放 pending/ 并取得授权）'
                            % (p.get('title'), year, COPYRIGHT_YEARS))
    return problems


def selftest_match():
    """匹配器自己会不会漏：坏样本必须被抓到，好样本不能误报。"""
    bad = []

    def poem(pid, title, author, lines, subtitle=None):
        return {'id': pid, 'title': title, 'author': author, 'lines': lines, 'subtitle': subtitle}

    def keys(problems):
        return {p['key'] for p in problems}

    # 1) 词牌顶替：仓内只有《念奴娇·赤壁怀古》，课标另一条《念奴娇·过洞庭》必须报缺失。
    #    旧匹配器就是在这里放过去的——归一把「·过洞庭」砍掉了。
    _a, p1 = match.match_syllabus(
        [poem('nnj1', '念奴娇·赤壁怀古', '苏轼', ['大江东去，浪淘尽，千古风流人物'])],
        [('高中', 26, '念奴娇·赤壁怀古', '苏轼'), ('高中', 33, '念奴娇·过洞庭', '张孝祥')])
    if 'missing:高中-33' not in keys(p1):
        bad.append('词牌顶替没抓到：仓内缺《念奴娇·过洞庭》，匹配器却放过了')

    # 2) 同名不同作者：王翰的《凉州词》不许顶掉王之涣那首。
    _a, p2 = match.match_syllabus(
        [poem('lz1', '凉州词', '王翰', ['葡萄美酒夜光杯，欲饮琵琶马上催'])],
        [('小学', 8, '凉州词（黄河远上白云间）', '王之涣')])
    if 'missing:小学-08' not in keys(p2):
        bad.append('同名不同作者没抓到：王翰《凉州词》把王之涣那首顶掉了')

    # 3) 只有名句、没有全文：课标标注的首句在正文里找不到，必须报。
    _a, p3 = match.match_syllabus(
        [poem('sdt1', '水调歌头', '苏轼', ['但愿人长久，千里共婵娟'])],
        [('初中', 31, '水调歌头（明月几时有）', '苏轼')])
    if 'fulltext:初中-31' not in keys(p3):
        bad.append('缺全文没抓到：仓内只有名句「但愿人长久」，匹配器却算它收到了')

    # 4) 全文齐的不许误报。
    _a, p4 = match.match_syllabus(
        [poem('sdt2', '水调歌头', '苏轼', ['明月几时有，把酒问青天', '但愿人长久，千里共婵娟'])],
        [('初中', 31, '水调歌头（明月几时有）', '苏轼')])
    if p4:
        bad.append('好样本被误报：%s' % ' / '.join(x['text'] for x in p4))

    # 5) 重复收录必须抓到。
    dup = match.find_duplicates([
        poem('x1', '赤壁', '杜牧', ['折戟沉沙铁未销，自将磨洗认前朝']),
        poem('x2', '赤壁', '杜牧', ['折戟沉沙铁未销，自将磨洗认前朝'])])
    if len(dup) != 1:
        bad.append('重复收录没抓到：两份一模一样的《赤壁》，find_duplicates 返回 %d 组' % len(dup))

    # 6) 同一篇被两份课标各列一次：只许报「共用」，不许报缺失。
    _a, p6 = match.match_syllabus(
        [poem('ly1', '《论语》十二章', '佚名', ['学而时习之，不亦说乎'])],
        [('初中', 41, '《论语》十二章', '《论语》'), ('高中', 1, '《论语》十二章', '《论语》')])
    if 'shared:高中-01' not in keys(p6):
        bad.append('共用例外没生效：%s' % ' / '.join(x['text'] for x in p6))
    if any(k.startswith('missing:') for k in keys(p6)):
        bad.append('共用被误报成缺失：%s' % ' / '.join(x['text'] for x in p6))

    return bad


def selftest():
    """这条校验自己会不会漏：坏样本必须被抓到，好样本不能误报。"""
    year = 2026
    problems = []

    cases = [
        ('1999 年卒（保护期到 2049）应当被拒',
         [{'title': '假作A', 'authorDied': 1999, 'authorEraEnd': None}], True),
        ('没有卒年证据的应当被拒',
         [{'title': '假作B', 'authorDied': None, 'authorEraEnd': None}], True),
        ('恰好届满 50 年的应当放行',
         [{'title': '假作C', 'authorDied': year - COPYRIGHT_YEARS, 'authorEraEnd': None}], False),
        ('差一年才届满的应当被拒',
         [{'title': '假作D', 'authorDied': year - COPYRIGHT_YEARS + 1, 'authorEraEnd': None}], True),
        ('佚名走 authorEraEnd 应当放行',
         [{'title': '假作E', 'authorDied': None, 'authorEraEnd': 220}], False),
        ('公元前卒年应当放行',
         [{'title': '假作F', 'authorDied': -278, 'authorEraEnd': None}], False),
    ]
    for label, poems, should_fail in cases:
        got = bool(check_public_domain(poems, year))
        if got != should_fail:
            problems.append('%s（实得：%s）' % (label, '报错' if got else '放行'))

    problems.extend(selftest_match())

    if problems:
        print('[!!] validate --selftest 失败：', file=sys.stderr)
        for x in problems:
            print('  - ' + x, file=sys.stderr)
        return 1
    print('[ok] validate --selftest 通过（保护期内被拒、缺证据被拒、恰好届满放行、差一年被拒、'
          '佚名走年代上限、公元前卒年放行、词牌顶替被抓、同名不同作者被抓、缺全文被抓、'
          '好样本不误报、重复收录被抓、课标共用不误报缺失都试到了）')
    return 0


def main():
    if '--selftest' in sys.argv:
        return selftest()
    partial = '--partial' in sys.argv
    print('%s丢词大作战 · 内容仓校验%s' % (C.BOLD, C.END))
    if partial:
        print('%s（增量模式：跳过课标完整性检查）%s' % (C.WARN, C.END))

    if not POEMS_DIR.exists():
        err('缺少 poems/ 目录')
        return report()
    if not SYLLABUS.exists():
        err('缺少 docs/syllabus-2022.md（课标契约文件）')
        return report()

    # 两份课标契约：义务教育（小学+初中）与 高中
    syllabus, extra_titles = parse_syllabus(SYLLABUS)
    if not syllabus:
        err('无法从 docs/syllabus-2022.md 解析出课标条目')
        return report()
    print('义务教育：小学 %d 篇 / 初中 %d 篇 / 合计 %d'
          % (sum(1 for s in syllabus if s[0] == '小学'),
             sum(1 for s in syllabus if s[0] == '初中'), len(syllabus)))

    if SYLLABUS_HS.exists():
        hs, _ = parse_syllabus(SYLLABUS_HS)
        print('高中课标：%d 篇' % len(hs))
        syllabus += hs
    else:
        notes.append('尚未建 docs/syllabus-2017.md（高中课标契约），'
                     '高中篇目暂不参与完整性比对')
    print('课标合计：%d 篇' % len(syllabus))
    print('教材拓展：%d 篇（不在课标内，但统编教材有）' % len(extra_titles))

    try:
        poems = load_poems()
    except SystemExit:
        err('解析 poems/ 失败（frontmatter 格式错误？）')
        return report()
    print('仓内篇目：%d 篇\n' % len(poems))

    # -------------------------------------------------- 2. id 唯一
    seen = {}
    for p in poems:
        if p['id'] in seen:
            err('id 重复：%s（%s 与 %s）' % (p['id'], seen[p['id']], p['_path']))
        seen[p['id']] = p['_path']

    # -------------------------------------------------- 1. 课标完整性
    # 去掉已暂缓的（pending）
    pending_ids = set()
    if PENDING_DIR.exists():
        ptxt = (PENDING_DIR / 'INDEX.md').read_text(encoding='utf-8')
        pending_titles = set()
        for line in ptxt.splitlines():
            m = re.match(r'^\|\s*\d+-\d+\s*\|\s*([^|]+?)\s*\|', line)
            if m:
                pending_titles.add(canon_title(m.group(1)))
        have = {canon_title(p["title"]) for p in poems}
        for t in pending_titles:
            # 暂缓条目可能带括号副标题，只用主标题匹配
            base = canon_title(re.split(r'[（(]', t)[0])
            if base in have:
                err('版权风险：%s 标记为 pending，却也出现在 poems/ 里' % t)
            else:
                pending_ids.add(t)
        print('暂缓收录：%d 篇（不在比对范围）\n' % len(pending_ids))

    # ------------------------------------- 2.5 课标 ⇄ 仓内：1:1 匹配 + 账目闭合
    # 旧做法用归一标题判断收没收到，而归一把词牌副题与括号里的首句一起砍掉，
    # 课标条目因此互相顶替：实测王翰《凉州词》把王之涣那首整个顶掉了，
    # 校验器一直说「齐了」，而王之涣那首全仓一个字都没有。
    # 匹配规则统一放在 tools/match.py，validate 与 build-ledger 共用一份，不许两边漂移。
    assignments, match_problems = match.match_syllabus(poems, syllabus)
    known = load_known_defects()
    seen_defects = set()
    for pr in match_problems:
        if pr['key'].startswith('shared:'):
            notes.append(pr['text'])
            continue
        if pr['key'] in known:
            seen_defects.add(pr['key'])
            notes.append('已知未修（%s 处理）：%s' % (known[pr['key']]['phase'], pr['text']))
        elif partial:
            warn(pr['text'] + '（增量模式）')
        else:
            err(pr['text'])
    assigned_ids = {p['id'] for _e, p, _s in assignments}
    extra_ids = {p['id'] for p in poems if canon_title(p['title']) in extra_titles}

    # 归类口径与 build-ledger.py 完全一致：课标命中 → 重复副本 → 教材拓展 → 来源不明。
    # 重复副本不算「来源不明」：它的病是重复，不是没出处，记一次就够。
    import hashlib
    fingerprint = lambda p: hashlib.sha256(''.join(p['lines']).encode('utf-8')).hexdigest()
    assigned_fp = {}
    for _e, p, _s in assignments:
        assigned_fp.setdefault(fingerprint(p), p)

    dup_copies, dup_copy_ids, extra_only, unknown = [], set(), set(), []
    for p in poems:
        if p['id'] in assigned_ids:
            continue
        if fingerprint(p) in assigned_fp:
            dup_copies.append(p)
            dup_copy_ids.add(p['id'])
            other = assigned_fp[fingerprint(p)]
            key = 'duplicate:' + '|'.join(sorted([p['id'], other['id']]))
            if key in known:
                seen_defects.add(key)
                notes.append('已知未修（%s 处理）：%s 是《%s》的重复副本（%s）'
                            % (known[key]['phase'], p['title'], other['title'], p['_path']))
            else:
                warn('%s 是《%s》的重复副本（%s）' % (p['title'], other['title'], p['_path']))
            continue
        if p['id'] in extra_ids:
            extra_only.add(p['id'])
            notes.append('%s：教材拓展篇目（不在课标内）' % p['title'])
            continue
        unknown.append(p)
        key = 'unknown:' + p['id']
        if key in known:
            seen_defects.add(key)
            notes.append('已知未修（%s 处理）：来源不明：%s（%s）' % (known[key]['phase'], p['title'], p['_path']))
        else:
            warn('来源不明：%s 既不在课标里，也不在教材拓展表里（%s）' % (p['title'], p['_path']))

    # 账目闭合：课标命中 + 教材拓展 + 来源不明 必须正好等于仓内篇数。
    # 不闭合就说明有一篇没人认领，或者一篇被算了两遍——这种账最容易糊过去。
    total = len(assigned_ids) + len(extra_only) + len(dup_copies) + len(unknown)
    if total != len(poems):
        err('账目不闭合：课标命中 %d + 教材拓展 %d + 重复副本 %d + 来源不明 %d = %d，仓内 %d 篇'
            % (len(assigned_ids), len(extra_only), len(dup_copies), len(unknown), total, len(poems)))
    else:
        print('账目闭合：课标命中 %d 篇 + 教材拓展 %d 篇 + 重复副本 %d 篇 + 来源不明 %d 篇 = 仓内 %d 篇\n'
              % (len(assigned_ids), len(extra_only), len(dup_copies), len(unknown), len(poems)))

    # 重复收录：原文指纹完全相同。同一节选在两份课标里各列一次（如《礼运》与《大道之行也》）
    # 也必须登记在 known-defects 里写明理由，不许静默放过。
    for group in match.find_duplicates(poems):
        key = 'duplicate:' + '|'.join(sorted(p['id'] for p in group))
        text = '重复收录：%s（%d 份原文完全相同：%s）' % (group[0]['title'], len(group),
                                             '、'.join(p['_path'] for p in group))
        if key in known:
            seen_defects.add(key)
            notes.append('已知未修（%s 处理）：%s' % (known[key]['phase'], text))
        else:
            err(text)

    # 登记必须对得上现实：登记过的问题如果已经消失，说明这条登记过期了，
    # 必须删掉——否则这张表迟早变成永久垃圾桶，什么都能往里扔。
    for key, d in known.items():
        if key not in seen_defects:
            err('已知未修登记过期：%s（%s）——问题已经不见了，请从 data/known-defects.json 删掉这条'
                % (key, d.get('title', '')))

    # -------------------------------------------------- 3. pairs 索引合法
    for p in poems:
        n = len(p['lines'])
        for pair in p['pairs']:
            for i in pair:
                if not (0 <= i < n):
                    err('%s: pairs 下标 %d 越界（共 %d 句）' % (p['title'], i, n))
        # pairs 为空是合法的：只有一句时无处可配（如《水调歌头》名句）
        if n >= 2 and not p['pairs']:
            notes.append('%s：%d 句但无 pairs（无法联句，仅作 solo 单元）'
                         % (p['title'], n))

    # -------------------------------------------------- 4. 字数匹配
    # 以「联」为单位校验：五言一联 = 10 字，七言一联 = 14 字。
    # 绝句/律诗都是整齐的一联两句；词、杂言、古诗文不适用（跳过）。
    # 篇目若在 frontmatter 写了 irregular（已知不规则），则降为提示。
    for p in poems:
        form = p.get('form')
        if form not in ('五言', '七言'):
            continue
        want = 10 if form == '五言' else 14
        odd = [len(x) for x in p['lines'] if len(x) != want]
        if not odd:
            continue
        msg = ('%s：标为%s，每联应为 %d 字，但有 %d 句为 %s'
               % (p['title'], form, want, len(odd), odd))
        if p.get('irregular'):
            notes.append('%s（已知不规则：%s）' % (msg, p['irregular']))
        else:
            warn(msg + '（请核对正文）')

    # -------------------------------------------------- 5/6/7. 字段与版权
    for p in poems:
        missing = [k for k in REQUIRED if p.get(k) in (None, [], '')]
        # 学段特有字段
        stage = p.get('stage')
        if stage in REQUIRED_BY_STAGE:
            missing += [k for k in REQUIRED_BY_STAGE[stage] if p.get(k) in (None, [])]
        if missing:
            err('%s: 缺必填字段 %s' % (p['title'], missing))

        lic = p.get('license')
        if lic != 'public-domain':
            err('版权风险：%s的 license 为 %r（应为 public-domain，'
                '保护期内的作品请放 pending/）' % (p['title'], lic))

        src = p.get('source') or ''
        if not src or src == 'null':
            err('%s: 缺 source（台账字段，见 docs/sources.md）' % p['title'])
        elif 'S3' not in src:
            warn('%s: source 为 %r，未引用 S3(chinese-poetry)，'
                 '请确认正文出处' % (p['title'], src))

    # -------------------------------------------------- 8. 公有领域证据（卒年）
    pd_problems = check_public_domain(poems, datetime.date.today().year)
    for m in pd_problems:
        err(m)
    if not pd_problems:
        print('公有领域证据：%d 篇全部可核验（卒年 + %d 年保护期）' % (len(poems), COPYRIGHT_YEARS))

    #-------------------------------------------------- 构建产物一致性
    if DATA_JSON.exists():
        built = json.loads(DATA_JSON.read_text(encoding='utf-8'))
        if built.get('count') != len(poems):
            warn('data/poems.json 记录 %d 篇，当前 poems/ 有 %d 篇，'
                 '请重跑 python tools/build.py' % (built.get('count'), len(poems)))
        else:
            print('data/poems.json 与 poems/ 一致（%d 篇）' % built['count'])
    else:
        notes.append('尚未构建 data/poems.json（跑 python tools/build.py 生成）')

    return report()


def report():
    print()
    if notes:
        for n in notes:
            print('%s· %s%s' % (C.DIM, n, C.END))
    if warnings:
        print('%s⚠警告 %d 项%s' % (C.WARN, len(warnings), C.END))
        for w in warnings:
            print('  %s· %s%s' % (C.WARN, w, C.END))
        print()
    if errors:
        print('%s✗错误 %d 项%s' % (C.FAIL, len(errors), C.END))
        for e in errors:
            print('  %s· %s%s' % (C.FAIL, e, C.END))
        return 1
    print('%s✓ 全部校验通过%s' % (C.OK, C.END))
    return 0


if __name__ == '__main__':
    sys.exit(main())