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
import requests
import json
import io
import time
from datetime import datetime
from bson import ObjectId
from typing import Optional

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


# ──────────────────────────────────────────────
# Funções de Banco de Dados (Clientes & Histórico)
# ──────────────────────────────────────────────
def listar_clientes_mongo(username: str) -> list[dict]:
    """Retorna a lista de clientes cadastrados para o usuário."""
    try:
        client = get_mongo_client()
        db = client["cardapio_auth"]
        colecao = db["clientes"]
        cursor = colecao.find({"username": username}).sort("nome", 1)
        clientes = []
        for doc in cursor:
            clientes.append({
                "_id": str(doc["_id"]),
                "nome": doc.get("nome", "Sem nome"),
                "cnpj": doc.get("cnpj", ""),
                "uf": doc.get("uf", ""),
                "cidade": doc.get("cidade", ""),
                "endereco": doc.get("endereco", ""),
                "numero": doc.get("numero", ""),
                "data_criacao": doc.get("data_criacao", datetime.now())
            })
        return clientes
    except Exception as e:
        st.error(f"Erro ao buscar clientes: {e}")
        return []

def criar_cliente_mongo(username: str, nome: str, cnpj: str, uf: str = "", cidade: str = "", endereco: str = "", numero: str = "") -> Optional[str]:
    """Cria um novo cliente no MongoDB. Retorna o ID, 'CNPJ_DUPLICADO' se já existir, ou None em caso de erro."""
    try:
        client = get_mongo_client()
        db = client["cardapio_auth"]
        colecao = db["clientes"]

        # Limpar CNPJ (manter apenas dígitos)
        cnpj_limpo = ''.join(filter(str.isdigit, cnpj))

        # Verificar duplicidade de CNPJ (global, independente do usuário)
        if colecao.find_one({"cnpj": cnpj_limpo}):
            return "CNPJ_DUPLICADO"

        res = colecao.insert_one({
            "username": username,
            "nome": nome.strip(),
            "cnpj": cnpj_limpo,
            "uf": uf,
            "cidade": cidade.strip(),
            "endereco": endereco.strip(),
            "numero": numero.strip(),
            "data_criacao": datetime.now()
        })
        return str(res.inserted_id)
    except Exception as e:
        st.error(f"Erro ao criar cliente: {e}")
        return None

def salvar_analise_mongo(username: str, cliente_id: str, rotulo: str, df: pd.DataFrame, kpis: dict) -> bool:
    """Salva uma análise/snapshot no MongoDB."""
    try:
        client = get_mongo_client()
        db = client["cardapio_auth"]
        colecao = db["analises"]
        
        dados_pratos = df.to_dict(orient="records")
        
        documento = {
            "username": username,
            "cliente_id": cliente_id,
            "rotulo": rotulo.strip(),
            "data_criacao": datetime.now(),
            "dados_pratos": dados_pratos,
            "kpis": kpis
        }
        colecao.insert_one(documento)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar análise: {e}")
        return False

def listar_analises_mongo(cliente_id: str) -> list[dict]:
    """Retorna todas as análises salvas de um determinado cliente."""
    try:
        client = get_mongo_client()
        db = client["cardapio_auth"]
        colecao = db["analises"]
        cursor = colecao.find({"cliente_id": cliente_id}).sort("data_criacao", -1)
        analises = []
        for doc in cursor:
            analises.append({
                "_id": str(doc["_id"]),
                "rotulo": doc.get("rotulo", "Análise sem nome"),
                "data_criacao": doc.get("data_criacao"),
                "dados_pratos": doc.get("dados_pratos", []),
                "kpis": doc.get("kpis", {})
            })
        return analises
    except Exception as e:
        st.error(f"Erro ao buscar análises: {e}")
        return []

def excluir_analise_mongo(analise_id: str) -> bool:
    """Exclui uma análise salva do MongoDB pelo ID."""
    try:
        client = get_mongo_client()
        db = client["cardapio_auth"]
        colecao = db["analises"]
        colecao.delete_one({"_id": ObjectId(analise_id)})
        return True
    except Exception as e:
        st.error(f"Erro ao excluir análise: {e}")
        return False


def excluir_cliente_mongo(cliente_id: str) -> bool:
    """Exclui um cliente e todas as suas análises vinculadas (cascade delete)."""
    try:
        client = get_mongo_client()
        db = client["cardapio_auth"]
        # Cascade: excluir todas as análises vinculadas ao cliente
        db["analises"].delete_many({"cliente_id": cliente_id})
        # Excluir o próprio cliente
        db["clientes"].delete_one({"_id": ObjectId(cliente_id)})
        return True
    except Exception as e:
        st.error(f"Erro ao excluir cliente: {e}")
        return False


