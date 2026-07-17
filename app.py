import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

# ---------------------------------------------------------------------------
# Configuração da página (precisa ser o primeiro comando Streamlit do script)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Vagas de Ciência de Dados",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Carrega variáveis de ambiente e monta a conexão com o banco
# ---------------------------------------------------------------------------
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
    st.error(
        "Variáveis de ambiente do banco não encontradas. Confira se o arquivo "
        ".env existe e contém DB_USER, DB_PASSWORD, DB_HOST, DB_PORT e DB_NAME."
    )
    st.stop()

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


@st.cache_resource
def get_engine():
    """Cria (uma única vez, graças ao cache) a engine de conexão com o Postgres."""
    return create_engine(DATABASE_URL)


@st.cache_data(ttl=600)
def load_data() -> pd.DataFrame:
    """Busca todas as vagas da tabela 'vagas'. Cache de 10 min para não bater
    no banco a cada interação do usuário (ex: trocar o filtro da sidebar)."""
    engine = get_engine()
    query = "SELECT titulo, empresa, localizacao, salario_min, salario_max, link, data_extracao FROM vagas"
    df = pd.read_sql(query, engine)
    df["data_extracao"] = pd.to_datetime(df["data_extracao"])
    return df


try:
    df = load_data()
except Exception as e:
    st.error(f"Erro ao conectar no banco de dados: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Título
# ---------------------------------------------------------------------------
st.title("📊 Pipeline de Dados - Vagas de Ciência de Dados (InfoJobs)")

if df.empty:
    st.warning("Nenhuma vaga encontrada na tabela 'vagas' ainda.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI - total de vagas
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
col1.metric("Total de vagas coletadas", len(df))
col2.metric("Empresas distintas", df["empresa"].nunique())
col3.metric("Última coleta", df["data_extracao"].max().strftime("%d/%m/%Y %H:%M"))

st.divider()

# ---------------------------------------------------------------------------
# Gráfico - Top 10 empresas com mais vagas
# ---------------------------------------------------------------------------
st.subheader("Top 10 empresas com mais vagas")

top_empresas = (
    df["empresa"]
    .value_counts()
    .head(10)
    .rename_axis("empresa")
    .reset_index(name="vagas")
    .set_index("empresa")
)

st.bar_chart(top_empresas)

st.divider()

# ---------------------------------------------------------------------------
# Sidebar - filtro por empresa
# ---------------------------------------------------------------------------
st.sidebar.header("Filtros")

empresas_disponiveis = ["Todas"] + sorted(df["empresa"].dropna().unique().tolist())
empresa_selecionada = st.sidebar.selectbox("Empresa", empresas_disponiveis)

if empresa_selecionada != "Todas":
    df_filtrado = df[df["empresa"] == empresa_selecionada].copy()
else:
    df_filtrado = df.copy()

st.sidebar.markdown(f"**{len(df_filtrado)}** vagas encontradas com esse filtro.")

# ---------------------------------------------------------------------------
# Tabela final com link clicável
# ---------------------------------------------------------------------------
st.subheader("Vagas filtradas")

df_exibicao = df_filtrado.copy()

# Formata o link como HTML clicável (abre em nova aba)
df_exibicao["link"] = df_exibicao["link"].apply(
    lambda url: f'<a href="{url}" target="_blank">Abrir vaga</a>' if pd.notna(url) else ""
)

# Formata datas e salários para exibição amigável
df_exibicao["data_extracao"] = df_exibicao["data_extracao"].dt.strftime("%d/%m/%Y %H:%M")
df_exibicao["salario_min"] = df_exibicao["salario_min"].apply(
    lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(v) else "—"
)
df_exibicao["salario_max"] = df_exibicao["salario_max"].apply(
    lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(v) else "—"
)

# Renomeia colunas para exibição e seleciona a ordem final pedida
df_exibicao = df_exibicao.rename(
    columns={
        "titulo": "Título",
        "empresa": "Empresa",
        "salario_min": "Salário Mínimo",
        "salario_max": "Salário Máximo",
        "data_extracao": "Data",
        "link": "Link",
    }
)[["Título", "Empresa", "Salário Mínimo", "Salário Máximo", "Data", "Link"]]

# st.dataframe não renderiza HTML (por segurança), então para o link ficar
# clicável usamos st.markdown com a tabela convertida para HTML.
st.markdown(
    df_exibicao.to_html(escape=False, index=False),
    unsafe_allow_html=True,
)
