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
    stats = {'total_tags': 0, 'total_inst': 0, 'total_tech': 0, 'total_prod': 0, 'total_people': 0}

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

                stats['total_tags'] += len(result.get('tags', []))
                stats['total_inst'] += len(result.get('institutions', []))
                stats['total_tech'] += len(result.get('technologies', []))
                stats['total_prod'] += len(result.get('products', []))
                stats['total_people'] += len(result.get('people', []))
                total += 1

            print(f'  Tagged {total} articles...', end='\r')

    print(f'\n\n[DONE] {total} articles tagged')
    print(f'  Topic tags: {stats["total_tags"]}')
    print(f'  Institution mentions: {stats["total_inst"]}')
    print(f'  Technology mentions: {stats["total_tech"]}')
    print(f'  Product mentions: {stats["total_prod"]}')
    print(f'  People mentions: {stats["total_people"]}')


def _write_tags(adapter, art, result, tags_json):
    """Write tags back to the article in its source DB."""
    conn = adapter._connect()
    try:
        cur = conn.cursor()
        row_id = int(art.id.split(':')[-1])

        if adapter.name == 'liangke_daily':
            # MySQL: merge with existing 5-category tag (DictCursor)
            cur.execute('SELECT tags FROM articles WHERE id = %s', (row_id,))
            existing = cur.fetchone()
            existing_tags = []
            if existing and existing.get('tags'):
                raw = existing['tags']
                try:
                    existing_tags = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    existing_tags = []
            five_cat = [t for t in existing_tags if t in ('资本运作','产品动态','企业资讯','科技前沿','宏观态势')]
            merged = result['tags'] + five_cat
            cur.execute('UPDATE articles SET tags = %s WHERE id = %s',
                       (json.dumps(merged, ensure_ascii=False), row_id))
            conn.commit()
        else:
            # SQLite
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
