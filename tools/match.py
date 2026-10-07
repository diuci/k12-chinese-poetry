#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""课标条目 ⇄ 仓内篇目 的匹配器（validate.py 与 build-ledger.py 共用一份）。

为什么要有这个文件：原来 validate.py 用「归一标题」判断某篇课标篇目收没收到，
而归一把词牌副题和括号里的首句全砍掉了 ——

    课标「念奴娇·过洞庭」  →  念奴娇  →  仓内《念奴娇·赤壁怀古》命中
    课标「凉州词（黄河远上白云间）」 → 凉州词 → 仓内王翰《凉州词》命中

于是缺篇不会报错。实测后果：王之涣《凉州词》全仓一个字都没有，校验器却一直说齐了。
这就是「空过的检查比没有检查更危险」。

匹配强度（强到弱）：
  3  课标括号里的首句  ↔  仓内篇目正文首句
  2  完整标题（含词牌副题 / 副标题）完全对上
  1  只对上主干标题（词牌名）——弱匹配，必须点名
作者对不上的一律降级；弱匹配只允许在「没有更强候选」时使用，且必须报告。
"""
import re

PUNCT = '，。、；：？！「」『』【】（）《》·—…“”‘’\u3000 \t'


def norm_full(s):
    """去书名号与空白，保留副题与括号内容。"""
    if s is None:
        return ''
    s = str(s)
    s = re.sub(r'[《》「」『』【】]', '', s)
    s = re.sub(r'\s', '', s)
    return s


def norm_base(s):
    """主干标题：砍掉括号与词牌副题，用于弱匹配兜底。"""
    if s is None:
        return ''
    s = re.sub(r'[（(].*?[）)]', '', str(s))
    s = re.sub(r'[·・].*$', '', s)
    s = norm_full(s)
    s = re.sub(r'其[一二三四五六七八九十]+$', '', s)
    s = re.sub(r'第[一二三四五六七八九十]+$', '', s)
    return s


def strip_punct(s):
    for ch in PUNCT:
        s = s.replace(ch, '')
    return s


def paren_of(title):
    m = re.search(r'[（(]([^）)]*)[）)]', str(title or ''))
    return m.group(1) if m else ''


def norm_author(s):
    if not s:
        return ''
    s = re.sub(r'[《》「」]', '', str(s))
    s = re.sub(r'\s', '', s)
    return s


def poem_keys(poem):
    """一篇仓内篇目能提供哪些键。"""
    title = poem.get('title') or ''
    subtitle = poem.get('subtitle') or ''
    keys_full = {norm_full(title)}
    if subtitle and subtitle not in ('null', 'None'):
        keys_full.add(norm_full(title) + norm_full(subtitle))
        keys_full.add(norm_full(title + '·' + subtitle))
    lines = poem.get('lines') or []
    first = strip_punct(lines[0]) if lines else ''
    return {
        'full': keys_full,
        'base': norm_base(title),
        'first': first,
        'text': strip_punct(''.join(lines)),
        'author': norm_author(poem.get('author')),
    }


NON_PERSON = ('乐府', '民歌', '佚名', '诗经', '古诗十九首', '文论', '见下', '总集')


def looks_like_first_line(paren):
    """括号里到底是首句（或节选范围的起头），还是「（四）」「（《左传》）」这种编号或出处。"""
    if not paren:
        return False
    s = str(paren).strip()
    if '《' in s or '》' in s or '【' in s or '；' in s or chr(8220) in s:
        return False
    if re.fullmatch(r'[0-9一二三四五六七八九十]+', s):
        return False
    if len(strip_punct(s.split('……')[0])) < 4:
        return False
    return True


def first_segment(paren):
    """「学不可以已……用心躁也」的起头那一段：节选范围用它来核对。"""
    return strip_punct(str(paren).split('……')[0])


def is_person_author(author):
    """课标作者栏是人名还是书名/集体：只有人名才用来卡「同名不同人」。"""
    if not author:
        return False
    s = str(author).strip()
    if '《' in s or '》' in s:
        return False
    for k in NON_PERSON:
        if k in s:
            return False
    return 1 <= len(s) <= 6


ALIASES_PATH = __import__('pathlib').Path(__file__).resolve().parents[1] / 'data' / 'title-aliases.json'


def load_title_aliases():
    """课标篇名 ⇄ 教材通名 的对照表（如课标「杂说（四）」= 教材《马说》）。

    别名必须显式登记在 data/title-aliases.json，不许硬编码进匹配器——
    硬编码的别名没人复核，等于给匹配器开了个后门。"""
    if not ALIASES_PATH.exists():
        return {}
    data = __import__('json').loads(ALIASES_PATH.read_text(encoding='utf-8'))
    out = {}
    for item in data.get('aliases', []):
        out.setdefault(norm_base(item['syllabusTitle']), []).append(item)
    return out


def match_syllabus(poems, syllabus):
    """返回 (assignments, problems)。

    assignments: [(entry_index, poem, strength)]，每条课标条目最多一篇，
                 每篇仓内篇目最多被一条课标条目占用。
    problems:    文字说明的错处列表。
    """
    problems = []
    pk = [poem_keys(p) for p in poems]
    alias_table = load_title_aliases()
    used_alias = {}

    candidates = []  # (strength, entry_index, poem_index)
    for ei, (stage, idx, title, author) in enumerate(syllabus):
        raw_paren = paren_of(title)
        paren = strip_punct(raw_paren) if looks_like_first_line(raw_paren) else ''
        want_author = norm_author(author) if is_person_author(author) else ''
        base = norm_base(title)
        full = norm_full(re.sub(r'[（(][^）)]*[）)]', '', title))
        alias_items = [a for a in alias_table.get(base, [])
                       if not a.get('author') or norm_author(a['author']) == want_author or not want_author]
        found = []
        for pi, k in enumerate(pk):
            strength = 0
            if paren and k['first'] and (k['first'].startswith(paren) or paren.startswith(k['first'])):
                strength = 3
            elif paren and k['text'] and paren in k['text']:
                strength = 3
            elif full and full in k['full']:
                strength = 2
            elif alias_items and any(norm_full(a['repoTitle']) in k['full'] or norm_base(a['repoTitle']) == k['base'] for a in alias_items):
                strength = 2
                used_alias[ei] = alias_items[0]
            elif base and base == k['base']:
                strength = 1
            if not strength:
                continue
            # 作者对不上：只有「课标括号里的首句」这种硬证据能越过作者栏，
            # 其余一律不匹配——否则王翰的《凉州词》会把王之涣那首顶掉。
            if want_author and k['author'] and want_author != k['author']:
                if strength == 3:
                    strength = 2
                else:
                    continue
            # 学段相同优先。《论语》十二章在两份课标里各列一次，统编教材也确实在两个学段
            # 各有一课（七年级上册第 12 课、选择性必修上册第 5 课），仓里两份各对各的。
            # 不排这一位，高中那条课标会去占初中那份，然后报「学段不一致」。
            candidates.append((strength, ei, pi, 1 if stage == poems[pi].get('stage') else 0))

    # 强匹配先占位，一篇只许被占一次；例外：两条课标条目本来就是同一篇
    # （如《论语》十二章在义务教育与高中两份课标里各列一次），允许共用同一篇。
    candidates.sort(key=lambda c: (-c[0], -c[3], c[1], c[2]))
    taken_poem = {}
    taken_entry = {}
    entry_keys = {}
    for ei, (_s, _i, _t, _a) in enumerate(syllabus):
        entry_keys[ei] = (norm_base(_t), norm_author(_a) if is_person_author(_a) else '')
    shared = []
    for strength, ei, pi, _same_stage in candidates:
        if ei in taken_entry:
            continue
        if pi in taken_poem:
            other_ei, other_key = taken_poem[pi]
            if other_key != entry_keys[ei]:
                continue
            shared.append((ei, other_ei, poems[pi]['title']))
        taken_entry[ei] = (pi, strength)
        taken_poem[pi] = (ei, entry_keys[ei])

    assignments = []
    for ei, (stage, idx, title, author) in enumerate(syllabus):
        if ei in taken_entry:
            pi, strength = taken_entry[ei]
            assignments.append((ei, poems[pi], strength))
            if ei in used_alias:
                a = used_alias[ei]
                problems.append({'key': 'alias:%s-%02d' % (stage, idx),
                                 'text': '篇名对照：课标「%s」= 仓内《%s》（%s）' % (title, poems[pi]['title'], a['reason'])})
            if strength == 1:
                problems.append({'key': 'weak:%s-%02d' % (stage, idx),
                                  'text': '弱匹配：%s %02d「%s」只对上主干标题，仓内《%s》——副题或首句没有核对，缺篇会被漏检' % (stage, idx, title, poems[pi]['title'])})
            raw_paren = paren_of(title)
            if looks_like_first_line(raw_paren):
                seg = first_segment(raw_paren)
                text = strip_punct(''.join(poems[pi].get('lines') or []))
                if seg not in text:
                    problems.append({'key': 'fulltext:%s-%02d' % (stage, idx),
                                     'text': '缺全文/收错篇：%s %02d「%s」要求含「%s」，仓内《%s》的正文里没有（仓内正文：%s）' % (stage, idx, title, seg, poems[pi]['title'], (text[:40] or '空'))})
        else:
            problems.append({'key': 'missing:%s-%02d' % (stage, idx),
                             'text': '课标要求收录但缺失：%s %02d %s（%s）' % (stage, idx, title, author)})
    for ei, other_ei, shared_title in shared:
        stage, idx, title0, author = syllabus[ei]
        problems.append({'key': 'shared:%s-%02d' % (stage, idx),
                         'text': '同一篇被两条课标条目共用：%s %02d「%s」与仓内《%s》——两份课标各列一次，属正常，但必须点名' % (stage, idx, title0, shared_title)})
    return assignments, problems


def duplicate_key(poem):
    return 'duplicate:' + poem['id']


def find_duplicates(poems):
    """原文指纹完全相同的篇目组（重复收录）。"""
    import hashlib
    groups = {}
    for p in poems:
        text = ''.join(p.get('lines') or [])
        if not text:
            continue
        groups.setdefault(hashlib.sha256(text.encode('utf-8')).hexdigest(), []).append(p)
    return [g for g in groups.values() if len(g) > 1]