def formatar_cnpj(cnpj: str) -> str:
    """Formata um CNPJ numérico para o padrão XX.XXX.XXX/XXXX-XX."""
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj_limpo) == 14:
        return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:14]}"
    return cnpj


def validar_cnpj(cnpj: str) -> bool:
    """Valida se o CNPJ possui exatamente 14 dígitos numéricos."""
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
    return len(cnpj_limpo) == 14



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
# Sidebar — Usuário logado + Cliente + Upload
# ──────────────────────────────────────────────
username_atual = st.session_state.get("username", "admin")

with st.sidebar:
    # Boas-vindas e logout
    st.markdown(f"### 👋 Olá, **{st.session_state.get('name', '')}**!")
    authenticator.logout("🚪 Sair", key="logout_btn")
    st.markdown("---")

    # 🏢 Seletor de Cliente
    st.header("🏢 Cliente / Restaurante")
    
    lista_clientes = listar_clientes_mongo(username_atual)
    opcoes_clientes = {"none": "Nenhum (Análise Avulsa)"}
    for c in lista_clientes:
        opcoes_clientes[c["_id"]] = f"🏢 {c['nome']}"
        
    escolha_cliente = st.selectbox(
        "Selecione o Cliente:",
        options=list(opcoes_clientes.keys()),
        format_func=lambda x: opcoes_clientes[x],
        key="select_cliente_active"
    )

    cliente_selecionado_obj = None

    if escolha_cliente != "none":
        cliente_selecionado_obj = next((c for c in lista_clientes if c["_id"] == escolha_cliente), None)
        if cliente_selecionado_obj:
            st.success(f"Ativo: **{cliente_selecionado_obj['nome']}**")

    st.caption("Para cadastrar ou gerenciar clientes, acesse a aba 🏢 Clientes.")
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
# Função de Correção Automática via IA (Gemini)
# ──────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def corrigir_csv_com_ia(texto_bruto_csv: str) -> Optional[pd.DataFrame]:
    """
    Envia o texto bruto do CSV para a API REST do Gemini.
    Usa chamada HTTP direta com gemini-flash-latest e cache do Streamlit
    para evitar re-chamadas desnecessárias e erros de cota (429).
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"

        prompt = f"""Você é um assistente especializado em limpeza de dados para restaurantes.

Recebemos o seguinte arquivo CSV bruto de um cliente. O arquivo pode ter:
- Nomes de colunas diferentes do padrão (ex: "Prato" em vez de "Nome do Prato")
- Valores com formatação errada (ex: "R$ 5,00" em vez de "5.00")
- Texto em campos numéricos (ex: "abc" em vez de um número)
- Colunas extras que não precisamos
- Separadores diferentes (ponto e vírgula, tabulação, etc.)

Seu trabalho é:
1. Identificar quais colunas correspondem a: Nome do Prato, Custo Unitário, Preço de Venda e Quantidade Vendida.
2. Limpar os valores numéricos (remover "R$", trocar vírgula por ponto, converter texto para número).
3. Se algum valor numérico for impossível de converter (como a palavra "abc"), coloque 0.
4. Retornar SOMENTE um JSON válido no seguinte formato (sem nenhum texto antes ou depois):

[{{
  "Nome do Prato": "nome aqui",
  "Custo Unitário": 0.00,
  "Preço de Venda": 0.00,
  "Quantidade Vendida": 0
}}]

