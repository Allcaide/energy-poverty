import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st

# Carregar GeoJSON
gdf = gpd.read_file("geojsons/ContinenteDistritos.geojson").to_crs("EPSG:4326")
geojson = gdf.__geo_interface__

# Dados fictícios para múltiplos anos
dados_anos = {
    2020: {
        "distrito": ["LISBOA", "PORTO", "SETÚBAL", "BRAGA", "COIMBRA", "FARO", "AVEIRO"],
        "valor":    [0.8,      0.5,    0.6,       0.7,    0.4,       0.65,  0.55]
    },
    2021: {
        "distrito": ["LISBOA", "PORTO", "SETÚBAL", "BRAGA", "COIMBRA", "FARO", "AVEIRO"],
        "valor":    [0.75,     0.48,   0.62,      0.68,   0.42,      0.63,  0.54]
    },
    2022: {
        "distrito": ["LISBOA", "PORTO", "SETÚBAL", "BRAGA", "COIMBRA", "FARO", "AVEIRO"],
        "valor":    [0.7,      0.45,   0.64,      0.65,   0.44,      0.61,  0.53]
    },
    2023: {
        "distrito": ["LISBOA", "PORTO", "SETÚBAL", "BRAGA", "COIMBRA", "FARO", "AVEIRO"],
        "valor":    [0.65,     0.42,   0.66,      0.62,   0.46,      0.59,  0.52]
    },
    2024: {
        "distrito": ["LISBOA", "PORTO", "SETÚBAL", "BRAGA", "COIMBRA", "FARO", "AVEIRO"],
        "valor":    [0.6,      0.4,    0.68,      0.59,   0.48,      0.57,  0.51]
    },
    2025: {
        "distrito": ["LISBOA", "PORTO", "SETÚBAL", "BRAGA", "COIMBRA", "FARO", "AVEIRO"],
        "valor":    [0.55,     0.38,   0.7,       0.56,   0.5,       0.55,  0.5]
    },
    2026: {
        "distrito": ["LISBOA", "PORTO", "SETÚBAL", "BRAGA", "COIMBRA", "FARO", "AVEIRO"],
        "valor":    [0.5,      0.35,   0.72,      0.53,   0.52,      0.53,  0.49]
    }
}

st.title("Análise de Dados de Energia - Portugal")
st.subheader("Pobreza Energética por Distrito (2020-2026)")

# Botões para selecionar indicador
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Pobreza Energética"):
        st.session_state.indicador = "Pobreza Energética"
with col2:
    if st.button("Consumo de Energia"):
        st.session_state.indicador = "Consumo de Energia"
with col3:
    if st.button("Eficiência Energética"):
        st.session_state.indicador = "Eficiência Energética"

# Inicializar
if "indicador" not in st.session_state:
    st.session_state.indicador = "Pobreza Energética"

# Barra deslizável para selecionar ano
ano_selecionado = st.slider("Selecione o ano:", 2020, 2026, 2020)

# Obter dados do ano selecionado
df = pd.DataFrame(dados_anos[ano_selecionado])

# Layout com mapa e gráfico de diferenças
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"{st.session_state.indicador} - {ano_selecionado}")
    
    # Criar mapa
    fig_mapa = px.choropleth_map(
        df,
        geojson=geojson,
        locations="distrito",
        featureidkey="properties.Distrito",
        color="valor",
        color_continuous_scale="RdYlGn_r",
        map_style="open-street-map",
        center={"lat": 39.5, "lon": -8.0},
        zoom=5,
        opacity=0.8,
        title=f"Mapa Coroplético - {ano_selecionado}"
    )
    
    fig_mapa.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0}, height=500)
    st.plotly_chart(fig_mapa, use_container_width=True)

with col2:
    st.subheader("Maior Diferença (2020-2026)")
    
    # Calcular diferença entre 2020 e ano selecionado
    df_2020 = pd.DataFrame(dados_anos[2020])
    df_diferenca = df.copy()
    df_diferenca["diferenca"] = df_diferenca["valor"] - df_2020["valor"].values
    df_diferenca = df_diferenca.sort_values("diferenca", ascending=False)
    
    # Gráfico de barras com cores
    fig_barras = px.bar(
        df_diferenca,
        x="valor",
        y="distrito",
        color="diferenca",
        color_continuous_scale="RdYlGn",
        orientation="h",
        title=f"Diferença vs 2020",
        labels={"valor": "Valor", "distrito": "Distrito", "diferenca": "Diferença"},
        height=500
    )
    
    fig_barras.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
    st.plotly_chart(fig_barras, use_container_width=True)

# Tabela de dados
st.subheader("Dados Detalhados")
st.dataframe(df_diferenca[["distrito", "valor", "diferenca"]], use_container_width=True)