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


# 内容冻结之后，登记表只许留两种条目：
#   正常 —— 不是缺陷，是设计如此（比如同一篇原文的重复副本被保留）；
#   口径 —— 不是缺陷，是我们做出的判断（比如课标学段与教材学段不一致，决定不复制第二份）。
# 不再接受「P3 处理」「P6 处理」这类「以后再说」：内容冻结了，以后就是现在。
DEFECT_PHASES = ('正常', '口径')
DEFECT_REQUIRED = ('key', 'title', 'reason', 'phase', 'added')


def defect_schema_problems(defects):
    """登记表本身的体检。返回问题列表（空表 = 干净）。

    容忍必须写下来：每一条都要有 key、标题、理由、阶段、登记日期，阶段只能取固定几个词。
    校验器对登记过的缺陷降级为提示，对没登记的直接报错；
    登记过但问题已经消失的也报错——防止这张表变成永久垃圾桶。
    """
    out = []
    seen = set()
    for d in defects:
        missing = [k for k in DEFECT_REQUIRED if not d.get(k)]
        if missing:
            out.append('登记不完整（缺 %s）：%s' % ('/'.join(missing), json.dumps(d, ensure_ascii=False)))
            continue
        if d['phase'] not in DEFECT_PHASES:
            out.append('登记阶段取值非法（%r，只许 %s）：%s' % (d['phase'], '/'.join(DEFECT_PHASES), d['key']))
        if d['key'] in seen:
            out.append('登记 key 重复：%s' % d['key'])
        seen.add(d['key'])
    return out


def load_known_defects():
    if not KNOWN_DEFECTS.exists():
        return {}
    data = json.loads(KNOWN_DEFECTS.read_text(encoding='utf-8'))
    for problem in defect_schema_problems(data.get('defects', [])):
        err('已知未修登记有问题：' + problem)
    out = {}
    for d in data.get('defects', []):
        if not d.get('key'):
            continue
        out[d['key']] = d
    return out


# -------------------------------------------------- 背诵要求与收录范围是否自相矛盾
def find_fulltext_conflicts(poems):
    """背诵要求写着「全文」，仓里却只收了节选。

    这类矛盾不会让构建失败，也不会让链接出错，但它直接决定「按这篇去背书够不够」：
    学生照着 recite=full 去背，背的却只是名句那几句，考试按全文默写就会丢分。
    """
    out = []
    for p in poems:
        if p.get('recite') == 'full' and not p.get('hasFulltext'):
            out.append('%s（%s·%s）' % (p['title'], p.get('stage'), p.get('volume')))
    return out


# ---------------------------------------------------------------- 玩法可用性
def find_unplayable(poems):
    """返回做不出玩法单元的篇目描述。

    玩法单元要两句才能配一对；pairs 为空就是「这篇在游戏里做不出东西」。
    以前这类篇目被静默跳过，台账上没人说为什么不做——那就是悬案。
    """
    out = []
    for p in poems:
        if not p.get('pairs'):
            out.append('%s（%s，%d 句）：pairs 为空，做不出玩法单元' % (p['title'], p.get('stage'), len(p['lines'])))
    return out


# ---------------------------------------------------------------- 背诵要求
RECITE_VALUES = ('full', 'section', 'line', 'none')


def find_missing_recite(poems):
    """返回 recite 缺失或取值非法的篇目描述列表。

    单独做成函数是为了能在 --selftest 里喂坏例子：一个空过的检查比没有检查更危险。
    """
    out = []
    for p in poems:
        r = p.get('recite')
        if not r:
            out.append('%s（%s）：缺 recite' % (p['title'], p.get('stage')))
        elif r not in RECITE_VALUES:
            out.append('%s：recite 取值非法（%r）' % (p['title'], r))
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
def check_glued_heading(path, text):
    """小节名被粘在上一行末尾（…（frontmatter 记录的册次）## 旧文本裁定）。

    这一类错让整节内容被吞进上一节：台账数小节、build.py 找正文、站点渲染都按行首的 ## 判断，
    粘在行末的 ## 等于这一节不存在。空过的检查比没有检查更危险，所以这条进 validate。"""
    problems = []
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith('#'):
            continue
        j = line.find('##')
        if j > 0 and line[j - 1] != "#":
            problems.append('%s:%d 小节名粘在行末：%s' % (path.name, i, line[max(0, j - 24):j + 20]))
    return problems