IMPORTANTE:
- Retorne APENAS o JSON puro, sem explicações, sem markdown, sem ```json.
- Os valores numéricos devem ser números (não strings).
- Mantenha todos os pratos que conseguir identificar.

Arquivo CSV bruto:
---
{texto_bruto_csv}
---"""

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        # Tentativas com tratamento de cota / rate limit (429)
        max_tentativas = 3
        resp = None

        for tentativa in range(max_tentativas):
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                break
            elif resp.status_code == 429 and tentativa < max_tentativas - 1:
                time.sleep(4)  # Aguarda 4 segundos se estourar a cota momentânea
            else:
                break

        if resp is None or resp.status_code != 200:
            err_msg = resp.text[:300] if resp else "Sem resposta"
            st.error(f"⚠️ Erro na API do Gemini (HTTP {resp.status_code if resp else 'N/A'}): {err_msg}")
            return None

        resultado = resp.json()
        texto_resposta = resultado["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Limpar possíveis marcadores de código que a IA pode adicionar
        if texto_resposta.startswith("```"):
            linhas = texto_resposta.split("\n")
            texto_resposta = "\n".join(linhas[1:-1])

        dados = json.loads(texto_resposta)
        df_corrigido = pd.DataFrame(dados)

        # Verificar se as 4 colunas obrigatórias estão presentes
        colunas_necessarias = ["Nome do Prato", "Custo Unitário", "Preço de Venda", "Quantidade Vendida"]
        for col in colunas_necessarias:
            if col not in df_corrigido.columns:
                return None

        # Garantir tipos numéricos
        df_corrigido["Custo Unitário"] = pd.to_numeric(df_corrigido["Custo Unitário"], errors="coerce").fillna(0)
        df_corrigido["Preço de Venda"] = pd.to_numeric(df_corrigido["Preço de Venda"], errors="coerce").fillna(0)
        df_corrigido["Quantidade Vendida"] = pd.to_numeric(df_corrigido["Quantidade Vendida"], errors="coerce").fillna(0).astype(int)

        return df_corrigido

    except Exception as e:
        st.error(f"⚠️ Erro interno na correção por IA: {e}")
        return None


# ──────────────────────────────────────────────
# MOTOR DE CÁLCULOS & GRÁFICO (Reutilizável)
# ──────────────────────────────────────────────
def processar_kasavana_smith(df_input: pd.DataFrame):
    """Aplica o algoritmo de Kasavana & Smith no DataFrame."""
    df = df_input.copy()
    
    # Garantir tipos numéricos
    df["Custo Unitário"] = pd.to_numeric(df["Custo Unitário"], errors="coerce").fillna(0)
    df["Preço de Venda"] = pd.to_numeric(df["Preço de Venda"], errors="coerce").fillna(0)
    df["Quantidade Vendida"] = pd.to_numeric(df["Quantidade Vendida"], errors="coerce").fillna(0).astype(int)

    # 1. Margem de Contribuição
    df["Margem de Contribuição (R$)"] = df["Preço de Venda"] - df["Custo Unitário"]
    
    # 2. Mix de Vendas (%)
    total_vendido = df["Quantidade Vendida"].sum()
    df["Mix de Vendas (%)"] = (df["Quantidade Vendida"] / total_vendido * 100) if total_vendido > 0 else 0
    
    # 3. Linhas de corte
    media_margem = df["Margem de Contribuição (R$)"].mean()
    num_pratos = len(df)
    media_popularidade = (1 / num_pratos) * 0.70 * 100 if num_pratos > 0 else 0
    
    def classificar(row: pd.Series) -> str:
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
    
    ACOES = {
        "Estrela 🌟": "Manter padrão de qualidade e estimular vendas.",
        "Burro de Carga 🐴": "Reduzir custo dos ingredientes ou aumentar preço discretamente.",
        "Quebra-Cabeça 🧩": "Dar destaque no cardápio visual ou criar combos.",
        "Cão 🐶": "Retirar do cardápio ou reformular prato e nome.",
    }
    df["Ação Recomendada"] = df["Classificação"].map(ACOES)
    
    return df, media_margem, media_popularidade, num_pratos


