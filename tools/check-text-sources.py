#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正文出处交叉核对：仓内每一篇的原文，能不能在独立来源里找到。

为什么必须有这一步：仓里出现过**编造的正文**——《虽有嘉肴》的「是故无冥明之察」
「善哉，答是」四句根本不是《礼记》原文，注释译文赏析还围着它编了一整套。
现有校验器查格式、查字数、查版权，唯独不查「这段话是不是真的」。

做法：
  1. 维基文库（zh.wikisource.org）检索接口找篇目页；
  2. 挑页：优先标题含篇名、含作者的页；跳过消歧义页、重定向页、
     以及「某某判决书」「某某有限公司」这类同名不同物的页；
  3. 取页面正文，繁体转简体（OpenCC TSCharacters 字表，Apache-2.0）；
  4. 剥掉页面里的「一作某」夹注（顺手记下来，那正是异文线索）；
  5. 另取一份 wikitext，解析 `{{另|甲|乙}}` 夹注——维基文库的异文是结构化的，
     渲染后异文藏在鼠标悬停才显示的 span 里，只读渲染文本等于把异文全丢掉。
  5. 把仓内每一句（剥标点）拿去页面里找，记下对上的句数。

这一步不替你改正文，它只把「对不上」的篇目摊出来。
用法：
  python tools/check-text-sources.py            # 全仓
  python tools/check-text-sources.py --limit 12 # 先试一小批
  python tools/check-text-sources.py --stage 高中
