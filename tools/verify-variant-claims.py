# -*- coding: utf-8 -*-
"""把「别本作某」「通行本作某」这种没有出处的异文断言，逐条回来源页核实。

规矩：一条异文说了另一种写法，就必须说得出在哪一页看到的。
这一条不新增任何断言——它只做两件事：
  1) 在来源页（正文 + wikitext 夹注）里找得到那个写法 → 补上出处（页名 + 链接）；
  2) 找不到 → 在条目里写明「仓内没核到」，不许让它继续装作已经考实。

--selftest 自带坏例子，包括「把仓内自己的用字当成别本」这种假命中。
"""
import json, os, re, sys, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'text-sources.json'
# 判定口径必须和台账同源：build-ledger 的名单修好了，这里还留着旧的窄名单，
# 结果 37 条没有出处的异文一条都没被处理，工具报「补上出处 0 条」，看起来像干净，其实是空过。
_bl_spec = importlib.util.spec_from_file_location('bledger', ROOT / 'tools' / 'build-ledger.py')
_bl = importlib.util.module_from_spec(_bl_spec)
_bl_spec.loader.exec_module(_bl)
VM = _bl.VARIANT_MARK
# 离线开关：DIUCI_OFFLINE=1 时不取来源页。用途只有一个——来源站不可达时链条照样能跑完，
# 但报告里必须写明这一轮没做联网核实。它不会把「没核到」改成「核到」，也不会改任何正文。
OFFLINE = os.environ.get('DIUCI_OFFLINE') == '1'
QUOTE = re.compile(r'「([^」]{1,40})」')
SPEC = importlib.util.spec_from_file_location('cts', ROOT / 'tools' / 'check-text-sources.py')
_C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(_C)


def np(s):
    return re.sub(r'[\W_]+', '', s or '', flags=re.UNICODE)


# 别本写法通常紧跟在「本作／一本作／文库作／页作／》作」后面。直接取最后一个引号段会取错：
# 「《左传》原文与维基文库本作「小惠未徧」（徧、遍同）。本仓作「遍」。」的最后一个引号段是「遍」——
# 那是仓内用字，不是别本，拿它去整页找必然命中，是假命中。
ALT_CITE = re.compile(r'(?:本作|一本作|一本无|别本作|来源页作|来源页注|页作|文库作|通行本作|旧本作|他本作|另一本作|误作|》作|原文与[^。]{0,12}作)\s*「([^」]+)」')


def claim_of(entry):
    """条目里断言的「另一种写法」。"""
    qs = [q.replace('*', '') for q in QUOTE.findall(entry)]
    # 认出来了就直接用，不能再往下走「取最后一个引号段」——
    # 「本仓作「遍」」那种句子的最后一个引号段是仓内用字，拿它去整页找必然命中。
    # 有多个时取最后一个：「通行本作「长久」，别本作「长健」」里「长久」是本仓用字，「长健」才是别本。
    hits = [x.strip('，、。 ') for x in ALT_CITE.findall(entry.replace('*', '')) if x.strip('，、。 ')]
    if hits:
        return hits[-1]
    if len(qs) < 2:
        return None
    last = qs[-1]
    if '作' in last:
        last = last.rsplit('作', 1)[-1]
    for junk in ('也有版本', '另有版本', '版本', '一本', '别本', '他本', '通行本', '旧本'):
        last = last.replace(junk, '')
    last = last.strip('，、。 ')
    if not last:
        return None

    # 断言的写法落在仓内用字里面（比如「官」落在「官戒也」里），整页必然命中，
    # 那是假命中不是核实；这类多半是通假字或词义说明，交给人看。
    first = np(qs[0])
    if first and np(last) in first:
        return None
    return last


def strip_stale(s):
    """把过期的「仓内没核到」整句删掉——不管它在条目的开头、中间还是末尾。

    以前只在末尾删（正则锚在 $）。将进酒 的两条目是「…出处：仓内没核到——…只作线索。」在中间、
    新出处「出处：维基文库《酒顛補/卷下》」在末尾，于是同一条既算带出处又算没核到，台账两边都在数它。"""
    s = re.sub(r'出处：仓内没核到[^。]*。\s*', '', s)
    s = re.sub(r'\s{2,}', ' ', s)
    return s.rstrip('。 ')
