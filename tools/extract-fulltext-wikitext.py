# -*- coding: utf-8 -*-
"""从维基文库的 wikitext 里取「这一页自己认定的正文」，并把夹注异文一并收出来。

为什么要读 wikitext 而不是渲染后的页面：
  {{另|甲|乙}} 渲染后是一个带悬停提示的 span，剥掉标签只剩主文，别本看不见；
  而渲染成纯文本时，很多页面会把「一作乙」直接混在正文里——照搬就把注释当成正文。
  wikitext 里第一个参数才是本页用字，第二个参数才是别本。

规矩：
  {{另|甲|乙}} / {{另2|甲|…}} → 正文取甲，乙登记成异文；
  {{ul|甲}}（专名加下划线）→ 取甲；
  <ref>…</ref> 是校勘笔记 → 丢，但记下丢了几条；
  不认识的模板 → 丢，并且**报出来**，不许静默吞掉。

本工具只产出候选（data/fulltext-candidates.json），**不写正文**。
候选要进仓，必须逐行过第二来源，并且有人判断完整性。
"""
import json, re, sys, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'fulltext-candidates.json'
SPEC = importlib.util.spec_from_file_location('cts', ROOT / 'tools' / 'check-text-sources.py')
# 最里层的模板先解：{{另|六龍{{另|回|迴}}日之高標|橫河斷海之浮雲}} 这种嵌套，
# 从外层切会切错。用 rfind 找最后一个 {{ 再往后配对，天然就是最里层。
# 注意 -{云}- 这种语言转换标记里也有花括号，不能简单用 [^{}] 排除。
def find_innermost(s):
    i = s.rfind('{{')
    if i < 0:
        return None
    depth, j = 1, i + 2
    while j < len(s):
        if s.startswith('{{', j):
            depth += 1; j += 2; continue
        if s.startswith('}}', j):
            depth -= 1
            if depth == 0:
                return (i, j + 2, s[i + 2:j])
            j += 2; continue
        j += 1
    return None
LINK = re.compile(r'\[\[([^\]|]*)\|([^\]]*)\]\]')
LINK2 = re.compile(r'\[\[([^\]]*)\]\]')
CONV = re.compile(r'-\{([^{}]+)\}-')
TAG = re.compile(r'</?(?:poem|CENTER|div|small|onlyinclude|br)[^>]*>', re.I)


def _params(body):
    """按 | 切参数，但不切进嵌套的 {{}} 或 -{}- 里。"""
    parts, depth, cur = [], 0, []
    i = 0
    while i < len(body):
        ch = body[i]
        if body.startswith('{{', i):
            depth += 1
            cur.append('{{'); i += 2; continue
        if body.startswith('}}', i):
            depth -= 1
            cur.append('}}'); i += 2; continue
        if ch == '|' and depth == 0:
            parts.append(''.join(cur)); cur = []; i += 1; continue
        cur.append(ch); i += 1
    parts.append(''.join(cur))
    return parts


def strip_inline_notes(text):
    """把渲染文本里混进正文的夹注摘掉，只留本页用字。

    《李太白全集/卷三》里的夹注比想象的脏：「奔流到萧本作倒海不复回」「请君谓我倾萧本8203作侧耳听」
    「但愿𫖸长醉不用一作复萧本作愿𫖸醒」——既有「萧本作某」，也有页码残迹混在里面。
    只认「一作某」的话，逐行核会报 2/13，那是工具的错，不是书的错。"""
    NOTE = re.compile(r'(?:[一二又别他旧通行]本?作|萧本作|萧本\d*作|\d{3,}作)\s*[^，、。；！？\s]{1,14}')
    t = text
    for _ in range(8):
        t2 = NOTE.sub('', t)
        if t2 == t:
            break
        t = t2
    t = re.sub(r'\d{3,}', '', t)
    return t


# 这些模板的内容不是正文：{{注|…}} 是校勘笔记，{{reflist}} 是注释列表，{{Header}} 是页头。
DROP_TEMPLATES = {'注', 'reflist', 'notes', 'header', 'header2', 'textquality', 'defaultsort',
                  'academictextquality', 'spoken_wikisource', 'smallrefs', 'noinclude', 'license',
                  'pd-old', 'pd-old-exact', '北宋作品', '唐朝作品', '唐詩三百首', '清诗', '宋诗'}