def selftest_glued_heading():
    """这条护栏自己带坏例子：漏掉一种写法，护栏就是空的。"""
    bad = '出处：统编教材《语文》必修下册（frontmatter 记录的册次）## 旧文本裁定'
    good = '出处：统编教材《语文》必修下册（frontmatter 记录的册次）'
    assert len(check_glued_heading(Path('x.md'), bad)) == 1, '坏例1：小节名粘在行末没被抓到'
    assert check_glued_heading(Path('x.md'), good) == [], '坏例2：正常行被误报'
    assert check_glued_heading(Path('x.md'), '### 三级标题在行首') == [], '坏例3：行首的 ### 被误报'
    # 正文行里出现 ## 一律可疑：markdown 会照原样渲染，读者看到两个井号。
    assert len(check_glued_heading(Path('x.md'), '正文里出现 ## 号')) == 1, '坏例4：正文行里的 ## 没被抓到'
    assert check_glued_heading(Path('x.md'), 'https://example.com/a%23b 这种链接不该报') == [], '坏例5：正常链接被误报'
    assert check_glued_heading(Path('x.md'), '# 一级标题') == [], '坏例5：行首 # 被误报'


def check_duplicate_sections(path, text):
    """同一篇里不许有两个同名小节。站点按名字取小节，重复了只认第一份——
    新写的内容会被整段丢掉，页面上一个字都看不见，而台账两边都在数它。"""
    errs = []
    seen = {}
    for line in text.splitlines():
        if line.startswith('## '):
            name = line[3:].strip()
            seen[name] = seen.get(name, 0) + 1
    for name, n in sorted(seen.items()):
        if n > 1:
            errs.append('%s 小节「%s」在同一篇里出现 %d 次——站点按名字取小节，只认第一份，其余会被丢掉' % (path.name, name, n))
    return errs

def selftest_duplicate_sections():
    ok = '## 异文\n- 甲\n\n## 注释\n- 乙\n'
    assert not check_duplicate_sections(Path('t.md'), ok), '坏例1：正常小节被误报'
    dup = '## 异文\n- 甲\n\n## 注释\n- 乙\n\n## 异文\n- 丙\n'
    assert len(check_duplicate_sections(Path('t.md'), dup)) == 1, '坏例2：同名小节重复没被抓到'
    near = '## 收录范围\n- 甲\n\n## 收录范围（第六段）\n- 乙\n'
    assert not check_duplicate_sections(Path('t.md'), near), '坏例3：名字不同的近名小节被误报'
    triple = '## 全文\n甲\n\n## 全文\n乙\n\n## 全文\n丙\n'
    assert len(check_duplicate_sections(Path('t.md'), triple)) == 1, '坏例4：出现三次只报一次是对的，但必须报'
    print('[ok] 同名小节重复自检通（4 个坏例子全部试到）')

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
    build.apply_gaokao_groups(poems)
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
# 册次必须与学段对得上。册次写错，站点的「按册浏览」会把课文挂到错误的课本上；
# 「七年级课外诵读」这种含糊写法更是看不出到底挂在哪一册。
VOLUME_PATTERNS = {
    '小学': r'^[一二三四五六]年级(上册|下册)$',
    '初中': r'^[七八九]年级(上册|下册|上册课外诵读|下册课外诵读)$',
    '高中': r'^(必修[上下]册|选择性必修[上中下]册|选修（2026起默写）)$',
}
VOLUME_HINT = {
    '小学': '一~六年级上册/下册',
    '初中': '七~九年级上册/下册，或某册的课外古诗词诵读',
    '高中': '必修上下册 / 选择性必修上下中册',
}

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

    # 7) 篇名对照表：课标「杂说（四）」必须能对上仓内《马说》，而且必须点名。
    _a, p7 = match.match_syllabus(
        [poem('ms1', '马说', '韩愈', ['世有伯乐，然后有千里马'])],
        [('初中', 52, '杂说（四）', '韩愈')])
    if any(k.startswith('missing:') for k in keys(p7)):
        bad.append('篇名对照没生效：课标「杂说（四）」对不上仓内《马说》')
    if 'alias:初中-52' not in keys(p7):
        bad.append('篇名对照没点名：用了别名却不报告，别名就成了暗门')

    # 8) 别名不许替「同名不同人」开后门：作者对不上就不许靠别名硬配。
    _a, p8 = match.match_syllabus(
        [poem('ms2', '马说', '假托者', ['世有伯乐，然后有千里马'])],
        [('初中', 52, '杂说（四）', '韩愈')])
    if not any(k.startswith('missing:') for k in keys(p8)):
        bad.append('别名后门：作者对不上却靠别名配上了')

    return bad


