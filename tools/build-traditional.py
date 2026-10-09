# -*- coding: utf-8 -*-
"""从简体正文派生繁体正文。

用的表是 OpenCC 的 **ST** 方向（S→T）：
  data/opencc/STPhrases.txt   词组级：一个简体词组 → 繁体写法（这一层最可靠）
  data/opencc/STCharacters.txt 单字级：一个简体字 → 繁体候选（默认在第一个）
仓里原有的 TSCharacters/TSPhrases 是反方向（T→S），只用于把繁体来源页转成简体来比对。

规矩（不可颠倒）：
  1. 简体 md 正文是唯一事实源。本工具不改 md，只写 data/traditional.json 与 docs/traditional.md。
  2. 每一处「一简对多繁」必须落到某一档，不许静默择一（优先级：页 > 裁定表 > 表）：
       page    来源页在这一处亲眼写作那个字（锚点核对过的；优先于表与裁定表）
       table   表在这一处只给出一个候选，没有选择余地
       pending 没依据 —— 留在待定清单里，页面上要看得见
     繁简同形（山、水、月）不算需要裁定，不进任何一档。
  3. 表外生僻字一律不认：候选必须是基本区汉字（U+4E00–U+9FFF），除非这个字本来就出现在本篇正文里。
     繁简表把「願」转成「𫖸」、「開」转成「𫔭」这类扩展区残迹一律拒收——那是表的脆，不是繁体字。
  4. 可逆性：派生出的繁体用 T→S 表转回去，必须一字不差等于原简体正文。回不去就是转换有问题。

--build 写产物；--selftest 自带坏例子；--allow-pages 显式许可当场取页（只有本地链条给）。
"""
import json
import sys, re, sys, difflib, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STC = ROOT / 'data' / 'opencc' / 'STCharacters.txt'
STP = ROOT / 'data' / 'opencc' / 'STPhrases.txt'
TSC = ROOT / 'data' / 'opencc' / 'TSCharacters.txt'
TSP = ROOT / 'data' / 'opencc' / 'TSPhrases.txt'
POEMS = ROOT / 'data' / 'poems.json'
LEDGER = ROOT / 'data' / 'ledger.json'
SRC = ROOT / 'data' / 'text-sources.json'
JOUT = ROOT / 'data' / 'traditional.json'
RULES = ROOT / 'data' / 's2t-rules.json'
REVC = ROOT / 'data' / 'reversal-exceptions.json'
MOUT = ROOT / 'docs' / 'traditional.md'
PUNCT = '，。！？；：、（）「」『』《》〈〉“”‘’—…·．,.;:!?()[]<>"\'\u3000\xa0'
MAXPHRASE = 8


def in_basic(c):
    return len(c) == 1 and 0x4E00 <= ord(c) <= 0x9FFF


def read_table(path):
    if not path.exists():
        raise SystemExit('缺 %s：繁简表没进仓，不许凭记忆转繁体' % path)
    table = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#') or '\t' not in line:
            continue
        key, val = line.split('\t', 1)
        key = key.strip()
        if not key:
            continue
        cands = val.split()
        if not cands:
            continue
        table.setdefault(key, [])
        for c in cands:
            if c not in table[key]:
                table[key].append(c)
    return table


def strip_punct(t):
    return ''.join(c for c in t if c not in PUNCT and not c.isspace())


def char_cands(c, s2c, own_chars):
    raw = s2c.get(c) or [c]
    return [x for x in raw if in_basic(x) or x in own_chars] or [c]


def phrase_ok(seg, cand, s2c, own_chars):
    """词组表不许改动单字表认为该照抄的那个字。

    词组表是照现代繁体习惯写的，拿去派生古籍会把字换掉：
    「古之欲明明德」→「古之慾明明德」、「吞二周」→「吞二週」、
    「百里奚」→「百裏奚」、「五溪」→「五谿」、「井干」→「井榦」。
    单字表认为这个字本来就写作这个形，词组表要换它，就是换词不是换字。"""
    if len(cand) != len(seg):
        return False
    for k, ch in enumerate(seg):
        cc = char_cands(ch, s2c, own_chars)
        if cc[0] == ch and cand[k] != ch:
            # 单字表认为这个字本来就写作这个形，词组表却要换成别的字 —— 那是换词不是换字
            return False
    return True


def convert(text, s2p, s2c, own_chars):
    """派生一行。词组表优先，单字表兜底。返回 (繁体, 需要裁定的位置)。

    默认取表的首选项 —— 表里「夫 ⇥ 夫 伕」「坐 ⇥ 坐 座」这类，首选项是照抄原字，
    后面那个是另一个词。曾经写过一版「跳过照抄项取第一个不同写法」，
    结果把「逝者如斯夫」派生成「逝者如斯伕」，被可逆性检查当场抓出来。
    """
    out, marks = [], []
    i = 0
    while i < len(text):
        seg = None
        for L in range(min(MAXPHRASE, len(text) - i), 1, -1):
            if text[i:i + L] in s2p:
                seg = text[i:i + L]
                break
        if seg is not None:
            raw = s2p[seg]
            cands = [x for x in raw if all(in_basic(y) or y in own_chars for y in x)]
            ok = [x for x in cands if phrase_ok(seg, x, s2c, own_chars)]
            # 被单字表挡下来的词组候选不许静默丢掉：那是一次真实存在的分歧。
            # 丢掉它，「两只袖子」就会悄悄留在繁体页上，谁也看不见。
            rejected = [x for x in cands if x not in ok and x != seg]
            # 被挡下来的候选仍然留在候选池里（排在后面）：默认值不变，
            # 但裁定表可以在这一步把它选出来 —— 前提是它写了理由。
            cands = (ok or [seg]) + [x for x in rejected if x not in ok]
        else:
            cands = char_cands(seg := text[i], s2c, own_chars)
            rejected = []
        default = cands[0]
        out.append(default)
        others = [x for x in cands if x != default and x != seg]
        kind = 'phrase' if len(seg) > 1 else 'char'
        ctx = text[max(0, i - 8):i + len(seg) + 8]
        if default != seg and others:
            marks.append({'at': i, 'n': len(seg), 'simp': seg, 'cands': cands,
                          'decision': 'pending', 'kind': kind, 'ctx': ctx})
        elif default != seg:
            marks.append({'at': i, 'n': len(seg), 'simp': seg, 'cands': cands,
                          'decision': 'table', 'kind': kind, 'ctx': ctx})
        elif others:
            # 表说照抄，但还给了别的写法：只有裁定表能在这里改我们的字
            marks.append({'at': i, 'n': len(seg), 'simp': seg, 'cands': cands,
                          'decision': 'identity', 'kind': kind, 'ctx': ctx})
        elif len(seg) > 1:
            # 词组表说这个词整个照抄（「倒霉 → 倒霉」）。不记一笔，
            # 后面那道「残留简体专用字必须带依据」的闸门就找不到它的理由。
            marks.append({'at': i, 'n': len(seg), 'simp': seg, 'cands': cands,
                          'decision': 'identity', 'kind': 'phrase', 'ctx': ctx})
        i += len(seg)
    return ''.join(out), marks


def to_simplified(text, t2p, t2c):
    """繁体转回简体（可逆性检查用）。"""
    out, i = [], 0
    while i < len(text):
        seg = None
        for L in range(min(MAXPHRASE, len(text) - i), 1, -1):
            if text[i:i + L] in t2p:
                seg = text[i:i + L]
                break
        if seg is not None:
            out.append(t2p[seg][0])
            i += len(seg)
            continue
        back = t2c.get(text[i])
        out.append(back[0] if back else text[i])
        i += 1
    return ''.join(out)


def load_rules():
    if not RULES.exists():
        raise SystemExit('缺 %s：一简对多繁的裁定表没进仓，不许让表的首选项替我们做决定' % RULES)
    return check_rules(json.loads(RULES.read_text(encoding='utf-8'))['rules'])


def check_rules(rules):
    for r in rules:
        if not r.get('why'):
            raise SystemExit('裁定表里「%s」没写理由：每条都必须说得出为什么这么写' % r['simp'])
        if r.get('except') and not r.get('pattern'):
            raise SystemExit('裁定表里「%s」是例外条目却没写 pattern：例外不能凭空生效' % r['simp'])
    return rules


def apply_rules(marks, rules):
    """来源页没给证据的，按裁定表落档。裁定必须在该处的候选里，否则是我们在凭空造字。"""
    for x in marks:
        if x['decision'] not in ('pending', 'identity', 'table'):
            continue
        hit = None
        for r in rules:
            if r['simp'] != x['simp']:
                continue
            if r.get('except'):
                if r.get('pattern') and r['pattern'] in x['ctx']:
                    hit = r
                    break
            elif hit is None and (x['decision'] != 'table' or r.get('apply_to_table')):
                hit = r
        if hit is None:
            continue                      # 没有规则 —— 留在 pending，不许蒙
        if hit['pick'] == x['simp']:
            # 裁定结论是照抄原字：表默认值可能已经把它换掉了（里 ⇥ 裏 里 哩），
            # 必须把 pick 也写成原字，否则正文留着表换出来的那个字。
            x['decision'] = 'identity'
            x['pick'] = x['simp']
            continue
        if hit['pick'] not in x['cands']:
            raise SystemExit('裁定表给「%s」选了「%s」，但候选里没有这个字：%s'
                             % (x['simp'], hit['pick'], '/'.join(x['cands'])))
        x['decision'] = 'rule'
        x['pick'] = hit['pick']
        x['why'] = hit['why']
        if hit.get('evidence'):
            x['evidence'] = hit['evidence']
        if hit.get('doubt'):
            x['doubt'] = True          # 裁定存疑：照这个写法走，但页面上要说明为什么存疑
        if hit.get('waive_roundtrip'):
            x['waive'] = True          # 表把罕用简体形转成了另一个字，可逆性检查会误拦


