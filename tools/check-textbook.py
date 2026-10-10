#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教材用字核对：仓内正文，和统编教材课文里的字句，一不一样。

为什么必须有这一步：v1 冻结时承认的最大缺口就是「统编教材用字尚未逐本核对」。
公有领域底本（维基文库）这条腿站得稳，教材本那条腿还没接上。
而我们的口径是「教材版为准 + 附异文清单」——口径定了，却没工具去执行它。

来源地位必须说清楚：统编教材是版权作品。本工具**只取课文原文的字句**作为
「教材这里写作某字」的证据；教材的注释、译文、赏析一个字都不许进仓。
缓存文件只存在 data/textbook-cache/（已 gitignore 的话也不外传）。

用法：
  python tools/check-textbook.py                 # 全仓
  python tools/check-textbook.py --stage 高中    # 先做考试暴露面最大的一批
  python tools/check-textbook.py --limit 20
  python tools/check-textbook.py --refresh       # 忽略缓存重抓
"""
import difflib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import validate as V  # noqa: E402

BASE = 'https://yw.suyang123.com'
UA = {'User-Agent': 'diuci-content-check/1.0 (contact: hi@diuci.com)'}
OUT = ROOT / 'data' / 'textbook-attestations.json'
CACHE = ROOT / 'data' / 'textbook-cache'

# 仓内册次 → 教材课文目录页
VOLUMES = {
    '一年级上册': '/xiaoxue/yinianji/shangce.html',
    '一年级下册': '/xiaoxue/yinianji/xiace.html',
    '二年级上册': '/xiaoxue/ernianji/shangce.html',
    '二年级下册': '/xiaoxue/ernianji/xiace.html',
    '三年级上册': '/xiaoxue/sannianji/shangce.html',
    '三年级下册': '/xiaoxue/sannianji/xiace.html',
    '四年级上册': '/xiaoxue/sinianji/shangce.html',
    '四年级下册': '/xiaoxue/sinianji/xiace.html',
    '五年级上册': '/xiaoxue/wunianji/shangce.html',
    '五年级下册': '/xiaoxue/wunianji/xiace.html',
    '六年级上册': '/xiaoxue/liunianji/shangce.html',
    '六年级下册': '/xiaoxue/liunianji/xiace.html',
    '七年级上册': '/chuzhong/qinianji/shangce.html',
    '七年级下册': '/chuzhong/qinianji/xiace.html',
    '八年级上册': '/chuzhong/banianji/shangce.html',
    '八年级下册': '/chuzhong/banianji/xiace.html',
    '九年级上册': '/chuzhong/jiunianji/shangce.html',
    '九年级下册': '/chuzhong/jiunianji/xiace.html',
    '必修上册': '/gaozhong/bixiushang.html',
    '必修下册': '/gaozhong/bixiuxia.html',
    '选择性必修上册': '/gaozhong/xuanxiushang.html',
    '选择性必修中册': '/gaozhong/xuanxiuzhong.html',
    '选择性必修下册': '/gaozhong/xuanxiuxia.html',
}
# 课标指定选修、统编教材课本里没有的篇目所在目录：不是错误，是「教材里没有这篇」
NO_TEXTBOOK_VOLUME = '选修（2026起默写）'

TEXT_WRAP = re.compile(r'<p class="text-wrap[^"]*"[^>]*>([\s\S]*?)</p>')
TAG = re.compile(r'<[^>]+>')
PUNCT = re.compile(r'[^一-鿿]')
# 目录页有两种写法：锚文本在 > 之后（可能换行缩进），也可能只在 title="…课文朗读" 属性里。
# 只认锚文本会漏掉整批课文——漏了就会把「工具没抓到」误报成「教材里没有这篇」。
TITLE_ATTR = re.compile(r'href="(/[^"]+?_langdu\.html)"[^>]*?title="([^"]{1,60}?)课文朗读"')
TITLE_LINE = re.compile(r'href="(/[^"]+?_langdu\.html)"[^>]*>([\s\S]{1,80}?)</a>')


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def cached(url, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r'[^0-9A-Za-z]', '_', url)[:-4] + '.html'
    p = CACHE / key
    if p.exists() and not refresh:
        return p.read_text(encoding='utf-8')
    html = fetch(url)
    p.write_text(html, encoding='utf-8')
    time.sleep(0.4)
    return html


def strip_tags(html):
    return TAG.sub(' ', html)


def norm(s):
    return PUNCT.sub('', s or '')


def volume_index(path, refresh=False):
    """一册的课文目录：[(课文名, 课文页 URL)]。"""
    html = cached(BASE + path, refresh)
    out, seen = [], set()
    for rx in (TITLE_ATTR, TITLE_LINE):
        for m in rx.finditer(html):
            url, name = m.group(1), strip_tags(m.group(2)).strip()
            if url in seen or not name:
                continue
            seen.add(url)
            out.append((name, BASE + url))
    return out


def lesson_text(url, refresh=False):
    """课文页里的原文段落（只取 audioModule 里的 text-wrap，不碰译文注释）。"""
    html = cached(url, refresh)
    i = html.find('audioModule play-box')
    if i < 0:
        i = 0
    j = html.find('details-box', i)
    seg = html[i:j if j > i else len(html)]
    paras = [strip_tags(x).strip() for x in TEXT_WRAP.findall(seg)]
    return [p for p in paras if norm(p)]


def stage_of(volume):
    if volume in ('必修上册', '必修下册') or volume.startswith('选择性必修'):
        return '高中'
    if volume[:1] in '七八九':
        return '初中'
    return '小学'


def same_stage(a, b):
    return stage_of(a) == stage_of(b)


def title_candidates(title, subtitle):
    t = re.sub(r'[《》]', '', title or '')
    subs = [t]
    if subtitle:
        s = re.sub(r'[《》（）]', '', subtitle)
        subs += [t + s, t + ' ' + s]
    return [re.sub(r'\s+', '', x) for x in subs]


GARDEN = ROOT / 'data' / 'textbook-garden.json'
ABSENCE = ROOT / 'data' / 'absence-checks.json'
GARDEN_RULES = ROOT / 'data' / 'garden-rulings.json'
COVERAGE = ROOT / 'data' / 'textbook-coverage.json'


def garden_name(s):
    """园地篇名与仓内篇名对齐。
    「（其二）」是第几首的编号，属于篇名本身——悯农其一、悯农其二是两首不同的诗；
    「（节选）」不是篇名的一部分，去掉。"""
    def keep(m):
        inner = (m.group(1) or '').strip()
        if re.fullmatch(r'其?[一二三四五六七八九十0-9]+', inner):
            return inner if inner.startswith('其') else '其' + inner
        return ''
    t = re.sub(r'[（(]([^）)]*)[）)]', keep, s or '')
    t = re.sub(r'[《》\s\u3000·]', '', t)
    return t


def load_garden():
    """{册: [(对齐名, 页面上写的篇名, 园地, URL)]}；表不在就返回 None（不许静默当成没有）。"""
    if not GARDEN.exists():
        return None
    data = json.loads(GARDEN.read_text(encoding='utf-8'))
    out = {}
    for vol, rows in (data.get('volumes') or {}).items():
        for r in rows:
            if not r.get('title'):
                continue
            out.setdefault(vol, []).append((garden_name(r['title']), r['title'], r.get('garden') or '', r.get('url') or ''))
    return out


def garden_match(poem, garden):
    """只按整名对，不许前缀互含。
    「画鸡」对「画」、「悯农其一」对「悯农其二」——前缀互含会把两首不同的诗当成同一首，
    判错的代价是把学生的背诵范围指错。"""
    cands = set()
    for c in title_candidates(poem.get('title'), poem.get('subtitle')):
        cands.add(garden_name(c))
    cands.discard('')
    for vol, rows in garden.items():
        for name, raw, garden_name_raw, url in rows:
            if name in cands:
                yield vol, raw, garden_name_raw, url

def garden_authors():
    """{（册, 对齐篇名): [页面上写的作者]}。园地证据要说「这一篇是谁的」，只看篇名不够——
    凉州词这个名字下统编有两首：四年级上册课文里是王翰的，五年级下册园地四里是王之涣的。"""
    if not GARDEN.exists():
        return {}
    data = json.loads(GARDEN.read_text(encoding='utf-8'))
    out = {}
    for vol, rows in (data.get('volumes') or {}).items():
        for r in rows:
            if not r.get('title'):
                continue
            out.setdefault((vol, garden_name(r['title'])), []).append((r.get('authorRaw') or '').strip())
    return out


def garden_sections():
    """{（册, 对齐篇名): 页面上写的栏目}。「语文园地四·词句段运用」与「语文园地四·日积月累」
    是两栏，学生在不同的地方背——只说「园地收了」不够。"""
    if not GARDEN.exists():
        return {}
    data = json.loads(GARDEN.read_text(encoding='utf-8'))
    out = {}
    for vol, rows in (data.get('volumes') or {}).items():
        for r in rows:
            if not r.get('title'):
                continue
            sec = (r.get('section') or '').strip()
            if sec:
                out[(vol, garden_name(r['title']))] = sec
    return out


def garden_author_match(poem, author_raw):
    """园地页上写的作者与仓内作者对不对得上。「[唐代] 王之涣」→「王之涣」。
    页面上没写作者就当对不上——猜一次的成本是把另一首诗算到我们这篇头上。"""
    a = re.sub(r'^\[[^\]]*\]\s*', '', author_raw or '').strip()
    if not a:
        return False
    return a == (poem.get('author') or '').strip()


def collision_garden_note(poem, garden_tbl, gauthors, vol, gsections=None):
    """课文目录里同名的是另一篇时，同一册的语文园地有没有我们这一篇。
    有就要说出来——以前这条分支直接判「教材收的是同名另一篇」就 continue，
    园地证据根本没机会说话，王之涣《凉州词》就是这么被说成「教材没收」的。
    作者对不上、园地在别的册、页面没写作者，都不算。"""
    if not garden_tbl:
        return None
    for v, raw, gname, url in garden_match(poem, garden_tbl):
        if v != vol:
            continue
        for a in gauthors.get((vol, garden_name(raw)), []):
            if garden_author_match(poem, a):
                sec = (gsections or {}).get((v, garden_name(raw))) or gname
                return v, raw, sec, url
    return None



def lesson_name(s):
    """覆盖表核验用的整名：去课号、括号、书名号、空白、间隔号，再去掉结尾的「节选/并序」。
    只按整名相等对，不许前缀互含——「相思」与「长相思」是两篇，「〈老子〉四章」与「〈老子〉八章」是两种覆盖。
    「其一/其二」这类编号留在括号里也没被抹掉：抹括号只抹内容不是编号的那些，见 garden_name。"""
    t = re.sub(r'^[\d.\-*（）\s]+', '', s or '')
    t = re.sub(r'[（(]([^）)]*)[）)]', lambda m: (m.group(1) if re.fullmatch(r'其?[一二三四五六七八九十0-9]+', (m.group(1) or '').strip()) else ''), t)
    t = re.sub(r'[《》〈〉“”\s\u3000·]', '', t)
    t = re.sub(r'(节选|并序)$', '', t)
    return t


def find_lesson(title, index):
    """在这一册目录里按整名找那一课；找不到返回 (None, None)。"""
    want = lesson_name(title)
    if not want:
        return None, None
    for name, url in index:
        if lesson_name(name) == want:
            return name, url
    return None, None


def load_coverage():
    """课标篇名与教材篇名不同的那几条（教材确实收了，只是名字不一样）。"""
    if not COVERAGE.exists():
        return {}
    return json.loads(COVERAGE.read_text(encoding='utf-8')).get('coverage') or {}


def garden_ruling_status(vol, rule, has_garden_hit):
    """园地裁定表的一条能不能成立：成立才判「语文园地收了（两条来源）」。

    返回 (status, why)。status='ok' 表示成立；其余是不成立的理由——不许降级成「只有一条来源」糊过去。"""
    srcs = [x for x in (rule.get('sources') or []) if x]
    mirror = [x for x in srcs if 'yw.suyang123.com' in x]
    if rule.get('volume') != vol:
        return 'broken', '园地裁定表说在「%s」，仓内却挂在「%s」——册次改动没落地或表过期' % (rule.get('volume'), vol)
    if len(srcs) < 2:
        return 'broken', '园地裁定表只有 %d 条来源，不够两条' % len(srcs)
    if len(mirror) > 1:
        return 'broken', '园地裁定表 %d 条来源里 %d 条出自同一个镜像目录——同源不算两条' % (len(srcs), len(mirror))
    if not has_garden_hit:
        return 'broken', '园地裁定表说这一册的园地里收了，园地表里却没有这一篇'
    return 'ok', ''

def load_absence_checks():
    """「查过了、没找到」的登记簿（data/absence-checks.json）。没有这张表时返回空。"""
    if not ABSENCE.exists():
        return {}
    return json.loads(ABSENCE.read_text(encoding='utf-8')).get('checks') or {}

def absence_record_ok(volume, rec):
    """登记簿的一条能不能撑起「没找到」这句话：册次要对、要写下查了哪些页、要给出结论。

    返回 (ok, why)。这条门槛的意义：谁要说「教材里没找到这一课」，谁就得先说清查了什么。"""
    if not rec:
        return False, '没有登记记录'
    if rec.get('volume') != volume:
        return False, '登记记录说在「%s」，仓内却挂在「%s」' % (rec.get('volume'), volume)
    if not [x for x in (rec.get('sources') or []) if x]:
        return False, '登记记录没写查过哪些页（sources 是空的）'
    if not (rec.get('gardenPages') or rec.get('lessonIndex')):
        return False, '登记记录没写查了什么内容'
    if not (rec.get('conclusion') or '').strip():
        return False, '登记记录没有结论'
    return True, ''

def garden_blind():
    """园地表里「只有栏目头、没列篇名」的页数：{册: 页数}。

    那一类页面镜像只抓到了栏目名（日积月累、字词句运用…），没抓到里面的篇名。数出来是为了让
    「教材里没有这一课」这句话带上自己的边界：这几页里有什么，我们不知道。"""
    if not GARDEN.exists():
        return {}
    data = json.loads(GARDEN.read_text(encoding='utf-8'))
    out = {}
    for vol, rows in (data.get('volumes') or {}).items():
        out[vol] = sum(1 for r in rows if not (r.get('title') or '').strip())
    return out

def absence_note(volume, blind_pages, is_syllabus, garden_covered=True, record=None, stage=''):
    """「教材里没有这一课」这句话要说清查了什么、边界在哪。

    三件事各自都是边界：园地表只抽了小学 12 册（初中、高中的册次没有「语文园地」这一栏，
    目录表里带「语文园地」的条目全部在小学 12 册里，这一点当场能从目录表数出来）；
    小学那 12 册里也有几页只列了栏目头、没列篇名，那几页里有什么我们不知道；
    不是课标篇目的（教材拓展）连「课标要背」这条依据也没有——以前它顶着
    「统编教材未收（课标要求）」，等于替课标作了一个课标没作过的声明。"""
    parts = ['同学段所有册的课文目录里都没有同名课文']
    if record and (record.get('lessonIndex') or record.get('gardenPages')):
        parts.append('查过的地方：' + '；'.join([x for x in (record.get('lessonIndex'), record.get('gardenPages')) if x]))
    if garden_covered:
        parts.append('这一册的语文园地页面上也没有')
        if blind_pages:
            parts.append('但园地表里「%s」有 %d 页只列了栏目头、没列篇名（镜像没写全）——找不到不等于没有'
                         % (volume, blind_pages))
    else:
        if stage == '小学':
            parts.append('语文园地那一档只核过小学 12 册，「%s」的园地页没核过——这句话只覆盖课文目录' % volume)
        else:
            parts.append('「语文园地」是小学册的栏目：目录表里带「语文园地」的条目全部在小学 12 册里，'
                         '初中与高中的册次没有这一栏——这句话覆盖整册课文目录，单元末的诵读篇目也在表里')
    if not is_syllabus:
        parts.append('这一篇在仓里是「教材拓展」（课标附录1里没有它），连「课标要背」这条依据也没有')
    return '；'.join(parts)

def load_garden_rules():
    """语文园地的册次裁定表（data/garden-rulings.json）。没有这张表时返回空，不报错。"""
    if not GARDEN_RULES.exists():
        return {}
    return json.loads(GARDEN_RULES.read_text(encoding='utf-8')).get('rulings') or {}


def match_lesson(poem, lessons):
    """按篇名在这一册的课文里找。副标题、带星号的自读课文、带编号都要能对上。

    包含关系只许「教材名比仓内名长」这一个方向（仓内名少于三字的除外）：教材那边常用
    「词牌·题目」或「篇名（说明）」，仓内常用「词牌 + 副标题」，《天净沙·秋思》对《天净沙》+「秋思」、
    《相见欢（金陵城上西楼）》对《相见欢》、《破阵子·为陈同甫赋壮词以寄之》对《破阵子》都是这一类。
    反方向一律不算对上——教材篇名只是仓内篇名的一部分，那是两篇：
    「忆江南」与「江南」（白居易 vs 汉乐府）、「舟夜书所见」与「夜书所见」（查慎行 vs 叶绍翁）。
    先前这条包含规则两头都认，把这两对判成了「同一篇、只是册次写错」。
    同名不等于同篇：这一关只找候选，是不是同一篇由后面的正文比对定（比得上才是同一篇）。"""
    cands = [re.sub(r'[《》〈〉（）\s\u3000·]', '', c) for c in title_candidates(poem.get('title'), poem.get('subtitle'))]
    for name, url in lessons:
        head = re.sub(r'^[\d.\-*（）\s]+', '', name)
        head = re.sub(r'\s*V\s*[\u4e00-\u9fff·]+$', '', head)   # 镜像在课文名后面挂的作者
        n = re.sub(r'[《》（）\s\u3000·]', '', head)
        n = re.sub(r'(节选|并序)$', '', n)
        if not n:
            continue
        for c in cands:
            if not c:
                continue
            if n == c:
                return name, url
            if len(c) >= 3 and n.startswith(c):
                return name, url
    return None, None


def cross_volume_status(paras, hit, total):
    """跨册同名这一关的结论：是「我们册次写错了」还是「教材那边同名的是另一篇」。

    只有三种说得出口：正文取到且比上了（同一篇，册次要改）；正文取到且本来有可比的句子、
    却一句都没对上（另一篇）；其余都是没核到，不许下结论。"""
    if not paras or not total:
        return 'volume-mismatch', '教材正文没取到或可比对的句子一句都没有，是不是同一篇没核'
    if hit:
        return 'volume-mismatch', '同一篇：正文 %d/%d 句对上' % (hit, total)
    return 'mismatch', '正文 %d 句一句都没对上：那是另一篇' % total


def diff_against(line, book):
    """对不上的那句，教材那边到底写的是什么。

    只报「对不上」没有用——得指出差在哪个字，否则下一步只能靠猜。
    先找这句与教材正文的最长公共片段当锚，取锚附近同样长的窗口，再逐段对齐。
    """
    key = norm(line)
    if not key or not book:
        return []
    sm = difflib.SequenceMatcher(None, key, book, autojunk=False)
    m = sm.find_longest_match(0, len(key), 0, len(book))
    if m.size < 4:
        return [{'ours': key, 'textbook': None}]
    start = max(0, m.b - m.a)
    window = book[start:start + len(key) + 40]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, key, window, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        out.append({'ours': key[i1:i2], 'textbook': window[j1:j2],
                    'context': window[max(0, j1 - 8):j2 + 8]})
    return out


def compare(poem, paras):
    """仓内每一句（名句 + 全文）去教材原文里找。

    返回 (对上的句数, 参与比对的句数, 太短没参与的句数, 没对上的明细)。
    先前分母用的是「所有句子」，可短于四字的句子从来没参与过比对——
    那样一篇正文与教材逐字相同的诗也会被判成 partial（《咏鹅》头一句「鹅鹅鹅」就是这种），
    假缺口比假对上便宜，但它是假的就该说清楚。
    """
    book = norm(''.join(paras))
    ours = []
    for ln in (poem.get('linesPunct') or []):
        ours.append(('名句', ln))
    for ln in (poem.get('fullLinesPunct') or []):
        ours.append(('全文', ln))
    hit, skipped, miss = 0, 0, []
    for kind, ln in ours:
        key = norm(ln)
        if len(key) < 4:
            skipped += 1
            continue
        if key in book:
            hit += 1
        else:
            miss.append({'kind': kind, 'line': ln.strip(), 'diff': diff_against(ln, book)})
    return hit, hit + len(miss), skipped, miss


def selftest():
    """教材核对这条腿自己也得有坏例子。它比对的是「考试真会考的那份正文」，
    判错一次就可能把学生的背诵范围指错。这里只测判定逻辑，不联网。"""
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    # 坏例1：norm 去标点；None 不许崩
    must(norm('床前明月光，疑是地上霜。') == '床前明月光疑是地上霜', '坏例1：标点没去掉')
    must(norm(None) == '', '坏例1b：None 没变成空串')
    must(norm('') == '', '坏例1c：空串没保持空')

    # 坏例2：strip_tags 把标签换成空格，内容一个字不许丢
    must('明月光' in strip_tags('<div class="t">明月光</div>'), '坏例2：剥标签把正文剥掉了')

    # 坏例3：学段判错就会跨学段乱配课文
    must(stage_of('必修上册') == '高中', '坏例3：必修上册不是高中')
    must(stage_of('选择性必修中册') == '高中', '坏例3b：选择性必修不是高中')
    must(stage_of('七年级下册') == '初中', '坏例3c：七年级不是初中')
    must(stage_of('一年级上册') == '小学', '坏例3d：一年级不是小学')
    must(same_stage('七年级上册', '七年级下册') is True, '坏例3e：同学段不同册被判成不同学段')
    must(same_stage('七年级上册', '必修上册') is False, '坏例3f：初中课文被允许配到高中篇目')

    # 坏例4：篇名候选——《》、副标题的两种写法都要能对上
    cands = title_candidates('《论语》十二章', '（十二则）')
    must('论语十二章' in cands and '论语十二章十二则' in cands, '坏例4：篇名候选没造出来：%s' % cands)
    must(title_candidates(None, None) == [''], '坏例4b：没有篇名却没返回空候选')

    # 坏例5：课文名里的编号、星号、括号必须能剥掉
    name, url = match_lesson({'title': '观沧海'}, [('1. 观沧海', 'u1')])
    must(name == '1. 观沧海' and url == 'u1', '坏例5：带编号的课文没对上')
    name2, _ = match_lesson({'title': '天上的街市'}, [('* 天上的街市', 'u2')])
    must(name2 is not None, '坏例5b：自读星号课文没对上')

    # 坏例6：短篇名不许用子串乱配——「春」配到「春风」就是把两篇课文合成一篇
    must(match_lesson({'title': '春'}, [('春风', 'u')])[0] is None, '坏例6：单字篇名被子串匹配抢走了')
    must(match_lesson({'title': '白鹅'}, [('天鹅', 'u')])[0] is None, '坏例6b：不同篇目被当成同一篇')
    must(match_lesson({'title': '天上的街市'}, [('天上的街市 V 郭沫若', 'u')])[0] is not None, '坏例6c：镜像挂在课文名后面的作者妨碍了对上')
    # 坏例6d：整名相等就算对上，不再按篇名长短放开子串——旧的长度闸门换成了「只认一个方向的包含」。
    must(match_lesson({'title': '海燕'}, [('海燕 V 高尔基', 'u')])[0] is not None,
         '坏例6d：整名相等的课文没被对上（两字篇名还被旧的长度闸门拦着）')
    # 坏例6e：教材篇名只是仓内篇名的一部分，那是两篇，不是「同一篇、册次写错」
    must(match_lesson({'title': '忆江南', 'subtitle': '江南好'}, [('2 江南', 'u')])[0] is None,
         '坏例6e：「忆江南」被教材里的「江南」（汉乐府）抢走')
    must(match_lesson({'title': '舟夜书所见'}, [('夜书所见', 'u')])[0] is None,
         '坏例6f：「舟夜书所见」（查慎行）被教材里的「夜书所见」（叶绍翁）抢走')
    must(match_lesson({'title': '相思'}, [('长相思', 'u')])[0] is None,
         '坏例6g：「相思」被「长相思」抢走')
    # 坏例6h：教材那边多出来的一截必须是括号里的说明或仓内的副标题，不许是别的词
    must(match_lesson({'title': '天净沙', 'subtitle': '秋思'}, [('天净沙·秋思', 'u')])[0] is not None,
         '坏例6h：词牌加副标题的课文没对上')
    must(match_lesson({'title': '相见欢'}, [('相见欢（金陵城上西楼）', 'u')])[0] is not None,
         '坏例6i：教材用括号补出题目的课文没对上')
    must(match_lesson({'title': '离骚'}, [('1.2离骚（节选）', 'u')])[0] is not None,
         '坏例6j：「（节选）」没剥掉')
    must(match_lesson({'title': '归去来兮辞'}, [('10.2归去来兮辞并序', 'u')])[0] is not None,
         '坏例6k：「并序」没剥掉')
    must(match_lesson({'title': '凉州词'}, [('凉州词', 'u')])[0] is not None,
         '坏例6l：整名相等的同名课文没对上（同名另一篇要靠正文判，篇名这一关不许先漏）')
    # 坏例6m：同名只是候选，是不是同一篇不许靠篇名判——分类由正文比对定，这里直接测那个分类。
    must(cross_volume_status(None, 0, 0)[0] == 'volume-mismatch',
         '坏例6m：教材正文没取到就被判成「另一篇」（没核到却下了结论）')
    must(cross_volume_status(['空话'], 0, 0)[0] == 'volume-mismatch',
         '坏例6m2：可比对的句子一句都没有（全太短），也被判成「另一篇」')
    must(cross_volume_status(['无言独上西楼月如钩寂寞梧桐深院锁清秋'], 0, 8)[0] == 'mismatch',
         '坏例6n：教材正文取到了、八句全对不上，却没被判成「另一篇」')
    must(cross_volume_status(['无言独上西楼月如钩'], 1, 8)[0] == 'volume-mismatch',
         '坏例6o：正文比上了（同一篇、册次写错）却没被判成册次对不上')
    must('没核' in cross_volume_status(None, 0, 0)[1],
         '坏例6p：教材正文没取到时，note 里没写明没核——读者看不出这一条是猜的还是查过的')

    # 坏例7：对不上的那句必须说清差在哪个字（不皲手 / 不龟手 那一类）
    d = diff_against('宋人有善为不龟手之药者', '宋人有善为不皲手之药者')
    must(d and any(x.get('ours') and x.get('textbook') for x in d),
         '坏例7：一字之差没被指出差在哪：%s' % d)
    # 坏例8：完全找不到必须明说「没找到」，不许返回空列表假装没问题
    must(diff_against('床前明月光', '枯藤老树昏鸦小桥流水') == [{'ours': '床前明月光', 'textbook': None}],
         '坏例8：找不到时返回了空列表：%s' % diff_against('床前明月光', '枯藤老树昏鸦小桥流水'))
    must(diff_against('', '任何教材文字') == [], '坏例8b：空句子被当成一次比对')
    must(diff_against('床前明月光', '') == [], '坏例8c：教材那边是空的却没报错')

    # 坏例9：compare 的口径是严格包含——教材写作别的样子就是没对上，不许按相似度放行
    hit, total, skipped, miss = compare({'linesPunct': ['海内存知己，天涯若比邻'], 'fullLinesPunct': []},
                                        ['海内存知己，天涯若比隣。'])
    must(hit == 0 and total == 1 and len(miss) == 1,
         '坏例9：邻/隣 一字之差被当成对上了（hit=%d miss=%d）' % (hit, len(miss)))
    must(miss[0]['diff'] and miss[0]['diff'][0].get('textbook'), '坏例9b：没对上却没说清教材怎么写')
    hit2, total2, skipped2, miss2 = compare({'linesPunct': ['海内存知己，天涯若比邻'], 'fullLinesPunct': []},
                                            ['海内存知己，天涯若比邻。'])
    must(hit2 == 1 and not miss2, '坏例9c：逐字对上的句子被报了')
    # 坏例10：短于四字的句子不参与比对（《咏鹅》头一句「鹅鹅鹅」这种，比对只会造噪音）
    hit3, total3, skipped3, miss3 = compare({'linesPunct': ['鹅鹅鹅'], 'fullLinesPunct': []}, ['完全无关的教材文字'])
    must(total3 == 0 and skipped3 == 1 and not miss3,
         '坏例10：三字短句没被单独登记（total=%d skipped=%d）——它从来没参与比对，不许进分母' % (total3, skipped3))
    hit3b, total3b, skipped3b, _ = compare({'linesPunct': ['不亦说乎'], 'fullLinesPunct': []}, ['完全无关的教材文字'])
    must(total3b == 1 and skipped3b == 0, '坏例10b：四字句子被漏掉，边界不在了')
    # 坏例11：全文与名句都要算，只算名句会把「教材收了全文」这件事漏掉
    hit4, total4, skipped4, _ = compare({'linesPunct': ['床前明月光'], 'fullLinesPunct': ['举头望明月']},
                                        ['床前明月光，举头望明月。'])
    must(total4 == 2 and hit4 == 2, '坏例11：全文那一遍没参与比对（total=%d hit=%d）' % (total4, hit4))

    # 坏例12：园地那一档的对名口径——「其一/其二」必须留着。
    # 悯农其一、悯农其二 是两首不同的诗（「春种一粒粟」与「锄禾日当午」），
    # 把尾数抹掉就把两首不同的诗当成同一首，学生的背诵范围就指错了。
    must(garden_name('悯农（其一）') == '悯农其一' and garden_name('悯农（其二）') == '悯农其二',
         '坏例12：其一/其二 被抹掉了（%r / %r）——两首不同的诗会被当成同一首' % (
             garden_name('悯农（其一）'), garden_name('悯农（其二）')))
    fake_garden = {'一年级上册': [('悯农其二', '悯农（其二）', '语文园地四', 'u1')],
                   '一年级上册b': [('画', '画', '语文园地二', 'u2')],
                   '二年级上册': [('古朗月行', '古朗月行（节选）', '语文园地六', 'u3')],
                   '三年级上册': [('所见', '所见', '语文园地', 'u4')]}
    got = list(garden_match({'title': '悯农其一', 'subtitle': None}, fake_garden))
    must(not got, '坏例12b：悯农其一 对上了 悯农（其二）（%s）——两首不同的诗被当成同一首' % got)
    got2 = list(garden_match({'title': '悯农其二', 'subtitle': None}, fake_garden))
    must(len(got2) == 1 and got2[0][0] == '一年级上册', '坏例12c：悯农其二 没对上自己那一篇（%s）' % got2)
    # 坏例13：不许前缀互含。「画鸡」不是「画」，「相思」也不是「相思（XXX）」之外的另一篇
    got3 = list(garden_match({'title': '画鸡', 'subtitle': None}, fake_garden))
    must(not got3, '坏例13：画鸡 被前缀对上了「画」（%s）——两篇不同的课文被当成同一篇' % got3)
    # 好例子不许误伤：教材把篇名写成「古朗月行（节选）」，仓内写「古朗月行」，应当对上
    got4 = list(garden_match({'title': '古朗月行', 'subtitle': None}, fake_garden))
    must(len(got4) == 1 and got4[0][1] == '古朗月行（节选）', '坏例13b：括号里的「节选」挡住了对名（%s）' % got4)
    # 坏例14：覆盖表里写的课必须在目录里找得到，找不到就是编的（这条在 main 里报 problem）
    must(match_lesson({'title': '这一课目录里不存在'}, [('鱼我所欲也', 'u')]) == (None, None),
         '坏例14：目录里没有的课名也被 match_lesson 认领了——覆盖表的核验就形同虚设')
    # 真产物：园地表本身不许是空的，且一年级上册必须有咏鹅
    real_garden = load_garden()
    if real_garden is None:
        print('     （data/textbook-garden.json 还没生成，真产物那两条没跑）')
    else:
        n = sum(len(v) for v in real_garden.values())
        must(n > 0, '坏例15：园地表抽到了零篇目——抽取失效却像成功一样退出')
        must(any(t == '咏鹅' for t, _, _, _ in real_garden.get('一年级上册', [])),
             '坏例15b：真产物里一年级上册没有咏鹅（抽取失效？）')
        # 悯农其一 在真表里确实有（二年级下册 语文园地），所以不许断言「对不上」；
        # 要断的是：它只能对上「其一」那一首，不许顺带对上「其二」。
        hits1 = list(garden_match({'title': '悯农其一'}, real_garden))
        must(hits1 and all('其一' in h[1] for h in hits1),
             '坏例15c：悯农其一 对上了别的首（%s）——编号口径失效' % [h[1] for h in hits1])
        hits2 = list(garden_match({'title': '悯农其二'}, real_garden))
        must(hits2 and all('其二' in h[1] for h in hits2),
             '坏例15d：悯农其二 对上了别的首（%s）' % [h[1] for h in hits2])

    # 坏例16：覆盖表核验的整名口径
    must(lesson_name('离骚（节选）') == lesson_name('离骚'), '坏例16：「节选」挡住了对名，离骚 会被判成教材未收')
    must(lesson_name('相思') != lesson_name('长相思'), '坏例16b：相思 与 长相思 被当成同一篇')
    must(lesson_name('《老子》四章') != lesson_name('《老子》八章'), '坏例16c：四章 与 八章 被当成同一种覆盖')
    must(lesson_name('5.2* 大学之道') == '大学之道', '坏例16d：课号没剥掉（%r）' % lesson_name('5.2* 大学之道'))
    must(find_lesson('木兰诗', [('9 木兰诗', 'u')])[1] == 'u', '坏例16e：目录里明写的课找不到——覆盖表核验形同虚设')
    must(find_lesson('这一课目录里没有', [('9 木兰诗', 'u')]) == (None, None), '坏例16f：目录里没有的课也被认领了')
    must(find_lesson('已亥杂诗', [('12 己亥杂诗', 'u')]) == (None, None), '坏例16g：镜像错字 已/己 被当成同一个字放行了')
    # 真产物：覆盖表自己得经得起检查（不联网，只查表）
    cov_all = load_coverage()
    if not cov_all:
        print('     （data/textbook-coverage.json 不在，覆盖表那几条没跑）')
    else:
        for cid, v in cov_all.items():
            must(len(v.get('sources') or []) >= 2,
                 '坏例17：%s 覆盖表里没写满两条独立来源——只有镜像一条来源的判不成教材收了' % cid)
            must(len(str(v.get('note') or '')) >= 20, '坏例17b：%s 没写清为什么' % cid)
            must(v.get('lessons'), '坏例17c：%s 覆盖表里没列那一课' % cid)
        must(cov_all.get('laozi8', {}).get('partial') is True,
             '坏例18：《老子》八章 没标 partial——教材只收四章，写成「教材收了」就是骗人')
        must('indexTitle' in json.dumps(open(COVERAGE, encoding='utf-8').read()),
             '坏例18b：己亥杂诗 的镜像错字没登记（覆盖表里该有 indexTitle）')

    # 坏例17：园地裁定表的门槛——进表就是把「镜像里看到了」升格成「教材收了」
    good = {'volume': '四年级下册', 'section': '语文园地二·日积月累',
            'sources': ['yw.suyang123.com 园地页', 'zy.21cnjy.com/24709078 教案']}
    must(garden_ruling_status('四年级下册', good, True)[0] == 'ok',
         '坏例17：册次对、两条来源（镜像一条）的裁定被误报：%s' % garden_ruling_status('四年级下册', good, True)[1])
    must(garden_ruling_status('三年级下册', good, True)[0] == 'broken',
         '坏例17b：仓内册次与裁定表不一致却没被拦')
    must(garden_ruling_status('四年级下册', {'volume': '四年级下册', 'sources': ['zy.21cnjy.com/24709078 教案']}, True)[0] == 'broken',
         '坏例17c：只有一条来源的裁定被放行')
    must(garden_ruling_status('四年级下册', {'volume': '四年级下册', 'sources': [
        'yw.suyang123.com 园地页', 'yw.suyang123.com 目录页']}, True)[0] == 'broken',
         '坏例17d：两条来源都出自同一个镜像却被放行（同源被数成了两条）')
    must(garden_ruling_status('四年级下册', good, False)[0] == 'broken',
         '坏例17e：园地表里其实没有这一篇，裁定却被放行')
    must('同源' in garden_ruling_status('四年级下册', {'volume': '四年级下册', 'sources': [
        'yw.suyang123.com a', 'yw.suyang123.com b']}, True)[1],
         '坏例17f：拦下了却没说清为什么拦')
    # 坏例19：「教材里没有这一课」必须带上自己的边界——那一册的园地页里有几页只列了栏目头
    n19 = absence_note('一年级下册', 3, True, True)
    must('3 页只列了栏目头' in n19, '坏例19：那一册有 3 页只列了栏目头，note 里没说这句话的边界：%s' % n19)
    n19b = absence_note('一年级上册', 0, True, True)
    must('只列了栏目头' not in n19b, '坏例19b：没有盲区页却写着盲区（%s）' % n19b)
    n19c = absence_note('一年级下册', 3, False, True)
    must('教材拓展' in n19c, '坏例19c：不是课标篇目却没说清依据：%s' % n19c)
    n19d = absence_note('七年级上册', 0, True, True)
    must('教材拓展' not in n19d, '坏例19d：课标篇目被写成了教材拓展（%s）' % n19d)
    must(len(n19) > len(n19b), '坏例19e：盲区没让这句话变长——等于没写')
    # 坏例19f：高中册没有「语文园地」这一栏——note 不许写得好像高中有园地、只是我们没核过
    n19f = absence_note('选择性必修下册', 0, True, False, None, '高中')
    must('没有这一栏' in n19f, '坏例19f：高中册的 note 没说明「语文园地」不是高中的栏目：%s' % n19f)
    must('园地页没核过' not in n19f, '坏例19f2：高中册的 note 还写着「园地页没核过」，等于替高中凭空添了一栏：%s' % n19f)
    must('诵读篇目也在表里' in n19f, '坏例19f3：高中册的 note 没说清这句话覆盖整册目录（含单元末诵读）：%s' % n19f)
    # 坏例19g：小学那册没核园地时，先说查过的、后说没核过的，顺序不许反
    n19f2 = absence_note('三年级下册', 0, True, False, None, '小学')
    must('园地页没核过' in n19f2, '坏例19g：小学册没核园地却没说：%s' % n19f2)
    must(n19f2.index('课文目录') < n19f2.index('园地页没核过'), '坏例19g2：先说没核过的东西、后说查过的，读起来像反话：%s' % n19f2)
    # 坏例19h：小学那册核过园地，就不许写「没核过」
    n19h = absence_note('三年级下册', 3, True, True)
    must('没核过' not in n19h, '坏例19h：小学册的园地明明核过，note 却说没核过：%s' % n19h)
    # 坏例19i~19m：「没找到」这句话必须由登记簿撑着——查了什么、查了哪几页
    good19 = {'volume': '一年级下册', 'lessonIndex': '小学 11 册目录里没有', 'gardenPages': '八页园地逐页读过',
              'sources': ['https://yw.suyang123.com/x/1'], 'conclusion': '没找到'}
    must(absence_record_ok('一年级下册', good19)[0], '坏例19i：一条完整的登记记录被误报：%s' % absence_record_ok('一年级下册', good19)[1])
    must(not absence_record_ok('一年级下册', None)[0], '坏例19j：没有登记记录也被当成查过了')
    must(not absence_record_ok('一年级下册', dict(good19, volume='二年级下册'))[0], '坏例19k：登记记录的册次与仓内不一致却被放行')
    must(not absence_record_ok('一年级下册', {k: v for k, v in good19.items() if k != 'sources'})[0],
         '坏例19l：没写查过哪几页的登记记录被放行')
    n19m = absence_note('一年级下册', 0, False, True, good19)
    must('查过的地方' in n19m and '八页园地逐页读过' in n19m,
         '坏例19m：登记簿写了查了什么，note 里却没带上：%s' % n19m)

    # 坏例20：课文目录里同名的是另一篇，同一册的语文园地却收了我们这一篇——证据不许被吞掉
    fake_g20 = {'五年级下册': [('凉州词', '凉州词', '语文园地四', 'u5d')],
                '四年级上册': [('凉州词', '凉州词', '课文 21', 'u4a')]}
    ga20 = {('五年级下册', '凉州词'): ['[唐代] 王之涣'], ('四年级上册', '凉州词'): ['[唐代] 王翰']}
    got20 = collision_garden_note({'title': '凉州词', 'author': '王之涣'}, fake_g20, ga20, '五年级下册')
    must(got20 and got20[0] == '五年级下册', '坏例20：同一册园地收了这一篇，碰撞分支却没把证据说出来：%s' % (got20,))
    must(got20 and got20[2] == '语文园地四', '坏例20a：园地栏目没带出来，读者不知道在哪一栏：%s' % (got20,))
    # 坏例20g：园地表里写了具体栏目（词句段运用 / 日积月累），note 必须用那一栏，不许糊成「语文园地」
    got20g = collision_garden_note({'title': '凉州词', 'author': '王之涣'}, fake_g20, ga20, '五年级下册',
                                   {('五年级下册', '凉州词'): '语文园地四·词句段运用'})
    must(got20g and got20g[2] == '语文园地四·词句段运用', '坏例20g：栏目写在园地表里却没被带出来：%s' % (got20g,))
    # 坏例20b：园地那篇作者对不上（王翰 vs 王之涣）——不许当成「我们这篇也收了」
    must(collision_garden_note({'title': '凉州词', 'author': '王之涣'}, fake_g20, ga20, '四年级上册') is None,
         '坏例20b：那一册园地写的是王翰的凉州词，也被算成王之涣这一篇')
    # 坏例20c：园地在别的册——不算「同一册收了」
    must(collision_garden_note({'title': '凉州词', 'author': '王之涣'}, {'四年级上册': [('凉州词', '凉州词', '语文园地四', 'u4a')]},
                               {('四年级上册', '凉州词'): ['[唐代] 王之涣']}, '五年级下册') is None,
         '坏例20c：别的册的园地证据被当成同一册收了')
    # 坏例20d：园地页没写作者——不许猜是谁的
    must(collision_garden_note({'title': '凉州词', 'author': '王之涣'}, fake_g20, {}, '五年级下册') is None,
         '坏例20d：园地表没写作者也被当成对上了')
    # 坏例20e：作者写法带朝代前缀，比对不许被前缀绊倒
    must(garden_author_match({'author': '王之涣'}, '[唐代] 王之涣'), '坏例20e：朝代前缀没剥掉，同一位作者被判成两个人')
    must(not garden_author_match({'author': '王之涣'}, ''), '坏例20f：空作者也被当成对上')

    print('[ok] check-textbook --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


def main():
    refresh = '--refresh' in sys.argv
    stage = None
    if '--stage' in sys.argv:
        stage = sys.argv[sys.argv.index('--stage') + 1]
    limit = 0
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    poems = V.load_poems()
    if stage:
        poems = [p for p in poems if p.get('stage') == stage]
    ids = None
    if '--ids' in sys.argv:
        ids = set(sys.argv[sys.argv.index('--ids') + 1].split(','))
    if ids:
        poems = [p for p in poems if p['id'] in ids]
    if limit:
        poems = poems[:limit]

    indexes = {}
    results = []
    garden = load_garden()
    gauthors = garden_authors()
    gsections = garden_sections()
    garden_rules = load_garden_rules()
    coverage = load_coverage()
    blind = garden_blind()
    absence_records = load_absence_checks()
    # 「课标篇目」还是「教材拓展」：口径在 validate.py 的课标表里，不在这里另立一份。
    _syllabus, extra_titles = V.parse_syllabus(V.SYLLABUS)
    extra_ids = {p['id'] for p in poems if V.canon_title(p['title']) in extra_titles}
    if garden is None:
        print('!! 没有 data/textbook-garden.json：语文园地那一档没跑（先跑 tools/build-textbook-garden.py）')
    problems = []
    for p in poems:
        vol = (p.get('volume') or '').replace('课外诵读', '').strip()
        entry = {'id': p['id'], 'title': p['title'], 'author': p.get('author'),
                 'stage': p.get('stage'), 'volume': p.get('volume')}
        if p.get('volume') == NO_TEXTBOOK_VOLUME:
            entry.update(status='no-textbook',
                         note='课标指定选修篇目，统编教材课本未收（不是错误）')
            results.append(entry)
            print('[%d/%d] -- %s：教材不收（选修指定）' % (len(results), len(poems), p['title']))
            continue
        path = VOLUMES.get(vol)
        if not path:
            entry.update(status='unknown-volume', note='册次对不上教材目录：%s' % p.get('volume'))
            results.append(entry)
            print('[%d/%d] !! %s（%s）册次对不上' % (len(results), len(poems), p['title'], p.get('volume')))
            continue
        if path not in indexes:
            indexes[path] = volume_index(path, refresh)
        lessons = indexes[path]
        name, url = match_lesson(p, lessons)
        found_vol = vol
        if not url:
            # 仓内册次写错，和教材里真没有这篇，长得一模一样。必须分开：
            # 在同学段别的册里找一遍，找到就是「册次写错」，找不到才是「教材里没有」。
            for other_vol, other_path in VOLUMES.items():
                if same_stage(other_vol, vol) and other_path != path:
                    if other_path not in indexes:
                        indexes[other_path] = volume_index(other_path, refresh)
                    name, url = match_lesson(p, indexes[other_path])
                    if url:
                        found_vol = other_vol
                        break
        if not url:
            # 三档必须分开，混在一起就会把「教材收了」说成「教材没有」：
            #   覆盖表 —— 课标篇名与教材篇名不同、教材确实收了（表里每一条都要能在目录里找到）；
            #   园地表 —— 课文目录里没有，但同一册的语文园地页面上有（与目录页同源，只算一条来源）；
            #   都没有 —— 才是真的没找到。
            cov = coverage.get(p['id'])
            if cov and len(cov.get('sources') or []) < 2:
                problems.append('%s 覆盖表里没写满两条独立来源——只有镜像一条来源的不许判成教材收了' % p['id'])
                cov = None
            if cov:
                lessons_ok = []
                for l in cov.get('lessons', []):
                    lpath = VOLUMES.get(l.get('volume') or '')
                    if not lpath:
                        problems.append('%s 覆盖表里的册次对不上目录：%s' % (p['id'], l.get('volume')))
                        continue
                    if lpath not in indexes:
                        indexes[lpath] = volume_index(lpath, refresh)
                    hit = find_lesson(l.get('title'), indexes[lpath])
                    if not hit[1] and l.get('indexTitle'):
                        # 镜像目录把字写错了（「已亥杂诗」）：按它写错的样子去找，找得到才认，
                        # 并在 note 里写明是镜像的错字——仓内篇名不许跟着错。
                        hit = find_lesson(l.get('indexTitle'), indexes[lpath])
                    if not hit[1]:
                        problems.append('%s 覆盖表说教材收了「%s」（%s），但目录里找不到这一课' % (
                            p['id'], l.get('title'), l.get('volume')))
                        continue
                    lessons_ok.append({'volume': l['volume'], 'lesson': l.get('lesson') or '',
                                       'title': l.get('title'), 'url': hit[1]})
                if lessons_ok:
                    entry.update(status=('coverage-partial' if cov.get('partial') else 'coverage-override'),
                                 lessons=lessons_ok,
                                 note=cov.get('note') or '课标篇名与教材篇名不同，教材收了')
                    results.append(entry)
                    print('[%d/%d] == %s：教材收了，收在别的课里（%s）' % (
                        len(results), len(poems), p['title'],
                        ' / '.join('%s《%s》' % (l['volume'], l['title']) for l in lessons_ok)))
                    continue
            hits = list(garden_match(p, garden)) if garden else []
            same = [h for h in hits if h[0] == vol]
            rule = garden_rules.get(p['id'])
            if rule:
                # 进裁定表就是把「镜像里看到了」升格成「教材收了」：册次、来源两条、镜像最多一条，
                # 三样都要在这一步复核——表与园地表或仓内打脸就是数据错了，不许降级糊过去。
                srcs = [x for x in (rule.get('sources') or []) if x]
                state, why = garden_ruling_status(vol, rule, bool(same))
                if state != 'ok':
                    problems.append('%s：%s' % (p['id'], why))
                    entry.update(status='garden-ruling-broken', note=why)
                    results.append(entry)
                    print('[%d/%d] !! %s（%s）园地裁定表不成立：%s' % (len(results), len(poems), p['title'], vol, why))
                    continue
                entry.update(status='garden-attested', volume_url=BASE + path,
                             gardenVolume=same[0][0], gardenTitle=same[0][1],
                             garden=same[0][2], url=same[0][3],
                             section=rule.get('section') or '语文园地', sources=len(srcs),
                             note=(rule.get('note') or '') + '（%d 条来源，其中镜像最多一条）' % len(srcs))
                results.append(entry)
                print('[%d/%d] == %s（%s）语文园地收了（%s，%d 条来源）' % (
                    len(results), len(poems), p['title'], vol, rule.get('section') or '语文园地', len(srcs)))
                continue
            if same:
                entry.update(status='garden-mirror-only', volume_url=BASE + path,
                             gardenVolume=same[0][0], gardenTitle=same[0][1],
                             garden=same[0][2], url=same[0][3],
                             note='课文目录里没有这一课，但同一册的语文园地页面上出现了这一篇；'
                                  '园地页与目录页同源（同一镜像），只算一条来源——'
                                  '登记为「镜像收了、第二条独立来源没核到」，不判成教材收了')
                results.append(entry)
                print('[%d/%d] ~~ %s（%s）课文目录没有，语文园地里有（一条来源）' % (
                    len(results), len(poems), p['title'], p.get('volume')))
                continue
            if hits:
                entry.update(status='garden-other-volume', volume_url=BASE + path,
                             gardenVolume=hits[0][0], gardenTitle=hits[0][1],
                             garden=hits[0][2], url=hits[0][3],
                             note='同学段所有册的课文目录里都没有；语文园地里有这一篇，但在「%s」——册次要单独查' % hits[0][0])
                results.append(entry)
                print('[%d/%d] ~~ %s（%s）园地里有，但在别的册（%s）' % (
                    len(results), len(poems), p['title'], p.get('volume'), hits[0][0]))
                continue
            rec = absence_records.get(p['id'])
            ok_rec, why_rec = absence_record_ok(vol, rec)
            if rec and not ok_rec:
                problems.append('%s：absence-checks.json 里这条不成立：%s' % (p['id'], why_rec))
            entry.update(status='lesson-not-found', volume_url=BASE + path,
                         note=absence_note(vol, blind.get(vol, 0),
                                           p['id'] not in extra_ids, vol in blind,
                                            rec if ok_rec else None, p.get('stage') or ''))
            results.append(entry)
            print('[%d/%d] !! %s（%s）教材里没有这篇' % (len(results), len(poems), p['title'], p.get('volume')))
            continue
        if found_vol != vol:
            # 册次对不上有两种，长得一模一样：真是我们这一篇的册次写错了，还是教材那边同名的
            # 是另一首诗。只看篇名分不出来，必须拿正文比：比得上才是同一篇（册次写错，要改册次）；
            # 一句都对不上就是另一篇——那一档仓里已有名字（mismatch），不许混进「册次写错」。
            # 教材正文没取到时不许猜：那一条照旧判册次对不上，但 note 里写明没核。
            paras = lesson_text(url, refresh)
            hit, total, skipped, miss = compare(p, paras) if paras else (0, 0, 0, [])
            status, why = cross_volume_status(paras, hit, total)
            note = ('仓内写「%s」，教材在「%s」有同名课文：%s' % (vol, found_vol, why)) if status == 'volume-mismatch' \
                   else ('教材在「%s」有同名课文：%s，不是册次写错' % (found_vol, why))
            entry.update(status=status, lesson=name, url=url, hit=hit, total=total,
                         declaredVolume=p.get('volume'), textbookVolume=found_vol, note=note)
            # 目录里同名的是另一篇，不等于我们这篇教材没收：同一册的语文园地可能收了它。
            # 以前这里直接判「教材收的是同名另一篇」就 continue，园地证据根本没机会说话——
            # 王之涣《凉州词》就是这么被说成「教材那边是另一篇」的，而统编五年级下册
            # 《语文园地四》词句段运用里收的正是王之涣这一首（作者对得上）。
            ggot = collision_garden_note(p, garden, gauthors, vol, gsections)
            if status == 'mismatch' and ggot:
                entry.update(gardenVolume=ggot[0], gardenTitle=ggot[1], garden=ggot[2], gardenUrl=ggot[3])
                note += ('；但同一册的语文园地里有这一篇（作者对得上）：%s《%s》·%s——'
                         '园地页与目录页同源（同一镜像），只算一条来源' % (ggot[0], ggot[1], ggot[2]))
            results.append(entry)
            print('[%d/%d] !! %s：教材在「%s」有同名课文（%s）' % (
                len(results), len(poems), p['title'], found_vol, note))
            continue
        paras = lesson_text(url, refresh)
        hit, total, skipped, miss = compare(p, paras)
        status = 'match' if (total and hit == total) else ('partial' if hit else 'mismatch')
        entry.update(status=status, lesson=name, url=url, hit=hit, total=total,
                     skippedShort=skipped,
                     textbookParas=len(paras), miss=miss)
        results.append(entry)
        for mm in miss:
            d = mm['diff'] or [{'ours': norm(mm['line']), 'textbook': None}]
            for piece in d[:3]:
                print('      [%s] 仓内「%s」 → 教材「%s」' % (
                    mm['kind'], piece['ours'],
                    piece['textbook'] if piece['textbook'] else '找不到对应'))
        flag = 'ok' if status == 'match' else '!!'
        print('[%d/%d] %s %s（%s） %d/%d 句对上  %s' % (
            len(results), len(poems), flag, p['title'], p.get('volume'), hit, total, name))

    stats = {}
    for r in results:
        stats[r['status']] = stats.get(r['status'], 0) + 1
    OUT.write_text(json.dumps({'generated': time.strftime('%Y-%m-%d'),
                               'source': BASE,
                               'stats': stats, 'results': results, 'problems': problems},
                              ensure_ascii=False, indent=2), encoding='utf-8')
    print('')
    print('教材核对：%s' % ' / '.join('%s %d' % (k, v) for k, v in sorted(stats.items())))
    print('已写 data/textbook-attestations.json')
    if problems:
        for x in problems[:20]:
            print('  !! ' + x)
        print('     共 %d 条问题（覆盖表里写了却找不到这一课，就是编的）' % len(problems))
        return 1
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
