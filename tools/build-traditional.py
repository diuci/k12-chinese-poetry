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

--build 写产物；--selftest 自带坏例子。
"""
import json, re, sys, difflib, datetime
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
            cands = [x for x in cands if phrase_ok(seg, x, s2c, own_chars)] or [seg]
        else:
            cands = char_cands(seg := text[i], s2c, own_chars)
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


def page_traditional(rec):
    """本篇比对页的繁体文本（剥标点，不转简体）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location('cts_srccheck', ROOT / 'tools' / 'check-text-sources.py')
    C = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(C)
    txts = []
    for pg in (rec.get('page') or '').split(' + '):
        if not pg:
            continue
        try:
            _, raw = C.page_text(pg)
        except Exception:
            continue
        txts.append(strip_punct(strip_notes(raw)))
    return ''.join(txts)


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
    """把一篇 md 按 ## 切成节。注释译文赏析是我们自己写的现代文字，
    繁体版也要有，所以它们同样得派生、同样过闸门。"""
    secs, cur = {}, None
    for ln in md_path.read_text(encoding='utf-8').splitlines():
        if ln.startswith('## '):
            cur = ln[3:].strip()
            secs.setdefault(cur, [])
        elif cur is not None and not ln.strip().startswith('>'):
            # 「> 出处：…」「> 收录判断：…」是元信息，站点也不渲染它们；
            # 把它们当正文派生，「全文」就会多出两行，与正文派生对不上。
            secs[cur].append(ln)
    return {k: [x for x in v if x.strip()] for k, v in secs.items()}


def build():
    s2c = read_table(STC)
    s2p = read_table(STP)
    t2c = read_table(TSC)
    t2p = read_table(TSP)
    poems = json.loads(POEMS.read_text(encoding='utf-8'))['poems']
    src = {x['id']: x for x in json.loads(SRC.read_text(encoding='utf-8'))['results']}

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
        out_rows.append({'id': c['id'], 'title': c['title'], 'page': (src.get(c['id']) or {}).get('page', ''),
                         'text_trad': trad_full, 'lines_trad': trad_lines,
                         'sections_trad': sections_trad, 'labels_trad': labels_trad,
                         'marks': [m for m in marks if not m['field'].startswith('sec:')],
                         'marks_app': app_marks})

    JOUT.write_text(json.dumps({'generated': datetime.date.today().isoformat(),
                                'note': '简体正文派生的繁体。decision：page 来源页这一处亲眼写作该字（优先于表与裁定表） / '
                                        'table 表只给一个候选 / rule 按裁定表 / variant 页写的是另一个字（异文，不改字） / '
                                        'pending 没依据，留在待定清单。',
                                'counts': counts, 'counts_apparatus': counts2,
                                'reversal': reversal, 'rows': out_rows},
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
         '繁体转回简体时，%d 处与我们的正文不一样。每一处单独交代依据：' % len(reversal),
         '',
         '- **照抄**：本篇正文本来就写作这个字（徵、於、覆、藉、巘、騑、纕、嘑、絀……），'
         '繁体没动它，是表把它转成了另一个字；',
         '- **裁定 / 页**：我们有意写作另一个繁体字（锺→鍾、迹→跡 这类），依据见下面的裁定表。', '',
         '| 篇 | 差在哪个字 | 依据 | 我们写作 | 表转回成 |', '|---|---|---|---|---|',
         '']
    for x in reversal:
        L.append('| %s | **%s** | %s | %s | %s |' % (
            x['title'], x['chars'], x['basis'].replace('|', '¦'),
            x['ours'][:24].replace('|', '¦'), x['back'][:24].replace('|', '¦')))
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
          '注释译文等 table %d / rule %d / identity %d / keep %d / pending %d；可逆性不一致 %d 处 → data/traditional.json 与 docs/traditional.md'
          % (len(out_rows), counts['page'], counts['table'], counts['rule'], counts['keep'],
             counts['identity'], counts['variant'], counts['pending'],
             counts2['table'], counts2['rule'], counts2['identity'], counts2['keep'],
             counts2['pending'], len(reversal)))
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
    print('[ok] build-traditional --selftest 通（24 个坏例子全部试到）')
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    if '--build' in sys.argv:
        sys.exit(build())
    print('用法：--build / --selftest')
    sys.exit(2)
