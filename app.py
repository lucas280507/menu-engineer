"""
Dashboard de Engenharia de Cardápio
====================================
Aplicação Streamlit para automatizar a análise de cardápio
baseada no Método de Kasavana & Smith.

Inclui sistema de autenticação com streamlit-authenticator
e integração com MongoDB Atlas para credenciais.

Execução: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from pymongo import MongoClient

# ──────────────────────────────────────────────
# Configuração da página
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Engenharia de Cardápio",
    page_icon="🍽️",
    layout="wide",
)

# ──────────────────────────────────────────────
# CSS personalizado
# ──────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Fonte global */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Cabeçalho principal */
    .main-title {
        text-align: center;
        padding: 1.2rem 0 0.2rem;
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #f97316, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-title {
        text-align: center;
        color: #9ca3af;
        margin-bottom: 1.8rem;
        font-size: 1rem;
    }

    /* Cards de métrica */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
        border: 1px solid #4338ca;
        border-radius: 12px;
        padding: 1rem 1.4rem;
        box-shadow: 0 4px 20px rgba(67, 56, 202, 0.25);
    }
    div[data-testid="stMetric"] label { color: #c7d2fe !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #e0e7ff !important;
        font-weight: 700;
    }

    /* Tabela de exemplo */
    .example-table {
        width: 100%;
        border-collapse: collapse;
        margin: 0.6rem 0 1.2rem;
        font-size: 0.85rem;
    }
    .example-table th {
        background: #312e81;
        color: #e0e7ff;
        padding: 0.5rem 0.8rem;
        text-align: left;
    }
    .example-table td {
        padding: 0.45rem 0.8rem;
        border-bottom: 1px solid #334155;
        color: #94a3b8;
    }

    /* Badges de classificação */
    .badge-estrela   { background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:6px; font-weight:600; }
    .badge-burro     { background:#dbeafe; color:#1e40af; padding:2px 8px; border-radius:6px; font-weight:600; }
    .badge-quebra    { background:#ede9fe; color:#5b21b6; padding:2px 8px; border-radius:6px; font-weight:600; }
    .badge-cao       { background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:6px; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════
# AUTENTICAÇÃO — MongoDB Atlas
# ══════════════════════════════════════════════

@st.cache_resource
def get_mongo_client():
    """Conecta ao MongoDB Atlas usando a URI armazenada em st.secrets."""
    try:
        client = MongoClient(st.secrets["mongo_uri"])
        # Testa a conexão
        client.admin.command("ping")
        return client
    except Exception as e:
        st.error(f"❌ Falha ao conectar ao MongoDB: {e}")
        st.stop()


def carregar_credenciais_mongo() -> dict:
    """
    Busca a coleção 'usuarios' no banco 'cardapio_auth' e monta
    o dicionário de credenciais no formato exigido pelo
    streamlit-authenticator.

    Estrutura esperada de cada documento no MongoDB:
    {
        "username": "admin",
        "name": "Administrador",
        "email": "admin@email.com",
        "password_hash": "$2b$12$..."   ← hash bcrypt
    }
    """
    client = get_mongo_client()
    db = client["cardapio_auth"]
    colecao = db["usuarios"]

    credenciais: dict = {"usernames": {}}

    for doc in colecao.find():
        username = doc.get("username")
        if not username:
            continue
        credenciais["usernames"][username] = {
            "name": doc.get("name", username),
            "email": doc.get("email", ""),
            "password": doc.get("password_hash", ""),
        }

    if not credenciais["usernames"]:
        st.error(
            "❌ Nenhum usuário encontrado na coleção `usuarios` do banco "
            "`cardapio_auth`. Certifique-se de ter inserido os documentos "
            "no MongoDB."
        )
        st.stop()

    return credenciais


# Carrega credenciais do MongoDB
credenciais = carregar_credenciais_mongo()

# Inicializa o autenticador
authenticator = stauth.Authenticate(
    credentials=credenciais,
    cookie_name="cardapio_auth_cookie",
    cookie_key="chave_secreta_cardapio_2024",
    cookie_expiry_days=30,
)

# ──────────────────────────────────────────────
# Tela de Login
# ──────────────────────────────────────────────
try:
    authenticator.login()
except Exception as e:
    st.error(f"Erro no login: {e}")

# Tratamento do estado de autenticação
if st.session_state.get("authentication_status") is False:
    st.error("❌ Usuário ou senha incorretos.")
    st.stop()

if st.session_state.get("authentication_status") is None:
    st.markdown(
        '<p class="main-title">🍽️ Dashboard de Engenharia de Cardápio</p>',
        unsafe_allow_html=True,
    )
    st.warning("👆 Por favor, insira seu usuário e senha para acessar o sistema.")
    st.stop()


# ══════════════════════════════════════════════
# ÁREA AUTENTICADA — Só chega aqui se logado
# ══════════════════════════════════════════════

# ──────────────────────────────────────────────
# Título
# ──────────────────────────────────────────────
st.markdown(
    '<p class="main-title">🍽️ Dashboard de Engenharia de Cardápio</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="sub-title">Método de Kasavana &amp; Smith — Classificação automática de pratos</p>',
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────
# Colunas esperadas no CSV
# ──────────────────────────────────────────────
COLUNAS_OBRIGATORIAS = [
    "Nome do Prato",
    "Custo Unitário",
    "Preço de Venda",
    "Quantidade Vendida",
]

# ──────────────────────────────────────────────
# Sidebar — Usuário logado + Upload + exemplo
# ──────────────────────────────────────────────
with st.sidebar:
    # Boas-vindas e logout
    st.markdown(f"### 👋 Olá, **{st.session_state.get('name', '')}**!")
    authenticator.logout("🚪 Sair", key="logout_btn")
    st.markdown("---")

    st.header("📂 Importar Dados")
    st.caption("Faça upload de um arquivo `.csv` com as colunas obrigatórias.")

    # Exemplo visual de como o CSV deve ser estruturado
    st.markdown("**Estrutura esperada do CSV:**")
    st.markdown(
        """
        <table class="example-table">
            <tr><th>Nome do Prato</th><th>Custo Unitário</th><th>Preço de Venda</th><th>Quantidade Vendida</th></tr>
            <tr><td>Filé Mignon</td><td>22.50</td><td>59.90</td><td>120</td></tr>
            <tr><td>Salada Caesar</td><td>8.00</td><td>32.00</td><td>85</td></tr>
            <tr><td>…</td><td>…</td><td>…</td><td>…</td></tr>
        </table>
        """,
        unsafe_allow_html=True,
    )

    arquivo = st.file_uploader("Selecione o arquivo CSV", type=["csv"])

# ──────────────────────────────────────────────
# Se nenhum arquivo foi enviado, mostrar instruções
# ──────────────────────────────────────────────
if arquivo is None:
    st.info("👈 Envie um arquivo CSV pela barra lateral para começar a análise.")
    st.stop()

# ──────────────────────────────────────────────
# Leitura e validação do CSV
# ──────────────────────────────────────────────
try:
    df = pd.read_csv(arquivo)
except Exception as e:
    st.error(f"❌ Erro ao ler o arquivo CSV: {e}")
    st.stop()

# Verificar colunas obrigatórias
colunas_faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
if colunas_faltantes:
    st.error(
        f"❌ O arquivo está com colunas ausentes ou nomeadas incorretamente.\n\n"
        f"**Colunas faltantes:** {', '.join(colunas_faltantes)}\n\n"
        f"**Colunas encontradas:** {', '.join(df.columns.tolist())}"
    )
    st.stop()

# Validar tipos numéricos
try:
    df["Custo Unitário"] = pd.to_numeric(df["Custo Unitário"], errors="raise")
    df["Preço de Venda"] = pd.to_numeric(df["Preço de Venda"], errors="raise")
    df["Quantidade Vendida"] = pd.to_numeric(df["Quantidade Vendida"], errors="raise")
except (ValueError, TypeError):
    st.error(
        "❌ As colunas numéricas contêm valores inválidos. "
        "Verifique se não há texto em 'Custo Unitário', 'Preço de Venda' "
        "ou 'Quantidade Vendida'."
    )
    st.stop()

# Verificar se há dados
if df.empty:
    st.warning("⚠️ O arquivo CSV está vazio. Adicione dados e tente novamente.")
    st.stop()

# ──────────────────────────────────────────────
# MOTOR DE CÁLCULOS
# ──────────────────────────────────────────────
# 1. Margem de Contribuição
df["Margem de Contribuição (R$)"] = df["Preço de Venda"] - df["Custo Unitário"]

# 2. Mix de Vendas (%)
total_vendido = df["Quantidade Vendida"].sum()
df["Mix de Vendas (%)"] = (df["Quantidade Vendida"] / total_vendido) * 100

# 3. Linhas de corte
media_margem = df["Margem de Contribuição (R$)"].mean()               # Eixo X
num_pratos = len(df)
media_popularidade = (1 / num_pratos) * 0.70 * 100                    # em %, Eixo Y


# ──────────────────────────────────────────────
# CLASSIFICAÇÃO NA MATRIZ
# ──────────────────────────────────────────────
def classificar(row: pd.Series) -> str:
    """Retorna a classificação do prato segundo Kasavana & Smith."""
    margem_alta = row["Margem de Contribuição (R$)"] >= media_margem
    mix_alto = row["Mix de Vendas (%)"] >= media_popularidade

    if margem_alta and mix_alto:
        return "Estrela 🌟"
    elif (not margem_alta) and mix_alto:
        return "Burro de Carga 🐴"
    elif margem_alta and (not mix_alto):
        return "Quebra-Cabeça 🧩"
    else:
        return "Cão 🐶"


df["Classificação"] = df.apply(classificar, axis=1)

# ──────────────────────────────────────────────
# PLANO DE AÇÃO AUTOMÁTICO
# ──────────────────────────────────────────────
ACOES = {
    "Estrela 🌟": "Manter padrão de qualidade e estimular vendas.",
    "Burro de Carga 🐴": "Reduzir custo dos ingredientes ou aumentar preço discretamente.",
    "Quebra-Cabeça 🧩": "Dar destaque no cardápio visual ou criar combos.",
    "Cão 🐶": "Retirar do cardápio ou reformular prato e nome.",
}
df["Ação Recomendada"] = df["Classificação"].map(ACOES)

# ──────────────────────────────────────────────
# INTERFACE DE SAÍDA
# ──────────────────────────────────────────────

# — Métricas no topo —
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    st.metric("📊 Média da Margem (Linha de Corte X)", f"R$ {media_margem:,.2f}")
with col2:
    st.metric("📈 Média de Popularidade (Linha de Corte Y)", f"{media_popularidade:,.2f}%")
with col3:
    st.metric("🍽️ Total de Pratos Analisados", num_pratos)

st.markdown("---")

# — Contagem por classificação —
st.subheader("Resumo por Classificação")
contagem = df["Classificação"].value_counts()
cols_resumo = st.columns(4)
labels_ordem = ["Estrela 🌟", "Burro de Carga 🐴", "Quebra-Cabeça 🧩", "Cão 🐶"]
for i, label in enumerate(labels_ordem):
    with cols_resumo[i]:
        qtd = int(contagem.get(label, 0))
        st.metric(label, qtd)

st.markdown("---")

# ──────────────────────────────────────────────
# GRÁFICO DE DISPERSÃO (Plotly)
# ──────────────────────────────────────────────
st.subheader("Matriz de Kasavana & Smith")

# Cores por classificação
CORES = {
    "Estrela 🌟": "#facc15",
    "Burro de Carga 🐴": "#3b82f6",
    "Quebra-Cabeça 🧩": "#a855f7",
    "Cão 🐶": "#ef4444",
}

fig = go.Figure()

# Plotar pontos agrupados por classificação (para legenda)
for classif, cor in CORES.items():
    subset = df[df["Classificação"] == classif]
    if subset.empty:
        continue
    fig.add_trace(
        go.Scatter(
            x=subset["Margem de Contribuição (R$)"],
            y=subset["Mix de Vendas (%)"],
            mode="markers+text",
            marker=dict(size=14, color=cor, line=dict(width=1, color="#1e1b4b")),
            text=subset["Nome do Prato"],
            textposition="top center",
            textfont=dict(size=10),
            name=classif,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Margem: R$ %{x:,.2f}<br>"
                "Mix: %{y:.2f}%<br>"
                "<extra></extra>"
            ),
        )
    )

# Linha de corte X (margem média) — vertical
fig.add_vline(
    x=media_margem,
    line_dash="dash",
    line_color="#94a3b8",
    line_width=1.5,
    annotation_text=f"Média Margem: R${media_margem:,.2f}",
    annotation_position="top",
    annotation_font_color="#94a3b8",
)

# Linha de corte Y (popularidade média) — horizontal
fig.add_hline(
    y=media_popularidade,
    line_dash="dash",
    line_color="#94a3b8",
    line_width=1.5,
    annotation_text=f"Média Popularidade: {media_popularidade:,.2f}%",
    annotation_position="right",
    annotation_font_color="#94a3b8",
)

# Anotações nos quadrantes
x_range = df["Margem de Contribuição (R$)"]
y_range = df["Mix de Vendas (%)"]
x_min, x_max = x_range.min(), x_range.max()
y_min, y_max = y_range.min(), y_range.max()

quadrante_labels = [
    dict(x=media_margem + (x_max - media_margem) / 2, y=media_popularidade + (y_max - media_popularidade) / 2, text="⭐ Estrela"),
    dict(x=media_margem - (media_margem - x_min) / 2, y=media_popularidade + (y_max - media_popularidade) / 2, text="🐴 Burro de Carga"),
    dict(x=media_margem + (x_max - media_margem) / 2, y=media_popularidade - (media_popularidade - y_min) / 2, text="🧩 Quebra-Cabeça"),
    dict(x=media_margem - (media_margem - x_min) / 2, y=media_popularidade - (media_popularidade - y_min) / 2, text="🐶 Cão"),
]

for ql in quadrante_labels:
    fig.add_annotation(
        x=ql["x"], y=ql["y"], text=ql["text"],
        showarrow=False,
        font=dict(size=14, color="rgba(148,163,184,0.45)"),
    )

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15,15,30,0.6)",
    xaxis_title="Margem de Contribuição (R$)",
    yaxis_title="Mix de Vendas (%)",
    height=560,
    margin=dict(t=40, b=60, l=60, r=40),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="center",
        x=0.5,
        font=dict(size=12),
    ),
)

st.plotly_chart(fig, width="stretch")

# ──────────────────────────────────────────────
# TABELA FINAL
# ──────────────────────────────────────────────
st.markdown("---")
st.subheader("📋 Tabela Detalhada")

# Formatar colunas monetárias para exibição
df_display = df.copy()
df_display["Custo Unitário"] = df_display["Custo Unitário"].map("R$ {:,.2f}".format)
df_display["Preço de Venda"] = df_display["Preço de Venda"].map("R$ {:,.2f}".format)
df_display["Margem de Contribuição (R$)"] = df_display["Margem de Contribuição (R$)"].map("R$ {:,.2f}".format)
df_display["Mix de Vendas (%)"] = df_display["Mix de Vendas (%)"].map("{:.2f}%".format)

st.dataframe(
    df_display,
    width="stretch",
    hide_index=True,
    column_order=[
        "Nome do Prato",
        "Custo Unitário",
        "Preço de Venda",
        "Quantidade Vendida",
        "Margem de Contribuição (R$)",
        "Mix de Vendas (%)",
        "Classificação",
        "Ação Recomendada",
    ],
)

# ──────────────────────────────────────────────
# Rodapé
# ──────────────────────────────────────────────
st.markdown("---")
st.caption("Desenvolvido com ❤️ usando Streamlit · Método de Kasavana & Smith")