def criar_grafico_matriz(df: pd.DataFrame, media_margem: float, media_popularidade: float, titulo: str = "Matriz de Kasavana & Smith"):
    CORES = {
        "Estrela 🌟": "#facc15",
        "Burro de Carga 🐴": "#3b82f6",
        "Quebra-Cabeça 🧩": "#a855f7",
        "Cão 🐶": "#ef4444",
    }
    fig = go.Figure()
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
    fig.add_vline(
        x=media_margem,
        line_dash="dash",
        line_color="#94a3b8",
        line_width=1.5,
        annotation_text=f"Média Margem: R${media_margem:,.2f}",
        annotation_position="top",
        annotation_font_color="#94a3b8",
    )
    fig.add_hline(
        y=media_popularidade,
        line_dash="dash",
        line_color="#94a3b8",
        line_width=1.5,
        annotation_text=f"Média Popularidade: {media_popularidade:,.2f}%",
        annotation_position="right",
        annotation_font_color="#94a3b8",
    )
    
    x_range = df["Margem de Contribuição (R$)"]
    y_range = df["Mix de Vendas (%)"]
    x_min, x_max = x_range.min(), x_range.max()
    y_min, y_max = y_range.min(), y_range.max()
    
    quadrante_labels = [
        dict(x=media_margem + (x_max - media_margem) / 2 if x_max > media_margem else media_margem + 1, y=media_popularidade + (y_max - media_popularidade) / 2 if y_max > media_popularidade else media_popularidade + 1, text="⭐ Estrela"),
        dict(x=media_margem - (media_margem - x_min) / 2 if media_margem > x_min else media_margem - 1, y=media_popularidade + (y_max - media_popularidade) / 2 if y_max > media_popularidade else media_popularidade + 1, text="🐴 Burro de Carga"),
        dict(x=media_margem + (x_max - media_margem) / 2 if x_max > media_margem else media_margem + 1, y=media_popularidade - (media_popularidade - y_min) / 2 if media_popularidade > y_min else media_popularidade - 1, text="🧩 Quebra-Cabeça"),
        dict(x=media_margem - (media_margem - x_min) / 2 if media_margem > x_min else media_margem - 1, y=media_popularidade - (media_popularidade - y_min) / 2 if media_popularidade > y_min else media_popularidade - 1, text="🐶 Cão"),
    ]
    for ql in quadrante_labels:
        fig.add_annotation(
            x=ql["x"], y=ql["y"], text=ql["text"],
            showarrow=False,
            font=dict(size=13, color="rgba(148,163,184,0.45)"),
        )

    fig.update_layout(
        title=dict(text=titulo, font=dict(size=15, color="#e0e7ff")),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,15,30,0.6)",
        xaxis_title="Margem de Contribuição (R$)",
        yaxis_title="Mix de Vendas (%)",
        height=520,
        margin=dict(t=50, b=50, l=50, r=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
    )
    return fig


# ──────────────────────────────────────────────
# ESTRUTURA DE ABAS PRINCIPAIS
# ──────────────────────────────────────────────
tab_analise, tab_historico, tab_comparador, tab_clientes = st.tabs([
    "📊 Análise Atual",
    "📁 Histórico do Cliente",
    "⚔️ Comparador (Antes vs. Depois)",
    "🏢 Clientes / Restaurantes"
])

