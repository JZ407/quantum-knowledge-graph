"""Project-based unified article tagger - each project reads only its own tag group."""
import jieba, json, re

# ── 周报项目：五大类标签 (互斥，每篇一个) ─────────────────────────

WEEKLY_CATEGORIES = {
    '资本运作': [
        '融资', '投资', '风投', 'ipo', '上市', '招股', '估值', '亿美元', '万美元',
        '千万', '百万', '亿元', '收购', '并购', '合并', '分拆', '剥离', '整合',
        '资助', '拨款', '补贴', '基金', '预算', '经费', '营收', '收入', '利润',
        '亏损', '财报', '业绩', '增长', '股权', '股东', '控股', '参股', '注资',
        '增资', '扩股', 'a轮', 'b轮', 'c轮', 'd轮', '种子轮', '天使轮', '战略融资',
        'raise', 'raised', 'raises', 'raising', 'funding', 'fund', 'funds',
        'series', 'equity', 'offering', 'pricing of', 'closes', 'acquires',
        'stock', 'shares', 'shareholder', 'market cap', 'capital', 'backed by',
        'led by', 'investor', 'venture', 'grant', 'awarded', 'contract award',
        'million dollar', 'billion dollar', 'm deal', 'mn deal',
    ],
    '产品动态': [
        '产品', '发布', '推出', '芯片', '处理器', '计算机', '量子计算机', '量子芯片',
        '量子处理器', '原型机', '样机', '系统', '平台', '软件', '工具', 'sdk', 'api',
        '云服务', '升级', '迭代', '性能', '指标', '保真度', '相干时间', '低温',
        '制冷机', '测控', '封装', '互联', '模块化', '量产', '商用', '部署', '交付',
        '生产线', '制造', 'launch', 'launches', 'release', 'unveil', 'roadmap',
    ],
    '企业资讯': [
        'ibm', 'google', '谷歌', '微软', 'microsoft', '亚马逊', 'amazon',
        '英伟达', 'nvidia', '英特尔', 'intel', 'ionq', 'rigetti', 'xanadu',
        'pasqal', 'd-wave', 'quera', 'quantinuum', '国盾量子', '本源量子',
        '国仪量子', '华为', '合作', '协议', '签约', '伙伴', '联盟', '成员',
        '任命', '高管', 'ceo', 'cto', '总裁', '创始人', '离职',
        '扩建', '新厂', '研发中心', '总部', '分部', '办事处',
        'partner', 'partnership', 'collaborat', 'alliance', 'consortium',
        'appoint', 'executive', 'chief',
    ],
    '科技前沿': [
        '论文', '研究', '突破', '实验', '发现', '理论', '算法', '模型',
        '量子比特', '量子门', '量子电路', '量子纠缠', '量子叠加',
        '量子纠错', '逻辑量子比特', '物理量子比特', '量子体积',
        '超导', '离子阱', '光量子', '中性原子', '硅自旋', '拓扑',
        '量子模拟', '量子机器学习', '变分量子', 'vqa', 'vqe',
        'arxiv', 'nature', 'science', '物理评论', 'prl',
        '预印本', '实验验证', '原理验证', '科学', '学术', '期刊',
        'research', 'breakthrough', 'paper', 'published', 'journal',
    ],
    '宏观态势': [
        '政策', '战略', '规划', '法规', '标准', '出口管制', '制裁', '法案',
        '人才', '教育', '培训', '科研', '产学研', '市场', '产业', '生态',
        '趋势', '报告', '预测', '全球', '国际', '国家量子', '量子计划',
        '路线图', '白皮书', '指南', '倡议', '竞争', '领先', '差距', '挑战',
        '机遇', '风险', 'market', 'industry', 'report', 'forecast', 'talent',
    ],
}

WEEKLY_PRIORITY = ['资本运作', '产品动态', '企业资讯', '科技前沿', '宏观态势']


# ── 知识图谱项目：实体标签 ─────────────────────────────────────────

from .entity_dict import (
    INSTITUTIONS, TECH_PLATFORMS, TOPIC_TAGS, KNOWN_PEOPLE, PRODUCTS,
)


# ── 检索筛选项目：细粒度主题标签 ──────────────────────────────────

