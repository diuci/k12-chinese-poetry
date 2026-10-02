#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量生成篇目 Markdown —— 初中 7-9 年级（课标60 篇）。

与gen-primary.py 的区别：
  小学篇目全部是诗，用 `lines` 存整句即可；
  初中含 20 篇文言文，段落动辄数百字，无法贴到地面、也无法判定联句。
  故文言文一律**名句化**：`lines` 只放课标要求背诵的名句，多为对举，
  与诗词完全同构；全文另存于正文的「全文」节供学习。

用法：
    python tools/gen-middle.py
    python tools/gen-middle.py --dry
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POEMS_DIR = ROOT / 'poems' / '初中'

# ============================================================================
# DATA
#   wenyan=True 时：lines 为必背名句（游戏单元），另需 full 存全文
#   grade   7/8/9
#   recite  full全文背诵 / section 背段落 / line 只背名句 / none 只理解
# ============================================================================

DATA = [
    # ==================== 七年级 ====================
    dict(id='guanju', grade=7, volume='七年级上册', title='关雎', author='佚名', dyn='先秦',
         form='诗经', theme=['爱情', '水滨'], emo='对美好爱情的向往',
         tech=['比兴', '叠词'], diff=3, freq=0.9, recite='line',
         lines=['关关雎鸠，在河之洲。', '窈窕淑女，君子好逑。']),
    dict(id='jianjia', grade=7, volume='七年级上册', title='蒹葭', author='佚名', dyn='先秦',
         form='诗经', theme=['爱情', '追寻'], emo='对爱慕者的执着追寻',
         tech=['比兴', '重章叠句'], diff=3, freq=0.8, recite='line',
         lines=['蒹葭苍苍，白露为霜。', '所谓伊人，在水一方。']),
    dict(id='shiwuzhongjunzheng', grade=7, volume='七年级上册', title='十五从军征',
         author='佚名', dyn='汉', form='乐府', theme=['战争', '民生'], emo='战乱与徭役的悲苦',
         tech=['对比'], diff=4, freq=0.6, recite='line',
         lines=['十五从军征，八岁开姓名。', '虽有战死与儿死者，无家可归依。'],
         irregular='第二句为节选合并，两句原文：「勿从俱死生，必使六尺之孤」与「无家可归依」；教材节选时并为一句'),
    dict(id='guancanghai', grade=7, volume='七年级上册', title='观沧海', author='曹操', dyn='汉',
         form='乐府', theme=['写景', '抱负'], emo='辽阔壮阔的胸襟与抱负',
         tech=['虚实结合', '夸张'], diff=4, freq=0.9, recite='full',
         lines=['东临碣石，以观沧海。', '水何澹澹，山岛竦峙。', '树木丛生，百草丰茂。',
                '秋风萧瑟，洪波涌起。', '日月之行，若出其中。', '星汉灿烂，若出其里。']),
    dict(id='yinjiujiusan', grade=7, volume='七年级上册', title='饮酒', sub='其五',
         author='陶潜', dyn='晋', form='五言', theme=['田园', '隐逸'], emo='超脱物欲的淡泊',
         tech=['象征', '对比'], diff=4, freq=0.9, recite='full',
         lines=['结庐在人境，而无车马喧。', '问君何能尔？心远地自偏。',
                '采菊东篱下，悠然见南山。', '山气日夕佳，飞鸟相与还。',
                '此中有真意，欲辨已忘言。']),
    dict(id='mulanci', grade=7, volume='七年级下册', title='木兰辞', author='佚名', dyn='北朝',
         form='乐府', theme=['战争', '孝亲'], emo='代父从军的英勇与对家的眷恋',
         tech=['排比', '复沓'], diff=4, freq=0.9, recite='section',
         lines=['万里赴戎机，关山度若飞。', '朔气传金柝，寒光照铁衣。',
                '将军百战死，壮士十年归。']),
    dict(id='songshaoshu', grade=7, volume='七年级上册', title='送杜少府之任蜀州',
         author='王勃', dyn='唐', form='五言', theme=['送别', '友情'], emo='豁达乐观的送别',
         tech=['对偶', '直抒胸臆'], diff=4, freq=0.9, recite='full',
         lines=['城阙辅三秦，风烟望五津。', '与君离别意，同是宦游人。',
                '海内存知己，天涯若比邻。', '无为在歧路，儿女共沾巾。']),
    dict(id='dengyouzhoutai', grade=7, volume='七年级下册', title='登幽州台歌',
         author='陈子昂', dyn='唐', form='杂言', theme=['感怀', '孤独'], emo='孤高失意的悲愤',
         tech=['反复', '直抒'], diff=3, freq=0.9, recite='full',
         lines=['前不见古人，后不见来者。', '念天地之悠悠，独怆然而涕下。']),
    dict(id='cibeigushanxia', grade=7, volume='七年级上册', title='次北固山下',
         author='王湾', dyn='唐', form='五言', theme=['思乡', '哲理'], emo='思乡与哲思交织',
         tech=['比喻', '炼字'], diff=3, freq=0.8, recite='full',
         lines=['客路青山外，行舟绿水前。', '潮平两岸阔，风正一帆悬。',
                '海日生残夜，江春入旧年。', '乡书何处达？归雁洛阳边。']),
    dict(id='shizhuisai', grade=7, volume='七年级上册', title='使至塞上', author='王维', dyn='唐',
         form='五言', theme=['边塞', '壮阔'], emo='出使边塞的雄壮与孤寂',
         tech=['比喻', '炼字'], diff=4, freq=1.0, recite='full',
         lines=['单车欲问边，属国过居延。', '征蓬出汉塞，归雁入胡天。',
                '大漠孤烟直，长河落日圆。', '萧关逢候骑，都护在燕然。']),
    dict(id='wenwangchangling', grade=7, volume='七年级上册',
         title='闻王昌龄左迁龙标遥有此寄', author='李白', dyn='唐',
         form='七言', theme=['送别', '友情'], emo='对友人被贬的牵挂',
         tech=['想象', '比兴'], diff=4, freq=0.9, recite='full',
         lines=['杨花落尽子规啼，闻道龙标过五溪。', '我寄愁心与明月，随君直到夜郎西。']),
    dict(id='xinglunan', grade=7, volume='九年级上册', title='行路难', sub='其一',
         author='李白', dyn='唐', form='杂言', theme=['抒怀', '理想'], emo='政治失意的苦闷与坚持',
         tech=['比兴', '象征'], diff=4, freq=0.9, recite='section',
         lines=['金樽清酒斗十千，玉盘珍羞直万钱。', '停杯投箸不能食，拔剑四顾心茫然。',
                '长风破浪会有时，直挂云帆济沧海。']),
    dict(id='huanghelou-cuiheng', grade=7, volume='七年级上册', title='黄鹤楼',
         author='崔颢', dyn='唐', form='七言', theme=['登临', '思乡'], emo='登临吊古的苍凉',
         tech=['对比', '虚实结合'], diff=4, freq=0.9, recite='full',
         lines=['昔人已乘黄鹤去，此地空余黄鹤楼。', '黄鹤一去不复返，白云千载空悠悠。',
                '晴川历历汉阳树，芳草萋萋鹦鹉洲。', '日暮乡关何处是？烟波江上使人愁。']),
    dict(id='wangyue', grade=7, volume='七年级下册', title='望岳', author='杜甫', dyn='唐',
         form='五言', theme=['山水', '抱负'], emo='登临望岳的雄心壮志',
         tech=['对比', '夸张'], diff=4, freq=1.0, recite='full',
         lines=['岱宗夫如何？齐鲁青未了。', '造化钟神秀，阴阳割昏晓。',
                '荡胸生曾云，决眦入归鸟。', '会当凌绝顶，一览众山小。']),
    dict(id='chunwang', grade=7, volume='七年级上册', title='春望', author='杜甫', dyn='唐',
         form='五言', theme=['战争', '忧国'], emo='战乱中的忧国伤时',
         tech=['对比', '拟人'], diff=4, freq=1.0, recite='full',
         lines=['国破山河在，城春草木深。', '感时花溅泪，恨别鸟惊心。',
                '烽火连三月，家书抵万金。', '白头搔更短，浑欲不胜簪。']),
    dict(id='maowu', grade=7, volume='七年级上册', title='茅屋为秋风所破歌',
         author='杜甫', dyn='唐', form='杂言', theme=['民生', '推己及人'], emo='穷困中的推己及人',
         tech=['对比', '议论'], diff=5, freq=0.7, recite='section',
         lines=['安得广厦千万间，大庇天下寒士俱欢颜。', '风雨不动安如山。']),
    dict(id='baixuege', grade=7, volume='七年级上册', title='白雪歌送武判官归京',
         author='岑参', dyn='唐', form='七言', theme=['边塞', '送别'], emo='雪中送别的苍茫与深情',
         tech=['比喻', '夸张'], diff=4, freq=0.8, recite='section',
         lines=['北风卷地白草折，胡天八月即飞雪。', '忽如一夜春风来，千树万树梨花开。',
                '轮台东门送君去，去时雪满天山路。']),
    dict(id='maotanshangwu', grade=7, volume='七年级下册', title='卖炭翁', author='白居易',
         dyn='唐', form='七言', theme=['民生', '讽喻'], emo='对宫市巧取豪夺的愤慨',
         tech=['对比', '细节'], diff=4, freq=0.8, recite='section',
         lines=['可怜身上衣正单，心忧炭贱愿天寒。', '卖炭得钱何所营？身上衣裳口中食。']),
    dict(id='qiantanghuchunxing', grade=7, volume='七年级下册', title='钱塘湖春行',
         author='白居易', dyn='唐', form='七言', theme=['春天', '西湖'], emo='早春西湖的喜悦',
         tech=['比喻', '白描'], diff=4, freq=0.8, recite='section',
         lines=['孤山寺北贾亭西，水面初平云脚低。', '几处早莺争暖树，谁家新燕啄春泥。',
                '乱花渐欲迷人眼，浅草才能没马蹄。', '最爱湖东行不足，绿杨阴里白沙堤。']),
    dict(id='yanmenshiweixing', grade=7, volume='七年级下册', title='雁门太守行',
         author='李贺', dyn='唐', form='七言', theme=['战争', '边塞'], emo='将士浴血报国的悲壮',
         tech=['比喻', '对比'], diff=4, freq=0.8, recite='section',
         lines=['黑云压城城欲摧，甲光向日金鳞开。', '角声满天秋色里，塞上燕脂凝夜紫。',
                '半卷红旗临易水，霜重鼓寒声不起。']),
    dict(id='chibi-du', grade=7, volume='七年级下册', title='赤壁', author='杜牧', dyn='唐',
         form='七言', theme=['怀古', '哲理'], emo='怀古伤今的感慨',
         tech=['议论', '借景抒情'], diff=4, freq=0.9, recite='full',
         lines=['折戟沉沙铁未销，自将磨洗认前朝。', '东风不与周郎便，铜雀春深锁二乔。']),
    dict(id='boqinhuai', grade=7, volume='七年级下册', title='泊秦淮', author='杜牧', dyn='唐',
         form='七言', theme=['怀古', '讽喻'], emo='对权贵苟安的愤慨',
         tech=['议论', '借景抒情'], diff=4, freq=0.9, recite='full',
         lines=['烟笼寒水月笼沙，夜泊秦淮近酒家。', '商女不知亡国恨，隔江犹唱后庭花。']),
    dict(id='yeyujibei', grade=7, volume='七年级下册', title='夜雨寄北', author='李商隐', dyn='唐',
         form='七言', theme=['思乡', '想象'], emo='跨越时空的相思',
         tech=['想象', '虚实结合'], diff=4, freq=1.0, recite='full',
         lines=['君问归期未有期，巴山夜雨涨秋池。', '何当共剪西窗烛，却话巴山夜雨时。']),
    dict(id='wuti', grade=7, volume='九年级上册', title='无题', sub='相见时难别亦难',
         author='李商隐', dyn='唐', form='七言', theme=['爱情', '执着'], emo='至死不渝的执着',
         tech=['比兴', '用典'], diff=4, freq=0.9, recite='section',
         lines=['相见时难别亦难，东风无力百花残。', '春蚕到死丝方尽，蜡炬成灰泪始干。']),
    dict(id='xiangjianhuan', grade=7, volume='九年级上册', title='相见欢', sub='无言独上西楼',
         author='李煜', dyn='南唐', form='词', theme=['亡国', '愁思'], emo='亡国之君的深沉哀愁',
         tech=['意象叠加'], diff=4, freq=0.9, recite='full',
         lines=['无言独上西楼，月如钩。', '寂寞梧桐深院锁清秋。',
                '剪不断，理还乱，是离愁。', '别是一般滋味在心头。']),
    dict(id='yujiaao-qiusi', grade=7, volume='九年级上册', title='渔家傲', sub='秋思',
         author='范仲淹', dyn='宋', form='词', theme=['边塞', '思乡'], emo='戍边思乡的复杂心境',
         tech=['对比', '白描'], diff=4, freq=1.0, recite='full',
         lines=['塞下秋来风景异，衡阳雁去无留意。', '四面边声连角起。',
                '千嶂里，长烟落日孤城闭。', '浊酒一杯家万里，燕然未勒归无计。',
                '羌管悠悠霜满地，人不寐，将军白发征夫泪。']),
    dict(id='huanxisha-yanque', grade=7, volume='九年级上册', title='浣溪沙', sub='一曲新词酒一杯',
         author='晏殊', dyn='宋', form='词', theme=['闺情', '怀念'], emo='追忆往事的惆怅',
         tech=['对比'], diff=4, freq=0.9, recite='full',
         lines=['一曲新词酒一杯，去年天气旧亭台。夕阳西下几时回？',
                '无可奈何花落去，似曾相识燕归来。小园香径独徘徊。']),
    dict(id='dengfeilaifeng', grade=7, volume='七年级下册', title='登飞来峰',
         author='王安石', dyn='宋', form='七言', theme=['哲理', '抱负'], emo='高瞻远瞩的抱负',
         tech=['比喻', '象征'], diff=3, freq=0.9, recite='full',
         lines=['飞来山上千寻塔，闻说鸡鸣见日升。', '不畏浮云遮望眼，自缘身在最高层。']),
    dict(id='jiangchengzi-laofeng', grade=7, volume='九年级上册', title='江城子', sub='密州出猎',
         author='苏轼', dyn='宋', form='词', theme=['豪迈', '爱国'], emo='出猎的豪迈与报国壮志',
         tech=['典故', '夸张'], diff=5, freq=0.9, recite='section',
         lines=['老夫聊发少年狂，左牵黄，右擎苍。', '锦帽貂裘，千骑卷平冈。',
                '为报倾城随太守，亲射虎，看孙郎。']),
    dict(id='shuidiaogetou', grade=7, volume='九年级上册', title='水调歌头', sub='明月几时有',
         author='苏轼', dyn='宋', form='词', theme=['思亲', '旷达'], emo='思念弟弟的旷达情怀',
         tech=['想象', '议论'], diff=4, freq=1.0, recite='section',
         lines=['但愿人长久，千里共婵娟。']),
    dict(id='yujiaao-tianjie', grade=7, volume='九年级上册', title='渔家傲', sub='天接云涛连晓雾',
         author='李清照', dyn='宋', form='词', theme=['梦境', '追寻'], emo='追求自由不畏艰险',
         tech=['想象', '夸张'], diff=5, freq=0.8, recite='full',
         lines=['天接云涛连晓雾，星河欲转千帆舞。', '仿佛梦魂归帝所。',
                '闻天语，殷勤问我归何处。', '我报路长嗟日暮，学诗谩有惊人句。',
                '九万里风鹏正举。']),
    dict(id='youshanxincun', grade=7, volume='七年级下册', title='游山西村', author='陆游', dyn='宋',
         form='七言', theme=['田园', '哲理'], emo='重获希望的开朗',
         tech=['对比', '议论'], diff=4, freq=0.9, recite='full',
         lines=['莫笑农家腊酒浑，丰年留客足鸡豚。', '山重水复疑无路，柳暗花明又一村。',
                '箫鼓追随春社近，衣冠简朴古风存。', '从今若许闲乘月，拄杖无时夜叩门。']),
    dict(id='nangxiangzi', grade=7, volume='九年级上册', title='南乡子', sub='何处望神州',
         author='辛弃疾', dyn='宋', form='词', theme=['爱国', '豪情'], emo='渴望收复失地的壮志',
         tech=['对比', '典故'], diff=4, freq=0.9, recite='section',
         lines=['何处望神州？满眼风光北固楼。千古兴亡多少事？悠悠。',
                '不尽长江滚滚流。', '年少万兜鍪，坐断东南战未休。',
                '天下英雄谁敌手？曹刘。', '生子当如孙仲谋。']),
    dict(id='pozhenzi', grade=7, volume='九年级上册', title='破阵子', sub='为陈同甫赋壮词以寄',
         author='辛弃疾', dyn='宋', form='词', theme=['爱国', '壮志'], emo='报国杀敌的壮志',
         tech=['对比', '夸张'], diff=4, freq=1.0, recite='full',
         lines=['醉里挑灯看剑，梦回吹角连营。', '八百里分麾下炙，五十弦翻塞外声。',
                '沙场秋点兵。', '马作的卢飞快，弓如霹雳弦惊。',
                '了却君王天下事，赢得生前身后名。', '可怜白发生！']),
    dict(id='guolingyang', grade=7, volume='九年级下册', title='过零丁洋', author='文天祥', dyn='宋',
         form='七言', theme=['爱国', '气节'], emo='舍生取义的浩然正气',
         tech=['对比', '象征'], diff=4, freq=1.0, recite='section',
         lines=['辛苦遭逢起一经，干戈寥落四周星。', '山河破碎风飘絮，身世浮沉雨打萍。',
                '惶恐滩头说惶恐，零丁洋里叹零丁。', '人生自古谁无死？留取丹心照汗青。']),
    dict(id='tianjingsha-qiusi', grade=7, volume='九年级下册', title='天净沙', sub='秋思',
         author='马致远', dyn='元', form='曲', theme=['羁旅', '愁思'], emo='漂泊无依的深切悲愁',
         tech=['意象叠加', '白描'], diff=3, freq=1.0, recite='full',
         lines=['枯藤老树昏鸦，小桥流水人家。', '古道西风瘦马，夕阳西下。', '断肠人在天涯。']),
    dict(id='shanpoyang', grade=7, volume='九年级下册', title='山坡羊', sub='潼关怀古',
         author='张养浩', dyn='元', form='曲', theme=['怀古', '同情'], emo='对人民疾苦的深切同情',
         tech=['对比', '议论'], diff=4, freq=0.8, recite='full',
         lines=['峰峦如聚，波涛如怒，山河表里潼关路。', '望西都，意踌躇。',
                '伤心秦汉经行处，宫阙万间都做了土。', '兴，百姓苦；亡，百姓苦。']),
    dict(id='jihai-jimao', grade=7, volume='九年级下册', title='己亥杂诗', sub='浩荡离愁白日斜',
         author='龚自珍', dyn='清', form='七言', theme=['离京', '抱负'], emo='辞别京城的复杂心情',
         tech=['象征', '对比'], diff=4, freq=0.9, recite='section',
         lines=['浩荡离愁白日斜，吟鞭东指即天涯。', '落红不是无情物，化作春泥更护花。']),
    dict(id='manjianghong-qiaojinghua', grade=7, volume='七年级下册', title='满江红', sub='小住京华',
         author='秋瑾', dyn='清', form='词', theme=['家国', '觉醒'], emo='女性觉醒的壮志',
         tech=['象征'], diff=4, freq=0.6, recite='full',
         lines=['小住京华，早又是、中秋佳节。', '为篱下、黄花开遍，秋容如拭。',
                '四面歌残终破楚，八年风味徒思浙。', '苦将侬、强派作蛾眉，殊未屑！',
                '身不得，男儿列。', '心却比，男儿烈！',
                '算平生肝胆，因人常热。', '俗子胸襟谁识我？英雄末路当磨折。',
                '莽红尘、何处觅知音？青衫湿！'],
         license='pending', pending_reason='秋瑾 1907 年遇害，著作权保护期未届满，暂缓入库'),
]


