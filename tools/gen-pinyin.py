#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Unicode Unihan 数据库提取拼音，生成 data/pinyin.txt。

数据源：**Unicode Unihan 数据库**（unicode.org，Unicode 许可）
字段：`kMandarin` —— 《通用规范汉字字典》（商务印书馆，2013）的普通话读音，
      与我国语文教学用字音标一致。1.2 万余字，覆盖本仓全部用字。

来源说明见 docs/sources.md的 S8。

用法：
    # 一次性：下载 Unihan.zip 并解压到 data/unihan/
    python tools/gen-pinyin.py --fetch
    # 生成拼音表
    python tools/gen-pinyin.py
"""

import re
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = DATA / 'pinyin.txt'
UNIHAN_DIR = DATA / 'unihan'
UNIHAN_URL = 'https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip'
READINGS = UNIHAN_DIR / 'Unihan_Readings.txt'

# kMandarin 给的是带声调拼音（qiū），站点要的是无声调（qiu）。
TONE = re.compile(r'[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹ]')
# 逐字还原：带调 → 基础调
TONED = {
    'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
    'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
    'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
    'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
    'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
    'ǖ': 'v', 'ǘ': 'v', 'ǚ': 'v', 'ǜ': 'v', 'ü': 'v',
    'ń': 'n', 'ň': 'n', 'ǹ': 'n',
}


def die(msg):
    print('[pinyin] ERROR: ' + msg, file=sys.stderr)
    sys.exit(1)


def fetch():
    """下载并解压 Unihan.zip（约 8MB，Unicode 许可）。"""
    import os
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    if READINGS.exists():
        print('[pinyin] Unihan 已就位：%s' % READINGS.relative_to(ROOT))
        return
    DATA.mkdir(parents=True, exist_ok=True)
    zpath = DATA / 'Unihan.zip'
    print('[pinyin] 下载 %s ...' % UNIHAN_URL)
    urlretrieve(UNIHAN_URL, zpath)
    print('[pinyin] 解压...')
    with zipfile.ZipFile(zpath) as z:
        z.extractall(UNIHAN_DIR)
    zpath.unlink()
    if not READINGS.exists():
        die('解压后未找到 Unihan_Readings.txt')
    print('[pinyin] 就绪：%s' % READINGS.relative_to(ROOT))


def parse_readings():
    """解析 kMandarin 字段，返回 {汉字: 无声调拼音}。"""
    if not READINGS.exists():
        die('缺少 Unihan_Readings.txt，请先跑 python tools/gen-pinyin.py --fetch')

    out = {}
    line_re = re.compile(r'^U\+([0-9A-F]{4,6})\s+kMandarin\s+([a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹ]+)'
                         r'(?:\s+(.+))?$')
    for raw in READINGS.read_text(encoding='utf-8').splitlines():
        if raw.startswith('#') or not raw.strip():
            continue
        m = line_re.match(raw)
        if not m:
            continue
        cp = int(m.group(1), 16)
        ch = chr(cp)
        # kMandarin 可能有多个读音（多音字），取第一个作为主读音
        first = m.group(2).split()[0]
        plain = ''.join(TONED.get(c, c) for c in first)
        out[ch] = plain
    return out


def collect_chars():
    """扫全仓篇目正文，收集所有汉字（只取正文，不取注释与赏析）。"""
    chars = set()
    for md in (ROOT / 'poems').rglob('*.md'):
        if md.name == '索引.md':
            continue
        text = md.read_text(encoding='utf-8')
        body = text.split('---', 2)[-1]
        for ch in body:
            if '㐀' <= ch <= '鿿':
                chars.add(ch)
    return chars


def main():
    if '--fetch' in sys.argv:
        fetch()

    table = parse_readings()
    used = collect_chars()
    covered = {c: p for c, p in table.items() if c in used}
    missing = sorted(used - set(table))

    print('[pinyin] Unihan 读音 %d 字；本仓用字 %d 个' % (len(table), len(used)))
    print('[pinyin] 覆盖 %d 个（%.1f%%）'
          % (len(covered), 100.0 * len(covered) / max(1, len(used))))
    if missing:
        print('[pinyin] 未覆盖 %d 个：%s' % (len(missing), ''.join(missing[:40])))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        '\n'.join('%s %s' % (c, p) for c, p in sorted(covered.items())) + '\n',
        encoding='utf-8')
    print('[pinyin] 写入 %s（%d 字）' % (OUT.relative_to(ROOT), len(covered)))
    print('[pinyin] 下一步：python tools/build-site.py（会自动加拼音）')


if __name__ == '__main__':
    main()