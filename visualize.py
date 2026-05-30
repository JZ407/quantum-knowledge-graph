"""Knowledge Graph Visualization - Streamlit + pyvis interactive graph."""
import sys, os, json, math
from collections import defaultdict

import streamlit as st
from pyvis.network import Network

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GRAPH_PATH = os.path.join(os.path.dirname(__file__), 'knowledge_graph.json')

st.set_page_config(page_title='量子计算知识图谱', layout='wide')
st.title('量子计算知识图谱')

# ── Load Data ─────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_graph():
    if not os.path.exists(GRAPH_PATH):
        return None
    with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

data = load_graph()
if not data:
    st.warning('图谱文件不存在，请先运行 build_graph.py')
    st.stop()

# ── Sidebar Filters ────────────────────────────────────────────────

st.sidebar.header('筛选')

# Entity type filter
node_types = defaultdict(int)
for n in data['nodes']:
    node_types[n['type']] += 1

selected_types = st.sidebar.multiselect(
    '实体类型',
    options=sorted(node_types.keys()),
    default=['institution', 'technology', 'product', 'topic', 'person'],
)

# Min article count
min_count = st.sidebar.slider('最少文章数', 1, 500, 2, 10)

# Search
search = st.sidebar.text_input('搜索实体', placeholder='输入名称...')

# Show stats
st.sidebar.markdown('---')
stats = data['meta']['stats']
st.sidebar.metric('总节点', stats['total_nodes'])
st.sidebar.metric('总边', stats['total_edges'])
st.sidebar.metric('文章数', stats['node_types'].get('article', 0))
st.sidebar.markdown('---')
st.sidebar.caption(f'处理状态: {json.dumps(stats.get("processed_state", {}), indent=2)}')

# ── Build Graph ────────────────────────────────────────────────────

COLORS = {
    'institution': '#4e79a7',
    'technology': '#f28e2b',
    'product': '#e15759',
    'topic': '#76b7b2',
    'person': '#59a14f',
}

# Filter nodes
filtered_nodes = []
entity_ids = set()
for n in data['nodes']:
    if n['type'] == 'article':
        continue
    if n['type'] not in selected_types:
        continue
    if n['count'] < min_count:
        continue
    if search and search.lower() not in n['id'].lower():
        continue
    filtered_nodes.append(n)
    entity_ids.add(n['id'])

# Filter edges between filtered entities
edges_between_entities = []
for e in data['edges']:
    if e['source'] in entity_ids and e['target'] in entity_ids:
        edges_between_entities.append(e)

# ── PyVis Network ──────────────────────────────────────────────────

st.subheader(f'实体关系网络 ({len(filtered_nodes)} 节点, {len(edges_between_entities)} 边)')

net = Network(height='650px', width='100%', directed=True, notebook=False)
net.set_options("""
{
  "physics": {
    "barnesHut": {
      "gravitationalConstant": -3000,
      "centralGravity": 0.3,
      "springLength": 200,
      "springConstant": 0.04
    },
    "minVelocity": 0.75
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 100
  }
}
""")

# Add nodes
max_count = max(n['count'] for n in filtered_nodes) if filtered_nodes else 1
for n in filtered_nodes:
    size = 10 + 30 * (n['count'] / max_count)
    label = n['id']
    if n['type'] in ('institution', 'product'):
        label = f'{n["id"]}\n({n["count"]}篇)'
    net.add_node(
        n['id'],
        label=label,
        title=f'{n["id"]}\n类型: {n["type"]}\n文章数: {n["count"]}',
        color=COLORS.get(n['type'], '#999'),
        size=size,
    )

# Add edges
for e in edges_between_entities:
    net.add_edge(
        e['source'], e['target'],
        title=e['relation'],
        label=e['relation'],
        arrows='to',
    )

# Save and display
html_path = os.path.join(os.path.dirname(__file__), 'graph_temp.html')
net.save_graph(html_path)
with open(html_path, 'r', encoding='utf-8') as f:
    st.components.v1.html(f.read(), height=700, scrolling=True)

# ── Entity Detail Table ────────────────────────────────────────────

st.markdown('---')
st.subheader('实体列表')

table_data = []
for n in filtered_nodes:
    # Find connected entities
    connected = set()
    for e in edges_between_entities:
        if e['source'] == n['id']:
            connected.add(f'{e["target"]} ({e["relation"]})')
        elif e['target'] == n['id']:
            connected.add(f'{e["source"]} ({e["relation"]})')

    table_data.append({
        '名称': n['id'],
        '类型': n['type'],
        '文章数': n['count'],
        '关联': ', '.join(sorted(connected)[:5]) + ('...' if len(connected) > 5 else ''),
    })

table_data.sort(key=lambda x: -x['文章数'])
st.dataframe(table_data, use_container_width=True, hide_index=True)

# ── Relation Type Distribution ─────────────────────────────────────

st.markdown('---')
col1, col2 = st.columns(2)
with col1:
    st.subheader('节点类型分布')
    st.bar_chart({k: v for k, v in node_types.items() if k != 'article'})
with col2:
    st.subheader('关系类型分布')
    st.bar_chart({k: v for k, v in stats['relation_types'].items() if v > 1})