"""
import difflib
import json
import re
import sys
import time
import hashlib
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import match as M  # noqa: E402
import validate as V  # noqa: E402

API = 'https://zh.wikisource.org/w/api.php'
UA = {'User-Agent': 'diuci-content-check/1.0 (contact: hi@diuci.com)'}
OUT = ROOT / 'data' / 'text-sources.json'
T2S = ROOT / 'data' / 'opencc' / 'TSCharacters.txt'
# 来源页本地缓存（data/page-cache/，已 gitignore）。
# 为什么要有：一轮全仓核对 5 秒/篇，几乎全花在取页上；改比对口径这种重跑本来不该再联网。
# 有了缓存，来源站不可达时也能把「同一批页、不同比法」重跑完——缓存只存公有领域的原文。
CACHE = ROOT / 'data' / 'page-cache'
REFRESH_PAGES = '--refresh-pages' in sys.argv
CACHE_HITS = [0, 0]  # [命中, 取页]

# 同名不同物的页面特征：维基文库也收现代文书，标题撞车的不在少数。
JUNK_HINTS = ('判决书', '纠纷', '有限公司', '通知', '人民政府', '方案', '集团',
              '中学', '大学', '酒店', '医院', '银行', '公司', '学校', '车站',
              '镇', '县', '市', '村', '社区', '协会', '博物馆', '遗址')
# 页面里的夹注：「城春一作荒草木深」——不剥掉就会把真句子判成对不上。
VARIANT_NOTE = re.compile(r'(?:一本作|一作|又作)[\u4e00-\u9fff]{1,4}')
JUNK_NOTE = re.compile(r'作[饭羹品曲者集者]')  # 只登记，不参与判定


def http_json(params):
    """取一次 JSON。被拒连接 / 超时就退避重试。

    为什么必须有：维基文库被连着问几百次会直接拒连接（WinError 10061）。
    以前一次失败就记「找不到来源页」——那是把「我们问得太快」写成「这篇没有来源」，
    台账上 20 篇凭空变成没来源，比漏掉更糟。"""
    url = API + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except Exception as exc:
            last = exc
            time.sleep(5 * (attempt + 1))
    raise last


def load_t2s():
    """繁体 → 简体 单字表。只用来比对，不用来改写仓内正文。"""
    if not T2S.exists():
        raise SystemExit('缺 %s：先跑一次本脚本，它会自动取 OpenCC 字表' % T2S)
    table = {}
    for line in T2S.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            table[parts[0]] = parts[1]
    return table


def to_simplified(text, table):
    return ''.join(table.get(ch, ch) for ch in text)


def ensure_dict():
    if T2S.exists():
        return
    print('先取 OpenCC 字表（Apache-2.0）…')
    urls = ['https://cdn.jsdelivr.net/gh/BYVoid/OpenCC@master/data/dictionary/TSCharacters.txt',
            'https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TSCharacters.txt']
    blob, last = None, None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                blob = r.read().decode('utf-8', 'replace')
            break
        except Exception as exc:
            last = exc
    if blob is None:
        raise SystemExit('取不到 OpenCC 字表：%s' % last)
    T2S.parent.mkdir(parents=True, exist_ok=True)
    T2S.write_text(blob, encoding='utf-8')
    print('  已存 %s（%d 字节）' % (T2S, len(blob)))


def _cache_file(title):
    return CACHE / (re.sub(r'[^0-9A-Za-z\u4e00-\u9fff_-]', '_', title)[:100]
                    + '-' + hashlib.md5(title.encode('utf-8')).hexdigest()[:12] + '.json')


def _cache_get(title, kind):
    """缓存里已经有这一项就直接用；没有返回 None。缓存坏掉就当没有，不许把核对带崩。"""
    if REFRESH_PAGES:
        return None
    try:
        rec = json.loads(_cache_file(title).read_text(encoding='utf-8'))
    except Exception:
        return None
    val = rec.get(kind)
    if val is None:
        return None
    CACHE_HITS[0] += 1
    return rec


def _cache_put(title, rec):
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        _cache_file(title).write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass


def strip_page_furniture(html):
    """页面上的家具不许留在正文里：样式、脚本、注码、编辑链接。"""
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    # 注码。MediaWiki 现在渲染成 <sup id="cite_ref-1" class="reference">[1]</sup>。
    # 先前这条只认 class 里带大写 Reference 的，小写 reference 整个漏过去：
    # 江南逢李龟年 那一页被剥成「岐王1宅里寻常见」，全仓 13 条记录的「页里最像的一段」带着注码数字，
    # 它从「全对上」掉成「1/2 句对上」。别人改了页面 markup，台账的数就跟着抖，而且没人报错。
    html = re.sub(r'<sup[^>]*class="[^"]*(?:reference|noprint)[^"]*"[^>]*>.*?</sup>', '', html, flags=re.S | re.I)
    html = re.sub(r'<sup[^>]*id="cite[^"]*"[^>]*>.*?</sup>', '', html, flags=re.S | re.I)
    html = re.sub(r'<span[^>]*class="[^"]*(?:mw-editsection|noprint)[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)
    return html



def page_text(title):
    hit = _cache_get(title, 'text')
    if hit:
        return hit.get('title', title), hit['text']
    CACHE_HITS[1] += 1
    d = http_json({'action': 'parse', 'page': title, 'prop': 'text',
                   'format': 'json', 'redirects': 1})
    parse = d.get('parse') or {}
    html = parse.get('text', {}).get('*', '')
    html = strip_page_furniture(html)
    txt = re.sub(r'<[^>]+>', ' ', html)
    txt = re.sub(r'&[a-z]+;', ' ', txt)
    # 数字实体（&#91;13&#93; 是注码 [13]）先前没剥：谏逐客书那一页的注码夹在正文里，
    # 句子被「&91;13&93;」打断，两句被判成页里没找到——那是页里的注码，不是版本差异。
    txt = re.sub(r'&#\d+;', ' ', txt)
    real = parse.get('title', title)
    old = {}
    try:
        old = json.loads(_cache_file(real).read_text(encoding='utf-8'))
    except Exception:
        old = {}
    old.update({'title': real, 'text': txt, 'fetched': time.strftime('%Y-%m-%d')})
    _cache_put(real, old)
    return real, txt


def page_wikitext(title):
    hit = _cache_get(title, 'wikitext')
    if hit:
        return hit.get('title', title), hit['wikitext']
    CACHE_HITS[1] += 1
    d = http_json({'action': 'parse', 'page': title, 'prop': 'wikitext',
                   'format': 'json', 'redirects': 1})
    parse = d.get('parse') or {}
    real = parse.get('title', title)
    wt = parse.get('wikitext', {}).get('*', '')
    old = {}
    try:
        old = json.loads(_cache_file(real).read_text(encoding='utf-8'))
    except Exception:
        old = {}
    old.update({'title': real, 'wikitext': wt, 'fetched': time.strftime('%Y-%m-%d')})
    _cache_put(real, old)
    return real, wt


# 维基文库的异文夹注：{{另|三|吳}} = 正文作「三」，另一本作「吳」。
# 渲染后它变成一个带悬停提示的 span，剥标签只剩主文——所以必须读 wikitext。
ALT_TEMPLATE = re.compile(r'\{\{\s*另\s*\|([^|{}]+)\|([^{}]+?)\}\}')


def strip_markup(text):
    """剥模板、链接、标签、引号空白，只留正文用来看上下文。"""
    for _ in range(4):
        new = re.sub(r'\{\{[^{}]*\}\}', '', text)
        if new == text:
            break
        text = new
    text = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'[\s\x27\u201c\u201d\u2018\u2019]+', '', text)


def alt_variants(wiki, table, page):
    """从 wikitext 里抽 {{另|甲|乙}} 夹注，繁→简，带上下文。

    做法：先把每个夹注换成一个纯字符哨兵（\x00编号\x00），再整页剥 markup，
    最后在干净文本里找哨兵取上下文。两侧直接开窗会把标签从中间切断，
    留下「oem>:」「edition=yes}}」这种残渣；用 find(本字) 定位又会撞到
    同一个字在别处的出现。哨兵两头都不踩。
    """
    marks = []

    def repl(m):
        a = to_simplified(m.group(1).strip(), table)
        b = to_simplified(re.sub(r'[、,，].*$', '', m.group(2).strip()), table)
        idx = len(marks)
        marks.append((a, b))
        return '\x00%d\x00' % idx

    stripped = strip_markup(ALT_TEMPLATE.sub(repl, wiki))
    out, seen = [], set()
    for idx, (a, b) in enumerate(marks):
        if not a or not b or a == b:
            continue
        if len(a) > 6 or len(b) > 6:
            continue
        if not re.match(r'^[\u4e00-\u9fff]+$', a) or not re.match(r'^[\u4e00-\u9fff]+$', b):
            continue
        token = '\x00%d\x00' % idx
        pos = stripped.find(token)
        ctx = stripped[max(0, pos - 16):pos + 30] if pos >= 0 else ''
        # 哨兵换回正文用字；窗口里别的夹注也换成它们各自的本字，读起来才是连贯的一句
        ctx = re.sub(r'\x00(\d+)\x00', lambda mm: marks[int(mm.group(1))][0], ctx)
        ctx = ctx.replace('\x00', '')   # 窗口边缘可能把哨兵切成半截
        key = (a, b, ctx)
        if key in seen:
            continue
        seen.add(key)
        out.append({'ours': a, 'other': b, 'context': ctx, 'page': page})
    return out


def search_pages(query):
    d = http_json({'action': 'query', 'list': 'search', 'srsearch': query,
                   'srlimit': 6, 'format': 'json'})
    return [x['title'] for x in d.get('query', {}).get('search', [])]


# ---------------------------------------------------------------- 强制页名
OVERRIDES_PATH = ROOT / 'data' / 'source-overrides.json'


def override_problems(overrides):
    """「维基文库没有正文页」这个出口必须带着证据用。

    为什么必须有：没有这道约束，「没有来源页」就会变成偷懒的出口——
    写一行 no_page 就能让一篇永远不用核。所以它必须交代：搜过哪些句子、为什么判定没有。
    """
    problems = []
    for key in sorted(overrides):
        ov = overrides[key] or {}
        if ov.get('no_page'):
            if ov.get('pages'):
                problems.append('%s：既说「没有正文页」又给了页名，二者只能留一个' % key)
            if not (ov.get('note') or '').strip():
                problems.append('%s：说「没有正文页」却没写为什么' % key)
            if not (ov.get('searched') or []):
                problems.append('%s：说「没有正文页」却没写下搜过哪些句子——下次没人能重走这条路' % key)
        elif not (ov.get('pages') or []):
            problems.append('%s：既没给页名，也没说「没有正文页」' % key)
    return problems


def load_overrides():
    if not OVERRIDES_PATH.exists():
        return {}
    return json.loads(OVERRIDES_PATH.read_text(encoding='utf-8')).get('overrides', {})

def page_drift(prev_results, new_results):
    """同一篇的来源页换了地方，必须当场说出来。

    为什么：来源页是按检索排序挑的，检索每次排法不完全一样。今天挑中 A 页（两句全对上），
    明天挑中 B 页（一句对不上），台账的数就跟着抖，写进文档的数字永远对不上产物。
    要稳住就在 data/source-overrides.json 钉住——钉住是决定，不是遮掩。"""
    out = []
    old = {r['id']: r.get('page') for r in prev_results if r.get('id')}
    for r in new_results:
        if not r.get('id'):
            continue
        before, now = old.get(r['id']), r.get('page')
        if before and now and before != now:
            out.append((r['id'], before, now))
    return out


# 维基文库的页面家具：作者行、「收录于」指针、「姊妹计划」、公有领域脚注、「编辑」链接、Wikidata 的 true/false。
# 它们不是正文。留在文本里会污染「页里最像的那一段」：种树郭橐驼传「传其事以为官戒也」的相似度
# 就是被页尾那段公有领域声明压到 0.538（阈值 0.55），从「页里写作别的样子」掉进「页里没找到」。
BOILERPLATE = (
    r'姊妹计划[:：]?(?:数据项|百科图册|图册|分类)?',
    r'本作品收录于',
    r'此[一-鿿]{0,6}作品在全世界都属于公有领域.{0,90}',
    # 「此」必须写死：先前写成可选，正则从左边贪吃，把「…传其事以为官戒」里的「官戒」也吃了进去
    # ——护栏吃掉正文，比不剥更糟。「姊妹计划」后面只认那几个固定标签，不用 \S 贪吃：
    # 页面上「姊妹计划:数据项」后面紧跟的就是正文，贪吃会把正文一起剥掉。
    r'本作品在全世界都属于公有领域.{0,90}',
    r'Public\s*domain',
    r'\b(?:true|false)\b',
    r'编辑',
)

def clean(text, table):
    """繁→简、剥标点空白。返回 (清洗后文本, 夹注列表)。

    夹注（「城春一作荒草木深」）只登记、不剥掉：剥掉会把句子切碎，
    反而让真句子判成对不上。打断交给 line_in 的「按顺序出现在一个够短的窗口里」那一档去认。"""
    # 页里的注码是 HTML 实体（&#91;13&#93; 就是 [13]）。先前只剥字母实体、不剥数字实体，
    # 而下面那一步又把 # 剥掉——剩下「&91;13&93;」卡在正文里，把句子打断：
    # 谏逐客书两句在页里明写着，却被判成「页里没找到」。实体是排版噪声，不是版本差异。
    # 取页那一步也补了同样的剥法；这里再剥一次，是因为缓存里的页文本是旧代码写出来的。
    text = re.sub(r'&#?[a-zA-Z0-9]+;', ' ', text)
    text = to_simplified(text, table)
    for pat in BOILERPLATE:
        text = re.sub(pat, ' ', text)
    notes = VARIANT_NOTE.findall(text)
    for ch in M.PUNCT + '\u3000\xa0↑↓*#':
        text = text.replace(ch, '')
    return re.sub(r'\s', '', text), notes


def single_table(table):
    """OpenCC 的歧义条目一个繁体字给两个候选（「藉→藉 借」「鍾→钟 锺」「乾→干 乾」「彷→彷 仿」）。
    比对时两个候选都要认；引用来源页时不许把两个候选一起写出来——页里只写了一个字。
    这里把歧义条目改成「照抄页里那个字」：引用不造字。"""
    out = {}
    for k, v in table.items():
        if ' ' in v:
            out[k] = k  # 歧义条目：照抄页里那个字
        elif all('\u4e00' <= ch <= '\u9fff' for ch in v):
            out[k] = v
        else:
            # 表把页里的字换成扩展区残迹（「巘→𪩘」）：页面上看不到这个字，是表自己的毛病，引用不许照搬
            out[k] = k
    return out


def clean_quote(text, table):
    """给「页里到底怎么写的」用的那份文本：剥 markup、剥标点，但不把歧义字换成另一个候选。
    比对用 clean()（两个候选都认，宁可宽），引用用这一份（页里写的是什么就是什么）。"""
    return clean(text, single_table(table))[0]


def strip_only(text):
    """页里原样：剥实体、剥标签、剥模板、剥标点，一个字都不换。

    连「照抄页里那个字」都嫌多：表里「巘→𪩘」这种条目会把页里的字换成页里没写的字。
    要问「页里到底写了哪些字」，只能用这一份。"""
    text = re.sub(r'&#?[a-zA-Z0-9]+;', ' ', text)
    for _ in range(4):
        new = re.sub(r'\{\{[^{}]*\}\}', ' ', text)
        if new == text:
            break
        text = new
    text = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    for ch in M.PUNCT + '\u3000\xa0↑↓*#':
        text = text.replace(ch, '')
    return re.sub(r'\s', '', text)


# 同一个字的另一个写法（不是繁简，是异体）：维基文库写作「一瓢飮」「飮水」「于於」，
# 教材与仓里写作「一瓢饮」「饮水」「于」。比对时必须认这两个是同一个字，否则整句判成找不到。
# 下面每一对都是这一轮出处核对里在来源页上亲眼看到的写法，不是猜的：
#   前赤壁賦「逝者如斯而未甞往也」、黄冈竹楼记「槩」、荀子/勸學篇「髙」「靑」、
#   論語/季氏第十六「顚」、過秦論「衞」、報任少卿書「戹」、北西廂記「吿」、諫逐客書「彊」。
# 故意不收的是真异文（不是同一个字的另一种写法）：渡/度、蔽/敝、孰/熟、泠泠/冷冷、
#   岐/歧、欤/与、已/己、锤/槌——那些要留在「没对上」里，作为异文登记给读者看。
VARIANT_GLYPHS = {'飮': '饮', '於': '于', '说': '说', '説': '说',
                  '甞': '尝', '槩': '概', '髙': '高', '靑': '青', '顚': '颠',
                  '衞': '卫', '戹': '厄', '吿': '告',
                  # 第二批：同样是在来源页上亲眼看到的写法，每一对都过了「两边读音必须相同」那条自检：
                  # 蘭亭集序「山隂」「懐」「舎」、老子翼「乆」、文章辨體彚選「愼」、過秦論「鬬」、滕王閣序「𬴂」。
                  '隂': '阴', '懐': '怀', '乆': '久', '愼': '慎', '鬬': '斗', '舎': '舍', '𬴂': '騑',
                  # 第三批：誠齋集 (四庫全書本)/卷011「穉子弄氷」那一行上亲眼看到的写法。
                  # 没收的：彩/綵/䌽——那一篇页里写作「彩䌽丝」，是页自己的异体夹写，交给按顺序那一档去认，不进这张表。
                  '穉': '稚', '氷': '冰',
                  # 第四批：送杜少府之任蜀州「海内存知己，天涯若比邻」。四庫全書系页面（古今詩刪 卷14）
                  # 写作「天涯若比隣」——「隣」(U+96A3) 是「邻」的异体字形，OpenCC 的 TSCharacters 里只有
                  # 「鄰→邻」没有这一条，不补就会把这一句判成没对上。Unihan kMandarin 两边都读 lín。
                  '隣': '邻',
                  # 第五批：滕王閣序（四部叢刊本、全唐文/卷0181、文章辨體彚選 三处都）写作「鴈阵惊寒」。
                   '鴈': '雁',
                   # 第六批：曹刿论战 的来源页写作「小惠未徧，民弗从也」。Unihan kMandarin 两边都读 biàn，
                   # kDefinition 都是「everywhere, all over」——同一个字的另一种写法，不是异文。
                   '徧': '遍',
                   # 第七批：撤掉「head/tail」那一档之后全仓重跑，露出 63 句先前被那一档蒙过去的句子。
                   # 其中这些对是同一个字的另一种写法（每一对都在来源页上亲眼看到，Unihan kMandarin 两边同音，
                   # kSemanticVariant 互相指认）：筯/箸、煖/暖、畧/略、譔/撰、潄/漱、粧/妆、瘖/喑、涙/泪、
                   # 怳/恍、罇/樽、簷/檐、踈/疏、疎/疏。按口径「异体字不算文字分歧」，它们不进「异文」。
                   '筯': '箸', '煖': '暖', '畧': '略', '譔': '撰', '潄': '漱', '粧': '妆',
                   '瘖': '喑', '涙': '泪', '怳': '恍', '罇': '樽', '簷': '檐', '踈': '疏', '疎': '疏',
                   # 第八批：补完第七批之后剩下的「没对上」里，这几对也是同一个字的另一种写法（都在页上亲眼看到，
                   # Unihan kMandarin 同音）：僊／仙（赤壁赋「羽化而登僊」）、扵／于（兰亭集序「不能喻之扵怀」）、
                   # 歩／步（劝学「不能十歩」）、飜／翻（六月二十七日望湖楼醉书「黑云飜墨」）、
                   # 闗／关（老子八章「善闭无闗楗」）。先前把 飜／翻 记成「异文线索」不准确：它不是版本分歧。
                   '僊': '仙', '扵': '于', '歩': '步', '飜': '翻', '闗': '关'}
                   # 露出来的其余那些是真异文，留在「没对上」里给读者看：暮/慕、火伴/夥伴、甚/盛、围/圈、
                   # 弈/奕、贞良/贞亮、淡/澹、朱/珠、孰/熟、辨/辩、柽/怪、餐/飧、泛/汛、喑/瘖以外的瘖/喑已收、
                   # 浑不怕/皆不顾、阁/搁、无赖/亡赖、輮/𫐐（Unihan 给 𫐐 的读音是 ní，不同音，不收）、
                   # 颍/颖、樗/摴、岗/冈、畋/田、閒/间（Unihan 读 xián vs jiān，不同音，不收）、
                   # 昭/韶、穆/缪、彊/强、震/振、惧/想、帐/怅、寄/奇、景以/景而、皆/混。
# 试过但没收的（不是同一个字的另一种写法，是真异文，留在「没对上」里给读者看）：
#   阁/合、己/已、又/自、山/峰、弈/奕、爱/映、至/宿、讥/议、鸣/声、纕/𬙋、𫐐/𫐓、
#   蔽/敝、那/哪、渡/度、歧/岐、欤/与——其中读音不同的那几对直接被自检拦下。
# 「彊→强」一度加进来过，被上面那条「两边读音必须相同」的自检拦下：
# Unihan kMandarin 里 彊 读 jiàng、强 读 qiáng，不能断定是同一个字的另一种写法。
# 所以 谏逐客书 那一句留在「没对上」里，作为异文登记，不当成已核到。


VARIANT_READINGS = ROOT / 'data' / 'variant-readings.json'
UNIHAN_READINGS = ROOT / 'data' / 'unihan' / 'Unihan_Readings.txt'


def _unihan_kmandarin(need):
    out = {}
    with UNIHAN_READINGS.open(encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 3 and parts[1] == 'kMandarin':
                ch = chr(int(parts[0][2:], 16))
                if ch in need:
                    out[ch] = sorted(set(w.strip(' .') for w in parts[2].split()))
    return out


def _table_chars():
    need = set()
    for a, b in VARIANT_GLYPHS.items():
        need.add(a)
        need.add(b)
    return need


def export_variant_readings():
    """把字表里每个字的 Unihan kMandarin 抄成一份小快照（这份要入库）。

    为什么要抄：全量 Unihan 8MB 且已 gitignore，CI 里没有它，「两边读音必须相同」那条自检
    就在 CI 里跑不了——存在但跑不了的检查等同于没有检查。快照只覆盖字表里的字，几 KB。
    """
    if not UNIHAN_READINGS.exists():
        raise SystemExit('!! 缺 %s：先跑 python tools/gen-pinyin.py --fetch' % UNIHAN_READINGS)
    need = _table_chars()
    out = _unihan_kmandarin(need)
    missing = sorted(need - set(out))
    if missing:
        raise SystemExit('!! Unihan 里查不到这些字的 kMandarin：%s' % '、'.join(missing))
    VARIANT_READINGS.write_text(json.dumps({
        'note': ('data/variant-readings.json 是 check-text-sources.py 里 VARIANT_GLYPHS 那张字表所用字的 '
                 'Unihan kMandarin 读数快照，由 python tools/check-text-sources.py --export-variant-readings '
                 '生成，不许手改。它存在的唯一理由：CI 没有 8MB 的 Unihan，而「异体字表每一对必须读音相同」'
                 '这条自检必须在 CI 里跑。字表加了新字而这份没重生成，自检会当场报错。'),
        'generated': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%d'),
        'chars': len(out),
        'readings': out}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('[ok] 已写 %s（%d 个字）' % (VARIANT_READINGS, len(out)))
    return 0


def load_variant_readings():
    """字表所用字的读音：有全量 Unihan 就用它，没有就用入库那份快照。两条路都必须覆盖整张表。"""
    need = _table_chars()
    if UNIHAN_READINGS.exists():
        out = _unihan_kmandarin(need)
    elif VARIANT_READINGS.exists():
        rec = json.loads(VARIANT_READINGS.read_text(encoding='utf-8'))
        out = {k: list(v) for k, v in (rec.get('readings') or {}).items()}
    else:
        raise SystemExit('!! 既没有 %s 也没有 %s：跑 python tools/check-text-sources.py --export-variant-readings'
                         % (UNIHAN_READINGS, VARIANT_READINGS))
    missing = sorted(need - set(out))
    if missing:
        raise SystemExit('!! 字表加了新字（%s）而读数快照没重生成：跑 --export-variant-readings'
                         % '、'.join(missing))
    return {k: set(v) for k, v in out.items()}


def _nopunct(t):
    t = re.sub(r'[\W_]+', '', t or '', flags=re.UNICODE)
    return ''.join(VARIANT_GLYPHS.get(c, c) for c in t)


def line_in(line, txt):
    """一句在不在来源里。除了整句直接命中，还认「夹注打断」：
    维基文库常把异文夹在正文里（「城春一作荒草木深」），直接找整句会漏。"""
    if line in txt:
        return 'exact'
    # 有的页面正文一个标点都不带（论语各章就是「子曰学而时习之不亦说乎有朋自远方来…」），
    # 带标点的句子直接找必然找不到，head/tail 也会被标点本身打断。去标点再比一次：只比字，不比标点。
    sl, st = _nopunct(line), _nopunct(txt)
    if sl and sl in st:
        return 'unpunct'
    # 去标点之后仍然可能被夹注打断（「于於我如浮云」：别本的「於」夹在正文里）。
    # 再退一档：字必须按顺序出现在一个够短的窗口里。
    if len(sl) >= 6 and subseq_window(sl, st, slack=40):
        return 'unpunct-subseq'
    # 「head/tail 各三字落在窗口里」这一档已撤（2026-10-10）。撤它的理由当场抓到的：
    # 过松源晨炊漆公店 我们作「正入万山围子里一山放出一山拦」，来源页《宋元詩㑹》卷四十一作
    # 「正入万山圈子里一山放出一山拦」——句首「正入万」、句末「一山拦」都在窗口里，中间那个字完全不同，
    # 这一档照样判「对上了」，这一篇的出处核对因此记成 2/2 全对上。
    # 它也不是「夹注打断」的解药：夹注打断时整句的字必然按顺序出现在页里，上面 unpunct-subseq
    # （窗口 len+40）已经接住；head/tail 的窗口只有 len+16，比它更窄，却又不查中间的字——
    # 于是只有「整句在这段里不是子序列」的句子才会从这一档拿到命中。这一档能命中的，全是中间字对不上的句子。
    # 撤。夹注很长时（「孤城遥望玉一作「雁」门关」）仍由下面的 subseq 接：只认顺序，不认连续。
    # 再退一档：整句的字必须按顺序出现在一个够短的窗口里——只认顺序，不认连续。
    if len(sl) >= 6 and subseq_window(sl, st):
        return 'subseq'

    # 先前这里还退到最后一档：difflib 相似度 >= 0.82 就算「对上了」。这一档被撤了。
    # 撤它的理由不是「已经骗过了谁」，是它能凭空造出命中：只差一个字的两行相似度 0.9，
    # 一句页里根本没有的诗就会被算成「全对上」。这种出口留着，早晚会用到不该用的地方。
    # 撤完全仓重跑一遍：215 全对上 / 36 部分 / 0 都对不上 / 1 没有正文页，与撤之前逐字相同——
    # 也就是说这一轮没有哪一篇是靠相似度蒙过去的。当场数过，不是推断。
    # 顺带把起疑的那一篇查干净了：送杜少府之任蜀州 的来源页《全蜀藝文志 (四庫全書本)/卷20》
    # 当场取页、走同一套 clean 之后数过——页里作「杜少府之任蜀州 王勃 城阙辅三秦 风烟望五津
    # 与君离别意 同是宦游人 海内存知己 天涯若比邻 无为在岐路 儿女共沾巾」，四句全是 exact。
    # 我先前直接搜 wikitext 说「页里没有」是搜错了：wikitext 是繁体（城闕輔三秦），简体串当然找不到。
    # 差得少的句子照样进 miss 列表，nearest 会把页里最像的那行连同相似度一起写出来，给异文登记用——
    # 但它不再计入「对上」的分子。
    return None


def subseq_window(line, txt, slack=28):
    """句子的字必须按顺序出现在 txt 的一个窗口里（窗口最多 len(line)+slack）。

    维基文库把异文夹在正文中间，整句和 head/tail 都会被打断；只认顺序能救回一批，
    但窗口卡死在句子长度附近，不至于把整页当成命中。
    """
    L = len(line)
    if L < 6 or len(txt) < L:
        return False
    span = L + slack
    # 只在「句首那个字出现的地方」起窗口：整页逐位扫是 O(页长×句长)，
    # 四库全书那种十几万字的页跑不完。锚在首字上，句首被夹注打断的情况仍然能认（首字本身必须连续）。
    head = line[0]
    i = txt.find(head)
    while i >= 0:
        pos = i + 1
        ok = True
        for ch in line[1:]:
            pos = txt.find(ch, pos)
            if pos < 0 or pos - i > span:
                ok = False
                break
            pos += 1
        if ok:
            return True
        i = txt.find(head, i + 1)
    return False


def nearest(line, txt):
    """对不上的句子，找出来源里最接近的一段——这就是异文线索，不是噪声。"""
    # 比对用剥过标点的两边：仓里有些正文用 ASCII 引号，页里的正文一个标点都不带。
    # 拿带引号的原文去比，相似度被标点压低，页里明写着的那一段会被当成「没找到」——
    # 种树郭橐驼传「传其事以为官戒也」就是这么从「页里写作别的样子」掉进「页里没找到」的。
    sl = _nopunct(line)
    st = _nopunct(txt)
    L = len(sl)
    if not sl or len(st) < 6:
        return None
    best = (0.0, '')
    # 先按句首字锚窗口，窗口只比句子长一点点。先前只有固定网格 + span=L+10：
    # 在四库那种长页上，窗口里塞进十个字的公有领域声明，相似度被稀释到 0.54——
    # 「传其事以为官戒」明明在页里（只差一个「也」字），却被写成「页里没找到」；
    # 「泉水激石冷冷作响」「夫子哂一作讯之」同理。那是对来源页说的假话，不是我们的口径。
    # 锚点取句子前三个字各试一遍：页里第一个字可能写作另一个字（我们作「哪里」、
    # 页作「那里」），只锚第一个字就找不到那段，一句明明写作别的样子会被写成「页里没找到」。
    anchors = []
    for ch in sl[:3]:
        if ch not in anchors:
            anchors.append(ch)
    for a in anchors:
        i = st.find(a)
        while i >= 0:
            for span in (L + 2, L + 4, L + 6):
                w = st[i:i + span]
                r = difflib.SequenceMatcher(None, sl, w).ratio()
                if r > best[0]:
                    best = (r, w)
            i = st.find(a, i + 1)
    # 句首字在页里一次都没出现（编者补的主语、我们这边多出来的字）：退回网格扫，
    # 让页里别的位置也有机会被指出来。
    if best[0] < 0.55:
        step = max(1, L // 3)
        span = L + 10
        for i in range(0, max(1, len(st) - L + 1), step):
            w = st[i:i + span]
            r = difflib.SequenceMatcher(None, sl, w).ratio()
            if r > best[0]:
                best = (r, w)
    if best[0] < 0.55:
        return None
    return {'line': line, 'source': best[1], 'ratio': round(best[0], 3)}


def candidates(title, author, dynasty, table, lines=None):
    """候选页面排序：标题含篇名 +3，含作者 +2，同名不同物 -8。"""
    base = M.norm_base(title)
    want = M.norm_author(author)
    queries = ['%s %s' % (title, want or '')]
    if want:
        queries.append('%s (%s)' % (title, want))
    if dynasty:
        queries.append('%s %s' % (title, dynasty))
        queries.append('%s (%s)' % (title, dynasty))
    # 用正文里的句子去搜：标题撞车的篇目（无衣、天净沙、论语）靠标题搜到的多半是别的书，
    # 拿句子搜才找得到真正收这篇的页。维基文库的检索简繁互通，简体句子也能命中繁体页。
    if lines:
        probe = max(lines, key=len)[:14] if lines else ''
        if len(probe) >= 6:
            queries.append(probe)
    seen, out = set(), []
    for q in queries:
        for c in search_pages(q):
            if c in seen:
                continue
            seen.add(c)
            conv = to_simplified(c, table)
            score = 0
            if base and base in conv:
                score += 3
            if want and want in conv:
                score += 2
            if any(h in conv for h in JUNK_HINTS):
                score -= 8
            out.append((score, c))
    out.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, c in out]


def _han_only(s):
    """只留汉字：对齐「我们的句子」与「页里最像的那一段」时，标点和空白不参与。"""
    return re.sub(r'[^\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', '', s or '')


def _han_only(s):
    return re.sub(r'[^\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', '', s or '')


_T2S_CACHE = []


def _plain(s):
    """把文本过一遍繁简表，只用来判断「这两个字算不算同一个字」。

    歧义条目（線→线 缐）两个候选都留着：这里不是比对，是问同一个字。"""
    if not _T2S_CACHE:
        _T2S_CACHE.append(load_t2s())
    return to_simplified(s or '', _T2S_CACHE[0])


def _page_han(rec):
    """这一篇来源页的整页文本（剥过标点、过繁简表）。取页走缓存，不额外联网。"""
    pages = [x.strip() for x in (rec.get('page') or '').split(' + ') if x.strip()]
    out = []
    for pg in pages:
        try:
            _real, raw = page_text(pg)
        except Exception:
            continue
        out.append(_han_only(_plain(clean(raw, load_t2s())[0])))
    return ''.join(out)


def apparatus_gaps(records, items, page_han_map=None):
    """出处核对里「没对上」的句子，出入的字有没有写进篇内「异文」。

    「出入的字」按最保守的算法数：我们句子里有、而整页来源里一个都没有的字。
    用整页而不是「页里最像的那一段」：那一段是按句长开的窗口，夹注一插就把窗口撑短，
    句尾的字掉出窗口会被当成出入——行路难「多岐路，今一作路/道/无此字安在」就是这么被误判的。
    页里别处出现过的字不算出入（宁可少数，也不把页里的字说成页里没有）。page_han_map 供自检注入。
    页里连「最像的一段」都给不出（C 档）也不在这里数——那是另一本账。
    这一条只报数、不判红：它是「交代还没写完」的清单，不是新错。每轮都要报，
    不然这几十句就会像没人接着做的缺口一样消失。"""
    out = []
    for pid, title, text in items:
        rec = records.get(pid)
        if not rec:
            continue
        m = re.search(r'^## 异文[^\n]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
        quoted = ''.join(re.findall(r'[「『]([^」』]*)[」』]', m.group(1))) if m else ''
        page_han = (page_han_map or {}).get(pid) if page_han_map is not None else _page_han(rec)
        if not page_han:
            continue
        for x in (rec.get('miss') or []):
            if not (x.get('nearest') or {}).get('source'):
                continue
            seen, ours = set(), []
            for ch in _han_only(_plain(x.get('line'))):
                if ch in page_han or ch in seen:
                    continue
                seen.add(ch)
                ours.append(ch)
            if not ours:
                continue
            if not all(ch in quoted for ch in ours):
                out.append((pid, title, ''.join(ours)[:10]))
    return out


def main():
    limit, stage, only_ids = 0, None, []
    for i, a in enumerate(sys.argv):
        if a == '--limit':
            limit = int(sys.argv[i + 1])
        if a == '--stage':
            stage = sys.argv[i + 1]
        if a == '--id':
            only_ids = [x for x in sys.argv[i + 1].split(',') if x]

    ensure_dict()
    overrides = load_overrides()
    table = load_t2s()
    all_poems = V.load_poems()
    poems = all_poems
    if stage:
        poems = [p for p in poems if p.get('stage') == stage]
    if only_ids:
        # --id 是「重核指定篇目并合并进正式表」，不是试跑：只换掉这几篇的记录，其余原样保留。
        missing = [x for x in only_ids if x not in {q['id'] for q in all_poems}]
        if missing:
            raise SystemExit('--id 里的这些键在仓里不存在（打错了？%s）' % '、'.join(missing))
        poems = [p for p in poems if p['id'] in only_ids]
    if limit:
        poems = poems[:limit]

    # 强制页名这张表也会过期：篇目改名或删掉了，键还留着，就会静默地不生效。
    # 这张表看的是全仓，不能被 --limit / --stage 的过滤带偏：
    # --limit 6 跑过一次，22 个好好的键全被报成「过期，必须删」。
    live = {p['id'] for p in all_poems}
    dead = sorted(k for k in overrides if k not in live)
    if dead:
        print('!! source-overrides.json 里有对不上任何篇目的键（过期，必须删）：%s' % '、'.join(dead))
    bad = override_problems(overrides)
    if bad:
        raise SystemExit('!! source-overrides.json 有问题：\n  ' + '\n  '.join(bad))

    results = []
    stats = {'attested': 0, 'partial': 0, 'notfound': 0, 'nosource': 0, 'withVariants': 0}
    for n, p in enumerate(poems, 1):
        title = p['title']
        author = p.get('author') or ''
        # 核对必须覆盖我们真正发出去的正文。
        # 长诗的 lines 只是必背名句（离骚 4 句），全文另有 26 联——
        # 以前那 26 联从没进过这道核对，「逐句全对上」就成了半真半假的话。
        # 现在 lines 与 fullLines 合并去重一起核：页面只取一次，多出来的只是比对句数。
        merged = []
        for x in list(p.get('linesPunct') or []) + list(p.get('fullLinesPunct') or []):
            # 核对单位是句子。散文的 fullLines 是整段（答司马谏议书 4 段、每段上百字），
            # 整段比对差一个字就整段不算对上——那是工具在骗人，不是内容有问题。
            for seg in re.split(r'[。！？；]', x):
                seg = strip_section_label(seg)
                s = M.strip_punct(seg)
                if len(s) >= 2 and s not in merged:
                    merged.append(s)
        lines = merged
        rec = {'id': p['id'], 'title': title, 'author': author, 'stage': p.get('stage'),
               'page': None, 'url': None, 'lines': len(lines), 'hit': 0,
               'miss': [], 'variantNotes': [], 'variants': []}
        blanks = blank_fragments(lines)
        if blanks:
            # 段尾的引号被切成独立一句：不算对上，也不算没对上，当场报出来。
            rec['blankFragments'] = len(blanks)
            rec['lines'] = len(lines) - len(blanks)
            print('   %s：%d 个碎片只剩标点（切句切出来的，不是内容缺陷）：%s'
                  % (title, len(blanks), ' '.join(repr(x) for x in blanks[:3])))
            lines = [s for s in lines if _nopunct(s)]
        try:
            best = None
            ov = overrides.get(p['id'])
            if ov and ov.get('no_page'):
                # 仓内搜过、维基文库确实没有这首诗的正文页：如实记「没有来源页」。
                # 不许为了台账好看，把一个不含这首诗的页名写进来源页那一栏。
                stats['nosource'] += 1
                rec['override'] = ov.get('note', '')
                # 下游工具不许靠「page 是空的」猜这是哪一种空：
                # 猜就会把「仓内核过确实没有」和「我们没去核」算成同一件事。
                rec['no_page'] = True
                rec['searched'] = list(ov.get('searched') or [])
                rec['miss'] = [{'line': ln, 'nearest': None} for ln in lines]
                results.append(rec)
                print('[%3d/%3d] -- %s %s  0/%d 句对上  仓内核过：维基文库没有正文页（搜过 %d 个串）'
                      % (n, len(poems), title, author, rec['lines'], len(rec['searched'])))
                continue
            if ov:
                pages = ov['pages']
                if ov.get('union'):
                    joined = []
                    joined_q = []
                    vnotes = []
                    valts = []
                    for pg in pages:
                        try:
                            real, raw = page_text(pg)
                            tt, nn = clean(raw, table)
                            joined.append(tt)
                            joined_q.append(clean_quote(raw, table))
                            vnotes.extend(nn)
                        except Exception:
                            continue
                        try:
                            r2, w2 = page_wikitext(pg)
                            valts.extend(alt_variants(w2, table, r2))
                        except Exception:
                            pass
                    txt_all = ''.join(joined)
                    txtq_all = ''.join(joined_q)
                    hit = sum(1 for ln in lines if ln and line_in(ln, txt_all))
                    best = {'page': ' + '.join(pages), 'hit': hit, 'notes': vnotes, 'len': len(txt_all), 'txt': txt_all}
                    if best['hit'] == len(lines):
                        stats['attested'] += 1
                    elif best['hit']:
                        stats['partial'] += 1
                    else:
                        stats['notfound'] += 1
                    rec['page'] = best['page']
                    rec['url'] = 'https://zh.wikisource.org/wiki/' + urllib.parse.quote(pages[0])
                    rec['hit'] = best['hit']
                    # 跨页合并这一支以前不记「差的是哪几句」：hit 是对着合并后的全文算的，
                    # 差几句却一条都没写下来——明细页就没东西可写（曹刿论战、兰亭集序、论语十二章都是这样）。
                    rec['miss'] = []
                    for ln in lines:
                        if not ln or line_in(ln, txt_all):
                            continue
                        rec['miss'].append({'line': ln, 'nearest': nearest(ln, txtq_all)})
                    rec['variantNotes'] = best['notes'][:12]
                    rec['variants'] = valts[:40]
                    rec['override'] = ov.get('note', '')
                    results.append(rec)
                    continue
                cand_list = pages
            else:
                cand_list = candidates(title, author, p.get('dynasty'), table, lines)[:4]
            for cand in cand_list:
                real, raw = page_text(cand)
                txt, notes = clean(raw, table)
                if '消歧义' in txt[:400] or '重定向' in txt[:40]:
                    continue
                hit = sum(1 for ln in lines if ln and line_in(ln, txt))
                if best is None or hit > best['hit']:
                    best = {'page': real, 'hit': hit, 'notes': notes, 'len': len(txt), 'txt': txt,
                            'txtq': clean_quote(raw, table)}
                if hit == len(lines):
                    break
                time.sleep(0.10)
            if best:
                rec['page'] = best['page']
                rec['url'] = 'https://zh.wikisource.org/wiki/' + urllib.parse.quote(best['page'])
                rec['hit'] = best['hit']
                rec['variantNotes'] = best['notes'][:12]
                try:
                    _, w2 = page_wikitext(best['page'])
                    rec['variants'] = alt_variants(w2, table, best['page'])[:40]
                except Exception:
                    rec['variants'] = []
                src_txt = best['txt']
                # 「页里最像的一段」是给人读的，也是异文条目的依据：用不造字的那一份。
                src_q = best.get('txtq') or best['txt']
                rec['miss'] = []
                for ln in lines:
                    if not ln or line_in(ln, src_txt):
                        continue
                    near = nearest(ln, src_q)
                    rec['miss'].append({'line': ln, 'nearest': near})
                if rec['hit'] == rec['lines']:
                    stats['attested'] += 1
                elif rec['hit']:
                    stats['partial'] += 1
                else:
                    stats['notfound'] += 1
            else:
                stats['nosource'] += 1
        except Exception as exc:
            rec['error'] = '%s: %s' % (type(exc).__name__, exc)
            stats['nosource'] += 1
        if rec.get('variants'):
            stats['withVariants'] += 1
        results.append(rec)
        flag = 'ok' if rec['hit'] == rec['lines'] and rec['lines'] else '!!'
        print('[%3d/%3d] %s %s（%s）  %d/%d 句对上  夹注异文 %d 条  %s' % (
            n, len(poems), flag, title, author, rec['hit'], rec['lines'],
            len(rec.get('variants') or []), rec['page'] or '找不到来源页'))
        time.sleep(0.10)

    # 四档一律从记录本身重算，不用循环里攒的那份。
    # 循环里攒的会漏：「跨页合并」（override 带 union）那一支 append 完就 continue，
    # 后面那句 withVariants 计数根本没跑到——48 条 override 里 13 篇带异文的就这么没被算进去，
    # 台账上「有异文的篇目」当场少 13 篇，而且没有任何一处报错。
    stats = stats_from_records(results)

    # --limit / --stage 是试跑用的，试跑不许覆盖正式表。
    # 刚才顺手跑了个 --limit 3，data/text-sources.json 当场从 252 篇变成 3 篇——
    # 这种覆盖不会报错，只会让后面所有读这张表的检查安静地读到残缺数据。
    filtered = bool(limit) or stage is not None
    target = (ROOT / 'data' / 'text-sources.partial.json') if filtered else OUT
    merge = bool(only_ids) and not filtered
    # 旧表必须在写盘之前读。以前写在这之后：--id 先把整张表覆盖成 6 篇，
    # 再「合并」时读到的旧表就是那 6 篇，252 篇的记录当场没了。
    old = json.loads(OUT.read_text(encoding='utf-8')) if merge else None
    target.write_text(json.dumps({
        'note': '每篇原文的独立出处核对结果。来源：维基文库 zh.wikisource.org（公有领域文本）。'
                '繁体转简体用 OpenCC TSCharacters 字表（Apache-2.0），只用于比对，不改仓内正文。'
                'variantNotes 是页面里的「一作某」夹注，是异文线索，不是错误。'
                'variants 是从 wikitext 解析的 {{另|甲|乙}} 夹注：ours 是页面正文用字，'
                'other 是别本用字，context 是上下文，page 是页名——考证时按页可核。',
        'generated': time.strftime('%Y-%m-%d'),
        'stats': stats,
        'results': results,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    if merge:
        # 合并而不是覆盖：--id 只换掉点名的那几篇，其余记录原样留着。
        by_id2 = {r['id']: r for r in old.get('results', [])}
        for r in results:
            by_id2[r['id']] = r
        merged = list(by_id2.values())
        # 合并之后 stats 必须按合并后的记录重算。以前这里照搬旧表的 stats：
        # --id 补收几篇，记录数涨了，四档的数却还是旧的——文档里的数字照样「对得上」，
        # 对的是那张旧账。台账的数在背后抖，比数字错了更难发现。
        new_stats = stats_from_records(merged)
        if new_stats != old.get('stats', {}):
            print('台账四档按记录重算：%s → %s' % (old.get('stats', {}), new_stats))
        OUT.write_text(json.dumps({
            'note': old.get('note', ''),
            'generated': time.strftime('%Y-%m-%d'),
            'stats': stats_from_records(merged),
            'results': merged,
        }, ensure_ascii=False, indent=2), encoding='utf-8')

    print()
    print('取页：缓存命中 %d 次 / 真的联网取页 %d 次%s'
          % (CACHE_HITS[0], CACHE_HITS[1], '（--refresh-pages：全部重取）' if REFRESH_PAGES else ''))
    print('出处核对：%d 全对上 / %d 部分对上 / %d 一句都对不上 / %d 找不到来源页'
          % (stats['attested'], stats['partial'], stats['notfound'], stats['nosource']))
    print('带 {{另}} 夹注异文的篇目：%d 篇' % stats['withVariants'])
    recs = {r['id']: r for r in results}
    items = [(p['id'], p['title'], (ROOT / p['_path']).read_text(encoding='utf-8')) for p in all_poems]
    gaps = apparatus_gaps(recs, items)
    print('[异文覆盖] 出处核对没对上、且出入的字没写进篇内「异文」的：%d 句（交代待补，不是新错）' % len(gaps))
    for pid, title, ours in gaps:
        print('   · %s：差在「%s」' % (title, ours))
    drift = page_drift(old.get('results', []) if old else [], results)
    if drift:
        print('!! 来源页换了地方 %d 篇（台账的数会跟着动；要稳住就在 data/source-overrides.json 钉住）：' % len(drift))
        for pid, pa, pb in drift[:12]:
            print('   %-22s %s → %s' % (pid, pa, pb))
    if filtered:
        print('试跑模式：结果写到 data/text-sources.partial.json，正式表 data/text-sources.json 未动')
    elif merge:
        print('已合并 %d 篇进 data/text-sources.json（其余 %d 篇记录未动）' % (len(results), len(merged) - len(results)))
    else:
        print('已写 data/text-sources.json')
    return 0


def strip_section_label(seg):
    """剥掉我们自己加的小节标签（【毛诗序】【与元九书】）。

    为什么：标签是我们加的，不是原文。留着它，「【毛诗序】诗者，志之所之也」就成了要核对的一句——
    来源页明写着「诗者志之所之也」，前面没有「毛诗序」三个字，整句被判成「页里没找到」。
    古代文论选段六句 C 档里，五句是这么来的。
    句末那一头也一样：《老子》八章 的全文每段末尾我们标了出处章次（「…故去彼取此。（第十二章）」），
    切句之后「第十二章」自己成了一句，拿去页里核对必然找不到——台账里凭空多出一条假「页里没找到」。
    只认「第…章/节/篇」这种标签；「（其一）」是篇名的一部分，不许剥。"""
    seg = re.sub(r'^【[^】]*】', '', seg or '')
    return re.sub(r'（第[一二三四五六七八九十百千零〇\d]+[章节篇]）$', '', seg)


def blank_fragments(lines):
    """切句留下的纯标点碎片：剥掉标点之后什么都不剩。

    为什么单列：这种碎片拿去来源页里找必然找不到，会被算成「页里没找到」——台账里凭空多出一条假缺陷。
    悄悄丢掉又等于放过真的空句（正文里真有一句是空的，也该看得见）。所以：不当对上、不当没对上，当场报数。"""
    return [ln for ln in lines if ln and not _nopunct(ln)]


def stats_from_records(records):
    """四档从记录本身重算，不靠跑的时候攒。合并模式必须用它。"""
    s = {'attested': 0, 'partial': 0, 'notfound': 0, 'nosource': 0, 'withVariants': 0}
    for r in records:
        if r.get('no_page') or r.get('error') or not r.get('page'):
            s['nosource'] += 1
        elif r.get('hit') == r.get('lines'):
            s['attested'] += 1
        elif r.get('hit'):
            s['partial'] += 1
        else:
            s['notfound'] += 1
        if r.get('variants'):
            s['withVariants'] += 1
    return s


def selftest():
    """这张字表必须自带坏例子，否则它就是一张没人验过的表。"""
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    # 坏例1：页里写作「未甞往也」，我们作「未尝往也」——不认这对，赤壁赋永远算没核到
    must(line_in('逝者如斯而未尝往也', '客亦知夫水与月乎逝者如斯而未甞往也盈虚者如彼') is not None,
         '坏例1：甞/尝 没被认成同一个字')
    # 坏例2：髙/高、靑/青、槩/概、顚/颠、衞/卫、戹/厄、吿/告、彊/强 同样必须认
    # 每一对都写成「我们这样写 / 页里那样写」的真句子，不许拿 xx 糊过去
    for a, b, ours, page in (
            ('高', '髙', '不可以已高', '学不可以已髙矣'),
            ('青', '靑', '而青于青', '青取之于靑而靑于青也'),
            ('概', '槩', '概乎其中', '然槩乎其中焉'),
            ('颠', '顚', '颠而不扶', '危而不持顚而不扶'),
            ('卫', '衞', '开关延卫', '于是秦人开关延衞'),
            ('厄', '戹', '此人皆厄', '此人皆戹如此'),
            ('告', '吿', '告与我的事', '吿与我的事')):
        must(line_in(ours, page) is not None, '坏例2：页里写作「%s」我们写作「%s」，没并成同一个字' % (b, a))
    # 坏例3：义近字与真异文不许混进这张表（說/悅、知/智、渡/度、蔽/敝、泠/冷）
    for a, b in (('說', '悅'), ('知', '智'), ('渡', '度'), ('蔽', '敝'), ('泠', '冷'), ('岐', '歧')):
        must(a not in VARIANT_GLYPHS and b not in VARIANT_GLYPHS, '坏例3：%s/%s 被当成同一个字' % (a, b))
    # 表里每一对必须是「同一个字的另一种写法」：两边读音必须相同（拿 Unihan kMandarin 验）
    # 读数从哪来：本地有全量 Unihan 就用它，CI 里没有就用入库那份快照。
    # 两条路都必须覆盖整张字表——load_variant_readings 会数，缺字就当场报错。
    mand = load_variant_readings()
    for a, b in VARIANT_GLYPHS.items():
        if a == b:
            continue
        ra, rb = mand.get(a), mand.get(b)
        must(ra and rb and (ra & rb), '坏例3b：%s(%s) 与 %s(%s) 读音不同，不该当同一个字' % (
             a, '/'.join(sorted(ra or [])), b, '/'.join(sorted(rb or []))))
    # 坏例4：页里明明白白有这句，不许因为窗口太脆判成没对上
    must(line_in('飘飘乎如遗世独立羽化而登仙', '如冯虚御风而不知其所止飘飘乎如遗世独立羽化而登仙焉') is not None,
         '坏例4：页里有的句子被判成没对上')
    # 坏例5：页里真没有这句，必须报没对上——字表不许把它抹平成「对上了」
    must(line_in('此四君者皆明智而忠信', '贾谊过秦论云诸侯不测') is None, '坏例5：没有的句子被当成对上了')
    # 坏例6：「维基文库没有正文页」这个出口不许空着用：没写为什么、没写搜过哪些句子、
    # 又给页名、或干脆两头都不给，都必须当场报错——否则它就会变成让一篇永远不用核的出口
    must(any('没写为什么' in x for x in override_problems({'某篇': {'no_page': True, 'note': '', 'searched': []}})),
         '坏例6：no_page 没写理由却没报错')
    must(any('搜过哪些句子' in x for x in override_problems({'某篇': {'no_page': True, 'note': '搜过', 'searched': []}})),
         '坏例6：no_page 没写搜过哪些句子却没报错')
    must(any('二者只能留一个' in x for x in override_problems({'某篇': {
        'no_page': True, 'note': '搜过两句都没有', 'searched': ['頭上紅冠不用裁'], 'pages': ['題畫 (唐寅)']}})),
         '坏例6：no_page 又给了页名却没报错')
    must(any('既没给页名' in x for x in override_problems({'某篇': {'pages': []}})),
         '坏例6：既没页名也没说没有正文页却没报错')
    # 坏例6b：带着证据用这个出口，不许误伤
    must(override_problems({'某篇': {'no_page': True, 'note': '搜过两句都没有',
                                    'searched': ['頭上紅冠不用裁', '一叫千門萬戶開']}}) == [],
         '坏例6b：带着证据的 no_page 被误伤')
    # 坏例7：四庫全書系页面写作「天涯若比隣」，我们作「比邻」——不认这对，这一篇永远算没核到
    must(line_in('海内存知己，天涯若比邻', '海内存知己天涯若比隣') is not None,
         '坏例7：隣/邻 没被认成同一个字')
    must('隣' in VARIANT_GLYPHS and VARIANT_GLYPHS['隣'] == '邻', '坏例7b：隣 没进字表或映射写错')
    # 坏例8：只差一个字、相似度 0.9 的句子，不许被当成「对上了」。
    # 这一条盯的是先前那档 difflib>=0.82 的出口：像不是对上了。
    must(line_in('城阙辅三秦风烟望五津', '城阙辅三秦风烟望五州') is None,
         '坏例8：只差一个字就被算成对上了（相似度那一档没撤干净）')
    must(line_in('海内存知己天涯若比邻', '海内存知己天涯若比邻') == 'exact', '坏例8b：整句直接命中反而不认了')
    # 坏例8c：句首句末都在窗口里、中间那个字页里根本没有——head/tail 那一档撤了，不许再判对上。
    # 这一条不是编的：过松源晨炊漆公店「正入万山围子里」对《宋元詩㑹》卷四十一的「正入万山圈子里」，
    # 先前正是这一档判成「对上了」，出处核对因此记 2/2 全对上。
    must(line_in('正入万山围子里一山放出一山拦', '正入万山圈子里一山放出一山拦') is None,
         '坏例8c：中间那个字不同（围／圈），head/tail 那一档还把它判成对上了')
    # 坏例8d：撤一档不许把真的撤掉——页里夹着「一作荒」的真句子必须仍然认。
    must(line_in('城春草木深感时花溅泪', '城春一作荒草木深感时花溅泪') is not None,
         '坏例8d：页里夹着「一作荒」的真句子被撤档误伤')
    # 坏例9：来源页换了地方必须说出来——不说，台账的数就在背后抖
    d9 = page_drift([{'id': 'a', 'page': '甲页'}], [{'id': 'a', 'page': '乙页'}])
    must(d9 == [('a', '甲页', '乙页')], '坏例9：来源页换了却没报：%s' % d9)
    must(page_drift([{'id': 'a', 'page': '甲页'}], [{'id': 'a', 'page': '甲页'}]) == [], '坏例9b：页没变也被报（误伤）')
    must(page_drift([], [{'id': 'a', 'page': '甲页'}]) == [], '坏例9c：第一次核也被当成换了页')
    must(page_drift([{'id': 'a', 'page': None}], [{'id': 'a', 'page': '甲页'}]) == [], '坏例9d：以前没有页、现在有了，不算换了页')
    # 坏例10：页里的注码是数字实体（&#91;13&#93;）。先前只剥字母实体，句子被「&91;13&93;」打断，
    # 谏逐客书两句在页里明写着却被判成「页里没找到」。
    txt10, _n10 = clean('惠王&#91;13&#93;用张仪&#91;14&#93;之计拔三川之地', {})
    must('&#91;' not in txt10 and '&91;' not in txt10 and '之计拔三川之地' in txt10,
         '坏例10：数字注码没剥掉：%r' % txt10)
    # 坏例11：仓里有些正文用 ASCII 引号。head 取到引号本身，页里明写着的句子就被判成没找到
    # （曹刿论战「对曰：小惠未遍，民弗从也」、邹忌讽齐王纳谏「明日徐公来，孰视之」都是这么丢的）。
    # 页里那个「徧」由字表并成「遍」（见 VARIANT_GLYPHS），所以这里喂给 line_in 的是 clean 之后的页文本。
    # 字表是在 line_in 去标点那一步生效的（_nopunct），所以这里直接喂原始页文本。
    must('遍' in _nopunct('对曰小惠未徧民弗从也'), '坏例11b：徧/遍 没被字表并成同一个字')
    must(line_in('"对曰"小惠未遍民弗从也', '对曰小惠未徧民弗从也') is not None,
         '坏例11：带 ASCII 引号的句子页里明写着却没被判对上')
    # 坏例12：切句留下的纯标点碎片——算成「没对上」就是台账里的假缺陷
    must(len(blank_fragments(['甲乙丙丁', '"\''])) == 1, '坏例12：切句留下的纯标点碎片没被抓到')
    must(blank_fragments(['甲乙丙丁']) == [], '坏例12b：正常句子被当成碎片（误伤）')
    must(len(blank_fragments(['，。', '"'])) == 2, '坏例12c：两个碎片只报了 %d 个' % len(blank_fragments(['，。', '"'])))
    # 坏例13：页里同一句出现两次、远处还挂着一段重复的尾巴。窗口按句长封顶，
    # 紧挨着的那一段必须认——先前 tail 取全文最后一个，窗口被拉到别处，紧挨着的反倒不算。
    must(line_in('小惠未遍民弗从也',
               '公曰忠之属也可以一战对曰小惠未遍民弗从也无关文字无关文字无关文字无关文字无关文字无关文字民弗从也') is not None,
         '坏例13：页里「弗从也」出现两次，远处那一段把窗口拉走就没判对上')
    # 坏例14：nearest 也得用剥过标点的两边。带引号的原文去比，相似度被标点压低，
    # 页里明写着的那一段会被当成「没找到」——种树郭橐驼传「传其事以为官戒也」就是这么丢的。
    _txt14 = '养树得养人术传其事以为官戒此唐朝作品'
    _plain = nearest('传其事以为官戒也', _txt14)
    _quote = nearest('"传其事以为官戒也。"', _txt14)
    must(_plain is not None and _quote is not None and abs(_quote['ratio'] - _plain['ratio']) < 0.02,
         '坏例14：同一句带不带引号，相似度从 %s 掉到 %s——标点把页里明写着的那一段压到阈值以下' % (
             _plain and _plain['ratio'], _quote and _quote['ratio']))
    must(nearest('甲乙丙丁戊己', '完全无关的一段文字内容') is None, '坏例14b：毫不相干的一段被当成最像的')
    # 坏例15：页尾那段公有领域声明不是正文。留着，「页里最像的那一段」的相似度就被压低——
    # 种树郭橐驼传「传其事以为官戒也」就是这么从「页里写作别的样子」掉进「页里没找到」的。
    _t15, _n15 = clean('吾问养树得养人术传其事以为官戒此唐朝作品在全世界都属于公有领域因为作者逝世已经超过100年且作品于1931年1月1日之前出版Publicdomain', {})
    must('公有领域' not in _t15 and 'Publicdomain' not in _t15 and '传其事以为官戒' in _t15,
         '坏例15：页尾的公有领域声明没剥掉：%s' % _t15[-40:])
    _t15b, _n15b = clean('姊妹计划:数据项关雎后妃之德也', {})
    must('姊妹计划' not in _t15b and '数据项' not in _t15b and '关雎后妃之德也' in _t15b,
         '坏例15b：页头的「姊妹计划/数据项」没剥掉：%s' % _t15b)
    must(clean('传其事以为官戒也', {})[0] == '传其事以为官戒也', '坏例15c：正文被页面家具的剥法误伤')
    _t15d, _n15d = clean('吾问养树得养人术传其事以为官戒此唐朝作品在全世界都属于公有领域因为作者逝世已经超过100年', {})
    must(nearest('传其事以为官戒也', _t15d) is not None,
         '坏例15d：页尾声明把相似度压到阈值以下，页里明写着的那一段没报出来（剥完是 %s）' % _t15d)

    # 坏例16：我们自己加的小节标签不许算进句子里核对
    must(strip_section_label('【毛诗序】诗者志之所之也') == '诗者志之所之也',
         '坏例16：小节标签没剥掉：%r' % strip_section_label('【毛诗序】诗者志之所之也'))
    must(strip_section_label('诗者志之所之也') == '诗者志之所之也', '坏例16b：没有标签的句子被误伤')
    must(strip_section_label('【毛诗序】') == '', '坏例16c：整行只有标签，剥完应当是空的')
    # 坏例16d：句末我们自己加的章次标签，切句之后自己成了一句，页里必然找不到——台账里的假缺陷
    must(strip_section_label('（第十二章）') == '', '坏例16d：句末章次标签没剥掉：%r' % strip_section_label('（第十二章）'))
    must(strip_section_label('五色令人目盲，驰骋田猎令人心发狂（第十二章）') == '五色令人目盲，驰骋田猎令人心发狂',
         '坏例16e：句末章次标签混在句子里没剥掉：%r' % strip_section_label('五色令人目盲，驰骋田猎令人心发狂（第十二章）'))
    # 坏例16f：剥标签不许过界——「（其一）」是篇名的一部分
    must(strip_section_label('秋词（其一）') == '秋词（其一）', '坏例16f：篇名的编号被当成标签剥掉了')
    must(strip_section_label('（其六）') == '（其六）', '坏例16g：只有编号的一行被误剥')
    must(strip_section_label('（第12章）') == '', '坏例16h：阿拉伯数字的章次标签没剥掉：%r' % strip_section_label('（第12章）'))
    # 坏例17：窗口不能只有固定网格那一条路——长页上窗口里塞进别的内容，相似度被稀释，
    # 页里明写着的那一段就被写成「页里没找到」。下面三句都是当场从真页里发现的。
    _t17a = ('皆生寒树负势竞上互相轩邈争高直指千百成峰泉水激石冷冷作响好鸟相鸣嘤嘤成韵'
             '蝉则千转不穷猿则百叫无绝鸢飞戾天者望峰息心经纶世务者窥谷忘反')
    must(nearest('泉水激石泠泠作响', _t17a) is not None,
         '坏例17：页里作「冷冷」、我们作「泠泠」，这一句被说成「页里没找到」（其实是版本差异）')
    _t17b = ('千乘之国摄乎大国之闲加之以师旅因之以饥馑由也为之比及三年可使有勇且知方也'
             '夫子哂一作讯之求尔何如对曰方六七十如五六十求也为之')
    must(nearest('夫子哂之', _t17b) is not None,
         '坏例17b：页里「夫子哂」与「之」之间夹着「一作讯」，这一句被说成「页里没找到」')
    _t17c = ('吾问养树得养人术传其事以为官戒'
             '此唐朝作品在全世界都属于公有领域因为作者逝世已经超过100年且作品于1931年1月1日之前出版')
    must(nearest('传其事以为官戒也', _t17c) is not None,
         '坏例17c：页尾声明把窗口撑长，页里明写着的那一段（只差一个「也」）没报出来')
    # 坏例17e：页里第一个字写作另一个字（我们作「哪里」、页作「那里」），只锚第一个字就找不到那段。
    _t17e = ('喇叭唢呐曲儿小腔儿大官船来往乱如麻全仗你抬声价军听了军愁民听了民怕那里去辨甚麼真共假'
             '眼见的吹翻了这家吹伤了那家只吹的水尽鹅飞罢')
    _n17e = nearest('哪里去辨甚么真共假', _t17e)
    must(_n17e is not None and '去辨' in _n17e['source'],
         '坏例17e：页里作「那里去辨甚麼真共假」，这一句被说成「页里没找到」（锚点只有第一个字）')
    must(nearest('江畔独步寻花黄四娘家花满蹊', _t17a + _t17b + _t17c) is None,
         '坏例17d：把窗口找松了以后，页里真没有的句子也该给个「最像的」——不许造出来')
    # 坏例19：表里「巘→𪩘」是单值条目，照转会写出一个页里根本没有的扩展区字。
    #          引用文本里必须还是页里那个「巘」。
    _q19 = clean_quote('重湖疊巘清', load_t2s())
    must('巘' in _q19 and '𪩘' not in _q19, '坏例19：引用文本把页里的「巘」换成了页里没有的「𪩘」（%s）' % _q19)
    # 坏例18：OpenCC 的歧义条目一个繁体字给两个候选。比对时两个都认，引用时不许把两个都写出来——
    # 「来源页作「藉借寇兵」」这种句子就是这么来的：页里只写「藉」，我们把两个候选拼在一起，
    # 等于对来源页说了一句它自己没写过的话。
    _t18 = ('此所謂藉寇兵而齎盜糧者也鍾子期死乾隆三十九年彷彿夢魂歸帝所')
    _q18 = clean_quote(_t18, load_t2s())
    must('藉借' not in _q18 and '藉' in _q18, '坏例18：引用文本把歧义条目两个候选拼在一起（%s）' % _q18)
    must('钟锺' not in _q18 and '鍾' in _q18, '坏例18b：页里写作「鍾」，引用文本却写成了别的（%s）' % _q18)
    must('乾隆' in _q18 and '干隆' not in _q18, '坏例18c：「乾隆」被歧义条目改成了「干隆」')
    must('彷佛' in _q18 and '仿仿佛' not in _q18 and '彷彷' not in _q18,
         '坏例18d：页里写作「彷」，引用文本把它换成了另一个候选')
    # 反向：比对那一份照旧两个候选都认——收紧引用口径不许把已经对上的句子判成没对上。
    _m18 = clean(_t18, load_t2s())[0]
    must(line_in('此所谓借寇兵而赍盗粮者也', _m18) is not None,
         '坏例18e：比对文本不再认歧义条目的另一个候选，已经对上的句子被判成没对上')
    # 坏例20：出处核对没对上、出入的字又没写进「异文」——必须数出来，不许悄悄过去。
    _recs20 = {'甲': {'id': '甲', 'miss': [{'line': '正入万山围子里一山放出一山拦',
                                          'nearest': {'source': '正入万山圈子里一山放出一山拦闷歌'}}]}}
    _md20 = '# 甲\n\n## 全文\n\n正入万山围子里。\n'
    _pg20 = {'甲': '正入万山圈子里一山放出一山拦闷歌'}
    _pg20c = {'甲': '甲乙丙丁戊己庚辛壬'}
    _pg20e = {'甲': '甲乙丙丁戊己庚辛'}
    must(apparatus_gaps(_recs20, [('甲', '甲', _md20)], _pg20) == [('甲', '甲', '围')],
         '坏例20：没对上又没写进「异文」的出入没被数出来')
    # 坏例20b：已经写进「异文」的不许再数（误伤会让这条清单失去意义）
    _md20b = '# 甲\n\n## 异文\n\n- 「万山围子」：来源页作「万山圈子」。取舍：从统编作「围子」。\n'
    must(apparatus_gaps(_recs20, [('甲', '甲', _md20b)], _pg20) == [], '坏例20b：已经写进「异文」的出入被重复数出来')
    # 坏例20c：页里那一段比我们的句子长出一截、我们的字它都有——窗口错位，不是字面出入，不许数
    _recs20c = {'甲': {'id': '甲', 'miss': [{'line': '甲乙丙丁戊己', 'nearest': {'source': '甲乙丙丁戊己庚辛壬'}}]}}
    must(apparatus_gaps(_recs20c, [('甲', '甲', _md20)], _pg20c) == [], '坏例20c：窗口错位被当成了字面出入')
    # 坏例20d：页里给不出「最像的一段」（C 档）不在这里数——那是另一本账
    _recs20d = {'甲': {'id': '甲', 'miss': [{'line': '甲乙丙丁戊己', 'nearest': None}]}}
    must(apparatus_gaps(_recs20d, [('甲', '甲', _md20)], _pg20) == [], '坏例20d：C 档被混进「异文待补」这本账')
    # 坏例20e：页里那段窗口被夹注撑短，句尾的字其实在页里别处——不许当成出入
    _recs20e = {'甲': {'id': '甲', 'page': '某页', 'miss': [{'line': '甲乙丙丁戊己庚辛',
                                             'nearest': {'source': '甲乙丙丁一作某无此字'}}]}}
    _g20e = apparatus_gaps(_recs20e, [('甲', '甲', _md20)], _pg20e)
    must(_g20e == [], '坏例20e：页里别处有的字被当成出入：%s' % _g20e)
    # 坏例21：合并之后照搬旧 stats——记录涨了、四档没涨，台账的数就在背后抖。
    # 这一条是本轮真实踩过的：--id 补收 7 篇，记录从 258 涨到 265，四档却还是 205/52/0/1，
    # 文档里的数字与产物「当场一致」，对的是那张旧账。
    _old21 = [{'id': 'a', 'page': '甲页', 'hit': 3, 'lines': 3}, {'id': 'b', 'page': '乙页', 'hit': 1, 'lines': 4}]
    must(stats_from_records(_old21) == {'attested': 1, 'partial': 1, 'notfound': 0, 'nosource': 0, 'withVariants': 0},
         '坏例21：四档本身算错：%s' % stats_from_records(_old21))
    must(stats_from_records(_old21 + [{'id': 'c', 'page': '丙页', 'hit': 2, 'lines': 2}])['attested'] == 2,
         '坏例21b：合并进来的那一篇没被算进四档')
    # 坏例21c：「没有来源页」的三种写法（核过确实没有 / 取页失败 / 连页名都没有）必须都落进 nosource
    _21c = [{'id': 'd', 'no_page': True, 'hit': 0, 'lines': 5}, {'id': 'e', 'error': 'URLError: x', 'hit': 0, 'lines': 2},
            {'id': 'f', 'hit': 0, 'lines': 3}]
    must(stats_from_records(_21c)['nosource'] == 3, '坏例21c：没有来源页的三种写法没都算进 nosource：%s' % stats_from_records(_21c))
    # 坏例21d：有页却一句都对不上是 notfound，不许并进 nosource——那是两回事
    must(stats_from_records([{'id': 'g', 'page': '丁页', 'hit': 0, 'lines': 6}])['notfound'] == 1,
         '坏例21d：有页没对上被算成找不到来源页')
    # 坏例21e：四档加起来必须等于记录数，不等就是漏了一档
    _21e = _old21 + _21c + [{'id': 'g', 'page': '丁页', 'hit': 0, 'lines': 6}]
    _s21 = stats_from_records(_21e)
    _sum21 = _s21['attested'] + _s21['partial'] + _s21['notfound'] + _s21['nosource']
    must(_sum21 == len(_21e), '坏例21e：四档加起来 %d，记录 %d 篇，漏了一档' % (_sum21, len(_21e)))
    # 坏例21f：误伤检查——一篇正常的表重算后必须一篇不差
    must(stats_from_records([{'id': x, 'page': '页', 'hit': 2, 'lines': 2} for x in 'abcdef'])['attested'] == 6,
         '坏例21f：正常表被重算误伤')
    # 坏例22：注码必须剥掉。MediaWiki 现在渲染成 <sup id="cite_ref-1" class="reference">[1]</sup>，
    # 先前只认大写 Reference，小写漏过去——江南逢李龟年 从「全对上」掉成「1/2 句对上」，
    # 全仓 13 条记录的「页里最像的一段」里夹着注码数字。页面 markup 一变，台账的数就跟着抖。
    _h22 = '岐王<sup id="cite&#95;ref-1" class="reference"><a href="#cite_note-1"><span class="cite-bracket">&#91;</span>1<span class="cite-bracket">&#93;</span></a></sup>宅裏尋常見'
    _f22 = strip_page_furniture(_h22)
    must('1' not in _f22, '坏例22：小写 reference 的注码没剥掉：%r' % _f22)
    must('岐王' in _f22 and '宅裏尋常見' in _f22, '坏例22b：剥注码把正文也弄坏了：%r' % _f22)
    # 坏例22c：旧写法（大写 Reference）不许被改坏
    must('1' not in strip_page_furniture('甲<sup class="Reference">1</sup>乙'), '坏例22c：大写 Reference 的注码没剥掉')
    # 坏例22d：只有 id、没有 class 的注码 sup 也要剥
    must('2' not in strip_page_furniture('甲<sup id="cite_ref-2">2</sup>乙'), '坏例22d：只有 id 的注码 sup 没剥掉')
    # 坏例22e：正文里真的带数字的句子不许被误剥
    must('三十年' in strip_page_furniture('金戈铁马气吞万里如虎三十年后'), '坏例22e：正文里的数字被误剥')
    # 坏例22f：样式块（{{另}} 模板带 CSS）不许留在正文里
    _f22f = strip_page_furniture('正<style data-mw-deduplicate="TemplateStyles:r1">.mw-parser-output .variant-text{color:red}</style>江南')
    must('color' not in _f22f and '江南' in _f22f, '坏例22f：内联样式没剥掉：%r' % _f22f)

    # 坏例21g：带异文的记录必须算进「有异文」，不管它是正常那一支还是跨页合并那一支写出来的
    # （真实漏点：跨页合并 append 完就 continue，循环里的 withVariants 计数没跑到，13 篇就这么没了）
    must(stats_from_records([{'id': 'a', 'page': '页', 'hit': 2, 'lines': 2, 'variants': [{'ours': '甲', 'other': '乙'}]}])['withVariants'] == 1,
         '坏例21g：带异文的记录没被算进 withVariants')
    must(stats_from_records([{'id': 'a', 'page': '甲页 + 乙页', 'hit': 3, 'lines': 3, 'variants': [{'ours': '甲'}]}, {'id': 'b', 'page': '丙页', 'hit': 1, 'lines': 2}])['withVariants'] == 1,
         '坏例21h：跨页合并的记录算错了 withVariants')
    print('[ok] check-text-sources --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    if '--export-variant-readings' in sys.argv:
        sys.exit(export_variant_readings())
    sys.exit(main())
