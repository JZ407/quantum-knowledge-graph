"""Deep relation extraction: scan all articles for institution-to-institution relations using LLM."""
import sys, os, json, re, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.llm import get_llm
from core.entity_dict import INSTITUTIONS
from core.graph import KnowledgeGraph

GRAPH_PATH = os.path.join(os.path.dirname(__file__), 'knowledge_graph.json')


def build_institution_index():
    """Build a map from alias (lowercase) to canonical institution name."""
    index = {}
    for canonical, aliases in INSTITUTIONS.items():
        for alias in aliases:
            index[alias.lower()] = canonical
    return index


def find_cooccurring_institutions(kg, inst_index):
    """Find all article pairs where 2+ institutions are mentioned together."""
    article_nodes = [n for n, d in kg.G.nodes(data=True) if d.get('type') == 'article']
    cooccurrences = defaultdict(list)  # (inst_a, inst_b) → [(title, article_id)]

    for art_id in article_nodes:
        data = kg.G.nodes[art_id]
        title = data.get('title', '')
        if not title:
            continue

        # Find all institutions mentioned in this article (via MENTIONS edges)
        mentioned = set()
        for _, tgt, edge_data in kg.G.edges(art_id, data=True):
            if edge_data.get('relation') == 'MENTIONS':
                mentioned.add(tgt)

        if len(mentioned) < 2:
            continue

        # Record all pairs
        mentioned_list = sorted(mentioned)
        for i in range(len(mentioned_list)):
            for j in range(i + 1, len(mentioned_list)):
                pair = (mentioned_list[i], mentioned_list[j])
                cooccurrences[pair].append((title[:150], art_id))

    return cooccurrences


def run():
    print('[LOAD] Loading knowledge graph...')
    kg = KnowledgeGraph.load(GRAPH_PATH)
    inst_index = build_institution_index()
    llm_client = get_llm()

    print('[SCAN] Finding institution co-occurrences...')
    cooc = find_cooccurring_institutions(kg, inst_index)
    print(f'  Found {len(cooc)} institution pairs co-occurring in articles')

    # Sort by frequency, focus on pairs that appear together often
    sorted_pairs = sorted(cooc.items(), key=lambda x: -len(x[1]))

    new_relations = 0
    llm_calls = 0
    batch_size = 15

    # Process top 100 most frequent pairs
    for (inst_a, inst_b), articles in sorted_pairs[:200]:
        if len(articles) < 1:
            break

        # Check if edge already exists
        existing_rels = set()
        if kg.G.has_edge(inst_a, inst_b):
            for d in kg.G[inst_a][inst_b].values():
                existing_rels.add(d.get('relation', ''))

        # Update existing edges with article data if missing
        has_strong = False
        strong_rel = None
        for r in existing_rels:
            if r in ('PARTNERS_WITH', 'ACQUIRES', 'SUPPLIES_TO', 'COMPETES_WITH'):
                has_strong = True
                strong_rel = r
                break

        if has_strong and strong_rel:
            # Check if existing edge already has articles
            has_articles = False
            if kg.G.has_edge(inst_a, inst_b):
                for key, d in kg.G[inst_a][inst_b].items():
                    if d.get('relation') == strong_rel:
                        if d.get('articles'):
                            has_articles = True
                        else:
                            # Update with article data, skip LLM
                            article_json = json.dumps([t for t, _ in articles[:10]], ensure_ascii=False)
                            kg.G[inst_a][inst_b][key]['articles'] = article_json
                            new_relations += 1
            if has_articles:
                continue  # Already complete, skip

        # Collect representative titles
        sample_titles = [t for t, _ in articles[:5]]

        # Use LLM to classify the relationship
        title_list = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(sample_titles))
        prompt = f"""以下新闻标题同时提到了「{inst_a}」和「{inst_b}」。请判断这两个机构之间的关系类型。

关系类型：
- PARTNERS_WITH: 合作关系、战略联盟、共同研发
- COMPETES_WITH: 竞争关系
- ACQUIRES: 一方收购或有意收购另一方
- SUPPLIES_TO: 一方为另一方提供产品或服务
- MENTIONS: 仅在新闻报道中被同时提及，无明显直接关系

只输出一个 JSON 对象：{{"relation": "关系类型", "confidence": "high/medium/low", "reason": "一句话说明"}}

标题：
{title_list}

输出："""

        try:
            response = llm_client.chat([{'role': 'user', 'content': prompt}])
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                result = json.loads(json_match.group(0))
                rel_type = result.get('relation', '')
                confidence = result.get('confidence', '')
                reason = result.get('reason', '')

                if rel_type and rel_type != 'MENTIONS':
                    article_json = json.dumps([t for t, _ in articles[:10]], ensure_ascii=False)
                    # Update existing edge or create new one
                    if kg.G.has_edge(inst_a, inst_b):
                        for key in list(kg.G[inst_a][inst_b].keys()):
                            if kg.G[inst_a][inst_b][key].get('relation') == rel_type:
                                kg.G[inst_a][inst_b][key]['articles'] = article_json
                                kg.G[inst_a][inst_b][key]['confidence'] = confidence
                                kg.G[inst_a][inst_b][key]['reason'] = reason
                                break
                        else:
                            kg.G.add_edge(inst_a, inst_b, relation=rel_type,
                                          confidence=confidence, reason=reason,
                                          articles=article_json)
                    else:
                        kg.G.add_edge(inst_a, inst_b, relation=rel_type,
                                      confidence=confidence, reason=reason,
                                      articles=article_json)
                    kg.edge_counts[(inst_a, inst_b, rel_type)] += len(articles)
                    new_relations += 1
                    print(f'  [{rel_type}] {inst_a} → {inst_b} ({confidence}, {len(articles)} articles) - {reason[:80]}')

            llm_calls += 1
            if llm_calls % 5 == 0:
                time.sleep(0.5)

        except Exception as e:
            print(f'  ERROR: {e}')

    print(f'\n[DONE] {new_relations} new relations added ({llm_calls} LLM calls)')
    kg.save(GRAPH_PATH)
    print(f'[SAVE] Graph updated')


if __name__ == '__main__':
    run()
