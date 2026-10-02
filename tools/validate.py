#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""丢词大作战 · 内容仓校验脚本

沿用主仓"文档即契约"的传统（tools/audio-test.mjs 直接解析 CONTRACTS.md
生成测试项），把 docs/syllabus-2022.md 当作可执行的契约：

    课标 135 篇  ⇄  poems/ 实际篇目  →  逐条比对

七项校验（任何一项失败即 exit 1）：
    1. 课标完整性   —— 漏收 / 多收
    2. id唯一性     —— 全库 id 不重复
    3. pairs 索引   —— 下标必须在 lines 范围内
    4. 字数匹配     —— form 声明与实际句长一致
    5. 台账完整     —— 缺 source / license 的篇目
    6. 版权零风险   —— 非公有领域的内容不得混入 poems/
    7. frontmatter  —— 必填字段齐全

用法：
    python tools/validate.py            # 完整校验（要求 135 篇齐）
    python tools/validate.py --partial  # 增量期校验：跳过"课标完整性"
"""

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
                extra.add(normalize_title(m.group(1)))
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


REQUIRED = ['id', 'title', 'author', 'lines', 'linesPunct', 'pairs',
            'theme', 'form', 'dynasty', 'stage', 'grade',
            'source', 'license', 'difficulty']


def main():
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
                pending_titles.add(normalize_title(m.group(1)))
        have = {normalize_title(p['title']) for p in poems}
        for t in pending_titles:
            # 暂缓条目可能带括号副标题，只用主标题匹配
            base = normalize_title(re.split(r'[（(]', t)[0])
            if base in have:
                err('版权风险：%s 标记为 pending，却也出现在 poems/ 里' % t)
            else:
                pending_ids.add(t)
        print('暂缓收录：%d 篇（不在比对范围）\n' % len(pending_ids))

    norm_to_poem = {}
    for p in poems:
        norm_to_poem.setdefault(normalize_title(p['title']), []).append(p)

    # 课标里每条，都要在仓里找到（增量模式跳过，允许分批迁移）
    if not partial:
        for stage, idx, title, author in syllabus:
            nt = normalize_title(title)
            if nt in pending_ids or normalize_title(title) in pending_ids:
                continue
            # 课标副标题含首句，用主标题兜底匹配
            base = normalize_title(re.split(r'[（(]', title)[0])
            if base in norm_to_poem:
                continue
            err('课标要求收录但缺失：%s %02d %s（%s）'
                % (stage, idx, title, author))
    else:
        covered = len({normalize_title(p['title']) for p in poems})
        print('课标覆盖：%d / %d 篇（增量期，未齐属正常）\n'
              % (covered, len(syllabus)))

    # 仓里每篇，都要在课标里或教材拓展表里（不收来源不明的篇目）
    syllabus_norms = {normalize_title(re.split(r'[（(]', t)[0]) for _, _, t, _ in syllabus}
    for p in poems:
        nt = normalize_title(p['title'])
        if nt in syllabus_norms:
            continue
        if nt in extra_titles:
            notes.append('%s：教材拓展篇目（不在课标 135 内）' % p['title'])
            continue
        warn('来源不明：%s 既不在课标 135 篇，也不在教材拓展表里（%s）'
             % (p['title'], p['_path']))

    # -------------------------------------------------- 3. pairs 索引合法
    for p in poems:
        n = len(p['lines'])
        for pair in p['pairs']:
            for i in pair:
                if not (0 <= i < n):
                    err('%s: pairs 下标 %d 越界（共 %d 句）' % (p['title'], i, n))

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