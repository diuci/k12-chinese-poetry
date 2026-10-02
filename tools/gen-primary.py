#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量生成篇目 Markdown —— 小学 4–6 年级。

与 migrate.py 的区别：
  migrate.py 是**一次性**工具，从游戏内 poems.js 迁移已有的 45 首；
  本脚本按人教社统编教材册次，逐首生成 4–6 年级的篇目。

每首的数据（正文、主题、情感、难度等）都写在本文件顶部的 DATA 里，
便于集中审阅。生成后 .md 文件即为唯一事实源，后续校订直接改 .md。

用法：
    python tools/gen-primary.py            # 生成小学 4-6 年级
    python tools/gen-primary.py --dry      # 只检查，不写文件
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POEMS_DIR = ROOT / 'poems' / '小学'

# ============================================================================
# DATA
#   volume  册次
#   form    体裁
#   dyn     朝代
#   theme   主题标签
#   emo     情感
#   tech    表现手法
#   diff    难度 1-5
#   freq    中考/高考出现频率估值0-1
#   lines   正文（整句，带标点；数据层会剥离标点）
#   sub     副标题（同名消歧）
# ============================================================================

DATA = [
    # ============================== 四年级上册 ==============================
    dict(id='luchai', volume='四年级上册', title='鹿柴', author='王维', dyn='唐',
         form='五言', theme=['山水', '幽静'], emo='空山幽寂的清幽',
         tech=['对偶', '以动衬静'], diff=2, freq=0.7,
         lines=['空山不见人，但闻人语响。', '返景入深林，复照青苔上。']),
    dict(id='mujiangyin', volume='四年级上册', title='暮江吟', author='白居易', dyn='唐',
         form='七言', theme=['秋天', '写景'], emo='暮景闲适的惬意',
         tech=['比喻', '炼字'], diff=3, freq=0.5,
         lines=['一道残阳铺水中，半江瑟瑟半江红。', '可怜九月初三夜，露似真珠月似弓。']),
    dict(id='longpo', volume='四年级上册', title='题西林壁', author='苏轼', dyn='宋',
         form='七言', theme=['哲理', '山水'], emo='看事物要全面、要辩证',
         tech=['议论', '比喻'], diff=2, freq=0.9,
         lines=['横看成岭侧成峰，远近高低各不同。', '不识庐山真面目，只缘身在此山中。']),
    dict(id='xuemei', volume='四年级上册', title='雪梅', author='卢梅坡', dyn='宋',
         form='七言', theme=['咏物', '哲理'], emo='各有所长、互为补充',
         tech=['对比', '托物言志'], diff=3, freq=0.5,
         lines=['梅雪争春未肯降，骚人搁笔费评章。', '梅须逊雪三分白，雪却输梅一段香。']),
    dict(id='change', volume='四年级上册', title='嫦娥', author='李商隐', dyn='唐',
         form='七言', theme=['神话', '孤独'], emo='孤高之姿的寂寞悲凉',
         tech=['托物言志'], diff=3, freq=0.4,
         lines=['云母屏风烛影深，长河渐落晓星沉。', '嫦娥应悔偷灵药，碧海青天夜夜心。']),
    dict(id='chusai', volume='四年级上册', title='出塞', author='王昌龄', dyn='唐',
         form='七言', theme=['边塞', '家国'], emo='对良将的渴望与忧国',
         tech=['对比', '用典'], diff=3, freq=0.9,
         lines=['秦时明月汉时关，万里长征人未还。', '但使龙城飞将在，不教胡马度阴山。']),
    dict(id='liangzhouci-wanghan', volume='四年级上册', title='凉州词', author='王翰', dyn='唐',
         form='七言', theme=['边塞', '豪壮'], emo='将士出征前的豪迈与悲凉',
         tech=['对比', '夸张'], diff=3, freq=0.8,
         lines=['葡萄美酒夜光杯，欲饮琵琶马上催。', '醉卧沙场君莫笑，古来征战几人回。']),
    dict(id='xiarijueju', volume='四年级上册', title='夏日绝句', author='李清照', dyn='宋',
         form='五言', theme=['爱国', '气节'], emo='宁死不屈的浩然正气',
         tech=['借古讽今', '对比'], diff=2, freq=0.8,
         lines=['生当作人杰，死亦为鬼雄。', '至今思项羽，不肯过江东。']),
    dict(id='biedongda', volume='四年级上册', title='别董大', author='高适', dyn='唐',
         form='七言', theme=['送别', '豪迈'], emo='送别中的豪迈与慰藉',
         tech=['对比', '白描'], diff=3, freq=0.7,
         lines=['千里黄云白日曛，北风吹雁雪纷纷。', '莫愁前路无知己，天下谁人不识君。']),

    # ============================== 四年级下册 ==============================
    dict(id='suxinshi', volume='四年级下册', title='宿新市徐公店', author='杨万里', dyn='宋',
         form='七言', theme=['春天', '童趣'], emo='油菜花中扑蝶的童趣',
         tech=['拟人', '白描'], diff=2, freq=0.7,
         lines=['篱落疏疏一径深，树头新绿未成阴。', '儿童急走追黄蝶，飞入菜花无处寻。']),
    dict(id='sishitianyuan-25', volume='四年级下册', title='四时田园杂兴', sub='其二十五',
         author='范成大', dyn='宋', form='七言', theme=['田园', '劳动'], emo='农事繁忙的生气',
         tech=['白描'], diff=3, freq=0.5,
         lines=['梅子金黄杏子肥，麦花雪白菜花稀。', '日长篱落无人过，惟有蜻蜓蛱蝶飞。']),
    dict(id='qingpingyue-cunju', volume='四年级下册', title='清平乐', sub='村居',
         author='辛弃疾', dyn='宋', form='词', theme=['田园', '家庭'], emo='农家和睦的闲适温馨',
         tech=['白描'], diff=3, freq=0.5,
         lines=['茅檐低小，溪上青青草。', '醉里吴音相媚好，白发谁家翁媪。',
                '大儿锄豆溪东，中儿正织鸡笼。', '最喜小儿亡赖，溪头卧剥莲蓬。']),
    dict(id='feng-mi', volume='四年级下册', title='蜂', author='罗隐', dyn='唐',
         form='七言', theme=['咏物', '讽喻'], emo='赞美辛勤、批评不劳而获',
         tech=['托物言志', '对比'], diff=3, freq=0.7,
         lines=['不论平地与山尖，无限风光尽被占。', '采得百花成蜜后，为谁辛苦为谁甜。']),
    dict(id='duzuojingting', volume='四年级下册', title='独坐敬亭山', author='李白', dyn='唐',
         form='五言', theme=['山水', '孤独'], emo='怀才不遇的孤独',
         tech=['拟人', '反复'], diff=2, freq=0.5,
         lines=['众鸟高飞尽，孤云独去闲。', '相看两不厌，只有敬亭山。']),
    dict(id='furonglou', volume='四年级下册', title='芙蓉楼送辛渐', author='王昌龄', dyn='唐',
         form='七言', theme=['送别', '冰心'], emo='送别中的高洁与自信',
         tech=['比喻', '用典'], diff=3, freq=0.9,
         lines=['寒雨连江夜入吴，平明送客楚山孤。', '洛阳亲友如相问，一片冰心在玉壶。']),
    dict(id='saixiaqu', volume='四年级下册', title='塞下曲', author='卢纶', dyn='唐',
         form='五言', theme=['边塞', '雪'], emo='将士雪夜追击的英武',
         tech=['白描', '侧面描写'], diff=3, freq=0.8,
         lines=['月黑雁飞高，单于夜遁逃。', '欲将轻骑逐，大雪满弓刀。']),
    dict(id='momei', volume='四年级下册', title='墨梅', author='王冕', dyn='元',
         form='七言', theme=['咏物', '志趣'], emo='不媚世俗的高洁',
         tech=['托物言志'], diff=3, freq=0.8,
         lines=['我家洗砚池头树，朵朵花开淡墨痕。', '不要人夸好颜色，只留清气满乾坤。']),

    # ============================== 五年级上册 ==============================
    dict(id='qiqiao', volume='五年级上册', title='乞巧', author='林杰', dyn='唐',
         form='七言', theme=['节日', '七夕'], emo='七夕乞巧的民俗与愿望',
         tech=['对偶'], diff=3, freq=0.4,
         lines=['七夕今宵看碧霄，牵牛织女渡河桥。', '家家乞巧望秋月，穿尽红丝几万条。']),
    dict(id='shier', volume='五年级上册', title='示儿', author='陆游', dyn='宋',
         form='七言', theme=['爱国', '遗嘱'], emo='临终的悲愤与不甘',
         tech=['对比', '反问'], diff=3, freq=0.8,
         lines=['死去元知万事空，但悲不见九州同。', '王师北定中原日，家祭无忘告乃翁。']),
    dict(id='tilinandi', volume='五年级上册', title='题临安邸', author='林升', dyn='宋',
         form='七言', theme=['爱国', '讽刺'], emo='对权贵苟安的愤慨',
         tech=['对比', '反讽'], diff=3, freq=0.9,
         lines=['山外青山楼外楼，西湖歌舞几时休。', '暖风熏得游人醉，直把杭州作汴州。']),
    dict(id='jihai', volume='五年级上册', title='己亥杂诗', sub='其一百二十五',
         author='龚自珍', dyn='清', form='七言', theme=['爱国', '变革'], emo='呼唤变革的激情',
         tech=['象征'], diff=3, freq=0.8,
         lines=['九州生气恃风雷，万马齐喑究可哀。', '我劝天公重抖擞，不拘一格降人才。']),
    dict(id='shanjuqiuming', volume='五年级上册', title='山居秋暝', author='王维', dyn='唐',
         form='五言', theme=['山水', '隐居'], emo='秋山清幽的恬淡与归意',
         tech=['白描', '对比'], diff=3, freq=0.7,
         lines=['空山新雨后，天气晚来秋。', '明月松间照，清泉石上流。',
                '竹喧归浣女，莲动下渔舟。', '随意春芳歇，王孙自可留。']),
    dict(id='fengqiaoyebo', volume='五年级上册', title='枫桥夜泊', author='张继', dyn='唐',
         form='七言', theme=['秋天', '羁旅'], emo='客旅他乡的孤寂愁思',
         tech=['对比', '意象叠加'], diff=3, freq=0.9,
         lines=['月落乌啼霜满天，江枫渔火对愁眠。', '姑苏城外寒山寺，夜半钟声到客船。']),
    dict(id='changxiangsi', volume='五年级上册', title='长相思', sub='山一程',
         author='纳兰性德', dyn='清', form='词', theme=['思乡', '边塞'], emo='行军途中的思乡之情',
         tech=['白描'], diff=3, freq=0.5,
         lines=['山一程，水一程，身向榆关那畔行，夜深千帐灯。',
                '风一更，雪一更，聒碎乡心梦不成，故园无此声。']),
    dict(id='yugezi', volume='五年级上册', title='渔歌子', author='张志和', dyn='唐',
         form='词', theme=['渔隐', '闲适'], emo='悠然自得的渔家生活',
         tech=['白描', '色彩'], diff=3, freq=0.7,
         lines=['西塞山前白鹭飞，桃花流水鳜鱼肥。', '青箬笠，绿蓑衣，斜风细雨不须归。']),
    dict(id='guanshu', volume='五年级上册', title='观书有感', sub='其一',
         author='朱熹', dyn='宋', form='七言', theme=['哲理', '读书'], emo='读诗穷理的感悟',
         tech=['比喻', '议论'], diff=2, freq=0.9,
         lines=['半亩方塘一鉴开，天光云影共徘徊。', '问渠那得清如许，为有源头活水来。']),
    dict(id='zengwang', volume='五年级上册', title='长歌行', author='汉乐府', dyn='汉',
         form='杂言', theme=['惜时', '哲理'], emo='劝人惜时的恳切',
         tech=['比喻', '反复'], diff=3, freq=0.8,
         lines=['青青园中葵，朝露待日晞。', '阳春布德泽，万物生光辉。',
                '常恐秋节至，焜黄华叶衰。', '百川东到海，何时复西归。',
                '少壮不努力，老大徒伤悲。']),

    # ============================== 五年级下册 ==============================
    dict(id='sishitianyuan-31', volume='五年级下册', title='四时田园杂兴', sub='其三十一',
         author='范成大', dyn='宋', form='七言', theme=['田园', '劳动'], emo='夏日农忙的辛勤',
         tech=['白描'], diff=3, freq=0.6,
         lines=['昼出耘田夜绩麻，村庄儿女各当家。', '童孙未解供耕织，也傍桑阴学种瓜。']),
    dict(id='zhizibing', volume='五年级下册', title='稚子弄冰', author='杨万里', dyn='宋',
         form='七言', theme=['童趣', '冬天'], emo='孩童玩冰的天真与失落',
         tech=['白描', '细节'], diff=3, freq=0.5,
         lines=['稚子金盆脱晓冰，彩丝穿取当银铮。', '敲成玉磬穿林响，忽作玻璃碎地声。']),
    dict(id='cunwan', volume='五年级下册', title='村晚', author='雷震', dyn='宋',
         form='七言', theme=['田园', '傍晚'], emo='乡村傍晚的闲适安宁',
         tech=['白描', '炼字'], diff=3, freq=0.5,
         lines=['草满池塘水满陂，山衔落日浸寒漪。', '牧童归去横牛背，短笛无腔信口吹。']),
    dict(id='niaomingjian', volume='五年级下册', title='鸟鸣涧', author='王维', dyn='唐',
         form='五言', theme=['山水', '幽静'], emo='月夜山涧的清幽',
         tech=['以动衬静', '拟人'], diff=2, freq=0.6,
         lines=['人闲桂花落，夜静春山空。', '月出惊山鸟，时鸣春涧中。']),
    dict(id='congjunxing', volume='五年级下册', title='从军行', sub='其二',
         author='王昌龄', dyn='唐', form='七言', theme=['边塞', '家国'], emo='将士卫国的豪情',
         tech=['对偶', '夸张'], diff=3, freq=0.7,
         lines=['青海长云暗雪山，孤城遥望玉门关。', '黄沙百战穿金甲，不破楼兰终不还。']),
    dict(id='songyuaner', volume='五年级下册', title='送元二使安西', author='王维', dyn='唐',
         form='七言', theme=['送别', '友情'], emo='送别中的深挚与安慰',
         tech=['白描', '比喻'], diff=3, freq=0.9,
         lines=['渭城朝雨浥轻尘，客舍青青柳色新。', '劝君更尽一杯酒，西出阳关无故人。']),
    dict(id='qiuyejiangxiao', volume='五年级下册', title='秋夜将晓出篱门迎凉有感',
         author='陆游', dyn='宋', form='七言', theme=['爱国', '忧民'], emo='忧国忧民的悲愤',
         tech=['对比', '象征'], diff=3, freq=0.7,
         lines=['三万里河东入海，五千仞岳上摩天。', '遗民泪尽胡尘里，南望王师又一年。']),
    dict(id='liangzhouci-wangzhihuan', volume='五年级下册', title='凉州词', author='王之涣', dyn='唐',
         form='七言', theme=['边塞', '苍凉'], emo='边塞的苍凉与思乡',
         tech=['比喻', '反问'], diff=3, freq=0.9,
         lines=['黄河远上白云间，一片孤城万仞山。', '羌笛何须怨杨柳，春风不度玉门关。']),
    dict(id='huanghelou', volume='五年级下册', title='黄鹤楼送孟浩然之广陵', author='李白', dyn='唐',
         form='七言', theme=['送别', '友情'], emo='送友远行的怅惘',
         tech=['比喻', '白描'], diff=3, freq=0.9,
         lines=['故人西辞黄鹤楼，烟花三月下扬州。', '孤帆远影碧空尽，唯见长江天际流。']),
    dict(id='xiangcunsiyue', volume='五年级下册', title='乡村四月', author='翁卷', dyn='宋',
         form='七言', theme=['田园', '农忙'], emo='江南四月农忙的紧张充实',
         tech=['白描'], diff=3, freq=0.6,
         lines=['绿遍山原白满川，子规声里雨如烟。', '乡村四月闲人少，才了蚕桑又插田。']),

    # ============================== 六年级上册 ==============================
    dict(id='sujiandejiang', volume='六年级上册', title='宿建德江', author='孟浩然', dyn='唐',
         form='五言', theme=['羁旅', '愁思'], emo='羁旅他乡的孤寂愁思',
         tech=['比喻', '对比'], diff=3, freq=0.5,
         lines=['移舟泊烟渚，日暮客愁新。', '野旷天低树，江清月近人。']),
    dict(id='wanghulou', volume='六年级上册', title='六月二十七日望湖楼醉书', author='苏轼', dyn='宋',
         form='七言', theme=['写景', '暴雨'], emo='骤雨来去的畅快',
         tech=['比喻', '夸张'], diff=3, freq=0.8,
         lines=['黑云翻墨未遮山，白雨跳珠乱入船。', '卷地风来忽吹散，望湖楼下水如天。']),
    dict(id='xijiangyue', volume='六年级上册', title='西江月', sub='夜行黄沙道中',
         author='辛弃疾', dyn='宋', form='词', theme=['田园', '丰收'], emo='夏夜乡村的丰收喜悦',
         tech=['白描', '拟人'], diff=3, freq=0.8,
         lines=['明月别枝惊鹊，清风半夜鸣蝉。', '稻花香里说丰年，听取蛙声一片。',
                '七八个星天外，两三点雨山前。', '旧时茅店社林边，路转溪桥忽见。']),
    dict(id='guogurenzhuang', volume='六年级上册', title='过故人庄', author='孟浩然', dyn='唐',
         form='五言', theme=['田园', '友情'], emo='做客农家的闲适亲切',
         tech=['白描'], diff=3, freq=0.6,
         lines=['故人具鸡黍，邀我至田家。', '绿树村边合，青山郭外斜。',
                '开轩面场圃，把酒话桑麻。', '待到重阳日，还来就菊花。']),
    dict(id='chunri', volume='六年级上册', title='春日', author='朱熹', dyn='宋',
         form='七言', theme=['春天', '哲理'], emo='春游踏青的愉悦与哲思',
         tech=['比喻', '议论'], diff=3, freq=0.8,
         lines=['胜日寻芳泗水滨，无边光景一时新。', '等闲识得东风面，万紫千红总是春。']),
    dict(id='huixiangyoushu', volume='六年级上册', title='回乡偶书', sub='其一',
         author='贺知章', dyn='唐', form='七言', theme=['思乡', '感慨'], emo='久客他乡的感慨',
         tech=['对比', '细节'], diff=3, freq=0.9,
         lines=['少小离家老大回，乡音无改鬓毛衰。', '儿童相见不相识，笑问客从何处来。']),
    dict(id='langtaosha', volume='六年级上册', title='浪淘沙', sub='其一',
         author='刘禹锡', dyn='唐', form='词', theme=['黄河', '气势'], emo='黄河的雄伟气势',
         tech=['夸张', '白描'], diff=3, freq=0.8,
         lines=['九曲黄河万里沙，浪淘风簸自天涯。', '如今直上银河去，同到牵牛织女家。']),
    dict(id='jiangnanchun', volume='六年级上册', title='江南春', author='杜牧', dyn='唐',
         form='七言', theme=['春天', '江南'], emo='江南春色的明丽烟雨',
         tech=['对比', '象征'], diff=3, freq=0.9,
         lines=['千里莺啼绿映红，水村山郭酒旗风。', '南朝四百八十寺，多少楼台烟雨中。']),
    dict(id='shuhuyin', volume='六年级上册', title='书湖阴先生壁', author='王安石', dyn='宋',
         form='七言', theme=['田园', '赞主人'], emo='对友人家居风光的赞美',
         tech=['白描', '拟人'], diff=3, freq=0.7,
         lines=['茅檐长扫净无苔，花木成畦手自栽。', '一水护田将绿绕，两山排闼送青来。']),

    # ============================== 六年级下册 ==============================
    dict(id='hanshi', volume='六年级下册', title='寒食', author='韩翃', dyn='唐',
         form='七言', theme=['节日', '春景'], emo='寒食节的暮春之景',
         tech=['对比'], diff=3, freq=0.6,
         lines=['春城无处不飞花，寒食东风御柳斜。', '日暮汉宫传蜡烛，轻烟散入五侯家。']),
    dict(id='tiaotiaoqianniuxing', volume='六年级下册', title='迢迢牵牛星', author='佚名', dyn='汉',
         form='五言', theme=['神话', '思念'], emo='隔河相望的相思哀愁',
         tech=['叠词', '比喻'], diff=3, freq=0.5,
         lines=['迢迢牵牛星，皎皎河汉女。', '纤纤擢素手，札札弄机杼。',
                '终日不成章，泣涕零如雨。', '河汉清且浅，相去复几许。',
                '盈盈一水间，脉脉不得语。']),
    dict(id='shiyiwangyue', volume='六年级下册', title='十五夜望月', author='王建', dyn='唐',
         form='七言', theme=['节日', '思念'], emo='中秋思乡的寂寥',
         tech=['对比'], diff=3, freq=0.4,
         lines=['中庭地白树栖鸦，冷露无声湿桂花。', '今夜月明人尽望，不知秋思落谁家。']),
    dict(id='mashi', volume='六年级下册', title='马诗', sub='其五',
         author='李贺', dyn='唐', form='五言', theme=['咏物', '抱负'], emo='怀才不遇的愤懑',
         tech=['托物言志', '对比'], diff=3, freq=0.5,
         lines=['大漠沙如雪，燕山月似钩。', '何当金络脑，快走踏清秋。']),
    dict(id='shihuiyin', volume='六年级下册', title='石灰吟', author='于谦', dyn='明',
         form='七言', theme=['咏物', '气节'], emo='不屈于难的坚定信念',
         tech=['托物言志', '象征'], diff=3, freq=0.9,
         lines=['千锤万凿出深山，烈火焚烧若等闲。', '粉骨碎身浑不怕，要留清白在人间。']),
    dict(id='zhushi', volume='六年级下册', title='竹石', author='郑燮', dyn='清',
         form='七言', theme=['咏物', '坚韧'], emo='刚强不屈的意志',
         tech=['托物言志', '拟人'], diff=3, freq=0.9,
         lines=['咬定青山不放松，立根原在破岩中。', '千磨万击还坚劲，任尔东西南北风。']),
    dict(id='caiwei', volume='六年级下册', title='采薇', sub='节选',
         author='佚名', dyn='先秦', form='四言', theme=['边塞', '思乡'], emo='戍边将士的思乡之苦',
         tech=['起承转合', '细节'], diff=4, freq=0.6,
         lines=['昔我往矣，杨柳依依。', '今我来思，雨雪霏霏。',
                '行道迟迟，载渴载饥。', '我心伤悲，莫知我哀。']),
    dict(id='chunyexiyu', volume='六年级下册', title='春夜喜雨', author='杜甫', dyn='唐',
         form='五言', theme=['春天', '写景'], emo='喜雨及时而来的喜悦',
         tech=['拟人', '比喻'], diff=3, freq=0.9,
         lines=['好雨知时节，当春乃发生。', '随风潜入夜，润物细无声。',
                '野径云俱黑，江船火独明。', '晓看红湿处，花重锦官城。']),
    dict(id='wenguanjun', volume='六年级下册', title='闻官军收河南河北', author='杜甫', dyn='唐',
         form='七言', theme=['爱国', '喜悦'], emo='闻捷后狂喜难抑的欣喜',
         tech=['夸张', '拟人'], diff=3, freq=0.8,
         lines=['剑外忽传收蓟北，初闻涕泪满衣裳。', '却看妻子愁何在，漫卷诗书喜欲狂。',
                '白日放歌须纵酒，青春作伴好还乡。', '即从巴峡穿巫峡，便下襄阳向洛阳。']),
    dict(id='zaochun', volume='六年级下册', title='早春呈水部张十八员外', author='韩愈', dyn='唐',
         form='七言', theme=['春天', '写景'], emo='对早春景色的惊喜与赞美',
         tech=['比喻', '炼字'], diff=3, freq=0.8,
         lines=['天街小雨润如酥，草色遥看近却无。', '最是一年春好处，绝胜烟柳满皇都。']),
    dict(id='jiangshangyuzhe', volume='六年级下册', title='江上渔者', author='范仲淹', dyn='宋',
         form='五言', theme=['民生', '同情'], emo='对渔人疾苦的深切同情',
         tech=['对比', '议论'], diff=3, freq=0.7,
         lines=['江上往来人，但爱鲈鱼美。', '君看一叶舟，出没风波里。']),
    dict(id='bochuanguazhou', volume='六年级下册', title='泊船瓜洲', author='王安石', dyn='宋',
         form='七言', theme=['思乡', '炼意'], emo='思乡与归心似箭',
         tech=['比喻', '炼字'], diff=3, freq=0.9,
         lines=['京口瓜洲一水间，钟山只隔数重山。', '春风又绿江南岸，明月何时照我还。']),
    dict(id='youyuanbuzhi', volume='六年级下册', title='游园不值', author='叶绍翁', dyn='宋',
         form='七言', theme=['春天', '哲理'], emo='游春受阻却别有韵致的欣喜',
         tech=['对比', '转折'], diff=3, freq=0.8,
         lines=['应怜屐齿印苍苔，小扣柴扉久不开。', '春色满园关不住，一枝红杏出墙来。']),
    dict(id='bosuanzi-song', volume='六年级下册', title='卜算子', sub='送鲍浩然之浙东',
         author='王观', dyn='宋', form='词', theme=['送别', '友情'], emo='送别中的清丽祝福',
         tech=['比喻', '对比'], diff=3, freq=0.5,
         lines=['水是眼波横，山是眉峰聚。', '欲问行人去那边？眉眼盈盈处。',
                '才始送春归，又送君归去。', '若到江南赶上春，千万和春住。']),
    dict(id='huanxisha-qishui', volume='六年级下册', title='浣溪沙', sub='游蕲水清泉寺',
         author='苏轼', dyn='宋', form='词', theme=['哲理', '旷达'], emo='逆境中的人间生意',
         tech=['议论', '比喻'], diff=3, freq=0.6,
         lines=['山下兰芽短浸溪，松间沙路净无泥。', '萧萧暮雨子规啼。',
                '谁道人生无再少？门前流水尚能西！', '休将白发唱黄鸡。']),
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
        print('[gen] --dry：%d 篇待生成，不写文件' % len(DATA))
        for d in DATA:
            print('  %-22s %s / %s' % (d['id'], d['volume'], d['title']))
        return

    CN = '一二三四五六'

    def grade_of(volume):
        """从册次名推出年级数：'四年级上册' → 4。"""
        cn2num = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6}
        return cn2num[volume[0]]
    written = 0
    skipped = 0

    for d in DATA:
        grade = grade_of(d['volume'])
        lines = d['lines']
        n = len(lines)
        # 联句配对：整句两两成联；奇数时末句不配
        pairs = ['%d-%d' % (i, i + 1) for i in range(0, n - 1, 2)]
        # render_split：按逗号数推每句在地面拆几行
        split = [max(1, len([x for x in l.rstrip('。！？；').split('，') if x.strip()]))
                 for l in lines]
        if sum(split) != sum(len([x for x in l.rstrip('。！？；').split('，')
                                  if x.strip()]) for l in lines):
            pass# 自洽，无需处理

        sub = d.get('sub')
        fm = [
            '---',
            'id: %s' % d['id'],
            'title: %s' % d['title'],
            'subtitle: %s' % (sub if sub else 'null'),
            'author: %s' % d['author'],
            'dynasty: %s' % d['dyn'],
            'form: %s' % d['form'],
            'stage: 小学',
            'grade: %d' % grade,
            'volume: %s' % d['volume'],
            'textbooks: [统编]',
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
        if any(x != 1 for x in split):
            fm.insert(-2, 'render_split: [%s]' % ', '.join(str(x) for x in split))

        head = '# %s%s' % (d['title'], ('（%s）' % sub) if sub else '')
        body = [
            head,
            '',
            '> %s · %s · %s · 小学%s年级 · %s'
            % (d['author'], d['dyn'], d['form'], CN[grade - 1], d['volume']),
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
        ]

        out = POEMS_DIR / d['volume'] / ('%s.md' % d['title'])
        if out.exists():
            skipped += 1
            print('  ! 跳过（已存在）%s' % out.relative_to(ROOT))
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('\n'.join(fm + body), encoding='utf-8')
        written += 1
        print('  ✓ %-8s %s' % (d['volume'], d['title']))

    print('[gen] 写出 %d 篇，跳过 %d 篇' % (written, skipped))
    print('[gen] 注：注释/译文/赏析为占位，需后续人工撰写（CC BY 4.0）')


if __name__ == '__main__':
    main()