SEARCH_TAGS = {
    '量子计算': ['quantum comput', 'quantum processor', 'qubit', '量子计算', '量子比特', 'qpu'],
    '量子纠错': ['error correct', 'fault-tolerant', 'surface code', 'logical qubit', '量子纠错', '容错'],
    '量子通信/QKD': ['quantum communic', 'qkd', 'quantum key', 'quantum network', '量子通信', '量子密钥'],
    '后量子密码': ['post-quantum', 'pqc', 'quantum safe', 'quantum-safe', '后量子', '抗量子'],
    '量子传感': ['quantum sens', 'magnetometer', 'gravimeter', '量子传感', '量子测量', 'atomic clock'],
    '超导': ['superconducting', 'transmon', 'josephson', '超导', 'superconductor'],
    '离子阱': ['ion trap', 'trapped ion', '离子阱', '囚禁离子', 'ytterbium'],
    '光量子': ['photonic', 'photon', 'squeezed light', '光量子', '光子'],
    '中性原子': ['neutral atom', 'rydberg', 'optical tweezer', '中性原子', '里德堡'],
    '拓扑': ['topological qubit', 'majorana', 'anyon', '拓扑', 'majorana zero mode'],
    '硅自旋': ['silicon spin', 'spin qubit', '硅自旋', 'quantum dot'],
    '金刚石NV': ['NV center', 'nitrogen vacancy', 'diamond qubit', 'NV色心'],
    '量子机器学习': ['quantum machine learning', 'quantum neural', '量子机器学习', 'tensorflow quantum'],
    '量子化学': ['quantum chemistry', 'molecular simulat', 'vqe', '量子化学', '量子模拟'],
    '融资商业': ['funding', 'series', 'raised', 'million', 'billion', 'ipo', '融资', '投资', '收购', '上市', '估值'],
    '产品发布': ['launch', 'release', 'unveil', 'roadmap', '产品', '发布', '推出', 'chip', 'processor'],
    '合作生态': ['partner', 'alliance', 'collaborat', 'agreement', 'mou', '合作', '战略', '联盟'],
    '政策标准': ['policy', 'regulation', 'standard', 'nist', '政策', '标准', '法规', '监管', '路线图'],
    '半导体': ['semiconductor', 'cmos', 'foundry', 'wafer', 'fab', '半导体', '芯片', '制造'],
    'HPC/超算': ['hpc', 'supercomput', 'gpu', 'hybrid classical', '高性能计算', '超算'],
    '国防军事': ['darpa', 'air force', 'army', 'navy', 'defense', 'military', '国防', '军事'],
    '量子教育': ['education', 'training', 'course', 'workshop', 'hackathon', '教育', '培训'],
    '能源': ['energy', 'battery', 'solar', 'grid', '能源', '电池', '电网', '太阳能'],
    '金融': ['finance', 'banking', 'portfolio', 'risk', 'trading', '金融', '银行', '保险'],
    '医药': ['drug', 'pharma', 'protein', 'molecular', 'clinical', '制药', '药物', '蛋白', '临床'],
}


def tag_article(title, content='', source=''):
    """Return project-based tags in a structured dict."""
    text = ((title or '') + ' ' + (content or '')[:2000]).lower()

    # ── 周报项目 ────────────────────────────────────────────────
    weekly_scores = {}
    for cat, keywords in WEEKLY_CATEGORIES.items():
        score = 0
        for kw in keywords:
            if kw.lower() in text:
                score += 1
        weekly_scores[cat] = score

    if max(weekly_scores.values()) > 0:
        weekly_tag = max(WEEKLY_PRIORITY, key=lambda t: (weekly_scores[t], WEEKLY_PRIORITY.index(t)))
    else:
        weekly_tag = '宏观态势'

    # ── 知识图谱项目 ─────────────────────────────────────────────
    institutions = []
    for canonical, aliases in INSTITUTIONS.items():
        for alias in aliases:
            if alias.lower() in text:
                institutions.append(canonical)
                break

    technologies = []
    for canonical, aliases in TECH_PLATFORMS.items():
        for alias in aliases:
            if alias.lower() in text:
                technologies.append(canonical)
                break

    products = []
    for canonical, aliases in PRODUCTS.items():
        for alias in aliases:
            if alias.lower() in text:
                products.append(canonical)
                break

    people = []
    title_lower = (title or '').lower()
    for canonical, aliases in KNOWN_PEOPLE.items():
        for alias in aliases:
            if alias.lower() in title_lower:
                people.append(canonical)
                break

    # ── 检索筛选项目 ────────────────────────────────────────────
    search_tags = []
    for tag_name, keywords in SEARCH_TAGS.items():
        for kw in keywords:
            if kw.lower() in text:
                search_tags.append(tag_name)
                break

    return {
        'weekly': [weekly_tag],
        'knowledge_graph': {
            'institutions': sorted(set(institutions)),
            'technologies': sorted(set(technologies)),
            'products': sorted(set(products)),
            'people': sorted(set(people)),
        },
        'search_tags': sorted(set(search_tags)),
    }
