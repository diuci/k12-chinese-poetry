# -*- coding: utf-8 -*-
"""把「别本作某」「通行本作某」这种没有出处的异文断言，逐条回来源页核实。

规矩：一条异文说了另一种写法，就必须说得出在哪一页看到的。
这一条不新增任何断言——它只做两件事：
  1) 在来源页（正文 + wikitext 夹注）里找得到那个写法 → 补上出处（页名 + 链接）；
  2) 找不到 → 在条目里写明「仓内没核到」，不许让它继续装作已经考实。

--selftest 自带坏例子，包括「把仓内自己的用字当成别本」这种假命中。
"""
import json, re, sys, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'text-sources.json'
# 判定口径必须和台账同源：build-ledger 的名单修好了，这里还留着旧的窄名单，
# 结果 37 条没有出处的异文一条都没被处理，工具报「补上出处 0 条」，看起来像干净，其实是空过。
_bl_spec = importlib.util.spec_from_file_location('bledger', ROOT / 'tools' / 'build-ledger.py')
_bl = importlib.util.module_from_spec(_bl_spec)
_bl_spec.loader.exec_module(_bl)
VM = _bl.VARIANT_MARK
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
    return -1


def load_records():
    return {r['id']: r for r in json.loads(SRC.read_text(encoding='utf-8'))['results']}


def main(write=False, refresh=False):
    C = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(C)
    records = load_records()
    fixed, unverified, skipped = 0, 0, 0
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
        table = C.load_t2s()
        # 取不取页要按「这一篇有没有条目要核」决定。--refresh 核的是已经写着「仓内没核到」的条目，
        # 那些条目带着「出处」二字，以前这个判断认不出来，于是页一张都不取、labels 是空的，
        # 结果给整篇写下「在 没有来源页 里找不到」这种废话——曹刿论战 就是这么被写坏的。
        def needs(x):
            x = x.strip()
            if not (x.startswith('- ') and VM.search(x)):
                return False
            return '出处' not in x or (refresh and '出处：仓内没核到' in x)

        need = any(needs(x) for x in re.split(r'\n(?=- )', body))
        if need:
            for pg in (rec.get('page') or '').split(' + '):
                try:
                    real, raw = C.page_text(pg)
                    tt, _ = C.clean(raw, table)
                    texts.append(tt)
                    labels.append(pg)
                except Exception:
                    continue
                try:
                    # wikitext 是繁体、还带模板，得同样过一遍转换才能比对。
                    _, wt = C.page_wikitext(pg)
                    wt2, _ = C.clean(wt, table)
                    texts.append(wt2)
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
                    s = re.sub(r'\s*出处：仓内没核到[^。]*。?\s*$', '', s).rstrip('。')
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
        new_body = '\n'.join(out)
        tail = len(body) - len(body.rstrip('\n'))
        new_body = new_body.rstrip('\n') + '\n' * max(1, tail)
        if changed and write:
            t = t[:m.start(1)] + new_body + t[m.end(1):]
            md.write_text(t, encoding='utf-8')
    print('[异文核实] 补上出处 %d 条 / 写明「仓内没核到」%d 条 / 没有来源页跳过 %d 篇' % (fixed, unverified, skipped))
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

    print('[ok] verify-variant-claims --selftest 通（11 个坏例子全部被拦住）')
    return 0


if '--selftest' in sys.argv:
    sys.exit(selftest())
main(write='--write' in sys.argv, refresh='--refresh' in sys.argv)
