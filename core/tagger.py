"""Unified article tagger - jieba + entity dictionary for all 12K articles."""
import jieba, json, re
from collections import defaultdict
from .entity_dict import (
    INSTITUTIONS, TECH_PLATFORMS, TOPIC_TAGS, KNOWN_PEOPLE, PRODUCTS, normalize_entity,
)

# Fine-grained tag categories (matching daily_report_app.py FINE_TAG_MAP)
ENTITY_TAG_MAP = {
    '量子计算': ['quantum comput', 'quantum processor', 'qubit', '量子计算', '量子比特', 'qpu', 'quantum chip'],
    '量子纠错': ['error correct', 'fault-tolerant', 'fault tolerant', 'surface code',
              'logical qubit', 'quantum error', '量子纠错', '容错', '纠错码'],
    '超导': ['superconducting', 'transmon', 'josephson', '超导', 'superconductor'],
    '离子阱': ['ion trap', 'trapped ion', 'ytterbium', 'barium ion', '离子阱', '囚禁离子'],
    '光量子': ['photonic', 'photon', 'squeezed light', '光量子', '光子'],
    '中性原子': ['neutral atom', 'rydberg', 'optical tweezer', 'optical lattice', '中性原子', '里德堡'],
    '拓扑': ['topological', 'majorana', 'anyon', '拓扑', 'majorana zero mode'],
    '量子通信': ['quantum communic', 'qkd', 'quantum key', 'quantum network', '量子通信', '量子密钥', '量子网络'],
    '后量子密码': ['post-quantum', 'pqc', 'quantum safe', 'quantum-safe', '后量子', '抗量子', '量子安全'],
    '量子传感': ['quantum sens', 'magnetometer', 'gravimeter', '量子传感', '量子测量', 'atomic clock'],
    'AI/ML': ['machine learning', 'neural network', 'llm', 'gpt', '人工智能', '机器学习', '深度学习'],
    '融资商业': ['funding', 'series', 'raised', 'million', 'billion', 'ipo', 'nyse', 'nasdaq',
              '融资', '投资', '收购', '上市', '估值', '财报', '营收', '利润', '股权'],
    '产品动态': ['launch', 'release', 'unveil', 'roadmap', 'sdk', '产品', '发布', '推出',
              'chip', 'processor', '芯片', '处理器', 'system', '平台', 'platform'],
    '企业资讯': ['partner', 'alliance', 'collaborat', 'agreement', 'mou',
              'appoint', 'ceo', 'cfo', 'cto', 'executive',
              '合作', '战略', '联盟', '任命', '高管'],
    '政策标准': ['policy', 'regulation', 'standard', 'nist', '政策', '标准', '法规', '监管'],
    '半导体': ['semiconductor', 'cmos', 'foundry', 'wafer', 'fab', '半导体', '芯片', '制造', '晶圆'],
    '科技前沿': ['research', 'breakthrough', 'nature', 'science', '论文', '研究', '突破',
              'arxiv', '预印本', 'journal', '期刊', 'discover'],
    '宏观态势': ['market', 'industry', 'report', 'forecast', '市场', '产业', '趋势',
              'talent', 'education', '人才', '教育', '培训'],
}


def tag_article(title, content='', source=''):
    """Generate standardized tags for a single article.

    Returns a dict with:
    - tags: fine-grained topic tags (list)
    - institutions: mentioned institutions (list)
    - technologies: tech platforms (list)
    - products: mentioned products (list)
    - people: mentioned people (list)
    """
    text = ((title or '') + ' ' + (content or '')[:2000]).lower()
    words = set(jieba.lcut(text))
    words_lower = {w.strip().lower() for w in words if len(w.strip()) >= 2}

    # Fine-grained tags
    tags = []
    for tag_name, keywords in ENTITY_TAG_MAP.items():
        for kw in keywords:
            if kw.lower() in text:
                tags.append(tag_name)
                break

    # Institutions
    institutions = []
    for canonical, aliases in INSTITUTIONS.items():
        for alias in aliases:
            if alias.lower() in text:
                institutions.append(canonical)
                break

    # Technologies
    technologies = []
    for canonical, aliases in TECH_PLATFORMS.items():
        for alias in aliases:
            if alias.lower() in text:
                technologies.append(canonical)
                break

    # Products
    products = []
    for canonical, aliases in PRODUCTS.items():
        for alias in aliases:
            if alias.lower() in text:
                products.append(canonical)
                break

    # People
    people = []
    title_lower = (title or '').lower()
    for canonical, aliases in KNOWN_PEOPLE.items():
        for alias in aliases:
            if alias.lower() in title_lower:
                people.append(canonical)
                break

    return {
        'tags': tags,
        'institutions': institutions,
        'technologies': technologies,
        'products': products,
        'people': people,
    }