MARK = re.compile(r'一作|又作|别本作|一本作|旧本作|通行本作')


def ambiguous_pairs(table):
    """OpenCC 字表里「一个繁体字给两个候选」的歧义条目（藉→藉 借、覆→覆 复、於→于 於、餘→余 馀）。"""
    out = []
    for v in table.values():
        if ' ' in v:
            parts = v.split(' ')
            if len(parts) == 2 and len(parts[0]) == 1 and len(parts[1]) == 1 and parts[0] != parts[1]:
                out.append((parts[0], parts[1]))
    return out


def doubled_claim(entry, pairs, single, texts):
    """条目断言的写法里出现「一个繁体字的两个候选拼在一起」，而页里并没有这一对。

    「来源页作「藉借寇兵」」这种句子就是这么写出来的：页里只写「藉」，比对时两个候选都认，
    引用时把两个候选一起写出来就等于对来源页说了一句它自己没写过的话。
    页里真写了这一对的不算——那确实是页里的写法。"""
    claim = claim_of(entry)
    if not claim:
        return None
    cn = _C.to_simplified(np(claim), single)
    form = None
    for a, b in pairs:
        if a + b in cn:
            form = a + b
            break
        if b + a in cn:
            form = b + a
            break
    if not form:
        return None
    for tx in texts:
        if form in np(tx):
            return None
    return (claim, form)


def marker_hit(k, jt, window=14):
    """页里有没有「一作＋这个写法」这种夹注。

    短句（4 字以下）在整页无标点的散文里没有区分度，所以不给它用一般的顺序兜底；
    但「钟期既一作相遇」「物换星移几度一作度几秋」这种是来源页自己标出来的别本，
    必须认——不认就是假阴性，把核得到的写成核不到。"""
    if not k:
        return False
    for m in MARK.finditer(jt):
        # 夹注的写法可以跨在标记两边：「钟锺期既一作相遇」里「钟期」在标记前、「相遇」在标记后。
        seg = jt[max(0, m.start() - 10): m.end() + window]
        it = iter(seg)
        if all(ch in it for ch in k):
            return True
    return False

def find_claim(claim, texts):
    """在几份文本里找这个写法（去标点后逐字比对）。返回命中的那份文本的序号。"""
    k = np(claim)
    if not k:
        return -1
    for i, t in enumerate(texts):
        jt = np(t)
        if k in jt:
            return i
    # 逐字找不到不等于这一页没有：来源页把「一作某」夹在正文里，夹注一插进来就把句子切开了
    # （《王子安集》《李太白全集》整页几乎没有标点）。这时按「顺序对得上、中间只多不少」再判一次。
    # 只给 6 字以上的写法用这个兜底：短句在整页无标点的散文里没有区分度，兜底只会造出假命中。
    if len(k) >= 6:
        for i, t in enumerate(texts):
            if _C.subseq_window(k, np(t), 25):
                return i
    else:
        # 短句只认「一作＋这个写法」这种页自己标出来的别本夹注。
        for i, t in enumerate(texts):
            if marker_hit(k, np(t)):
                return i
    return -1


def load_records():
    return {r['id']: r for r in json.loads(SRC.read_text(encoding='utf-8'))['results']}