# ==============================================================================
# ABA 1: ANÁLISE ATUAL
# ==============================================================================
with tab_analise:
    if arquivo is None:
        st.info("👈 Envie um arquivo CSV pela barra lateral para começar a análise.")
    else:
        arquivo.seek(0)
        texto_bruto = arquivo.read().decode("utf-8", errors="replace")
        arquivo.seek(0)

        csv_precisa_correcao = False

        try:
            df_bruto = pd.read_csv(io.StringIO(texto_bruto))
        except Exception:
            csv_precisa_correcao = True
            df_bruto = None

        if df_bruto is not None:
            colunas_faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in df_bruto.columns]
            if colunas_faltantes:
                csv_precisa_correcao = True

        if df_bruto is not None and not csv_precisa_correcao:
            try:
                df_bruto["Custo Unitário"] = pd.to_numeric(df_bruto["Custo Unitário"], errors="raise")
                df_bruto["Preço de Venda"] = pd.to_numeric(df_bruto["Preço de Venda"], errors="raise")
                df_bruto["Quantidade Vendida"] = pd.to_numeric(df_bruto["Quantidade Vendida"], errors="raise")
            except (ValueError, TypeError):
                csv_precisa_correcao = True

        if csv_precisa_correcao:
            st.warning(
                "⚠️ O arquivo CSV está fora do padrão esperado. "
                "A Inteligência Artificial está analisando e corrigindo os dados automaticamente..."
            )
            with st.spinner("🤖 Gemini AI está padronizando seu arquivo..."):
                df_bruto = corrigir_csv_com_ia(texto_bruto)

            if df_bruto is None or df_bruto.empty:
                st.error(
                    "❌ Não foi possível corrigir o arquivo automaticamente.\n\n"
                    "Por favor, verifique se o seu CSV contém pelo menos as seguintes informações:\n\n"
                    "- Nome dos pratos\n- Custo de cada prato\n- Preço de venda\n- Quantidade vendida"
                )
                st.stop()
            else:
                st.success(
                    f"✅ A IA corrigiu o arquivo com sucesso! "
                    f"**{len(df_bruto)} pratos** foram identificados e padronizados."
                )

        if df_bruto is not None and not df_bruto.empty:
            df_processado, media_margem, media_popularidade, num_pratos = processar_kasavana_smith(df_bruto)

            # Métricas principais
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                st.metric("📊 Média da Margem (Linha X)", f"R$ {media_margem:,.2f}")
            with col2:
                st.metric("📈 Popularidade de Corte (Linha Y)", f"{media_popularidade:,.2f}%")
            with col3:
                st.metric("🍽️ Pratos Analisados", num_pratos)

            st.markdown("---")

            # Resumo por classificação
            st.subheader("Resumo por Classificação")
            contagem = df_processado["Classificação"].value_counts()
            cols_resumo = st.columns(4)
            labels_ordem = ["Estrela 🌟", "Burro de Carga 🐴", "Quebra-Cabeça 🧩", "Cão 🐶"]
            for i, label in enumerate(labels_ordem):
                with cols_resumo[i]:
                    st.metric(label, int(contagem.get(label, 0)))

            st.markdown("---")

            # Gráfico de Dispersão
            st.subheader("Matriz de Kasavana & Smith")
            fig = criar_grafico_matriz(df_processado, media_margem, media_popularidade)
            st.plotly_chart(fig, width="stretch")

            # Tabela Detalhada
            st.markdown("---")
            st.subheader("📋 Tabela Detalhada")

            df_display = df_processado.copy()
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

            # 💾 SEÇÃO DE SALVAMENTO NO HISTÓRICO
            st.markdown("---")
            st.subheader("💾 Salvar Análise no Histórico")

            if cliente_selecionado_obj is None:
                st.info("💡 **Dica:** Selecione ou cadastre um **Cliente/Restaurante** no menu lateral para salvar esta análise no histórico dele e fazer comparações futuras!")
            else:
                with st.expander(f"📌 Salvar Snapshot para: {cliente_selecionado_obj['nome']}", expanded=True):
                    rotulo_input = st.text_input(
                        "Rótulo / Nome da Análise:",
                        value=f"Análise de {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                        placeholder="Ex: Julho/2026 - Pré Reajuste"
                    )
                    if st.button("💾 Confirmar e Salvar no Histórico", type="primary"):
                        lucro_total = float((df_processado["Margem de Contribuição (R$)"] * df_processado["Quantidade Vendida"]).sum())
                        receita_total = float((df_processado["Preço de Venda"] * df_processado["Quantidade Vendida"]).sum())
                        
                        kpis_save = {
                            "lucro_total": lucro_total,
                            "receita_total": receita_total,
                            "margem_media": float(media_margem),
                            "popularidade_corte": float(media_popularidade),
                            "num_pratos": int(num_pratos),
                            "contagem": {k: int(v) for k, v in contagem.to_dict().items()}
                        }

                        sucesso = salvar_analise_mongo(
                            username=username_atual,
                            cliente_id=cliente_selecionado_obj["_id"],
                            rotulo=rotulo_input,
                            df=df_processado,
                            kpis=kpis_save
                        )
                        if sucesso:
                            st.success(f"✅ Análise **'{rotulo_input}'** salva no histórico de **{cliente_selecionado_obj['nome']}**!")


# ==============================================================================
# ABA 2: HISTÓRICO DO CLIENTE
# ==============================================================================
with tab_historico:
    if cliente_selecionado_obj is None:
        st.info("👈 Selecione um **Cliente / Restaurante** na barra lateral para visualizar seu histórico de análises.")
    else:
        st.subheader(f"📁 Histórico de Análises — {cliente_selecionado_obj['nome']}")
        
        analises_salvas = listar_analises_mongo(cliente_selecionado_obj["_id"])
        
        if not analises_salvas:
            st.warning(f"Nenhuma análise salva para **{cliente_selecionado_obj['nome']}** ainda.")
            st.caption("Faça upload de um arquivo na aba 'Análise Atual' e salve-o para guardar no histórico.")
        else:
            st.write(f"Total de análises registradas: **{len(analises_salvas)}**")
            
            for idx, a in enumerate(analises_salvas):
                data_str = a["data_criacao"].strftime("%d/%m/%Y às %H:%M") if isinstance(a["data_criacao"], datetime) else "Data desconhecida"
                k = a.get("kpis", {})
                
                with st.expander(f"🗓️ **{a['rotulo']}** — ({data_str})", expanded=(idx == 0)):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Lucro Total", f"R$ {k.get('lucro_total', 0):,.2f}")
                    c2.metric("Receita Total", f"R$ {k.get('receita_total', 0):,.2f}")
                    c3.metric("Margem Média", f"R$ {k.get('margem_media', 0):,.2f}")
                    c4.metric("Pratos Analisados", k.get('num_pratos', 0))

                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        if st.button(f"👁️ Visualizar Matriz", key=f"view_btn_{a['_id']}"):
                            st.session_state[f"show_details_{a['_id']}"] = not st.session_state.get(f"show_details_{a['_id']}", False)
                            
                    with col_btn2:
                        if st.button(f"🗑️ Excluir Análise", key=f"del_btn_{a['_id']}"):
                            if excluir_analise_mongo(a["_id"]):
                                st.success("Análise excluída!")
                                st.rerun()

                    if st.session_state.get(f"show_details_{a['_id']}", False):
                        df_saved = pd.DataFrame(a["dados_pratos"])
                        st.markdown("---")
                        fig_hist = criar_grafico_matriz(
                            df_saved,
                            k.get("margem_media", 0),
                            k.get("popularidade_corte", 0),
                            titulo=f"Matriz — {a['rotulo']}"
                        )
                        st.plotly_chart(fig_hist, width="stretch")
                        
                        st.dataframe(df_saved, hide_index=True, width="stretch")