def die(msg):
    print('[gen] ERROR: ' + msg, file=sys.stderr)
    sys.exit(1)


def main():
    dry = '--dry' in sys.argv

    ids = [d['id'] for d in DATA]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        die('id 重复：%s' % dup)

    if dry:
        pending = [d for d in DATA if d.get('license') == 'pending']
        print('[gen] --dry：%d 篇待生成（其中暂缓 %d 篇）'
              % (len(DATA), len(pending)))
        return

    CN = {7: '七', 8: '八', 9: '九'}
    written = 0
    pending = 0

    for d in DATA:
        if d.get('license') == 'pending':
            pending += 1
            print('  ⏸ 暂缓（保护期内）%s' % d['title'])
            continue

        lines = d['lines']
        n = len(lines)
        pairs = ['%d-%d' % (i, i + 1) for i in range(0, n - 1, 2)]
        split = [max(1, len([x for x in l.rstrip('。！？；').split('，') if x.strip()]))
                 for l in lines]

        sub = d.get('sub')
        fm = [
            '---',
            'id: %s' % d['id'],
            'title: %s' % d['title'],
            'subtitle: %s' % (sub if sub else 'null'),
            'author: %s' % d['author'],
            'dynasty: %s' % d['dyn'],
            'form: %s' % d['form'],
            'stage: 初中',
            'grade: %d' % d['grade'],
            'volume: %s' % d['volume'],
            'textbooks: [统编]',
            'recite: %s' % d.get('recite', 'line'),
            'theme: [%s]' % ', '.join(d['theme']),
            'emotion: %s' % d['emo'],
            'technique: [%s]' % ', '.join(d['tech']),
            'difficulty: %d' % d['diff'],
            'exam_freq: %s' % d['freq'],
            'pairs: [%s]' % ', '.join(pairs),
            'tags: [%s]' % ', '.join(d['theme'] + [d['dyn'] + d['form']]),
            'source: S3+S1+S2',
            'license: public-domain',
            'copyright: { text: public-domain, annotations: cc-by-4.0 }',
            '---',
            '',
        ]
        if d.get('irregular'):
            fm.insert(-2, 'irregular: %s' % d['irregular'])
        if any(x != 1 for x in split):
            fm.insert(-2, 'render_split: [%s]' % ', '.join(str(x) for x in split))

        head = '# %s%s' % (d['title'], ('（%s）' % sub) if sub else '')
        body = [
            head,
            '',
            '> %s · %s · %s · 初中 · %s' % (d['author'], d['dyn'], d['form'], d['volume']),
            '',
            '## 必背%s' % ('全文' if d.get('recite') == 'full' else '名句'),
            '',
        ]
        for l in lines:
            body.append(l)
            body.append('')
        body += [
            '## 注释',
            '',
            '- （待补：字词注释）',
            '',
            '## 译文',
            '',
            '（待补：白话译文）',
            '',
            '## 赏析',
            '',
            '（待补：文学常识与赏析）',
            '',
            '## 玩法数据',
            '',
            '- 游戏单元：%d 个%s' % (n, '整句' if d['form'] not in ('文言',) else '名句'),
            '- 联句：%s' % ('、'.join('第%d⇄第%d' % (a + 1, b + 1) for a, b in
                                    [(int(x.split('-')[0]), int(x.split('-')[1]))
                                     for x in pairs]) or '（无）'),
            '- 背诵要求：%s' % d.get('recite', 'line'),
            '',
        ]

        out = POEMS_DIR / d['volume'] / ('%s.md' % d['title'])
        if out.exists():
            print('  ! 跳过（已存在）%s' % out.relative_to(ROOT))
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('\n'.join(fm + body), encoding='utf-8')
        written += 1
        print('  ✓ %s %s' % (d['volume'], d['title']))

    print('[gen] 写出 %d 篇，暂缓 %d 篇' % (written, pending))


if __name__ == '__main__':
    main()