def resolve(wt):
    """返回 (正文, 异文列表, 丢掉的模板名列表, 丢掉的 ref 数)。"""
    variants, dropped = [], []
    wt = re.sub(r'<ref[^>/]*/>', '', wt)
    nref = len(re.findall(r'<ref', wt))
    wt = re.sub(r'<ref[^>]*>.*?</ref>', '', wt, flags=re.S)
    for _ in range(200):
        m = find_innermost(wt)
        if not m:
            break
        i0, i1, body = m
        params = _params(body)
        name = params[0].strip().lower()
        if name in ('另', '另2'):
            main = params[1] if len(params) > 1 else ''
            alt = params[2] if len(params) > 2 else ''
            if alt.strip():
                variants.append((main.strip(), alt.strip()))
            repl = main
        elif name == 'ul':
            repl = params[1] if len(params) > 1 else ''
        elif name in ('textquality', 'header', 'header2', '唐朝作品', '唐詩三百首',
                      'spoken_wikisource', 'defaultsort', 'academictextquality'):
            repl = ''
        elif name in DROP_TEMPLATES:
            dropped.append(params[0].strip())
            repl = ''
        else:
            # 不认识的模板不能一律丢掉：{{ProperNoun|琅琊}} 的第一个参数就是正文本体。
            # 丢掉它，正文就成了「望之蔚然而深秀者，也。」——专名全没了，句子还是通的，
            # 所以这种错不会被读出来，只会在逐行核里表现为一大片对不上。
            first = params[1] if len(params) > 1 else ''
            plain = first.strip()
            if plain and '=' not in plain and re.match(r'^[\u4e00-\u9fff，、。；！？：（）\s]+$', plain):
                dropped.append(params[0].strip() + '（取第一个参数）')
                repl = first
            else:
                dropped.append(params[0].strip())
                repl = ''
        wt = wt[:i0] + repl + wt[i1:]
    wt = LINK.sub(lambda x: x.group(2), wt)
    wt = LINK2.sub('', wt)
    wt = CONV.sub(lambda x: x.group(1).split(';')[0].split(':')[-1], wt)
    wt = TAG.sub('\n', wt)
    # == 注釋 == 这种小节标题可能和正文粘在同一行，得就地切开，不能只按整行判断。
    wt = re.sub(r'={2,}[^=\n]+={2,}', '\n', wt)
    while find_innermost(wt):
        i0, i1, _ = find_innermost(wt)
        wt = wt[:i0] + wt[i1:]
    lines = [x.strip() for x in wt.splitlines()]
    lines = [x for x in lines if x and not x.startswith('Category:')]
    # <templatestyles …/> 与 ---- 这种分隔线不是正文。
    lines = [x for x in lines if '<templatestyles' not in x.lower() and x.strip('-— ') != '']
    # == 注釋 == 这种小节标题不是正文。
    lines = [x for x in lines if not re.match(r'^==+[^=]*==+$', x.strip())]
    return '\n'.join(lines), variants, dropped, nref


def selftest():
    wt = '{{另|六龍{{另|回|迴}}日之高標|橫河斷海之浮雲}}'
    t, v, d, _ = resolve(wt)
    assert t == '六龍回日之高標', '坏例1：嵌套的另没从最里层解：%r' % t
    assert ('回', '迴') in v and ('六龍回日之高標', '橫河斷海之浮雲') in v, '坏例2：嵌套异文没收全：%r' % v

    t, v, d, n = resolve('君不見，{{另|高堂|牀頭}}明鏡悲白髮<ref>敦煌殘卷無此句</ref>。')
    assert t == '君不見，高堂明鏡悲白髮。', '坏例3：ref 或模板残迹漏进正文：%r' % t
    assert n == 1, '坏例4：丢掉的 ref 没计数'

    t, v, d, _ = resolve('{{ul|錦城}}雖{{另|-{云}-|言}}樂。')
    assert t == '錦城雖云樂。', '坏例5：-{…}- 转换没做：%r' % t

    t, v, d, _ = resolve('{{另2|天生我材必有用|一作「天生吾徒有俊材」，又作「天生我身必有財」}}')
    assert t == '天生我材必有用', '坏例6：另2 的主文没取对：%r' % t
    assert v and '天生吾徒有俊材' in v[0][1], '坏例7：另2 的别本没登记'

    t, v, d, _ = resolve('{{SomeUnknownTemplate|甲}}乙[[Category:唐詩]]')
    # 不认识的模板：第一个参数是纯正文的，取第一个参数（{{ProperNoun|琅琊}} 那种）；
    # 带 key=value 的，是模板参数不是正文，丢掉。
    assert t == '甲乙', '坏例8：纯正文参数的模板被丢掉了：%r' % t
    t, v, d, _ = resolve('{{SomeTemplate|key=value}}乙')
    assert t == '乙', '坏例8b：带 key=value 的模板参数漏进正文：%r' % t
    t, v, d, _ = resolve('{{SomeUnknownTemplate|甲}}乙')
    assert d == ['SomeUnknownTemplate（取第一个参数）'], '坏例9：丢掉的模板没报出来（或吞正文没标注）：%r' % d

    # 专名模板的第一个参数就是正文本体，丢掉它正文就成了「…者，也。」
    t, v, d, _ = resolve('望之蔚然而深秀者，{{ProperNoun|琅琊}}也。山之僧曰{{ProperNoun|智仙}}也。')
    assert t == '望之蔚然而深秀者，琅琊也。山之僧曰智仙也。', '坏例11：专名模板把正文本体吞掉了：%r' % t
    t, v, d, _ = resolve('酿泉为酒{{注|一本作让泉}}。==注釋==')
    assert t == '酿泉为酒。', '坏例12：校勘笔记或小节标题漏进正文：%r' % t

    t, v, d, _ = resolve('{{另|甲|乙}}')
    assert t == '甲' and v == [('甲', '乙')], '坏例10：最基本的情况都错了'
    print('[ok] extract-fulltext-wikitext --selftest 通（12 个坏例子全部被拦住）')
    return 0


