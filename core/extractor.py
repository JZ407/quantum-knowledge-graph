"""Entity and relation extraction: rule-based + LLM fallback."""
import re
from collections import defaultdict
from .entity_dict import (
    INSTITUTIONS, TECH_PLATFORMS, TOPIC_TAGS,
    KNOWN_PEOPLE, PRODUCTS, RELATION_PATTERNS, normalize_entity,
)


def _match(text, alias):
    """Match alias in text, using word boundary for short names (≤4 chars)."""
    alias_lower = alias.lower()
    if len(alias) <= 4:
        return bool(re.search(r'\b' + re.escape(alias_lower) + r'\b', text))
    return alias_lower in text


def extract_entities_rule(title, content=''):
    """Rule-based entity extraction from title and content."""
    text = (title + ' ' + (content or '')[:500]).lower()
    entities = defaultdict(set)

    # Institutions
    for canonical, aliases in INSTITUTIONS.items():
        for alias in aliases:
            if _match(text, alias):
                entities['institution'].add(canonical)
                break

    # Tech platforms
    for canonical, aliases in TECH_PLATFORMS.items():
        for alias in aliases:
            if _match(text, alias):
                entities['technology'].add(canonical)
                break

    # Topics
    for canonical, aliases in TOPIC_TAGS.items():
        for alias in aliases:
            if _match(text, alias):
                entities['topic'].add(canonical)
                break

    # People
    title_lower = title.lower()
    for canonical, aliases in KNOWN_PEOPLE.items():
        for alias in aliases:
            if _match(title_lower, alias):
                entities['person'].add(canonical)
                break

    # Products
    for canonical, aliases in PRODUCTS.items():
        for alias in aliases:
            if _match(text, alias):
                entities['product'].add(canonical)
                break

    return {k: sorted(v) for k, v in entities.items()}


def extract_relations_rule(title):
    """Rule-based relation extraction from title text."""
    relations = []
    text = title  # Relations primarily from title

    for pattern, rel_type in RELATION_PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            subj_raw = m.group(1).strip()
            obj_raw = m.group(2).strip()

            # Clean noise words
            noise = {'the', 'a', 'an', 'its', 'new', 'first', 'next', 'major', 'key'}
            if subj_raw.lower() in noise or obj_raw.lower() in noise:
                continue

            # Normalize
            subj = normalize_entity(subj_raw)
            obj = normalize_entity(obj_raw)

            if subj != subj_raw or obj != obj_raw:  # At least one matched a known entity
                relations.append({
                    'subject': subj,
                    'relation': rel_type,
                    'object': obj,
                })

    return relations


def extract_article_meta(article):
    """Extract all entities and relations for one article."""
    entities = extract_entities_rule(article.title, article.content)
    relations = extract_relations_rule(article.title)

    # PUBLISHED_BY relation: article → source institution
    source_entity = normalize_entity(article.source)
    if source_entity != article.source:
        relations.append({
            'subject': article.id,
            'relation': 'PUBLISHED_BY',
            'object': source_entity,
        })

    # MENTIONS relations: article → mentioned institution
    for inst in entities.get('institution', []):
        if inst != source_entity:
            relations.append({
                'subject': article.id,
                'relation': 'MENTIONS',
                'object': inst,
            })

    # COVERS_TOPIC relations
    for topic in entities.get('topic', []):
        relations.append({
            'subject': article.id,
            'relation': 'COVERS_TOPIC',
            'object': topic,
        })

    # USES_TECH relations
    for tech in entities.get('technology', []):
        relations.append({
            'subject': source_entity,
            'relation': 'USES_TECH',
            'object': tech,
        })

    return entities, relations