def main(write=False, refresh=False):
    if OFFLINE and write:
        # 离线时没有来源页可比，find_claim 一律报「没核到」；带着 --write 就会把
        # 本来有出处的条目整批改写成「仓内没核到」——那是拿网络故障去污染内容。
        print('[!] 离线模式（DIUCI_OFFLINE=1）不写盘：这一轮只读不改动。')
        write = False
    C = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(C)
    records = load_records()
    fixed, unverified, skipped, offline = 0, 0, 0, 0
    _tab0 = C.load_t2s()
    pairs = ambiguous_pairs(_tab0)
    single0 = C.single_table(_tab0)
    doubled = []
    for md in sorted((ROOT / 'poems').rglob('*.md')):
        t = md.read_text(encoding='utf-8')
        fid = re.search(r'^id:\s*(\S+)', t, re.M)
        if not fid:
            continue
        rec = records.get(fid.group(1))
        if not rec or not rec.get('page'):
            skipped += 1
            continue
        m = re.search(r'^## 异文[^\n]*\n(.*?)(?=^## |\Z)', t, re.M | re.S)
        if not m:
            continue
        body = m.group(1)
        out = []
        changed = False
        # 来源页只取一次：以前每条异文都重新取一遍页，98 条就是几百次请求。
        texts, labels = [], []
        texts_q = []  # 页里原样那一份：一个字都不换，用来查「拼出来的写法」
        table = C.load_t2s()
        # 取不取页要按「这一篇有没有条目要核」决定。--refresh 核的是已经写着「仓内没核到」的条目，
        # 那些条目带着「出处」二字，以前这个判断认不出来，于是页一张都不取、labels 是空的，
        # 结果给整篇写下「在 没有来源页 里找不到」这种废话——曹刿论战 就是这么被写坏的。
        def needs(x):
            x = x.strip()
            if not (x.startswith('- ') and VM.search(x)):
                return False
            return '出处' not in x or (refresh and '出处：仓内没核到' in x)

        entries = re.split(r'\n(?=- )', body)
        need = any(needs(x) for x in entries)
        # 引用了来源页的条目也要取页：不取页就只能听条目自己怎么说。
        cited = any(('维基文库' in x or 'wikisource' in x) and claim_of(x) for x in entries)
        if (need or cited) and OFFLINE:
            offline += 1
        if (need or cited) and not OFFLINE:
            for pg in (rec.get('page') or '').split(' + '):
                try:
                    real, raw = C.page_text(pg)
                    tt, _ = C.clean(raw, table)
                    texts.append(tt)
                    texts_q.append(C.strip_only(raw))
                    labels.append(pg)
                except Exception:
                    continue
                try:
                    # wikitext 是繁体、还带模板，得同样过一遍转换才能比对。
                    _, wt = C.page_wikitext(pg)
                    wt2, _ = C.clean(wt, table)
                    texts.append(wt2)
                    texts_q.append(C.strip_only(wt))
                    labels.append(pg + '（wikitext 原文）')
                except Exception:
                    pass
        for ln in re.split(r'\n(?=- )', body):
            s = ln.rstrip()
            stripped = s.strip()
            # --refresh：来源页换了、探针修好了，以前写的「仓内没核到」要能重新核一遍。
            # 不刷新就会永远留着一句过期的结论——曹刿论战 就是例子：比对页早就从《左氏博議》
            # 换成单页《曹劌論戰》，条目里还写着在评论集里找不到。
            stale = '出处：仓内没核到' in stripped
            if stripped.startswith('- ') and VM.search(stripped) and ('出处' not in stripped or (refresh and stale)):
                if stale:
                    s = strip_stale(s)
                claim = claim_of(stripped)
                if not claim:
                    out.append(s)
                    continue
                hit = find_claim(claim, texts)
                if hit >= 0:
                    s = s.rstrip('。') + '。出处：维基文库《%s》 %s' % (labels[hit], rec.get('url') or '')
                    fixed += 1
                    changed = True
                    print('  [核到] %-22s 「%s」 ← %s' % (md.stem, claim, labels[hit]))
                else:
                    s = s.rstrip('。') + '。出处：仓内没核到——在 %s 里找不到「%s」这个写法；这一条只作线索，不作为已考实的异文。' % (
                        '、'.join(dict.fromkeys(labels)) or '没有来源页', claim)
                    unverified += 1
                    changed = True
                    print('  [没核到] %-20s 「%s」' % (md.stem, claim))
            out.append(s)
        # 小节末尾的空行要照原样留着。以前 join 完直接接回去，
        # 下一个 ## 就粘在上一行末尾（望海潮、桂枝香、古代文论选段、《论语》十二章 四处），
        # 整节被吞进上一节，台账的分母跟着错。
        if texts_q:
            for x in out:
                bad = doubled_claim(x, pairs, single0, texts_q)
                if bad:
                    doubled.append((md.stem, bad[0], bad[1]))
        new_body = '\n'.join(out)
        tail = len(body) - len(body.rstrip('\n'))
        new_body = new_body.rstrip('\n') + '\n' * max(1, tail)
        if changed and write:
            t = t[:m.start(1)] + new_body + t[m.end(1):]
            md.write_text(t, encoding='utf-8')
    print('[异文核实] 补上出处 %d 条 / 写明「仓内没核到」%d 条 / 没有来源页跳过 %d 篇' % (fixed, unverified, skipped))
    if doubled:
        print('[异文核实] %d 条异文条目写的「另一种写法」是转换表拼出来的，页里没有这一对：' % len(doubled))
        for stem, claim, form in doubled:
            print('   %s 「%s」 拼=%s' % (stem, claim, form))
        raise SystemExit('异文条目不许写页里没有的拼字：按页里原字改写，或撤掉那条。')
    if OFFLINE:
        print('[异文核实] 离线模式（DIUCI_OFFLINE=1）：%d 篇该核的条目这一轮没有联网核实。'
              '这一轮不算核过——来源站能连上时必须重跑一遍不带 DIUCI_OFFLINE 的。' % offline)
    return 0