def main(ids):
    C = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(C)
    table = C.load_t2s()
    np = lambda s: re.sub(r'[\W_]+', '', s or '', flags=re.UNICODE)
    records = {r['id']: r for r in json.loads((ROOT / 'data' / 'text-sources.json').read_text(encoding='utf-8'))['results']}
    out = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    out.setdefault('说明', '候选全文。进仓前必须逐行过第二来源，并有人判断完整性。')
    out.setdefault('candidates', {})
    for pid in ids:
        rec = records.get(pid)
        if not rec:
            print('  %s：没有比对记录' % pid); continue
        pages = (rec.get('page') or '').split(' + ')
        done = False
        for pg in pages:
            try:
                _, wt = C.page_wikitext(pg)
            except Exception:
                continue
            if len(wt) < 400:
                continue
            body, variants, dropped, nref = resolve(wt)
            if len(body) < 200:
                continue
            lines = [x for x in body.splitlines() if x]
            # 第二来源逐行核
            others = [p for p in pages if p != pg]
            otext = ''
            for op in others:
                try:
                    _, raw = C.page_text(op)
                    tt, _ = C.clean(raw, table)
                    otext += tt
                except Exception:
                    pass
            # 第二来源是「渲染成纯文本」的页面，夹注混在正文里（「四萬八千歲不一作乃與秦塞通人煙」。
            # 不先把这些「一作某」摘掉，逐行核就永远是 1/27——那是工具的错，不是书的错。
            oj = np(otext)
            # wikitext 是繁体，第二来源的渲染文本被转成了简体：不比一遍繁简，
            # 「蜀道之難」永远对不上「蜀道之难」，逐行核永远是 0。
            conf = 0
            units = 0
            unconfirmed = []
            cmp_lines = []
            for ln in lines:
                # 先按句切，再逐句做繁简转换：clean() 会把标点全部剥掉，
                # 先转换后切句就切不动了——一整段当一个单位，散文页永远核不过。
                for unit in re.split(r'(?<=[。！？；])', ln):
                    try:
                        sc, _ = C.clean(unit, table)
                    except Exception:
                        sc = unit
                    k = np(sc)
                    if not k:
                        continue
                    units += 1
                    if not C.subseq_window(k, oj, 25):
                        unconfirmed.append(unit)
                    else:
                        conf += 1
            out['candidates'][pid] = {
                'page': pg, 'url': rec.get('url') or '',
                'lines': lines, 'chars': sum(len(np(x)) for x in lines),
                'secondSource': others, 'confirmedBySecond': conf, 'totalUnits': units, 'totalLines': len(lines),
                'unconfirmedBySecond': unconfirmed,
                'variants': [{'main': a, 'alt': b} for a, b in variants],
                'droppedTemplates': sorted(set(dropped)), 'droppedRefs': nref,
            }
            print('  %s ← %s：%d 行 / %d 字；第二来源按句核到 %d/%d 句；夹注异文 %d 条；丢掉模板 %s / ref %d 条'
                  % (pid, pg, len(lines), out['candidates'][pid]['chars'], conf, units, len(variants),
                     sorted(set(dropped)) or '无', nref))
            done = True
            break
        if not done:
            print('  %s：这一篇的来源页没有可用的 wikitext（可能是只含 {{Header2}} 的目录页）' % pid)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if '--selftest' in sys.argv:
    sys.exit(selftest())
ids = sys.argv[1:] or ['shudaonan', 'jiangjinjiu']
sys.exit(main(ids))
