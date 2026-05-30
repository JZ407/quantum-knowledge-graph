"""LLM client wrapper for knowledge graph entity extraction."""
import sys, os, yaml

sys.path.insert(0, 'D:/Claude_code/rag_system/rag_system')
from llm_client import LLMClient


def get_llm():
    cfg_path = 'D:/Claude_code/knowledge_graph/config.yaml'
    cfg = yaml.safe_load(open(cfg_path, encoding='utf-8'))
    rag_cfg = yaml.safe_load(open('D:/Claude_code/rag_system/config.yaml', encoding='utf-8'))
    llm_cfg = rag_cfg['llm']
    return LLMClient(
        provider='openai',
        api_key=llm_cfg['api_key'],
        api_base=llm_cfg['api_base'],
        model=llm_cfg['model'],
        max_tokens=2048,
        timeout=120,
    )


def extract_batch(client, titles_batch):
    """Extract entities and relations from a batch of article titles using LLM."""
    title_list = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(titles_batch))
    prompt = f"""从以下量子计算新闻标题中，提取关键实体和关系。输出 JSON 数组。

实体类型：institution(机构), person(人物), technology(技术平台), product(产品), topic(主题)
关系类型：ACQUIRES(收购), PARTNERS_WITH(合作), RELEASES(发布), WORKS_AT(任职)

只提取明确在标题中出现的实体。不认识的名字不要编造。
每个标题输出一个 JSON 对象：{{"idx": 编号, "entities": [{{"name": "", "type": ""}}], "relations": [{{"subject": "", "relation": "", "object": ""}}]}}

标题列表：
{title_list}

输出 JSON 数组："""

    try:
        response = client.chat([{'role': 'user', 'content': prompt}])
        # Extract JSON from response
        import json, re
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception:
        pass
    return []