def selftest():
    # 1) 断言的别本写法要能找出来
    e1 = '- 「但愿人长久」：通行本作「长久」，别本作「长健」。'
    assert claim_of(e1) == '长健', '坏例1：没认出断言的别本写法'
    # 2) 只有一句引号的条目（没有别本断言）不许处理
    assert claim_of('- 「水尤清洌」：来源页夹注「也有版本作冽」') == '冽', '坏例2：夹注里的写法没认出来'
    assert claim_of('- 「肉食者谋之」：句式与仓内一致。') is None, '坏例3：没有别本断言也去核实'
    # 3) 核实是真去页上找，不是看条目自己怎么说
    texts = ['明月幾時有把酒問青天不知天上宮闕今夕是何年但愿人长久千里共嬋娟']
    assert find_claim('长健', texts) == -1, '坏例4：页上没有的写法被当成核到'
    # 别本写法紧跟在「文库作」后面，不是最后一个引号段：最后那段「遍」是仓内用字，拿它去整页找必然命中。
    assert claim_of('- 「小惠未遍」：《左传》原文与维基文库本作「小惠未徧」（徧、遍同）。本仓作「遍」。') == '小惠未徧', '坏例8：取的是仓内用字而不是别本写法'
    assert claim_of('- 「黄鹤之飞尚不得过」：《四库全书》本《李太白全集》作「黄鹤之飞尙不得过」。') == '黄鹤之飞尙不得过', '坏例9：》作 后面的别本没认出来'
    assert find_claim('长久', texts) == 0, '坏例5：页上有的写法没被认出来'
    # 4) 仓内自己的用字不能算「别本核到」——那只能证明正文，不能证明别本
    # 页上是繁体，仓内是简体：比对必须过一遍繁简转换，否则真命中会被漏掉。
    C = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(C)
    table = C.load_t2s()
    conv, _ = C.clean('千里共嬋娟', table)
    assert find_claim('婵娟', [conv]) == 0, '坏例6：繁简转换没做，真命中被漏'
    assert find_claim('长健', [conv]) == -1, '坏例7：页上没有的写法被当成核到'
    # 10) 夹注把句子切开：整页几乎没有标点，逐字找不到，但顺序对得上——必须算核到
    # 真实流程里 texts 已经是「过完繁简转换的页文本」，这里必须照做，否则繁体探针对简体断言必然 0 命中。
    _tab = _C.load_t2s()
    cut = [_C.clean('岑夫子丹丘生将进酒君一作杯莫停与君歌一曲请君为我侧耳听', _tab)[0]]
    assert find_claim('将进酒杯莫停', cut) == 0, '坏例10：被夹注切开的真命中被判成没核到'
    # 11) 短句不许用兜底：整页无标点的散文里，4 个字的片段到处都能凑出顺序
    assert find_claim('长健', cut) == -1, '坏例11：短句用了兜底，造出假命中'

    # 12) 过期的「仓内没核到」在条目中间，也必须被清掉（否则同一条既算带出处又算没核到）
    mid = '- 「径须沽取对君酌」：《酒顛補》作「且须沽酒」。出处：仓内没核到——在 將進酒 (李白) 里找不到这个写法；这一条只作线索，不作为已考实的异文。 取舍：从「径须沽取」。出处：维基文库《酒顛補/卷下》'
    got = strip_stale(mid)
    assert '仓内没核到' not in got, '坏例12：写在中间的过期结论没被清掉'
    assert '酒顛補/卷下' in got, '坏例13：清过期结论时把真出处一起删了'
    assert '取舍' in got, '坏例14：清过期结论时把取舍一起删了'
    tail = '- 「与尔同销万古愁」：别本作「同消」。出处：仓内没核到——在 X 里找不到。'
    assert strip_stale(tail) == '- 「与尔同销万古愁」：别本作「同消」', '坏例15：末尾的过期结论没清干净'

    # 16) 短句只认页自己标出来的别本夹注：「钟期既一作相遇」里的「钟期相遇」必须认
    mk = ['抚凌云而自惜钟锺期既一作相遇奏流水以何慙呜呼胜地']
    assert find_claim('钟期相遇', mk) == 0, '坏例16：页里明写「一作相遇」却被判成没核到'
    # 17) 没有「一作」标记的短句不许靠顺序兜底蒙对
    # 页里根本没有「长健」这两个字连在一起，也没有任何「一作」标记——不许靠顺序蒙对
    nomark = ['长者有疾吾子有疾先问长者后问吾子康宁而已']
    assert find_claim('长健', nomark) == -1, '坏例17：没有别本标记的短句被当成核到'

    # 18) 转换表的歧义条目（一个繁体字给两个候选）拼出来的写法：页里只写一个字，条目写成两个字。
    #     「来源页作「藉借寇兵」」这种句子就是这么写出来的——对来源页说了一句它自己没写过的话。
    _tab2 = _C.load_t2s()
    _single2 = _C.single_table(_tab2)
    _pairs2 = ambiguous_pairs(_tab2)
    _pg18 = [_C.strip_only('此所謂藉寇兵而齎盜糧者也')]
    _bad18 = doubled_claim('- 「此所谓藉寇兵而赍盗粮者也」：维基文库本页作「藉借寇兵」。', _pairs2, _single2, _pg18)
    assert _bad18 is not None and _bad18[1] == '藉借', '坏例18：页里只写「藉」，条目写成「藉借」没拦住'
    # 19) 反向：页里真写了这一对的不许误报（讎 是页里的字）
    _pg19 = [_C.strip_only('及仇讎已滅天下已定')]
    assert doubled_claim('- 「仇雠」：来源页作「仇讎」。', _pairs2, _single2, _pg19) is None, '坏例19：页里真写的字被误报'
    # 20) 「餘→余 馀」这一族：页里写作「餘」，条目写成「余馀」必须拦住
    _pg20 = [_C.strip_only('祖母无臣无以终餘年')]
    assert doubled_claim('- 「无以终余年」：来源页作「终余馀年」。', _pairs2, _single2, _pg20) is not None, '坏例20：「余馀」这种拼字没拦住'
    # 21) 条目里没有别本断言（只是词义说明）不许去查，也不许报
    assert doubled_claim('- 「藉，借。」：词义说明。', _pairs2, _single2, _pg18) is None, '坏例21：词义说明被当成异文断言'
    print('[ok] verify-variant-claims --selftest 通（21 个坏例子全部被拦住）')
    return 0


if '--selftest' in sys.argv:
    sys.exit(selftest())
main(write='--write' in sys.argv, refresh='--refresh' in sys.argv)