def selftest():
    selftest_glued_heading()
    selftest_duplicate_sections()
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

    recite_cases = [
        ('缺 recite 的应当被拒',
         [{'title': '假作G', 'recite': None}], True),
        ('recite 取值非法（写成中文「全文」）的应当被拒',
         [{'title': '假作H', 'recite': '全文'}], True),
        ('recite 取值合法的应当放行',
         [{'title': '假作I', 'recite': 'full'}], False),
    ]
    for label, poems, should_fail in recite_cases:
        got = bool(find_missing_recite(poems))
        if got != should_fail:
            problems.append('%s（实得：%s）' % (label, '报错' if got else '放行'))

    play_cases = [('pairs 为空的应当被拒', [{'title': '假作J', 'stage': '小学', 'lines': ['甲', '乙'], 'pairs': []}], True),
                  ('有成对的应当放行', [{'title': '假作K', 'stage': '小学', 'lines': ['甲', '乙'], 'pairs': [[0, 1]]}], False)]
    for label, ps, should_fail in play_cases:
        got = bool(find_unplayable(ps))
        if got != should_fail:
            problems.append('%s（实得：%s）' % (label, '报错' if got else '放行'))

    full_cases = [
        ('recite=full 但只有节选应当被拒', [{'id': 'f1', 'title': 'T', 'stage': '初中', 'volume': 'V', 'recite': 'full', 'hasFulltext': False}], True),
        ('recite=full 且有全文应当放行', [{'id': 'f2', 'title': 'T', 'stage': '初中', 'volume': 'V', 'recite': 'full', 'hasFulltext': True}], False),
        ('recite=section 只有节选是合法的', [{'id': 'f3', 'title': 'T', 'stage': '初中', 'volume': 'V', 'recite': 'section', 'hasFulltext': False}], False),
    ]
    for label, ps, should_fail in full_cases:
        got = bool(find_fulltext_conflicts(ps))
        if got != should_fail:
            problems.append('%s（实得：%s）' % (label, '报错' if got else '放行'))

    defect_cases = [
        ('缺 reason 的应当被拒', [{'key': 'x1', 'title': 'T', 'phase': '口径', 'added': '2026-01-01'}], True),
        ('阶段写「P6 处理」的应当被拒', [{'key': 'x2', 'title': 'T', 'reason': 'r', 'phase': 'P6 处理', 'added': '2026-01-01'}], True),
        ('key 重复的应当被拒', [{'key': 'x3', 'title': 'T', 'reason': 'r', 'phase': '口径', 'added': '2026-01-01'},
                              {'key': 'x3', 'title': 'T2', 'reason': 'r', 'phase': '正常', 'added': '2026-01-01'}], True),
        ('写全了的应当放行', [{'key': 'x4', 'title': 'T', 'reason': 'r', 'phase': '口径', 'added': '2026-01-01'}], False),
    ]
    for label, ds, should_fail in defect_cases:
        got = bool(defect_schema_problems(ds))
        if got != should_fail:
            problems.append('%s（实得：%s）' % (label, '报错' if got else '放行'))

    problems.extend(selftest_match())

    if problems:
        print('[!!] validate --selftest 失败：', file=sys.stderr)
        for x in problems:
            print('  - ' + x, file=sys.stderr)
        return 1
    print('[ok] validate --selftest 通过：保护期内被拒、缺证据被拒、恰好届满放行、差一年被拒、'
          '佚名走年代上限、公元前卒年放行、词牌顶替被抓、同名不同作者被抓、缺全文被抓、'
          '好样本不误报、重复收录被抓、课标共用不误报缺失、篇名对照生效且点名、'
          '别名不许替作者不符开后门、背诵要求缺失被拒、背诵要求取值非法被拒、'
          '背诵要求合法不误报、玩法悬案被拒、玩法可用作出不误报、登记表缺字段被拒、登记表阶段非法被拒、登记表 key 重复被拒、登记表写全不误报、背诵要求与收录范围矛盾被拒、全文齐备不误报、节选配段落不误报、同名小节重复被抓——都试到了')
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

    # -------------------------------------------------- 1.5 小节名必须独占一行
    for md in sorted(POEMS_DIR.rglob('*.md')):
        if md.name == '索引.md':
            continue
        _txt = md.read_text(encoding='utf-8')
        for msg in check_glued_heading(md, _txt):
            err(msg)
        for msg in check_duplicate_sections(md, _txt):
            err(msg)

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
        if pr['key'].startswith('shared:') or pr['key'].startswith('alias:'):
            notes.append(pr['text'])
            continue
        if pr['key'] in known:
            seen_defects.add(pr['key'])
            notes.append('已知未修（%s 处理）：%s' % (known[pr['key']]['phase'], pr['text']))
        elif partial:
            warn(pr['text'] + '（增量模式）')
        else:
            err(pr['text'])
    # -------------------------------------------------- 2.9 课标学段 ⇄ 篇目学段
    # 课标把某篇列在 A 学段、统编教材却把它放进 B 学段的课本，这种情形真实存在（现有两处）：
    #   初中 41《论语》十二章 —— 统编放在高中必修上册
    #   高中 09 山居秋暝     —— 统编放在小学五年级上册第 21 课《古诗三首》
    # 跨学段覆盖必须点名登记，不许静默通过：否则站点的「按学段浏览」会少一篇，
    # 而校验器还会说「课标齐了」。
    for idx, p, _s in assignments:
        sec, no, stitle, _a = syllabus[idx]
        if sec != p['stage']:
            key = 'stage-cross:%s-%02d' % (sec, no)
            text = ('课标 %s %02d「%s」由%s篇目《%s》覆盖（%s）'
                    % (sec, no, stitle, p['stage'], p['title'], p['_path']))
            if key in known:
                seen_defects.add(key)
                notes.append('已知未修（%s 处理）：%s' % (known[key]['phase'], text))
            else:
                err(text + '——学段不一致且未登记')

    # -------------------------------------------------- 2.10 高考默写范围按届区分
    # 2025 及以前 = 60 篇（必修 10 + 选择性必修 10 + 诗词曲 40）；
    # 2026 起 = 72 篇（加入选修 12 篇）。分组从课标表算，不许在篇目文件里手写。
    import build as _build  # noqa: E402
    gg = _build.load_gaokao_groups()
    gcount = {}
    for _g, _n in gg.values():
        gcount[_g] = gcount.get(_g, 0) + 1
    want = {'必修': 10, '选择性必修': 10, '选修': 12, '诗词曲': 40}
    if gcount != want:
        err('高中课标分组计数不对：%s（应为 %s）' % (gcount, want))
    until2025 = sum(1 for _g, _n in gg.values() if _g != '选修')
    if until2025 != 60:
        err('2025 及以前的高考默写范围按课标分组算出 %d 篇，应为 60 篇' % until2025)
    no_since = [p['title'] for p in poems if p.get('stage') == '高中' and not p.get('gaokaoSince')]
    if no_since:
        err('高中篇目缺 gaokaoSince（从哪一届起在默写范围内）：%s' % '、'.join(no_since[:6]))
    bad_since = [p['title'] for p in poems if p.get('gaokaoSince') not in (None, 2023, 2026)]
    if bad_since:
        err('gaokaoSince 取值非法（只许 2023 或 2026）：%s' % '、'.join(bad_since[:6]))
    # 课标「选修 12」这一组以前一律挂在「选修（2026起默写）」目录，隐含的意思是「统编教材没有这一课」。
    # 核对教材目录之后这个假设破了：兰亭集序 在选必下 10.1、大学 在选必上 5.2、
    # 《老子》八章 在选必上 6.1、谏逐客书 在必修下 11.1——四篇教材里都有这一课。
    # 所以规则改成：要么挂「选修（2026起默写）」，要么挂教材里那一册；
    # 挂教材册的，必须在篇内「收录范围」写明教材课号，不许空口说。
    unsourced = []
    for p in poems:
        if p.get('gaokaoGroup') != '选修' or p.get('volume') == '选修（2026起默写）':
            continue
        ptxt = (ROOT / p['_path']).read_text(encoding='utf-8')
        if '## 收录范围' not in ptxt or not re.search(r'统编教材《语文》[^。]*第 ?[\d.]+ ?课', ptxt):
            unsourced.append(p['title'])
    if unsourced:
        err('这几篇挂着统编教材的册次，篇内却没写教材课号出处：%s' % '、'.join(unsourced))

    # -------------------------------------------------- 2.16 教材收录状态必须和核对结论一致
    # data/volume-findings.json 是教材目录核对的结论表。每篇 frontmatter 的 textbookStatus
    # 必须和这张表对得上。没有这一条，核对结论就只是一份没人读的文档：
    # 篇目文件说「这篇教材收了」，核对表说没有，站点照篇目文件显示，学生照着背错。
    TS_COLLECTED = '统编教材收录'
    TS_NOT = '统编教材未收（课标要求）'
    TS_CLASH = '统编教材收的是同名另一篇'
    TS_COVERED = '统编教材收在别的课里'
    TS_PARTIAL = '统编教材收了一部分（课标要求更多）'
    vf_path = ROOT / 'data' / 'volume-findings.json'
    if not vf_path.exists():
        err('缺 data/volume-findings.json：先跑 python tools/build-textbook-lessons.py --report')
    else:
        vf = json.loads(vf_path.read_text(encoding='utf-8'))
        found = {x['id']: x['status'] for x in vf.get('findings', [])}
        for x in vf.get('absent', []):
            found[x['id']] = 'absent'
        for x in vf.get('titleCollision', []):
            found[x['id']] = 'title-collision'
        # 覆盖表：教材收了、但收在别的课里（篇名不同）。这张表里的篇目期望值就是 TS_COVERED。
        cov_path = ROOT / 'data' / 'textbook-coverage.json'
        covered = set()
        if cov_path.exists():
            # 要的是整张表（不是只有 id）：partial 标记在这里，抹成 set 就把「收了一部分」这一档丢了
            covered = json.loads(cov_path.read_text(encoding='utf-8')).get('coverage', {})
        no_status, wrong_status, unfixed = [], [], []
        for p in poems:
            st = p.get('textbookStatus')
            if not st:
                no_status.append(p['title'])
                continue
            if st not in (TS_COLLECTED, TS_NOT, TS_CLASH, TS_COVERED, TS_PARTIAL):
                wrong_status.append('%s 的 textbookStatus 取值非法：%r' % (p['title'], st))
                continue
            status = found.get(p['id'])
            if status == 'volume-mismatch':
                unfixed.append(p['title'])
                continue
            if p['id'] in covered:
                # partial 的条目不许期望成「收在别的课里」——那等于说教材全覆盖了
                expect = TS_PARTIAL if (covered.get(p['id']) or {}).get('partial') else TS_COVERED
            elif p.get('volume') == '选修（2026起默写）':
                expect = TS_NOT
            elif status in ('match', 'title-variant', 'claimed-absent-but-present'):
                expect = TS_COLLECTED
            elif status == 'title-collision':
                expect = TS_CLASH
            elif status == 'absent':
                expect = TS_NOT
            else:
                expect = None
            if expect and st != expect:
                wrong_status.append('%s：篇内写「%s」，教材核对结论是「%s」' % (p['title'], st, expect))
        if no_status:
            err('%d 篇没有 textbookStatus（跑 python tools/apply-textbook-status.py --write）：%s'
                % (len(no_status), '、'.join(no_status[:8])))
        if wrong_status:
            err('textbookStatus 与教材核对结论不一致：%s' % '；'.join(wrong_status[:8]))
        if unfixed:
            err('教材核对发现册次不一致但还没改：%s' % '、'.join(unfixed[:8]))

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

    # -------------------------------------------------- 2.7 render_split 与逗号段数
    # 约定：render_split[i] = 第 i 句按逗号能拆成几段（migrate.py 生成时就是这个算法）。
    # 数值与正文不符，游戏贴花层就会把一句拆错行。
    rs_bad = []
    for p in poems:
        punct = p.get('linesPunct') or []
        rs = p.get('render_split') or []
        if len(punct) != len(rs):
            continue
        for i, (ln, want) in enumerate(zip(punct, rs)):
            segs = len([x for x in ln.rstrip('。！？；').split('，') if x.strip()])
            if max(1, segs) != want:
                if p.get('render_split_reason'):
                    notes.append('%s 第%d句 render_split 与逗号段数不符，篇内已写明理由：%s'
                                 % (p['title'], i + 1, p['render_split_reason']))
                    continue
                rs_bad.append('%s 第%d句（记 %d，按逗号应为 %d）' % (p['title'], i + 1, want, max(1, segs)))
    if rs_bad:
        key = 'render_split:mismatch'
        text = 'render_split 与逗号段数不符：%d 处。例：%s' % (len(rs_bad), '；'.join(rs_bad[:4]))
        if key in known:
            seen_defects.add(key)
            notes.append('已知未修（%s 处理）：%s' % (known[key]['phase'], text))
        else:
            err(text)

    # -------------------------------------------------- 2.8 背诵要求字段必须存在且取值合法
    # recite 决定学古诗站给不给「背诵」标签、给哪种：
    #   full    全篇背诵        section 节选范围背诵      line 只背名句      none 不要求背诵
    # 缺这个字段不是小事：站点会当成「没有背诵要求」，家长看不到这篇到底要不要背。
    bad_recite = find_missing_recite(poems)
    if bad_recite:
        err("背诵要求缺失或取值非法：%d 篇。例：%s"
            % (len(bad_recite), '；'.join(bad_recite[:4])))

    # -------------------------------------------------- 2.11 玩法可用性不许有悬案
    unplayable = find_unplayable(poems)
    for p in poems:
        if not p.get('pairs'):
            key = 'nopair:' + p['id']
            if key in known:
                seen_defects.add(key)

    if unplayable:
        err('玩法悬案：%d 篇做不出玩法单元，必须补做或在登记表里写明「为什么不做」：%s'
            % (len(unplayable), '；'.join(unplayable[:4])))

    # --------------------------------- 2.12 背诵要求 ⇄ 收录范围不许自相矛盾
    conflicts = find_fulltext_conflicts(poems)
    for p in poems:
        if p.get('recite') == 'full' and not p.get('hasFulltext'):
            key = 'fulltext-required:' + p['id']
            if key in known:
                seen_defects.add(key)
    if conflicts:
        err('背诵要求与收录范围矛盾：%d 篇写着 recite=full 但仓内只有节选，要么补全文，要么改 recite，要么登记理由：%s'
            % (len(conflicts), '；'.join(conflicts[:4])))

    # -------------------------------------------------- 2.14 必背名句必须能在全文里逐字找到
    # 有「## 全文」小节的篇，必背名句必须是全文里出现过的句子。
    # 为什么这条要紧：学生看到的是一句「必背名句」和一段「全文」。两者对不上，
    # 他要么背了一句全文里没有的话，要么照着全文默写、结果和名句答案不一样——考场上这就是丢分。
    # 比对只比字面，不比标点：全文里「国破山河在，城春草木深」和名句「国破山河在城春草木深」是同一句。
    # 只比字面，不比标点。标点清单列不全：全文里用的是直角引号还是弯引号，是抄来的格式，不是内容。
    # 所以反过来做——只留字，其余全删。这样「惠子谓庄子曰：「魏王…」」和「惠子谓庄子曰："魏王…"」算同一句。
    def _strip_punct(t):
        return re.sub(r'[\W_]+', '', t or '', flags=re.UNICODE)
    broken_lines = []
    for p in poems:
        full = p.get('fullLines') or []
        if not full:
            continue
        ftxt = _strip_punct(''.join(full))
        for ln in (p.get('lines') or []):
            key = _strip_punct(ln)
            if key and key not in ftxt:
                broken_lines.append((p['id'], p['title'], ln))
    unregistered = []
    for pid, title, ln in broken_lines:
        key = 'fullline:' + pid
        if key in known:
            seen_defects.add(key)
        else:
            unregistered.append('%s：必背句「%s」在这篇的全文里找不到' % (title, ln[:20]))
    if unregistered:
        err('必背名句与全文对不上：%d 处。补全文、改名句，或在 known-defects 里写明为什么允许对不上：%s'
            % (len(unregistered), '；'.join(unregistered[:6])))

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

    # -------------------------------------------------- 4.5 全文占位符
    # 「## 全文」下面写一句「完整原文待补」不算有全文。课标把这些篇目列在默写范围里，
    # 只有名句等于没备齐——学生按我们的页面去默写，写出来的是半篇。
    placeholder_files = []
    for p in poems:
        raw_all = (ROOT / p['_path']).read_text(encoding='utf-8')
        body_all = raw_all
        if raw_all.startswith('---'):
            cut_all = raw_all.find('\n---', 3)
            if cut_all > 0:
                body_all = raw_all[cut_all + 4:]
        in_sec = False
        saw_section = False
        have = []
        for raw in body_all.splitlines():
            s = raw.strip()
            if s.startswith('## '):
                in_sec = s[3:].strip() in ('必背全文', '全文')
                if in_sec:
                    saw_section = True
                continue
            if not in_sec or not s or s.startswith('>'):
                continue
            have.append(s)
        if saw_section and (not have or any('待补' in x for x in have)):
            placeholder_files.append(p['_path'])
    if placeholder_files:
        key = 'placeholder:fulltext'
        text = '全文占位符：%d 篇的「必背全文/全文」小节是空的或写着「完整原文待补」，而课标要求这些篇目默写。例：%s' % (len(placeholder_files), '、'.join(placeholder_files[:4]))
        if key in known:
            seen_defects.add(key)
            notes.append('已知未修（%s 处理）：%s' % (known[key]['phase'], text))
        else:
            err(text)

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
        # 正文来源必须能追到一个可核对的文本库。S3 是 chinese-poetry，S9 是维基文库。
        # 先秦与文言长篇 S3 根本没有（《论语》《左传》不在那个库里），只认 S3 会把
        # 有出处的篇目一路报警；报警多了就等于没有报警。
        elif 'S3' not in src and 'S9' not in src:
            warn('%s: source 为 %r，既未引用 S3(chinese-poetry) 也未引用 S9(维基文库)，'
                 '请确认正文出处' % (p['title'], src))

        # 册次 ⇄ 学段一致性
        vol = (p.get('volume') or '').strip()
        pat = VOLUME_PATTERNS.get(stage)
        if pat is None:
            err('%s: stage 为 %r，不是小学/初中/高中' % (p['title'], stage))
        elif not vol:
            err('%s: 缺 volume（册次）' % p['title'])
        elif not re.match(pat, vol):
            err('%s: 册次「%s」与学段 %s 不匹配（应为 %s）'
                % (p['title'], vol, stage, VOLUME_HINT[stage]))

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

    # 登记必须对得上现实：登记过的问题如果已经消失，说明这条登记过期了，
    # 必须删掉——否则这张表迟早变成永久垃圾桶，什么都能往里扔。
    # 放在所有检查之后：登记是在这些检查里被「认领」的，早一步比对就会误报过期。
    for key, d in known.items():
        if key not in seen_defects:
            err('已知未修登记过期：%s（%s）——问题已经不见了，请从 data/known-defects.json 删掉这条'
                % (key, d.get('title', '')))

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