# ==============================================================================
# ABA 3: COMPARADOR (ANTES vs. DEPOIS)
# ==============================================================================
with tab_comparador:
    if cliente_selecionado_obj is None:
        st.info("👈 Selecione um **Cliente / Restaurante** na barra lateral para acessar o comparador.")
    else:
        analises_salvas = listar_analises_mongo(cliente_selecionado_obj["_id"])
        
        if len(analises_salvas) < 2:
            st.warning(f"⚠️ É necessário ter **pelo menos 2 análises salvas** no histórico de **{cliente_selecionado_obj['nome']}** para realizar uma comparação.")
            st.caption("💡 Salve uma análise inicial (ex: 'Antes das Alterações') e depois envie e salve uma nova análise (ex: 'Pós Alterações').")
        else:
            st.subheader(f"⚔️ Comparador de Desempenho (Antes vs. Depois) — {cliente_selecionado_obj['nome']}")
            
            mapa_analises = {a["_id"]: a for a in analises_salvas}
            opcoes_comp = {a["_id"]: f"{a['rotulo']} ({a['data_criacao'].strftime('%d/%m/%Y') if isinstance(a['data_criacao'], datetime) else ''})" for a in analises_salvas}
            
            c_sel1, c_sel2 = st.columns(2)
            with c_sel1:
                id_a = st.selectbox(
                    "Análise A (Base / ANTES):",
                    options=list(opcoes_comp.keys()),
                    index=len(analises_salvas) - 1,
                    format_func=lambda x: opcoes_comp[x],
                    key="sel_comp_a"
                )
            with c_sel2:
                id_b = st.selectbox(
                    "Análise B (Comparativa / DEPOIS):",
                    options=list(opcoes_comp.keys()),
                    index=0,
                    format_func=lambda x: opcoes_comp[x],
                    key="sel_comp_b"
                )
                
            if id_a == id_b:
                st.info("💡 Por favor, selecione duas análises diferentes para comparar o desempenho.")
            else:
                ana_a = mapa_analises[id_a]
                ana_b = mapa_analises[id_b]
                
                k_a = ana_a.get("kpis", {})
                k_b = ana_b.get("kpis", {})
                
                lucro_a = k_a.get("lucro_total", 0)
                lucro_b = k_b.get("lucro_total", 0)
                diff_lucro = lucro_b - lucro_a
                pct_lucro = ((diff_lucro / lucro_a) * 100) if lucro_a > 0 else 0
                
                rec_a = k_a.get("receita_total", 0)
                rec_b = k_b.get("receita_total", 0)
                diff_rec = rec_b - rec_a
                pct_rec = ((diff_rec / rec_a) * 100) if rec_a > 0 else 0
                
                marg_a = k_a.get("margem_media", 0)
                marg_b = k_b.get("margem_media", 0)
                diff_marg = marg_b - marg_a

                st.markdown("---")
                st.markdown("### 📈 Principais Indicadores de Impacto")
                
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric(
                    "Lucro Total (Margem Bruta)",
                    f"R$ {lucro_b:,.2f}",
                    delta=f"R$ {diff_lucro:+,.2f} ({pct_lucro:+.1f}%)"
                )
                mc2.metric(
                    "Faturamento / Receita",
                    f"R$ {rec_b:,.2f}",
                    delta=f"R$ {diff_rec:+,.2f} ({pct_rec:+.1f}%)"
                )
                mc3.metric(
                    "Margem Média por Prato",
                    f"R$ {marg_b:,.2f}",
                    delta=f"R$ {diff_marg:+,.2f}"
                )

                st.markdown("---")
                st.markdown("### 🔄 Migração de Quadrantes por Prato")
                
                df_a = pd.DataFrame(ana_a["dados_pratos"])
                df_b = pd.DataFrame(ana_b["dados_pratos"])
                
                if "Nome do Prato" in df_a.columns and "Nome do Prato" in df_b.columns:
                    df_comp = pd.merge(
                        df_a[["Nome do Prato", "Classificação", "Preço de Venda", "Margem de Contribuição (R$)"]],
                        df_b[["Nome do Prato", "Classificação", "Preço de Venda", "Margem de Contribuição (R$)"]],
                        on="Nome do Prato",
                        suffixes=(" (Antes)", " (Depois)")
                    )

                    def avaliar_evolucao(row):
                        c_antes = row["Classificação (Antes)"]
                        c_depois = row["Classificação (Depois)"]
                        margem_antes = row["Margem de Contribuição (R$) (Antes)"]
                        margem_depois = row["Margem de Contribuição (R$) (Depois)"]
                        
                        if c_antes == c_depois:
                            if margem_depois < margem_antes:
                                return "Atenção ⚠️ (Margem caiu)"
                            elif margem_depois > margem_antes:
                                return "Melhorou 🟢 (Margem subiu)"
                            else:
                                return "Mantido ➡️"
                        elif c_depois == "Estrela 🌟":
                            return "Excelente Ev. 🎯 (Virou Estrela)"
                        elif c_antes == "Cão 🐶" and c_depois != "Cão 🐶":
                            return "Melhorou 🟢 (Saiu de Cão)"
                        elif c_depois == "Cão 🐶":
                            return "Atenção 🔴 (Caiu para Cão)"
                        else:
                            return "Mudança 🔄"

                    df_comp["Evolução"] = df_comp.apply(avaliar_evolucao, axis=1)

                    st.dataframe(
                        df_comp,
                        hide_index=True,
                        width="stretch",
                        column_order=[
                            "Nome do Prato",
                            "Classificação (Antes)",
                            "Classificação (Depois)",
                            "Evolução",
                            "Preço de Venda (Antes)",
                            "Preço de Venda (Depois)",
                            "Margem de Contribuição (R$) (Antes)",
                            "Margem de Contribuição (R$) (Depois)",
                        ]
                    )

                # Gráficos de Matriz Lado a Lado
                st.markdown("---")
                st.markdown("### 📊 Matrizes Lado a Lado")
                c_fig1, c_fig2 = st.columns(2)
                with c_fig1:
                    fig_a = criar_grafico_matriz(
                        df_a, k_a.get("margem_media", 0), k_a.get("popularidade_corte", 0),
                        titulo=f"ANTES: {ana_a['rotulo']}"
                    )
                    st.plotly_chart(fig_a, width="stretch")
                with c_fig2:
                    fig_b = criar_grafico_matriz(
                        df_b, k_b.get("margem_media", 0), k_b.get("popularidade_corte", 0),
                        titulo=f"DEPOIS: {ana_b['rotulo']}"
                    )
                    st.plotly_chart(fig_b, width="stretch")