def roundtrip_ok(ours_seg, trad_seg, t2p, t2c):
    """这一处改出来的繁体字，转回简体必须还是原来那个字。

    为什么必须有：表里有一批「只给一个候选」的映射其实是另一个词——
    夫→伕、坐→座、堤→隄、具→俱、了→瞭、豆→荳、背→揹、澄→澂。
    照抄会把「逝者如斯夫」写成「逝者如斯伕」。转不回原字就是表在换词，不是繁简。"""
    if ours_seg == trad_seg:
        return True
    return to_simplified(trad_seg, t2p, t2c) == ours_seg


def vet_table_choices(trad, arr, marks, t2p, t2c, field):
    """表给的写法过不了可逆性检查的，一律退回原字，并记成 keep。"""
    kept = []
    for m in marks:
        if m['decision'] != 'table' or m['field'] != field:
            continue
        if m.get('waive'):
            continue                   # 裁定表已说明为什么放行
        ours_seg = arr[m['line']][m['at']:m['at'] + m['n']]
        trad_seg = trad[m['line']][m['at']:m['at'] + m['n']]
        if roundtrip_ok(ours_seg, trad_seg, t2p, t2c):
            continue
        trad[m['line']] = trad[m['line']][:m['at']] + ours_seg + trad[m['line']][m['at'] + m['n']:]
        m['decision'] = 'keep'
        m['kept'] = ours_seg
        m['table_wanted'] = trad_seg
        kept.append(m)
    return kept


def apply_picks(line, marks):
    """把裁定结果写回这一行（从后往前改，下标不会串位）。"""
    out = line
    for x in sorted([m for m in marks if m.get('pick')], key=lambda m: -m['at']):
        if out[x['at']:x['at'] + x['n']] == x['pick']:
            continue
        out = out[:x['at']] + x['pick'] + out[x['at'] + x['n']:]
    return out


ANGLE_RE = re.compile(r'〈[^〉]{0,24}〉')
NOTE_RE = re.compile(r'\s+(?:一[作本]|又作|或作|另有作|一本作)\s*[「『『][^」』』]{1,14}[」』』]\s*')


def strip_notes(text):
    """剥掉来源页里的校勘夹注，只留正文用字。

    维基文库的页把异文直接插在正文中间：
      「俊  彩 一作「寀」  星馳」「願 一作「贈」 君多采擷」「所共  食 一作「適」」
    不剥掉就会把注里的字读成正文用字 —— 曾经把「俊采」派生成「俊寀」。
    夹注是「这一处另有写法」的线索，不是「这一处写作那个字」的证据。"""
    text = ANGLE_RE.sub('', text)
    return NOTE_RE.sub(' ', text)


# 取页这件事必须显式许可。CI 里前一步的自检（check-text-sources --selftest、check-variant-sources --selftest 等）
# 会把当场抓回来的页写进 data/page-cache——那一轮 build-traditional 要是照用这些页，产物就不是同一份产物：
# 同一个提交连着红了两轮，三套档位数字都是这么来的。默认不取页，只有 --allow-pages 才取。
ALLOW_PAGES = '--allow-pages' in sys.argv

def page_from_cache(C, title):
    """只认缓存里已有的页：缓存里没有这一页就返回 None，不许当场取页。"""
    if not ALLOW_PAGES:
        return None
    try:
        if not C._cache_file(title).exists():
            return None
    except Exception:
        return None
    try:
        _, raw = C.page_text(title)
    except Exception:
        return None
    return raw


