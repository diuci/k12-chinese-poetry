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


def page_text(title):
    hit = _cache_get(title, 'text')
    if hit:
        return hit.get('title', title), hit['text']
    CACHE_HITS[1] += 1
    d = http_json({'action': 'parse', 'page': title, 'prop': 'text',
                   'format': 'json', 'redirects': 1})
    parse = d.get('parse') or {}
    html = parse.get('text', {}).get('*', '')
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<sup[^>]*class="[^"]*(?:Reference|noprint)[^"]*"[^>]*>.*?</sup>', '', html, flags=re.S)
    html = re.sub(r'<span[^>]*class="[^"]*(?:mw-editsection|noprint)[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)
    txt = re.sub(r'<[^>]+>', ' ', html)
    txt = re.sub(r'&[a-z]+;', ' ', txt)
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


def clean(text, table):
    """繁→简、剥标点空白。返回 (清洗后文本, 夹注列表)。

    夹注（「城春一作荒草木深」）只登记、不剥掉：剥掉会把句子切碎，
    反而让真句子判成对不上。打断交给 line_in 的 annotated / near 两档去认。"""
    text = to_simplified(text, table)
    notes = VARIANT_NOTE.findall(text)
    for ch in M.PUNCT + '\u3000\xa0↑↓*#':
        text = text.replace(ch, '')
    return re.sub(r'\s', '', text), notes


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
                  '隣': '邻'}
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
    if len(line) >= 6:
        head, tail = line[:3], line[-3:]
        i, j = txt.find(head), txt.rfind(tail)
        if i >= 0 and j > i and (j - i) <= len(line) + 16:
            return 'annotated'
    # 夹注很长时（「孤城遥望玉一作「雁」门关」）head/tail 会被夹注本身打断。
    # 再退一档：整句的字必须按顺序出现在一个够短的窗口里——只认顺序，不认连续。
    if len(line) >= 6 and subseq_window(line, txt):
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
    L = len(line)
    if not L or len(txt) < 6:
        return None
    best = (0.0, '')
    step = max(1, L // 3)
    span = L + 10
    for i in range(0, max(1, len(txt) - L + 1), step):
        w = txt[i:i + span]
        r = difflib.SequenceMatcher(None, line, w).ratio()
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
                s = M.strip_punct(seg)
                if len(s) >= 2 and s not in merged:
                    merged.append(s)
        lines = merged
        rec = {'id': p['id'], 'title': title, 'author': author, 'stage': p.get('stage'),
               'page': None, 'url': None, 'lines': len(lines), 'hit': 0,
               'miss': [], 'variantNotes': [], 'variants': []}
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
                    vnotes = []
                    valts = []
                    for pg in pages:
                        try:
                            real, raw = page_text(pg)
                            tt, nn = clean(raw, table)
                            joined.append(tt)
                            vnotes.extend(nn)
                        except Exception:
                            continue
                        try:
                            r2, w2 = page_wikitext(pg)
                            valts.extend(alt_variants(w2, table, r2))
                        except Exception:
                            pass
                    txt_all = ''.join(joined)
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
                        rec['miss'].append({'line': ln, 'nearest': nearest(ln, txt_all)})
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
                    best = {'page': real, 'hit': hit, 'notes': notes, 'len': len(txt), 'txt': txt}
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
                rec['miss'] = []
                for ln in lines:
                    if not ln or line_in(ln, src_txt):
                        continue
                    near = nearest(ln, src_txt)
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
        OUT.write_text(json.dumps({
            'note': old.get('note', ''),
            'generated': time.strftime('%Y-%m-%d'),
            'stats': old.get('stats', {}),
            'results': merged,
        }, ensure_ascii=False, indent=2), encoding='utf-8')

    print()
    print('取页：缓存命中 %d 次 / 真的联网取页 %d 次%s'
          % (CACHE_HITS[0], CACHE_HITS[1], '（--refresh-pages：全部重取）' if REFRESH_PAGES else ''))
    print('出处核对：%d 全对上 / %d 部分对上 / %d 一句都对不上 / %d 找不到来源页'
          % (stats['attested'], stats['partial'], stats['notfound'], stats['nosource']))
    print('带 {{另}} 夹注异文的篇目：%d 篇' % stats['withVariants'])
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
    # 坏例9：来源页换了地方必须说出来——不说，台账的数就在背后抖
    d9 = page_drift([{'id': 'a', 'page': '甲页'}], [{'id': 'a', 'page': '乙页'}])
    must(d9 == [('a', '甲页', '乙页')], '坏例9：来源页换了却没报：%s' % d9)
    must(page_drift([{'id': 'a', 'page': '甲页'}], [{'id': 'a', 'page': '甲页'}]) == [], '坏例9b：页没变也被报（误伤）')
    must(page_drift([], [{'id': 'a', 'page': '甲页'}]) == [], '坏例9c：第一次核也被当成换了页')
    must(page_drift([{'id': 'a', 'page': None}], [{'id': 'a', 'page': '甲页'}]) == [], '坏例9d：以前没有页、现在有了，不算换了页')

    print('[ok] check-text-sources --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    if '--export-variant-readings' in sys.argv:
        sys.exit(export_variant_readings())
    sys.exit(main())
