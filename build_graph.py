"""Knowledge graph builder - processes articles from all registered databases."""
import sys, os, yaml, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.adapters import (
    InstitutionsAdapter, LiangkeHistoricalAdapter, LiangkeDailyAdapter,
)
from core.extractor import extract_article_meta
from core.graph import KnowledgeGraph
from core.llm import get_llm, extract_batch


def run():
    cfg_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    config = yaml.safe_load(open(cfg_path, encoding='utf-8'))
    kg_config = config['knowledge_graph']
    output_path = os.path.join(os.path.dirname(__file__), kg_config['output'])
    batch_size = kg_config.get('batch_size', 50)

    # LLM config
    llm_cfg = config.get('llm', {}).get('entity_extraction', {})
    llm_enabled = llm_cfg.get('enabled', True)
    llm_batch_size = llm_cfg.get('batch_size', 20)
    llm_max_calls = llm_cfg.get('max_calls_per_run', 10)
    llm_client = get_llm() if llm_enabled else None

    # Load existing graph
    print('[LOAD] Loading existing knowledge graph...')
    kg = KnowledgeGraph.load(output_path)
    stats = kg.get_stats()
    print(f'  Nodes: {stats["total_nodes"]}, Edges: {stats["total_edges"]}')

    # Build adapters
    adapters = build_adapters(config)
    print(f'[ADAPTERS] {len(adapters)} databases registered')
    print(f'[LLM] Entity extraction: {"enabled" if llm_client else "disabled"}')

    total_processed = 0
    llm_call_count = 0

    for adapter in adapters:
        last_id = kg.processed_state.get(adapter.name, 0)
        total_count = adapter.get_total_count()
        unprocessed = adapter.get_unprocessed_ids(last_id)

        if not unprocessed:
            print(f'\n[{adapter.name}] Up to date (last_id={last_id}, total={total_count})')
            continue

        print(f'\n[{adapter.name}] {len(unprocessed)} new articles (last_id={last_id}, total={total_count})')

        for i in range(0, len(unprocessed), batch_size):
            batch_ids = unprocessed[i:i + batch_size]
            articles = adapter.get_articles(batch_ids)

            # Rule-based extraction (use standardized tags if available)
            for art in articles:
                entities, relations = extract_article_meta(art)
                # Merge standardized tags from DB if present
                if art.tags:
                    try:
                        std_tags = json.loads(art.tags) if isinstance(art.tags, str) else art.tags
                        if isinstance(std_tags, dict):
                            for inst in std_tags.get('institutions', []):
                                entities.setdefault('institution', []).append(inst)
                            for tech in std_tags.get('technologies', []):
                                entities.setdefault('technology', []).append(tech)
                            for prod in std_tags.get('products', []):
                                entities.setdefault('product', []).append(prod)
                            for topic in std_tags.get('tags', []):
                                entities.setdefault('topic', []).append(topic)
                        elif isinstance(std_tags, list):
                            # Old format: plain list of topic tags
                            for t in std_tags:
                                if isinstance(t, str) and t not in ('资本运作','产品动态','企业资讯','科技前沿','宏观态势'):
                                    entities.setdefault('topic', []).append(t)
                        # Deduplicate
                        for k in entities:
                            entities[k] = sorted(set(entities[k]))
                    except (json.JSONDecodeError, TypeError):
                        pass
                kg.add_article(art, entities, relations)

            # LLM enhancement for deep relations
            if llm_client and llm_call_count < llm_max_calls:
                batch_titles = [(j, a.title) for j, a in enumerate(articles) if a.title and len(a.title) > 15]
                if len(batch_titles) >= 5:
                    for j in range(0, len(batch_titles), llm_batch_size):
                        if llm_call_count >= llm_max_calls:
                            break
                        sub = batch_titles[j:j + llm_batch_size]
                        sub_indices = [idx for idx, _ in sub]
                        sub_only_titles = [t for _, t in sub]
                        llm_results = extract_batch(llm_client, sub_only_titles)
                        llm_call_count += 1

                        for result in llm_results:
                            llm_idx = result.get('idx', 0) - 1
                            if 0 <= llm_idx < len(sub_indices):
                                art_idx = sub_indices[llm_idx]
                                art = articles[art_idx]
                                # Add LLM-extracted entities
                                for ent in result.get('entities', []):
                                    name = ent.get('name', '')
                                    etype = ent.get('type', '')
                                    if name and not kg.G.has_node(name):
                                        kg.G.add_node(name, type=etype)
                                        kg.node_counts[name] += 1
                                # Add LLM-extracted relations
                                for rel in result.get('relations', []):
                                    s = rel.get('subject', '')
                                    o = rel.get('object', '')
                                    r = rel.get('relation', '')
                                    if s and o and r:
                                        if not kg.G.has_node(s):
                                            kg.G.add_node(s, type='unknown')
                                        if not kg.G.has_node(o):
                                            kg.G.add_node(o, type='unknown')
                                        kg.G.add_edge(s, o, relation=r)
                                        kg.edge_counts[(s, o, r)] += 1

                    print(f'  LLM enhanced ({llm_call_count}/{llm_max_calls} calls)')

            kg.update_processed(adapter.name, batch_ids[-1])
            total_processed += len(articles)
            print(f'  Batch {i // batch_size + 1}: processed {len(articles)} articles')

    # Save
    print(f'\n[SAVE] Saving graph ({total_processed} new articles processed)...')
    kg.save(output_path)

    final_stats = kg.get_stats()
    print(f'  Nodes: {final_stats["total_nodes"]}')
    print(f'  Edges: {final_stats["total_edges"]}')
    print(f'  Node types: {final_stats["node_types"]}')
    print(f'  Relation types: {final_stats["relation_types"]}')
    print(f'[OK] Graph saved to {output_path}')


def build_adapters(config):
    adapters = []
    for db_cfg in config['databases']:
        if not db_cfg.get('enabled', True):
            continue
        name = db_cfg['name']
        if name == 'institutions':
            adapters.append(InstitutionsAdapter(db_cfg['path']))
        elif name == 'liangke_historical':
            adapters.append(LiangkeHistoricalAdapter(db_cfg['path']))
        elif name == 'liangke_daily':
            adapters.append(LiangkeDailyAdapter(
                db_cfg['host'], db_cfg['port'],
                db_cfg['user'], db_cfg['password'], db_cfg['database'],
            ))
        else:
            print(f'  Unknown DB type: {name}')
    return adapters


if __name__ == '__main__':
    run()