def page_traditional(rec):
    """本篇比对页的繁体文本（剥标点，不转简体）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location('cts_srccheck', ROOT / 'tools' / 'check-text-sources.py')
    C = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(C)
    # 页证据只认缓存里已有的页。缓存里没有就不取——CI 里当场抓回来的页与本地那份不是同一份
    # （页改过、抓一半失败、只抓到半页都会发生），拿它当证据就是拿运气当证据。
    # 判据不能是「缓存目录在不在」：CI 里别的工具会把空目录建出来。
    txts = []
    for pg in (rec.get('page') or '').split(' + '):
        if not pg:
            continue
        raw = page_from_cache(C, pg)
        if raw is None:
            continue
        txts.append(strip_punct(strip_notes(raw)))
    return ''.join(txts)


def apply_recorded(x, ctx, rec):
    """这一轮这一处没有页可查时，沿用上一份已提交产物里同一处的页证据。
    页说话优先：有页可查且页给出了答案，永远不会走到这里（调用方只在 res 为空时才调）。
    沿用必须同一处：篇、字段、行、位置、问的字、上下文逐字相同，差一个字符就不沿用——
    正文改过之后把旧证据贴到新位置上，比没有证据更危险。"""
    if not rec:
        return False
    if rec.get('decision') not in ('page', 'variant'):
        return False
    if strip_punct(rec.get('ctx') or '') != ctx or rec.get('simp') != x['simp'] or rec.get('at') != x['at']:
        return False
    if rec.get('field') != x.get('field') or rec.get('line') != x.get('line'):
        return False
    x['decision'] = rec['decision']
    x['page_char'] = rec.get('page_char')
    x['from_record'] = True
    if rec.get('pick'):
        x['pick'] = rec['pick']
    if 'in_ledger' in rec:
        x['in_ledger'] = rec['in_ledger']
    return True


def page_char_for(ctx, simp, page, page_s):
    """在页里找这段上下文的最佳窗口，读出页在这一处实际写作的那个字。

    页是繁体、我们的上下文是简体，直接找字符串永远对不上（共享字形太少，
    「吾闻竹工云」这种五个字里只有一个字同形的锚点全数落空）。
    所以先把页转成简体来定位（转简是一一对应的，下标不串位），
    再回读繁体原页上的那个字。"""
    if not ctx or not page:
        return None
    off = ctx.find(simp)
    if off < 0:
        return None
    starts = set()
    short = 4 if len(ctx) >= 6 else max(2, len(ctx) - 1)
    for a in (ctx[:short], ctx[-short:], ctx[max(0, off - 2):off],
              ctx[off + len(simp):off + len(simp) + short]):
        if len(a) < 2:
            continue
        i = page_s.find(a)
        while i >= 0:
            starts.add(i - ctx.find(a))
            i = page_s.find(a, i + 1)
    best = None
    for s in sorted(starts):
        if s < 0 or s >= len(page_s):
            continue
        # 来源页里夹着校勘注（茅屋为秋风所破歌的页写作「多年冷似一作象铁」），
        # 页比我们多几个字是常态，所以窗口允许放宽，用顺序对齐而不是定长比对。
        for extra in range(0, 13):
            e = s + len(ctx) + extra
            if e > len(page_s):
                break
            w = page_s[s:e]
            matched, mapped = 0, None
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ctx, w, autojunk=False).get_opcodes():
                if tag == 'equal':
                    matched += i2 - i1
                    if i1 <= off < i2:
                        mapped = j1 + (off - i1)
                elif tag == 'replace' and i1 <= off < i2 and (off - i1) < (j2 - j1):
                    mapped = j1 + (off - i1)
            # 除了我们问的这个字，其余每一个字都必须在页里按顺序对上；
            # 对不上就是窗口歪到了隔壁句子（「报任安书 于→重」那种假异文）。
            if mapped is None or matched < len(ctx) - 1:
                continue
            best = (matched, s, mapped)
            break
        if best:
            break
    if best is None:
        return None
    matched, s, mapped = best
    diffs = [] if page_s[s + mapped] == ctx[off] else [off]
    return page[s + mapped], diffs, off


SKIP_SECTIONS = {'玩法数据', '出处核对'}


def md_sections(md_path):
    """把一篇 md 按 ## 切成节，与站点 parse_poem 同一套切法。
    小学结构里 H1 之后没有 H2，正文直接跟着——那一节站点叫「正文」，
    繁体派生也必须切出同一节，否则简体页有这一节、繁体页没有。"""
    secs, cur = {}, None
    seen_h1 = False
    for ln in md_path.read_text(encoding='utf-8').splitlines():
        s = ln.strip()
        if s.startswith('# '):
            seen_h1 = True
            cur = None
            continue
        if s.startswith('## '):
            cur = s[3:].strip()
            secs.setdefault(cur, [])
            continue
        if s.startswith('>'):
            # 「> 出处：…」「> 收录判断：…」是元信息，站点也不渲染它们
            continue
        if cur is None:
            if not seen_h1:
                continue
            cur = '正文'
        secs.setdefault(cur, []).append(ln)
    return {k: [x for x in v if x.strip()] for k, v in secs.items()}


def load_reversal_exceptions(path=None):
    """可逆性例外的登记表。缺文件、缺字段、转回与原字相同、重复登记——都直接停，不许含糊。"""
    path = path or REVC
    if not path.exists():
        raise SystemExit('缺 %s：可逆性不一致必须逐条裁定并登记，不许只列出来不裁定' % REVC)
    entries = (json.loads(path.read_text(encoding='utf-8')).get('entries') or [])
    table, seen = {}, set()
    for e in entries:
        for k in ('id', 'simp', 'trad', 'back', 'why', 'basis'):
            if not str(e.get(k) or '').strip():
                raise SystemExit('可逆性例外登记缺「%s」：%s' % (k, json.dumps(e, ensure_ascii=False)[:140]))
        if e['simp'] == e['back']:
            raise SystemExit('可逆性例外登记里「%s」转回还是「%s」——这一条不是例外，是废话' % (e['simp'], e['back']))
        key = (e['id'], e['simp'], e['trad'], e['back'])
        if key in seen:
            raise SystemExit('可逆性例外登记重复：%s' % ('/'.join(key),))
        seen.add(key)
        table[key] = e
    return table
def check_reversal_registration(rev_exc, rev_used, reversal):
    """登记表两边都要拦：这一轮没用上的登记条目必须删掉（过期登记比没有登记更误导人）；
    没登记的不一致不许写进产物。"""
    unused = [k for k in rev_exc if k not in rev_used]
    if unused:
        raise SystemExit('[繁体派生] 可逆性例外登记里有 %d 条这一轮没用上（表改了还是正文改了？过期登记必须删）：%s'
                         % (len(unused), '；'.join('%s %s→%s（转回 %s）' % k for k in sorted(unused))))
    open_ends = [x for x in reversal if x['unexplained']]
    if open_ends:
        raise SystemExit('[繁体派生] 可逆性不一致里有 %d 处说不出凭什么（必须先在 %s 里登记裁定与依据）：%s'
                         % (len(open_ends), REVC, '、'.join(x['unexplained'][0] for x in open_ends)))


def build():
    s2c = read_table(STC)
    s2p = read_table(STP)
    t2c = read_table(TSC)
    t2p = read_table(TSP)
    poems = json.loads(POEMS.read_text(encoding='utf-8'))['poems']
    src = {x['id']: x for x in json.loads(SRC.read_text(encoding='utf-8'))['results']}
    # 页证据要么来自 data/page-cache（不入库：统编教材是版权作品），要么当场联网取页。
    # CI 里两者都没有：那一轮这些位置就退回表，产物不再是同一份产物——
    # 同一份简体正文，两次构建给出不同的繁体字，这是最坏的一种不一致。
    # 所以没有页可查的那些处沿用上一份已提交产物里的记录（逐字同一处才沿用）。
    recorded = {}
    if JOUT.exists():
        try:
            prev = json.loads(JOUT.read_text(encoding='utf-8'))
        except Exception:
            prev = {}
        for row in prev.get('rows', []):
            for m in (row.get('marks') or []):
                if m.get('decision') in ('page', 'variant'):
                    recorded[(row['id'], m.get('field'), m.get('line'), m.get('at'), m.get('simp'))] = m
            for t in (row.get('page_marks') or []):
                recorded[(row['id'], t[0], t[1], t[2], t[3])] = {'field': t[0], 'line': t[1], 'at': t[2],
                    'simp': t[3], 'ctx': t[4], 'page_char': t[5], 'decision': t[6], 'pick': t[7] or None}
                if t[8] is not None:
                    recorded[(row['id'], t[0], t[1], t[2], t[3])]['in_ledger'] = t[8]
    used_record = [0]

    def as_list(v):
        if isinstance(v, str):
            return [v]
        return list(v or [])

    counts = {'page': 0, 'table': 0, 'rule': 0, 'keep': 0, 'identity': 0, 'variant': 0, 'pending': 0}
    # 注释译文赏析（现代文字）单独计数：它们没有来源页可查，只能靠裁定表与表
    counts2 = {'table': 0, 'rule': 0, 'identity': 0, 'keep': 0, 'pending': 0}
    # 台账里已经记过的异文（md 的「一作 / 另有作」那一行），用来判断页读出来的异文是不是新主张
    md_variant = {}
    if LEDGER.exists():
        for row in json.loads(LEDGER.read_text(encoding='utf-8'))['rows']:
            f = ROOT / row['path']
            if not f.exists():
                continue
            lines = []
            for ln in f.read_text(encoding='utf-8').splitlines():
                if '一作' in ln or '另有作' in ln or '一本作' in ln or '一作' in ln:
                    lines.append(ln)
            md_variant[row['id']] = '\n'.join(lines)
    rules = load_rules()
    reversal = []
    rev_exc = load_reversal_exceptions()
    rev_used = set()
    left_behind = []
    AUDIT = [] if '--audit-left' in sys.argv else None
    out_rows = []
    for c in poems:
        full = as_list(c.get('fullLinesPunct') or c.get('fullLines'))
        lines = as_list(c.get('linesPunct') or c.get('lines'))
        own = set(''.join(full)) | set(''.join(lines))
        trad_full, trad_lines, marks = [], [], []
        flat, spans = [], []
        for field, arr in (('full', full), ('lines', lines)):
            for li, seg in enumerate(arr):
                tt, mm = convert(seg, s2p, s2c, own)
                (trad_full if field == 'full' else trad_lines).append(tt)
                stripped = strip_punct(seg)
                flat.append(stripped)
                spans.append((field, li, len(flat) - 1, stripped))
                for x in mm:
                    x['field'] = field
                    x['line'] = li
                    marks.append(x)
        # ---- 标题 / 作者 / 朝代 / 学段 / 册次 / 体裁 / 标签：页面上要显示的字 ----
        labels_trad = {}
        for k in ('title', 'subtitle', 'author', 'dynasty', 'stage', 'volume', 'form', 'recite', 'textbookStatus'):
            v = c.get(k)
            if not isinstance(v, str) or not v:
                continue
            tt, mm = convert(v, s2p, s2c, own | set(v))
            for x in mm:
                x['field'] = 'label:' + k
                x['line'] = 0
            apply_rules(mm, rules)
            vet_table_choices([tt], [v], mm, t2p, t2c, 'label:' + k)
            if any(m.get('pick') for m in mm):
                tt = apply_picks(tt, mm)
            for ch in tt:
                if ch in s2c and ch not in s2c[ch] and ch not in own and ch not in set(v):
                    raise SystemExit('繁体标签「%s」里留下简体字「%s」（%s·%s）' % (v, ch, c['title'], k))
            labels_trad[k] = tt
        for k in ('theme', 'technique', 'tags'):
            vs = c.get(k) or []
            out_list = []
            for v in vs:
                if not isinstance(v, str) or not v:
                    continue
                tt, mm = convert(v, s2p, s2c, own | set(v))
                for x in mm:
                    x['field'] = 'label:' + k
                    x['line'] = 0
                apply_rules(mm, rules)
                vet_table_choices([tt], [v], mm, t2p, t2c, 'label:' + k)
                if any(m.get('pick') for m in mm):
                    tt = apply_picks(tt, mm)
                out_list.append(tt)
            if out_list:
                labels_trad[k] = out_list
        page = page_traditional(src.get(c['id']) or {})
        page_s = to_simplified(page, t2p, t2c)
        # ---- 正文之外的每一节：同样派生、同样过页证据、同样过闸门 ----
        # 注释译文里也引用古籍原句，那些句子同样该由来源页说话，
        # 否则同一篇里正文写「踏裏裂」、注释写「踏里裂」，一页两种字形。
        sections_trad, sec_src = {}, {}
        md_path = ROOT / c['_path'] if c.get('_path') else None
        if md_path and md_path.exists():
            secs = md_sections(md_path)
            for name in [k for k in secs if k not in SKIP_SECTIONS]:
                arr = secs.get(name) or []
                if not arr:
                    continue
                own2 = own | set(''.join(arr))
                trad_arr, mm = [], []
                for li, seg in enumerate(arr):
                    tt, m = convert(seg, s2p, s2c, own2)
                    trad_arr.append(tt)
                    for x in m:
                        x['field'] = 'sec:' + name
                        x['line'] = li
                        mm.append(x)
                marks += mm
                sections_trad[name] = trad_arr
                sec_src[name] = arr
        for x in marks:
            if x['decision'] not in ('pending', 'table'):
                continue
            ctx = strip_punct(x['ctx'])
            if not ctx or x['n'] != 1:
                continue            # 只认单字：词组在页里只对得上半个字，那种错位见过
            res = page_char_for(ctx, x['simp'], page, page_s)
            if not res:
                if apply_recorded(x, ctx, recorded.get((c['id'], x.get('field'), x.get('line'), x['at'], x['simp']))):
                    used_record[0] += 1
                continue
            got, diffs, off = res
            # 上下文少于三个字不足以定位。页与我们的差异只有两种合法形状：
            #   0 处 = 页在这一处写作同样的字（确认）
            #   1 处且差在我们问的这一处 = 页写作另一个字（推翻表 / 异文）
            if len(ctx) < 3 or len(diffs) > 1 or (len(diffs) == 1 and diffs[0] != off):
                continue
            if got in x['cands']:
                # 来源页在这一处亲眼写作某个候选写法：与表一致是确认，不一致是推翻表。
                # 无论哪种，裁定表都不许再动这一处 —— 页优先。
                # 「踏裏裂」（页作裏）、「孤雲獨去閑」（页作閑）都是这一档定下来的。
                x['decision'] = 'page'
                x['page_char'] = got
                if got != x['cands'][0]:
                    x['pick'] = got
            elif (got not in x['cands'] and got != x['simp']
                  and x['simp'] in x['cands']
                  and to_simplified(got, t2p, t2c) != x['simp']):
                # 我们这个字本身就是繁体里可用的写法（候选里有照抄项），
                # 而页在这一处写的是另一个字 —— 那是异文，不是繁简，照抄我们的用字。
                # 滕王阁序「俊采」：五处来源页全作「俊彩」（页内夹注「彩 一作寀」）。
                x['decision'] = 'variant'
                x['page_char'] = got
                x['pick'] = x['simp']
                # 这条异文台账里记过吗？记过 = 我们早就核对过并写了出处；
                # 没记过 = 页里确实这么写，但我们没核过，页面上必须写成「台账未记」，不许冒充已核。
                x['in_ledger'] = bool(got) and got in md_variant.get(c['id'], '')
        apply_rules(marks, rules)
        vet_table_choices(trad_full, full, marks, t2p, t2c, 'full')
        vet_table_choices(trad_lines, lines, marks, t2p, t2c, 'lines')
        for field, arr, trad in (('full', full, trad_full), ('lines', lines, trad_lines)):
            for li in range(len(arr)):
                sel = [m for m in marks if m['field'] == field and m['line'] == li]
                if any(m.get('pick') for m in sel):
                    arr[li] = arr[li]
                    trad[li] = apply_picks(trad[li], sel)
        for x in marks:
            if not x['field'].startswith('sec:'):
                counts[x['decision']] += 1
        # 闸门：繁体正文里不许留下只有简体才用的字（表把它换掉、我们却没换 = 繁体页上出现简体字）
        for field, trad in (('full', trad_full), ('lines', trad_lines)):
            for seg in trad:
                for ch in seg:
                    if ch in s2c and ch not in s2c[ch] and ch not in own:
                        raise SystemExit('繁体派生留下简体字「%s」（%s·%s）：表要求换成 %s，'
                                         '这一处的裁定必须给出繁体写法' % (ch, c['title'], field, s2c[ch][0]))
        for name, trad_arr in sections_trad.items():
            arr = sec_src[name]
            vet_table_choices(trad_arr, arr, marks, t2p, t2c, 'sec:' + name)
            for li in range(len(arr)):
                sel = [m for m in marks if m['field'] == 'sec:' + name and m['line'] == li]
                if any(m.get('pick') for m in sel):
                    trad_arr[li] = apply_picks(trad_arr[li], sel)
            own2 = own | set(''.join(arr))
            for seg in trad_arr:
                for ch in seg:
                    if ch in s2c and ch not in s2c[ch] and ch not in own2:
                        raise SystemExit('繁体「%s」节里留下简体字「%s」（%s）：表要求换成 %s，'
                                         '这一处的裁定必须给出写法' % (name, ch, c['title'], s2c[ch][0]))
        # 同一篇不许出现两种繁体：正文派生与「全文 / 必背名句」节的派生必须逐字一致
        for name, want in (('全文', trad_full), ('必背全文', trad_full), ('必背名句', trad_lines)):
            got = sections_trad.get(name)
            if not got or not want:
                continue
            a = ''.join(strip_punct(x) for x in got)
            b = ''.join(strip_punct(x) for x in want)
            if a != b:
                raise SystemExit('同一篇里两种繁体对不上：%s「%s」这一节的派生与正文派生不一致'
                                 % (c['title'], name))
        # 注释译文那几节只登记说得清依据的档：待定、裁定、退回、异文，
        # 以及「页推翻了表」的 page（页与表一致的那种确认不存，存下来文件大到没法读）
        app_marks = [x for x in marks if x['field'].startswith('sec:')
                     and (x['decision'] in ('pending', 'rule', 'keep', 'variant')
                          or (x['decision'] == 'page' and x.get('pick')))]
        for x in marks:
            if x['field'].startswith('sec:'):
                counts2[x['decision']] = counts2.get(x['decision'], 0) + 1
        for field, arr, trad in (('full', full, trad_full), ('lines', lines, trad_lines)):
            for li, (seg, tt) in enumerate(zip(arr, trad)):
                back = to_simplified(tt, t2p, t2c)
                if back != seg:
                    sel = [m for m in marks if m['field'] == field and m['line'] == li]
                    pairs, basis, unexplained = [], [], []
                    for k in range(min(len(seg), len(back))):
                        if seg[k] == back[k]:
                            continue
                        pairs.append('%s→%s' % (seg[k], back[k]))
                        tk = tt[k] if k < len(tt) else ''
                        ex = rev_exc.get((c['id'], seg[k], tk, back[k]))
                        if ex:
                            rev_used.add((c['id'], seg[k], tk, back[k]))
                            basis.append('登记例外（%s）：%s' % ('正文本来就写作这个字' if tk == seg[k] else '有意写作另一个繁体字', ex['why']))
                            continue
                        if k >= len(tt) or tt[k] == seg[k]:
                            basis.append('照抄')  # 本篇正文本来就写作这个字
                            continue
                        why = ''
                        for m in sel:
                            if not (m['at'] <= k < m['at'] + max(1, m['n'])):
                                continue
                            if m['decision'] == 'rule' and m.get('why'):
                                why = '裁定「%s」：%s' % (m['pick'], m['why'])
                                break
                            if m['decision'] in ('page', 'variant') and m.get('page_char'):
                                why = '来源页作「%s」' % m['page_char']
                                break
                        if why:
                            basis.append(why)
                        else:
                            basis.append('（说不通）')
                            unexplained.append('%s·%s' % (c['title'], seg[k]))
                    reversal.append({'id': c['id'], 'title': c['title'], 'field': field, 'line': li,
                                     'ours': seg, 'trad': tt, 'back': back,
                                     'chars': '、'.join(pairs) or '（长度不同）',
                                     'basis': '；'.join(dict.fromkeys(basis)),
                                     'unexplained': unexplained})
        # ---- 繁体文本里留下的「只有简体才用的字」：每一处都要说得出为什么 ----
        # 这些字不是漏网：来源页写作这个形、或正文自己就写作这个形（古籍用字，
        # 词组表不许换它）。说不出为什么的，当场失败，不许留在产物里。
        # ---- 繁体文本里留下的「只有简体才用的字」：每一处都要说得出为什么 ----
        def name_of(_ch):
            for _n, _a in sec_src.items():
                for _l in _a:
                    if _ch in _l:
                        return _n
            for _l in list(full) + list(lines):
                if _ch in _l:
                    return '正文'
            for _k, _v in labels_trad.items():
                if _ch in (_v if isinstance(_v, str) else ''.join(_v)):
                    return 'label:' + _k
            return '?'
        pairs = []
        for _i, _tt in enumerate(trad_full):
            pairs.append((_tt, full[_i] if _i < len(full) else ''))
        for _i, _tt in enumerate(trad_lines):
            pairs.append((_tt, lines[_i] if _i < len(lines) else ''))
        for _name, _arr in sections_trad.items():
            _src = sec_src.get(_name) or []
            for _i, _tt in enumerate(_arr):
                pairs.append((_tt, _src[_i] if _i < len(_src) else ''))
        for _k, _v in labels_trad.items():
            _sv = c.get(_k)
            if isinstance(_v, list):
                _ss = c.get(_k) or []
                for _i, _tt in enumerate(_v):
                    pairs.append((_tt, _ss[_i] if _i < len(_ss) else ''))
            else:
                pairs.append((_v, _sv if isinstance(_sv, str) else ''))
        QUOTE = re.compile(r'「[^」]*」|“[^”]*”')
        left = {}
        for _tt, _st in pairs:
            quoted = set(''.join(QUOTE.findall(_st)))
            for ch in _tt:
                if ch not in s2c or ch in s2c[ch] or ch in left:
                    continue
                why = None
                for x in marks:
                    hit = None
                    if x.get('pick') == ch or x.get('kept') == ch:
                        hit = '单字'
                    elif len(x['simp']) > 1 and (ch in (x.get('pick') or '') or ch in (x.get('kept') or '')):
                        hit = '词组'
                    elif x['simp'] == ch and x['decision'] in ('identity', 'keep'):
                        hit = '照抄'
                    elif len(x['simp']) > 1 and x['decision'] == 'identity' and ch in x['simp']:
                        hit = '词组表说这个词照抄'
                    if hit:
                        why = '%s（%s）：%s' % (
                            x['decision'], hit,
                            x.get('why') or x.get('page_char') or x.get('table_wanted')
                            or '表与页都说这个字本来就写作这个形')
                        break
                if why is None and ch in page:
                    # 表把某个字列在简体一侧，来源页却亲眼写作这个形：
                    # 古籍里的异体字（如「𢧐」）常落在这种位置，照页，不照表
                    why = '来源页写作这个形：表把它列在简体一侧，页上却是这个字'
                if why is None and ch in own:
                    why = '正文自己写作这个形：单字表认为它本来就写作这个字，词组表不许换它'
                if why is None and ch in quoted:
                    # 异文一节引的是别本 / 来源页夹注里的写法，带出处，不是我们的用字
                    why = '引文：这一处引的是别本或来源页夹注的写法，出处已写在同一行'
                if why is None:
                    if AUDIT is not None:
                        AUDIT.append((c['title'], name_of(ch), ch))
                        why = '（待裁定）'
                    else:
                        raise SystemExit('[繁体派生] %s：繁体文本里留下只有简体才用的字「%s」，'
                                         '却说不出凭什么 —— 不许留在产物里' % (c['title'], ch))
                left[ch] = why

        left_behind.extend({'id': c['id'], 'title': c['title'], 'char': k, 'why': v}
                           for k, v in sorted(left.items()))

        out_rows.append({'id': c['id'], 'title': c['title'], 'page': (src.get(c['id']) or {}).get('page', ''),
                         'text_trad': trad_full, 'lines_trad': trad_lines,
                         'sections_trad': sections_trad, 'labels_trad': labels_trad,
                         'marks': [{k: v for k, v in m.items() if k != 'from_record'}
                                   for m in marks if not m['field'].startswith('sec:')],
            'page_marks': [[m['field'], m['line'], m['at'], m['simp'], m['ctx'], m.get('page_char'),
                            m['decision'], m.get('pick') or '', m.get('in_ledger')]
                           for m in marks if m['field'].startswith('sec:')
                           and m['decision'] in ('page', 'variant')],
                         'marks_app': [{k: v for k, v in m.items() if k != 'from_record'} for m in app_marks],
                         'left_behind': [{'char': k, 'why': v} for k, v in sorted(left.items())]})

    if AUDIT is not None:
        import collections
        cnt = collections.Counter((_w, ch) for _t, _w, ch in AUDIT)
        ex = {}
        for _t, _w, ch in AUDIT:
            ex.setdefault((_w, ch), _t)
        print('[诊断] 说不出凭据的残留简体专用字：%d 处' % len(AUDIT))
        for (where, ch), v in sorted(cnt.items(), key=lambda x: -x[1]):
            print('  %s ×%-4d %-10s 例：%s' % (ch, v, where, ex[(where, ch)]))
        raise SystemExit(0)

    # 登记表两边都要拦：这一轮没用上的登记条目必须删掉（过期登记比没有登记更误导人）；
    # 没登记的不一致不许写进产物。
    check_reversal_registration(rev_exc, rev_used, reversal)
    # 产物里不写当场日期：闸门比的是逐字节，而日期取决于跑它的那台机器的时区与当天——
    # 本地 UTC+8 的深夜写 2026-10-10、CI 的 UTC 写 2026-10-09，同一份输入两份产物。要时间找 git。
    JOUT.write_text(json.dumps({
                                'note': '简体正文派生的繁体。decision：page 来源页这一处亲眼写作该字（优先于表与裁定表） / '
                                        'table 表只给一个候选 / rule 按裁定表 / variant 页写的是另一个字（异文，不改字） / '
                                        'pending 没依据，留在待定清单。',
                                'counts': counts, 'counts_apparatus': counts2,
                                'reversal': reversal, 'left_behind': left_behind,
                                'rows': out_rows},
                               ensure_ascii=False, indent=1), encoding='utf-8')
    BT = chr(96)
    L = ['# 繁体版：每一处「一简对多繁」是怎么定的', '',
         '> 这一页由 ' + BT + 'tools/build-traditional.py' + BT + ' 生成，不要手改。',
         '> 简体 md 正文是唯一事实源；繁体是派生物，每一处都要说得出依据。', '',
         '## 总数', '',
         '| 档 | 处数 | 依据 |', '|---|---|---|',
         '| page | %d | 来源页在这一处亲眼写作那个字（确认或推翻表；裁定表不许再动） |' % counts['page'],
         '| table | %d | 表在这一处只给出一个候选 |' % counts['table'],
         '| rule | %d | 按 data/s2t-rules.json 裁定（每条带理由） |' % counts['rule'],
         '| keep | %d | 表给的写法转不回原字，正文照抄原字（表在换词，不是繁简） |' % counts['keep'],
         '| identity | %d | 繁简同形，照抄原字 |' % counts['identity'],
         '| variant | %d | 表要换字，但来源页那一处写的是另一个字 —— 那是异文，正文照抄我们的用字 |' % counts['variant'],
         '| pending | %d | 没依据 —— 待定，不许当成已定 |' % counts['pending'], '',
         '',
         '正文之外的每一节（注释、译文、赏析、全文、异文、收录范围、考点……；玩法数据与出处核对除外）另外计数：'
         'table %d / rule %d / identity %d / keep %d / pending %d。'
         '这几节没有来源页可查，依据只有裁定表和表；表只给一个候选时照表，'
         '给多个候选而裁定表没说的，列进下面的待定清单。'
         % (counts2['table'], counts2['rule'], counts2['identity'],
            counts2['keep'], counts2['pending']), '',
         '## 可逆性（繁体转回简体必须一字不差）', '',
          ('繁体转回简体时，%d 处与我们的正文不一样。每一处都在 ' + BT + 'data/reversal-exceptions.json' + BT + ' 里登记了裁定与依据（%d 条）：') % (len(reversal), len(rev_exc)),
          '没登记的就写不出产物；登记了却这一轮没用上的，也会被闸门拦下。',
         '- **照抄**：本篇正文本来就写作这个字（徵、於、覆、藉、巘、騑、纕、嘑、絀……），'
         '繁体没动它，是表把它转成了另一个字；',
         '- **裁定 / 页**：我们有意写作另一个繁体字（锺→鍾、迹→跡 这类），依据见下面的裁定表。', '',
         '| 篇 | 差在哪个字 | 依据 | 我们写作 | 表转回成 |', '|---|---|---|---|---|',
         '']
    for x in reversal:
        L.append('| %s | **%s** | %s | %s | %s |' % (
            x['title'], x['chars'], x['basis'].replace('|', '¦'),
            x['ours'][:24].replace('|', '¦'), x['back'][:24].replace('|', '¦')))
    L += ['', '## 可逆性例外的登记（逐条裁定，来自 data/reversal-exceptions.json）', '',
          '| 篇 | 正文里的字 | 繁体写作 | 表转回成 | 为什么 | 凭什么 |', '|---|---|---|---|---|---|', '']
    for k in sorted(rev_exc, key=lambda x: (x[0], x[1])):
        e = rev_exc[k]
        L.append('| %s | **%s** | %s | %s | %s | %s |' % (
            e['id'], e['simp'], e['trad'], e['back'],
            e['why'].replace('|', '¦'), e['basis'].replace('|', '¦')))
    L += ['', '## 表被拒用的写法（转不回原字）', '',
          '| 原字 | 表想写成 | 处数 |', '|---|---|---|', '']
    rejected = {}
    for r in out_rows:
        for m in r['marks']:
            if m['decision'] == 'keep':
                k = (m['kept'], m['table_wanted'])
                rejected[k] = rejected.get(k, 0) + 1
    for (kept, wanted), c in sorted(rejected.items(), key=lambda kv: (-kv[1], kv[0][0])):
        L.append('| %s | %s | %d |' % (kept, wanted, c))
    L += ['',
         '## 裁定表（每一处为什么这么写）', '',
         '| 简 | 写作 | 理由 | 处数 |', '|---|---|---|---|',
         '']
    used = {}
    for r in out_rows:
        for m in r['marks']:
            if m['decision'] == 'rule':
                used[(m['simp'], m['pick'], m['why'])] = used.get((m['simp'], m['pick'], m['why']), 0) + 1
    for (simp, pick, why), c in sorted(used.items(), key=lambda kv: (-kv[1], kv[0][0])):
        doubt = any(m.get('doubt') for r in out_rows for m in r['marks']
                    if m['decision'] == 'rule' and (m['simp'], m['pick'], m['why']) == (simp, pick, why))
        L.append('| %s | %s | %s%s | %d |' % (simp, pick, why, '（存疑）' if doubt else '', c))
    L += ['', '## 来源页在这一处写的是另一个字（异文）', '',
          '正文照抄我们的用字，不改。台账里记过的，说明我们早就核过并写了出处；',
          '**台账未记的只是「页里这么写」，我们没核过，不许当成已核的异文。**', '',
          '| 篇 | 我们写作 | 页写作 | 台账 | 上下文 |', '|---|---|---|---|---|',
          '']
    for r in out_rows:
        for m in r['marks']:
            if m['decision'] == 'variant':
                L.append('| %s | %s | %s | %s | %s |' % (
                    r['title'], m['simp'], m['page_char'],
                    '已记' if m.get('in_ledger') else '**未记**',
                    m['ctx'].replace('|', '¦')[:34]))
    L += ['', '## 待定清单', '']
    for r in out_rows:
        pend = [m for m in (r['marks'] + r.get('marks_app', [])) if m['decision'] == 'pending']
        if not pend:
            continue
        L.append('### %s（%d 处）' % (r['title'], len(pend)))
        for m in pend:
            where = '正文' if m['field'] in ('full', 'lines') else m['field'][4:]
            L.append('- 「%s」候选 %s ｜ 位置：%s ｜ 上下文：%s'
                     % (m['simp'], '/'.join(m['cands']), where, m['ctx']))
        L.append('')
    MOUT.write_text('\n'.join(L), encoding='utf-8')
    print('[繁体派生] %d 篇：正文 page %d / table %d / rule %d / keep %d / identity %d / variant %d / pending %d；'
          '注释译文等 table %d / rule %d / identity %d / keep %d / pending %d；可逆性不一致 %d 处（登记裁定 %d 条）；沿用已提交页证据 %d 处 → data/traditional.json 与 docs/traditional.md'
          % (len(out_rows), counts['page'], counts['table'], counts['rule'], counts['keep'],
             counts['identity'], counts['variant'], counts['pending'],
             counts2['table'], counts2['rule'], counts2['identity'], counts2['keep'],
             counts2['pending'], len(reversal), len(rev_exc), used_record[0]))
    return 0


def selftest():
    s2c = {'愿': ['願', '𫖸'], '干': ['幹', '干', '乾'], '開': ['開', '\U0002B6ED'], '山': ['山']}
    s2p = {'中國': ['中國'], '干戈': ['干戈']}
    own = set()
    # 坏例1：表外生僻字（扩展区）不许进产物
    t, _ = convert('願望', {}, {'願': ['願', '𫖸']}, own)
    assert '𫖸' not in t, '坏例1：表外生僻字 𫖸 被当成了繁体字'
    t, _ = convert('開門', s2p, s2c, own)
    assert '\U0002B6ED' not in t, '坏例1b：扩展区残迹被当成了繁体字'
    # 坏例2：一简对多繁不许静默择一（单字级没有词组可依时，必须落 pending）
    t2, m2 = convert('干', s2p, s2c, own)
    pend = [x for x in m2 if x['decision'] == 'pending']
    assert pend and pend[0]['simp'] == '干' and len(pend[0]['cands']) >= 2, '坏例2：一简对多繁被静默择一了'
    # 坏例2b：词组表能消歧时不许再报单字待定（否则待定里全是噪音）
    _, m2b = convert('干戈', {'干戈': ['干戈']}, s2c, own)
    assert not any(x['decision'] == 'pending' for x in m2b), '坏例2b：词组表已经定了还报待定'
    # 坏例3：繁简同形不算需要裁定
    t3, m3 = convert('山', s2p, s2c, own)
    assert t3 == '山' and not m3, '坏例3：繁简同形被算成需要裁定'
    # 坏例4：词组表给出唯一写法时可以用，但必须记档（改了字就要说得出依据）
    t4, m4 = convert('后门', {'后门': ['後門']}, {'后': ['後', '后'], '门': ['門']}, set())
    assert t4 == '後門' and m4 and m4[0]['decision'] == 'table', '坏例4：词组表改了字没记档'
    # 坏例5：本篇正文里本来就有的扩展区字不许被拒（生僻字不是表外残迹）
    rare = '\U00020818'
    t5, _ = convert(rare, {}, {rare: [rare]}, set(rare))
    assert t5 == rare, '坏例5：仓内本来就有的生僻字被拒掉了'
    # 坏例6：可逆性检查必须真的会转
    assert to_simplified('後', {}, {'後': ['后']}) == '后', '坏例6：可逆性检查连单字回转都不会做'
    assert to_simplified('乾', {'乾坤': ['乾坤']}, {'乾': ['干']}) == '干', '坏例6b：可逆性检查的词组优先没生效'
    # 坏例7：裁定表选了候选之外的字，必须当场拦下（不许凭空造字）
    marks = [{'at': 0, 'n': 1, 'simp': '干', 'cands': ['幹', '干', '乾'], 'decision': 'pending',
              'kind': 'char', 'ctx': '干戈'}]
    bad = [{'simp': '干', 'pick': '杆', 'why': '瞎写的'}]
    try:
        apply_rules(marks, bad)
        raise AssertionError('坏例7：裁定表凭空造字没被拦下')
    except SystemExit:
        pass
    # 坏例8：没有规则的待定不许被蒙掉
    marks2 = [{'at': 0, 'n': 1, 'simp': '囧', 'cands': ['囧', '迥'], 'decision': 'pending', 'kind': 'char', 'ctx': '囧'}]
    apply_rules(marks2, [{'simp': '干', 'pick': '幹', 'why': '别的字'}])
    assert marks2[0]['decision'] == 'pending', '坏例8：没有规则时被偷偷定了'
    # 坏例9：例外条目必须优先于默认条目
    marks3 = [{'at': 1, 'n': 1, 'simp': '发', 'cands': ['發', '髮', '发'], 'decision': 'pending',
               'kind': 'char', 'ctx': '白发三千丈'}]
    apply_rules(marks3, [{'simp': '发', 'pick': '發', 'why': '发出义'},
                         {'simp': '发', 'pick': '髮', 'why': '头发义', 'except': True, 'pattern': '白发'}])
    assert marks3[0]['pick'] == '髮', '坏例9：例外没优先于默认'
    # 坏例10：例外条目没写 pattern 必须被拦
    try:
        check_rules([{'simp': '发', 'pick': '髮', 'why': '头发义', 'except': True}])
        raise AssertionError('坏例10：例外条目没写 pattern 没被拦下')
    except SystemExit:
        pass
    # 坏例11：裁定必须真的写回正文
    assert apply_picks('白發三千丈', [{'at': 1, 'n': 1, 'pick': '髮'}]) == '白髮三千丈', '坏例11：裁定没写回正文'
    # 坏例12：表给的写法转不回原字（换词了），必须被拒用
    arr = ['逝者如斯夫']
    trad = ['逝者如斯伕']
    marks = [{'at': 4, 'n': 1, 'simp': '夫', 'cands': ['伕', '夫'], 'decision': 'table', 'kind': 'char',
              'field': 'full', 'line': 0, 'ctx': '逝者如斯夫'}]
    kept = vet_table_choices(trad, arr, marks, {}, {}, 'full')   # 表里根本没有 伕→夫 这条，转不回原字
    assert kept and trad[0] == '逝者如斯夫', '坏例12：表换词的写法没被拒用'
    assert marks[0]['decision'] == 'keep', '坏例12：拒用没记档'
    # 坏例12b：表把照抄项放在首位时，不许跳到那个「另一个词」
    tt, mm = convert('逝者如斯夫', {}, {'夫': ['夫', '伕']}, set())
    assert tt == '逝者如斯夫', '坏例12b：照抄项被跳过，派生成伕了'
    assert mm and mm[0]['decision'] == 'identity', '坏例12b：照抄但另有候选没记成 identity'
    # 坏例13：正常繁简转换不许被误拒
    arr2 = ['明月几时有']
    trad2 = ['明月幾時有']
    marks2 = [{'at': 2, 'n': 1, 'simp': '几', 'cands': ['幾'], 'decision': 'table', 'kind': 'char',
               'field': 'full', 'line': 0, 'ctx': '明月几时有'},
              {'at': 3, 'n': 1, 'simp': '时', 'cands': ['時'], 'decision': 'table', 'kind': 'char',
               'field': 'full', 'line': 0, 'ctx': '明月几时有'},
              {'at': 2, 'n': 1, 'simp': '几', 'cands': ['幾'], 'decision': 'table', 'kind': 'char',
               'field': 'lines', 'line': 0, 'ctx': '明月几时有'}]
    assert not vet_table_choices(trad2, arr2, marks2, {}, {'幾': ['几'], '時': ['时']}, 'full'), '坏例13：正常的繁简转换被误拒了'
    # 坏例13b：full 与 lines 两档不许互相串台
    assert vet_table_choices(trad2, arr2, marks2, {}, {'幾': ['几'], '時': ['时']}, 'lines') == [], '坏例13b：两档之间串台了'
    # 坏例16：罕用简体形（锺）按裁定放行后，可逆性检查不许再把它打回去
    arr3 = ['锺子期']
    trad3 = ['鍾子期']
    marks3b = [{'at': 0, 'n': 1, 'simp': '锺', 'cands': ['鍾'], 'decision': 'table', 'kind': 'char',
                'field': 'full', 'line': 0, 'ctx': '锺子期'}]
    apply_rules(marks3b, [{'simp': '锺', 'pick': '鍾', 'why': '教材用字', 'apply_to_table': True,
                           'waive_roundtrip': True}])
    assert marks3b[0]['waive'] is True, '坏例16：放行标记没生效'
    assert not vet_table_choices(trad3, arr3, marks3b, {}, {'鍾': ['钟']}, 'full'), '坏例16：已放行的写法仍被可逆性检查打回'
    assert trad3[0] == '鍾子期', '坏例16：放行后正文被改回了罕用简体形'
    # 坏例17：来源页写作照抄原字时，不许被表默认值改掉
    rows = [{'id': 'x', 'title': '竹楼', 'text': ['吾闻竹工云'], 'lines': [], 'page': 'P'}]
    marks = [{'at': 4, 'n': 1, 'simp': '云', 'cands': ['雲', '云'], 'decision': 'table', 'kind': 'char',
              'field': 'full', 'line': 0, 'ctx': '吾闻竹工云'}]
    pg = '吾聞竹工云，竹之爲瓦'
    r17 = page_char_for(strip_punct('吾闻竹工云'), '云', pg, to_simplified(pg, {}, {'聞': ['闻'], '爲': ['为'], '之': ['之'], '瓦': ['瓦']}))
    assert r17 and r17[0] == '云' and r17[1] == [], '坏例17：页上明明写作「云」却没读出来 ' + repr(r17)
    # 坏例17b：页上写作「雲」时要读成「雲」，不许读错
    pg2 = '人閑桂花落'
    r17b = page_char_for('人闲桂花落', '闲', pg2, to_simplified(pg2, {}, {'閑': ['闲']}))
    assert r17b and r17b[0] == '閑' and r17b[1] == [], \
        '坏例17b：页上写作「閑」没读出来 ' + repr(r17b)   # 閑 转简就是 闲，与我们的字同形，差异 0 处
    # 坏例17c：页里这一句跟我们差好几个字（对不上），不许当证据
    pg3 = '春风又到江南岸明月'
    r17c = page_char_for('春风又绿江南岸何月', '绿', pg3, pg3)
    assert not r17c, '坏例17c：对不上的页被当成了证据 ' + repr(r17c)
    # 坏例17d：页里夹着校勘注（多出来几个字）不许把证据打掉
    pg4 = '多年冷似一作象铁娇儿恶卧踏里裂床头屋漏无干处'
    r17d = page_char_for('似铁娇儿恶卧踏里裂床头屋漏无干', '里', '多年冷似一作象鐵嬌兒惡臥踏裏裂床頭屋漏無乾處', pg4)
    assert r17d and r17d[0] == '裏', '坏例17d：页里的校勘注把证据打掉了 ' + repr(r17d)
    # 坏例17e：页里的校勘夹注不许被读成正文用字
    raw17 = '雄州霧列，俊  彩 一作「寀」  星馳。臺隍枕夷夏之交'
    pg17 = strip_punct(strip_notes(raw17))
    assert '寀' not in pg17, '坏例17e：夹注没剥掉 ' + pg17
    pg17_s = to_simplified(pg17, {}, {'霧': ['雾'], '馳': ['驰'], '臺': ['台'], '列': ['列'], '隍': ['隍']})
    assert len(pg17_s) == len(pg17), '坏例17e：转简后字数变了，下标会串位'
    r17e = page_char_for('俊采星驰台隍', '采', pg17, pg17_s)
    assert r17e and r17e[0] == '彩', '坏例17e：页的正文用字没读出来 ' + repr(r17e)
    # 坏例18：表要换字，但页写的是另一个字（异文），必须照抄我们的用字
    rows2 = [{'id': 'y', 'title': '滕王阁序', 'text': ['俊采星馳'], 'lines': [], 'page': 'P'}]
    # 页在这一处写作「彩」：不是「采」的繁简对子，是异文（锚点法在纯繁体页上对不齐，
    # 仓里这类是靠整篇全局对齐读出来的，这里直接给读到的结果）
    got = '彩'
    trad4 = ['俊採星馳']
    arr4 = ['俊采星驰']
    marks4 = [{'at': 1, 'n': 1, 'simp': '采', 'cands': ['採', '采', '寀'], 'decision': 'table', 'kind': 'char',
               'field': 'full', 'line': 0, 'ctx': '俊采星驰'}]
    if got and got not in marks4[0]['cands'] and got != marks4[0]['simp']:
        marks4[0]['decision'] = 'variant'
        marks4[0]['pick'] = marks4[0]['simp']
    assert apply_picks(trad4[0], marks4) == '俊采星馳', '坏例18：异文被当成繁简转换改了字'
    # 坏例19：词组只对上半个字的错位，不许被当成异文
    marks5 = [{'at': 0, 'n': 2, 'simp': '万里', 'cands': ['萬里'], 'decision': 'table', 'kind': 'phrase',
               'field': 'full', 'line': 0, 'ctx': '万里'}]
    trad5 = ['萬里']
    arr5 = ['万里']
    got5 = '萬'
    veto5 = (got5 and marks5[0]['n'] == 1 and marks5[0]['decision'] == 'table'
             and got5 not in marks5[0]['cands'] and got5 != marks5[0]['simp']
             and to_simplified(got5, {}, {'萬': ['万']}) != marks5[0]['simp'])
    assert not veto5, '坏例19：词组半个字的错位被当成异文拦了'
    # 坏例20：页上的字是我们这个字的繁简对应字时，不算异文（为/爲 这种）
    assert to_simplified('爲', {}, {'爲': ['为']}) == '为', '坏例20：繁简对应字没认出来'
    # 坏例20b：页里根本没有这一句（只有别的句子），不许当证据
    pg3 = '溯洄从之蒹葭萋萋白露未晞'
    assert page_char_for('道阻且长溯游从之', '长', pg3, pg3) is None, \
        '坏例20b：页里没有这一句却被当成了证据 ' + repr(page_char_for('道阻且长溯游从之', '长', pg3, pg3))
    # 坏例20b2：页里这一句与我们差三个字，不许当证据
    pg3b = '道阻且长溯洄从之宛在水中坻'
    assert page_char_for('道阻且右溯游从之宛在水中沚', '右', pg3b, pg3b) is None, \
        '坏例20b2：差三个字的句子被当成了证据 ' + repr(page_char_for('道阻且右溯游从之宛在水中沚', '右', pg3b, pg3b))
    # 坏例20c：同一页里本章与隔壁章都在（蒹葭「道阻且长／道阻且跻」），必须取全对得上的那一处
    pg3c = '道阻且长溯洄从之道阻且跻溯游从之'
    r20c = page_char_for('道阻且长溯洄从之', '长', pg3c, pg3c)
    assert r20c and r20c[0] == '长', '坏例20c：读到了隔壁章 ' + repr(r20c)
    # 坏例21：词组表要换单字表认为该照抄的字，必须被否掉
    assert not phrase_ok('之欲', '之慾', {'欲': ['欲', '慾'], '之': ['之']}, set()), '坏例21：之欲→之慾 没被否掉'
    assert phrase_ok('万里', '萬里', {'万': ['萬'], '里': ['里', '裏']}, set()), '坏例21b：正常的万里→萬里 被误否'
    assert not phrase_ok('百里奚', '百裏奚', {'百': ['百'], '里': ['里', '裏'], '奚': ['奚']}, set()), '坏例21c：百里奚→百裏奚 没被否掉'
    # 坏例21e：单字表本来就要换字的（干→幹），词组表换成同族另一个字（乾）不许被否
    assert phrase_ok('不干', '不乾', {'不': ['不'], '干': ['幹', '乾', '干', '榦']}, set()), '坏例21e：不乾 被误否'
    # 坏例22：窗口差两个字（对歪到隔壁句子）不算证据
    pg = '青青子衿悠悠我心'
    pg_s = to_simplified(pg, {}, {'青': ['青'], '子': ['子'], '衿': ['衿']})
    r22 = page_char_for('悠悠我思悠悠', '思', pg, pg_s)
    assert (not r22) or len(r22[1]) != 1 or r22[1][0] != r22[2], '坏例22：对歪的窗口被当成了证据 ' + repr(r22)
    assert convert('吞二周而亡诸侯', {'二周': ['二週']}, {'二': ['二'], '周': ['周'], '吞': ['吞'], '诸': ['諸'], '而': ['而'], '亡': ['亡'], '侯': ['侯']}, set())[0] == '吞二周而亡諸侯', \
        '坏例21d：吞二周被派生成二週'
    # 坏例23：「征」这一支必须两头都站得住——正文照抄「征」，「象征」「魏征」必须转成「徵」。
    # 不裁定时表的首选项是「徵」：同一篇里正文作「征帆」、注释作「徵帆」就是这么来的。
    marks23 = [{'at': 3, 'n': 1, 'simp': '征', 'cands': ['徵', '征'], 'decision': 'table', 'kind': 'char', 'ctx': '翠峰如簇征帆去棹残阳'},
               {'at': 1, 'n': 1, 'simp': '征', 'cands': ['徵', '征'], 'decision': 'table', 'kind': 'char', 'ctx': '明月象征知遇'},
               {'at': 1, 'n': 1, 'simp': '征', 'cands': ['徵', '征'], 'decision': 'table', 'kind': 'char', 'ctx': '这是魏征的处境'}]
    apply_rules(marks23, [{'simp': '征', 'pick': '征', 'why': '征伐行旅义照抄「征」', 'apply_to_table': True},
                          {'simp': '征', 'pick': '徵', 'why': '象征义作「徵」', 'except': True, 'pattern': '象征'},
                          {'simp': '征', 'pick': '徵', 'why': '人名魏徵', 'except': True, 'pattern': '魏征'}])
    assert marks23[0]['pick'] == '征' and marks23[0]['decision'] == 'identity', '坏例23：正文那一支没照抄「征」'
    assert marks23[1]['pick'] == '徵', '坏例23：「象征」没转成「象徵」'
    assert marks23[2]['pick'] == '徵', '坏例23：「魏征」没转成「魏徵」'
    # 坏例23b：真实裁定表里这三条必须都在，且例外排在默认之后也能赢（apply_rules 扫完全部规则）
    _real = load_rules()
    assert any(r['simp'] == '征' and r['pick'] == '征' and r.get('apply_to_table') for r in _real), '坏例23b：表里没有「征→征」这条'
    assert any(r['simp'] == '征' and r['pick'] == '徵' and r.get('pattern') == '象征' for r in _real), '坏例23b：表里没有「象征→徵」这条'
    assert any(r['simp'] == '征' and r['pick'] == '徵' and r.get('pattern') == '魏征' for r in _real), '坏例23b：表里没有「魏征→徵」这条'
    # 坏例24：这一轮没有页可查时沿用已提交的记录——只许沿用「同一处」的记录。
    # CI 里没有页缓存也不许联网；不沿用就退回表：同一份简体正文两次构建给出不同的繁体字。
    _rec = {'id': 'x', 'field': 'full', 'line': 0, 'at': 4, 'simp': '云', 'ctx': '吾闻竹工云', 'decision': 'page', 'page_char': '云'}
    def _fresh():
        return {'at': 4, 'n': 1, 'simp': '云', 'cands': ['雲', '云'], 'decision': 'table', 'kind': 'char', 'ctx': '吾闻竹工云', 'field': 'full', 'line': 0}
    _m = _fresh()
    ok24 = apply_recorded(_m, '吾闻竹工云', _rec)
    assert ok24 and _m['decision'] == 'page' and _m['page_char'] == '云' and _m.get('from_record'), '坏例24：同一处的页证据没沿用'
    _m = _fresh()
    assert (not apply_recorded(_m, '吾闻竹工云云', _rec)) and _m['decision'] == 'table' and not _m.get('page_char'), '坏例24b：正文改过（上下文不同）还把旧页证据贴到新位置'
    # 坏例24h：产物里存的上下文带标点，查询用的是剥过标点的上下文——同一处必须认出来。
    # 先前就是漏在这一条上：认不出同一处，「沿用」等于没做，CI 里那些位置照样退回表。
    _m = _fresh()
    _rec_punct = dict(_rec)
    _rec_punct['ctx'] = '吾闻竹工云，'
    assert apply_recorded(_m, '吾闻竹工云', _rec_punct) is True and _m.get('from_record'), \
        '坏例24h：产物里带标点的上下文认不出同一处，沿用等于没做'
    _m = _fresh()
    _rec_far = dict(_rec)
    _rec_far['ctx'] = '吾闻竹工云，木兰'
    assert not apply_recorded(_m, '吾闻竹工云', _rec_far), '坏例24h2：窗口更长（多出一截正文）却当成了同一处'
    _m = _fresh()
    _m['at'] = 5
    assert not apply_recorded(_m, '吾闻竹工云', _rec), '坏例24c：位置挪了一位也照抄旧记录（正文加过字，下标会串位）'
    _m = _fresh()
    _m['field'] = 'lines'
    assert not apply_recorded(_m, '吾闻竹工云', _rec), '坏例24d：正文那一档的记录被贴到了必背名句那一档上'
    _m = _fresh()
    _bad_rec = dict(_rec)
    _bad_rec['decision'] = 'table'
    assert (not apply_recorded(_m, '吾闻竹工云', _bad_rec)) and _m['decision'] == 'table', '坏例24e：表的结论被当成了页证据'
    _m = _fresh()
    assert (not apply_recorded(_m, '吾闻竹工云', None)) and _m['decision'] == 'table', '坏例24f：既没有页也没有记录，却被判成有页证据'
    _m = _fresh()
    assert apply_recorded(_m, '吾闻竹工云', _rec) and 'in_ledger' not in _m, \
        '坏例24j：沿用给这一处添了一个本地没有的键——产物就不是同一份产物了'
    # 坏例24k / 24l：页证据只认缓存里已有的页。缓存里没有这一页还不许去取——
    # CI 里当场抓回来的页与本地那份不是同一份，同一份简体正文就会生成两份繁体产物。
    class _FakeSrc:
        def __init__(self, has):
            self.has = has
            self.fetched = 0
        def _cache_file(self, title):
            if self.has:
                return ROOT / 'data' / 'opencc' / 'STCharacters.txt'
            return ROOT / 'data' / '这一页不在缓存里.json'
        def page_text(self, title):
            self.fetched += 1
            return (title, '頁裡的内容')
    global ALLOW_PAGES
    ALLOW_PAGES = True
    _no = _FakeSrc(False)
    assert page_from_cache(_no, '某页') is None and _no.fetched == 0, \
        '坏例24k：缓存里没有这一页还是去取了页'
    _yes = _FakeSrc(True)
    assert page_from_cache(_yes, '某页') == '頁裡的内容' and _yes.fetched == 1, \
        '坏例24l：缓存里已有这一页却没用到'
    # 坏例24m：默认不许取页。CI 里前一步的自检会把当场抓回来的页写进 data/page-cache，
    # 那一轮照用这些页，同一个提交就会生成另一套档位数字（连着红两轮就是这么来的）。
    ALLOW_PAGES = False
    assert page_from_cache(_yes, '某页') is None and _yes.fetched == 1, \
        '坏例24m：没给 --allow-pages 也去取页——CI 里那些页是前一步自检当场抓的，不是同一份证据'
    _trad = json.loads(JOUT.read_text(encoding='utf-8')) if JOUT.exists() else {}
    # 坏例24g：产物里不许留下「这一轮没有页可查」这种只有这一轮才有的标记。
    # CI 那一轮没有页缓存、本地那一轮有：留下标记，同一份简体正文就会生成两份不一样的产物。
    assert not any(m.get('from_record') for _r in _trad.get('rows', []) for m in (_r.get('marks') or [])), \
        '坏例24g：产物里留下了 from_record 标记'
    assert not any(len(t) > 9 for _r in _trad.get('rows', []) for t in (_r.get('page_marks') or [])), \
        '坏例24g：page_marks 里留下了这一轮特有的标记'
    assert 'page_from_record' not in _trad, '坏例24g：沿用处数写进了产物（那一轮才有意义，产物必须是同一份）'
    # 坏例24i：注释/全文/必背名句那一档的页证据也必须存进产物。只存正文那一半，
    # CI 里那一档就没有记录可用，退回表，正文与「全文」两档当场对不上。
    _pm = [t for _r in _trad.get('rows', []) for t in (_r.get('page_marks') or [])]
    _ca = _trad.get('counts_apparatus', {})
    assert len(_pm) == _ca.get('page', 0) + _ca.get('variant', 0), \
        '坏例24i：产物里存的页证据 %d 条，与注释那一档当场数到的 page %d + variant %d 对不上' % (len(_pm), _ca.get('page', 0), _ca.get('variant', 0))
    assert all(t[0].startswith('sec:') and t[6] in ('page', 'variant') for t in _pm), \
        '坏例24i：page_marks 里混进了不该有的条目'

    # 坏例25 系列：可逆性例外的登记表。闸门两边都要拦——没登记的不许写进产物，
    # 登记了却没用上的也不许留在表里。这一串坏例子全用临时文件，不碰仓里的登记表。
    import tempfile
    _tmpdir = tempfile.mkdtemp()
    def _write_rev(name, obj):
        p = ROOT / '_selftest-rev-tmp' / name
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        return p
    try:
        # 坏例25：登记表文件不存在也照样往下走
        try:
            load_reversal_exceptions(ROOT / '_selftest-rev-tmp' / '没有这个文件.json')
            raise AssertionError('坏例25：可逆性例外登记表不存在也照样往下走')
        except SystemExit:
            pass
        # 坏例25b：登记缺依据
        try:
            load_reversal_exceptions(_write_rev('b.json', {'entries': [
                {'id': 'x', 'simp': '乾', 'trad': '乾', 'back': '干', 'why': '表有损'}]}))
            raise AssertionError('坏例25b：登记没写凭什么也收下了')
        except SystemExit:
            pass
        # 坏例25c：转回还是原字，这一条不是例外
        try:
            load_reversal_exceptions(_write_rev('c.json', {'entries': [
                {'id': 'x', 'simp': '後', 'trad': '後', 'back': '後', 'why': '表有损', 'basis': '正文原字'}]}))
            raise AssertionError('坏例25c：「转回还是原字」的条目也收下了')
        except SystemExit:
            pass
        # 坏例25d：同一条重复登记
        try:
            _one = {'id': 'x', 'simp': '乾', 'trad': '乾', 'back': '干', 'why': '表有损', 'basis': '正文原字'}
            load_reversal_exceptions(_write_rev('d.json', {'entries': [_one, dict(_one)]}))
            raise AssertionError('坏例25d：同一条登记重复也收下了')
        except SystemExit:
            pass
        # 坏例25e：登记了却这一轮没用上（过期登记）
        try:
            check_reversal_registration({('x', '乾', '乾', '干'): _one}, set(), [])
            raise AssertionError('坏例25e：过期登记留在表里也没人管')
        except SystemExit:
            pass
        # 坏例25f：不一致没登记就写进产物
        try:
            check_reversal_registration({}, set(), [{'unexplained': ['某篇·乾']}])
            raise AssertionError('坏例25f：说不出凭什么的不一致照样进产物')
        except SystemExit:
            pass
        # 坏例25g：登记表必须与产物里那些不一致严丝合缝——多一条、少一条都算失败
        _trip = set()
        for _x in _trad.get('reversal', []):
            _o, _t, _b = _x['ours'], _x['trad'], _x['back']
            for _k in range(min(len(_o), len(_b))):
                if _o[_k] != _b[_k]:
                    _trip.add((_x['id'], _o[_k], _t[_k] if _k < len(_t) else '', _b[_k]))
        if _trip:
            _reg = set(load_reversal_exceptions())
            assert _reg == _trip, ('坏例25g：登记表与产物里的可逆性不一致对不上（登记 %d 条，产物 %d 处不同）：%s'
                                   % (len(_reg), len(_trip), '、'.join(sorted('/'.join(k) for k in (_reg - _trip) | (_trip - _reg)))))
    finally:
        import shutil
        shutil.rmtree(ROOT / '_selftest-rev-tmp', ignore_errors=True)

    import ast, inspect
    # 坏例子个数当场从这份源码数出来：数 assert 语句与「必须抛错」的 try 块本身，
    # 先前数的是源码文本里 'assert ' 与 'try:' 出现几次——把计数那一行自己也数了进去。
    _tree = ast.parse(inspect.getsource(selftest))
    _n = sum(1 for _x in ast.walk(_tree) if isinstance(_x, ast.Assert))
    _n += sum(1 for _x in ast.walk(_tree)
              if isinstance(_x, ast.Try) and any(isinstance(_s, ast.Raise) for _s in _x.body))
    print('[ok] build-traditional --selftest 通（%d 处断言全部试到）' % _n)
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    if '--build' in sys.argv:
        sys.exit(build())
    print('用法：--build [--allow-pages] / --selftest（默认不取页：页证据沿用已提交产物里同一处的记录）')
    sys.exit(2)