# ==============================================================================
# ABA 4: CLIENTES / RESTAURANTES
# ==============================================================================
with tab_clientes:
    st.subheader("🏢 Cadastro de Clientes / Restaurantes")
    st.caption("Gerencie seus clientes cadastrados e adicione novos restaurantes para acompanhar o desempenho do cardápio.")

    # ── Formulário de Cadastro ──
    with st.expander("➕ Cadastrar Novo Cliente", expanded=not bool(lista_clientes)):
        with st.form("form_cadastro_cliente", clear_on_submit=True):
            st.markdown("##### 📝 Dados do Estabelecimento")

            col_nome, col_cnpj = st.columns([1, 1])
            with col_nome:
                nome_cli = st.text_input("Nome do Restaurante/Cliente *", placeholder="Ex: Restaurante Paris")
            with col_cnpj:
                cnpj_cli = st.text_input("CNPJ *", placeholder="XX.XXX.XXX/XXXX-XX", help="Informe os 14 dígitos do CNPJ (com ou sem pontuação).")

            col_uf, col_cidade = st.columns([1, 2])
            with col_uf:
                UF_BRASIL = [
                    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
                    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
                    "RO", "RR", "RS", "SC", "SE", "SP", "TO"
                ]
                uf_cli = st.selectbox("UF", options=[""] + UF_BRASIL, index=0)
            with col_cidade:
                cidade_cli = st.text_input("Cidade", placeholder="Ex: São Paulo")

            col_end, col_num = st.columns([3, 1])
            with col_end:
                endereco_cli = st.text_input("Endereço", placeholder="Ex: Rua Augusta")
            with col_num:
                numero_cli = st.text_input("Número", placeholder="Ex: 1234")

            btn_cadastrar = st.form_submit_button("✅ Cadastrar Cliente", type="primary")

            if btn_cadastrar:
                if not nome_cli.strip():
                    st.error("❌ O **nome** do cliente é obrigatório.")
                elif not cnpj_cli.strip():
                    st.error("❌ O **CNPJ** é obrigatório.")
                elif not validar_cnpj(cnpj_cli):
                    st.error("❌ CNPJ inválido. Informe exatamente 14 dígitos numéricos (com ou sem formatação).")
                else:
                    resultado = criar_cliente_mongo(
                        username=username_atual,
                        nome=nome_cli,
                        cnpj=cnpj_cli,
                        uf=uf_cli,
                        cidade=cidade_cli,
                        endereco=endereco_cli,
                        numero=numero_cli
                    )
                    if resultado == "CNPJ_DUPLICADO":
                        st.error(f"❌ Já existe um cliente cadastrado com o CNPJ **{formatar_cnpj(cnpj_cli)}**. Cada CNPJ pode ser cadastrado apenas uma vez.")
                    elif resultado:
                        st.success(f"✅ Cliente **{nome_cli}** cadastrado com sucesso!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Erro inesperado ao cadastrar o cliente. Tente novamente.")

    # ── Lista de Clientes Cadastrados ──
    st.markdown("---")
    st.subheader("📋 Meus Clientes Cadastrados")

    lista_clientes_tab = listar_clientes_mongo(username_atual)

    if not lista_clientes_tab:
        st.info("Nenhum cliente cadastrado ainda. Use o formulário acima para adicionar seu primeiro restaurante! 🍽️")
    else:
        st.write(f"Total de clientes: **{len(lista_clientes_tab)}**")

        for cli in lista_clientes_tab:
            data_str = cli["data_criacao"].strftime("%d/%m/%Y") if isinstance(cli["data_criacao"], datetime) else "—"
            cnpj_display = formatar_cnpj(cli.get("cnpj", "")) if cli.get("cnpj") else "Não informado"

            with st.expander(f"🏢 **{cli['nome']}** — CNPJ: {cnpj_display}", expanded=False):
                info_c1, info_c2, info_c3 = st.columns(3)
                info_c1.markdown(f"**UF:** {cli.get('uf') or '—'}")
                info_c2.markdown(f"**Cidade:** {cli.get('cidade') or '—'}")
                info_c3.markdown(f"**Cadastrado em:** {data_str}")

                endereco_completo = cli.get('endereco', '')
                if cli.get('numero'):
                    endereco_completo += f", nº {cli['numero']}"
                if endereco_completo:
                    st.markdown(f"**Endereço:** {endereco_completo}")

                st.markdown("---")

                # ── Controle de confirmação de exclusão ──
                confirm_key = f"confirm_del_cli_{cli['_id']}"

                if st.session_state.get(confirm_key, False):
                    st.warning(f"⚠️ **Tem certeza que deseja excluir '{cli['nome']}'?** Todas as análises vinculadas a este cliente também serão excluídas permanentemente.")
                    col_sim, col_nao = st.columns(2)
                    with col_sim:
                        if st.button("⚠️ Sim, excluir permanentemente", key=f"yes_del_{cli['_id']}", type="primary"):
                            if excluir_cliente_mongo(cli["_id"]):
                                st.success(f"Cliente '{cli['nome']}' e todas as suas análises foram excluídos.")
                                st.session_state[confirm_key] = False
                                time.sleep(1)
                                st.rerun()
                    with col_nao:
                        if st.button("❌ Cancelar", key=f"no_del_{cli['_id']}"):
                            st.session_state[confirm_key] = False
                            st.rerun()
                else:
                    if st.button(f"🗑️ Excluir Cliente", key=f"del_cli_{cli['_id']}"):
                        st.session_state[confirm_key] = True
                        st.rerun()


# ──────────────────────────────────────────────
# Rodapé
# ──────────────────────────────────────────────
st.markdown("---")
st.caption("Desenvolvido com ❤️ usando Streamlit · Método de Kasavana & Smith")

