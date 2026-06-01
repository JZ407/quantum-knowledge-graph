"""Bulk-tag all 12,000 articles across 3 databases using unified tagger."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.tagger import tag_article
from core.adapters import (
    InstitutionsAdapter, LiangkeHistoricalAdapter, LiangkeDailyAdapter,
)

ADAPTERS = [
    InstitutionsAdapter('../institution_news/institutions.db'),
    LiangkeHistoricalAdapter('../liangke_historical/historical.db'),
    LiangkeDailyAdapter('127.0.0.1', 3306, 'scraper', 'scraper123', 'liangke_scraper'),
]

TAG_COLUMN = 'tags'  # Column name varies: MySQL uses 'tags', SQLite uses 'tags'

def run():
    total = 0
    stats = {'weekly': 0, 'kg_inst': 0, 'kg_tech': 0, 'kg_prod': 0, 'kg_people': 0, 'search': 0}

    for adapter in ADAPTERS:
        count = adapter.get_total_count()
        print(f'\n[{adapter.name}] {count} articles')

        # Process in batches
        batch_size = 100
        for offset in range(0, count, batch_size):
            ids = adapter.get_unprocessed_ids(offset)
            ids = ids[:batch_size]
            if not ids:
                break

            articles = adapter.get_articles(ids)
            for art in articles:
                result = tag_article(art.title, art.content, art.source)
                tags_json = json.dumps(result, ensure_ascii=False)

                # Write tags back to the appropriate DB
                _write_tags(adapter, art, result, tags_json)

                kg = result.get('knowledge_graph', {})
                stats['weekly'] += len(result.get('weekly', []))
                stats['kg_inst'] += len(kg.get('institutions', []))
                stats['kg_tech'] += len(kg.get('technologies', []))
                stats['kg_prod'] += len(kg.get('products', []))
                stats['kg_people'] += len(kg.get('people', []))
                stats['search'] += len(result.get('search_tags', []))
                total += 1

            print(f'  Tagged {total} articles...', end='\r')

    print(f'\n\n[DONE] {total} articles tagged')
    print(f'  周报标签: {stats["weekly"]}')
    print(f'  知识图谱-机构: {stats["kg_inst"]}')
    print(f'  知识图谱-技术: {stats["kg_tech"]}')
    print(f'  知识图谱-产品: {stats["kg_prod"]}')
    print(f'  知识图谱-人物: {stats["kg_people"]}')
    print(f'  检索标签: {stats["search"]}')


def _write_tags(adapter, art, result, tags_json):
    """Write project-based tags back to DB."""
    conn = adapter._connect()
    try:
        cur = conn.cursor()
        row_id = int(art.id.split(':')[-1])

        if adapter.name == 'liangke_daily':
            cur.execute('UPDATE articles SET tags = %s WHERE id = %s',
                       (tags_json, row_id))
            conn.commit()
        else:
            conn.execute('UPDATE articles SET tags = ? WHERE id = ?', (tags_json, row_id))
            conn.commit()
    except Exception as e:
        print(f'\n  ERROR writing tags for {art.id}: {e}')
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    run()
