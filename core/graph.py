"""Knowledge graph storage using NetworkX + JSON export."""
import json, os
from collections import defaultdict

import networkx as nx


class KnowledgeGraph:
    def __init__(self):
        self.G = nx.MultiGraph()
        self.node_counts = defaultdict(int)        # node_id → article count
        self.edge_counts = defaultdict(int)         # (src, tgt, rel) → count
        self.processed_state = {}                   # db_name → last_processed_id

    def add_article(self, article, entities, relations):
        """Add an article node and all extracted entity/relation nodes."""
        # Article node
        self.G.add_node(
            article.id,
            type='article',
            title=article.title[:120],
            source=article.source,
            date=article.publish_date,
            db=article.db_name,
        )
        self.node_counts[article.id] += 1

        # Extract year from publish_date for time tracking
        year = article.publish_date[:4] if article.publish_date else ''

        # Entity nodes
        for etype, names in entities.items():
            for name in names:
                if not self.G.has_node(name):
                    self.G.add_node(name, type=etype)
                self.node_counts[name] += 1

        # Relation edges
        seen_edges = set()
        for rel in relations:
            subj, obj, rtype = rel['subject'], rel['object'], rel['relation']
            if not self.G.has_node(subj) or not self.G.has_node(obj):
                continue
            key = (subj, obj, rtype)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            # Track years for this edge
            if self.G.has_edge(subj, obj):
                for k in self.G[subj][obj]:
                    if self.G[subj][obj][k].get('relation') == rtype:
                        years = set(self.G[subj][obj][k].get('years', []))
                        if year:
                            years.add(year)
                        self.G[subj][obj][k]['years'] = sorted(years)
                        break
                else:
                    self.G.add_edge(subj, obj, relation=rtype, years=[year] if year else [])
            else:
                self.G.add_edge(subj, obj, relation=rtype, years=[year] if year else [])
            self.edge_counts[key] += 1

    def update_processed(self, db_name, last_id):
        """Mark the last processed article ID for a database."""
        self.processed_state[db_name] = last_id

    def get_stats(self):
        """Return graph statistics."""
        node_types = defaultdict(int)
        for n, data in self.G.nodes(data=True):
            node_types[data.get('type', 'unknown')] += 1

        rel_types = defaultdict(int)
        for u, v, data in self.G.edges(data=True):
            rel_types[data.get('relation', 'unknown')] += 1

        return {
            'total_nodes': self.G.number_of_nodes(),
            'total_edges': self.G.number_of_edges(),
            'node_types': dict(node_types),
            'relation_types': dict(rel_types),
            'processed_state': self.processed_state,
        }

    def to_json(self):
        """Export graph as JSON for visualization."""
        nodes = []
        for n, data in self.G.nodes(data=True):
            nodes.append({
                'id': n,
                'type': data.get('type', 'unknown'),
                'count': self.node_counts.get(n, 1),
                'title': data.get('title', ''),
                'source': data.get('source', ''),
                'date': data.get('date', ''),
            })

        edges = []
        seen = set()
        for u, v, data in self.G.edges(data=True):
            rel = data.get('relation', '')
            key = (u, v, rel)
            if key in seen:
                continue
            seen.add(key)
            edges.append({
                'source': u,
                'target': v,
                'relation': rel,
                'count': self.edge_counts.get(key, 1),
                'articles': data.get('articles', ''),
                'reason': data.get('reason', ''),
                'confidence': data.get('confidence', ''),
                'years': data.get('years', []),
            })

        return {
            'meta': {
                'stats': self.get_stats(),
            },
            'nodes': nodes,
            'edges': edges,
        }

    @classmethod
    def load(cls, path):
        """Load graph from JSON file."""
        kg = cls()
        if not os.path.exists(path):
            return kg

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Restore processed state
        meta = data.get('meta', {})
        kg.processed_state = meta.get('stats', {}).get('processed_state', {})

        # Restore graph
        for node in data.get('nodes', []):
            nid = node['id']
            kg.G.add_node(
                nid,
                type=node.get('type', 'unknown'),
                title=node.get('title', ''),
                source=node.get('source', ''),
                date=node.get('date', ''),
            )
            kg.node_counts[nid] = node.get('count', 1)

        for edge in data.get('edges', []):
            src, tgt, rel = edge['source'], edge['target'], edge['relation']
            kg.G.add_edge(src, tgt, relation=rel,
                          articles=edge.get('articles', ''),
                          reason=edge.get('reason', ''),
                          confidence=edge.get('confidence', ''),
                          years=edge.get('years', []))
            kg.edge_counts[(src, tgt, rel)] = edge.get('count', 1)

        return kg

    def save(self, path):
        """Save graph to JSON file."""
        data = self.to_json()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
