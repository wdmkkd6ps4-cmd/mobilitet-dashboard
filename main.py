import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import geopandas as gpd
import random
import json

# ============================================================================
# KONFIGURASJON - ENDRE DENNE STIEN TIL DIN SHAPEFIL
# ============================================================================
SHAPEFIL_PATH = "Shape/Delområder.shp"
NAVN_FELT = "delomraden"  # Feltet som inneholder områdenavn
# ============================================================================

# Konfigurasjon
st.set_page_config(
    page_title="Mobilitetsdashboard",
    page_icon="🚗",
    layout="wide"
)


@st.cache_data
def les_shapefil(filepath):
    """Leser shapefil og returnerer GeoDataFrame"""
    try:
        gdf = gpd.read_file(filepath)

        # Prosjiser til WGS84 for webkart
        if gdf.crs and gdf.crs != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')

        return gdf
    except Exception as e:
        st.error(f"Kunne ikke lese shapefil: {e}")
        return None


@st.cache_data
def generer_tilfeldig_od_data(områder_liste):
    """Genererer tilfeldig OD-data basert på områdeliste"""
    od_data = {}

    for fra in områder_liste:
        for til in områder_liste:
            if fra != til:
                # Tilfeldig antall reiser mellom 300 og 3000
                antall = random.randint(300, 3000)
                od_data[(fra, til)] = antall

    return od_data


# Last shapefil
gdf = les_shapefil(SHAPEFIL_PATH)

if gdf is None:
    st.error(f"⚠️ Kunne ikke laste shapefil fra: {SHAPEFIL_PATH}")
    st.info("Sjekk at stien er riktig og at filen eksisterer.")
    st.stop()

# Sjekk at navn-feltet eksisterer
if NAVN_FELT not in gdf.columns:
    st.error(f"⚠️ Finner ikke feltet '{NAVN_FELT}' i shapefilen.")
    st.info(f"Tilgjengelige felt: {', '.join(gdf.columns)}")
    st.stop()

# Hent områder fra shapefil
områder_liste = sorted(gdf[NAVN_FELT].unique().tolist())
st.success(f"✅ Lastet {len(områder_liste)} områder fra shapefil")

# Generer tilfeldig OD-data
od_data = generer_tilfeldig_od_data(områder_liste)

# === SESSION STATE ===
if 'valgt_område' not in st.session_state:
    st.session_state.valgt_område = områder_liste[0]

# === TITTEL ===
st.title("🚗 Mobilitetsdashboard")
st.markdown(f"Visualisering av reisestrømmer mellom {len(områder_liste)} delområder")

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Innstillinger")

    st.subheader("📊 Data")
    st.metric("Antall områder", len(områder_liste))
    st.metric("Antall forbindelser", len(od_data))

    st.markdown("---")

    # Dropdown med områder fra shapefil
    valgt = st.selectbox(
        "Velg område",
        områder_liste,
        index=områder_liste.index(st.session_state.valgt_område)
    )
    st.session_state.valgt_område = valgt

    st.markdown("---")
    st.markdown("### 📁 Shapefil")
    st.caption(f"**Fil:** {SHAPEFIL_PATH.split('/')[-1]}")
    st.caption(f"**Navn-felt:** {NAVN_FELT}")
    st.caption(f"**CRS:** {gdf.crs}")

    st.markdown("---")
    st.markdown("### ℹ️ Om")
    st.info("Dette dashbordet viser reisestrømmer mellom delområder. "
            "Data er tilfeldig generert for demonstrasjon.")

# === HOVEDINNHOLD ===
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📍 Områdekart")
    st.caption(f"Klikk på et område for å se reisestrømmer")

    # Lag kart med polygoner fra shapefil
    fig_map = go.Figure()

    # Legg til hver polygon
    for idx, row in gdf.iterrows():
        område_navn = row[NAVN_FELT]
        er_valgt = (område_navn == st.session_state.valgt_område)

        # Konverter geometri til koordinater
        geom = row.geometry

        if geom.geom_type == 'Polygon':
            coords = [list(geom.exterior.coords)]
        elif geom.geom_type == 'MultiPolygon':
            coords = [list(poly.exterior.coords) for poly in geom.geoms]
        else:
            continue

        # Tegn polygon(er)
        for coord_ring in coords:
            lons = [c[0] for c in coord_ring]
            lats = [c[1] for c in coord_ring]

            fig_map.add_trace(go.Scattermapbox(
                lon=lons,
                lat=lats,
                mode='lines',
                fill='toself',
                fillcolor='rgba(255, 0, 0, 0.4)' if er_valgt else 'rgba(100, 149, 237, 0.2)',
                line=dict(
                    color='red' if er_valgt else 'blue',
                    width=3 if er_valgt else 1
                ),
                name=område_navn,
                text=område_navn,
                hovertemplate=f"<b>{område_navn}</b><br>Klikk for å velge<extra></extra>",
                customdata=[[område_navn]] * len(lons)
            ))

    # Sentrer kart på shapefil
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    # Beregn zoom basert på utstrekning
    lat_range = bounds[3] - bounds[1]
    lon_range = bounds[2] - bounds[0]
    max_range = max(lat_range, lon_range)

    if max_range < 0.1:
        zoom = 12
    elif max_range < 0.5:
        zoom = 10
    elif max_range < 1.0:
        zoom = 9
    else:
        zoom = 8

    fig_map.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom
        ),
        height=500,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        hovermode='closest'
    )

    # Vis kart med klikk-funksjonalitet
    selected = st.plotly_chart(
        fig_map,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="map"
    )

    # Håndter klikk på polygon
    if selected and selected.get('selection') and selected['selection'].get('points'):
        if len(selected['selection']['points']) > 0:
            clicked = selected['selection']['points'][0]
            if 'customdata' in clicked and clicked['customdata']:
                nytt_område = clicked['customdata'][0]
                if nytt_område != st.session_state.valgt_område:
                    st.session_state.valgt_område = nytt_område
                    st.rerun()

with col2:
    st.subheader(f"🔄 Reisestrømmer: {st.session_state.valgt_område}")

    # Hent data for valgt område
    reiser_ut = []
    reiser_inn = []

    for (fra, til), antall in od_data.items():
        if fra == st.session_state.valgt_område:
            reiser_ut.append({'til': til, 'antall': antall})
        if til == st.session_state.valgt_område:
            reiser_inn.append({'fra': fra, 'antall': antall})

    # Statistikk
    col_a, col_b, col_c = st.columns(3)
    total_ut = sum([r['antall'] for r in reiser_ut])
    total_inn = sum([r['antall'] for r in reiser_inn])

    col_a.metric("Reiser UT", f"{total_ut:,}")
    col_b.metric("Reiser INN", f"{total_inn:,}")
    col_c.metric("Netto", f"{total_inn - total_ut:+,}")

    # Lag Sankey
    alle_noder = [st.session_state.valgt_område]
    andre = [o for o in områder_liste if o != st.session_state.valgt_område]

    # Begrens antall noder i Sankey for lesbarhet
    MAX_ANDRE_NODER = 10
    if len(andre) > MAX_ANDRE_NODER:
        # Vis kun topp 10 relasjoner
        alle_relasjoner = reiser_ut + reiser_inn
        if alle_relasjoner:
            df_rel = pd.DataFrame(alle_relasjoner)
            if 'til' in df_rel.columns:
                top_områder = df_rel.nlargest(MAX_ANDRE_NODER, 'antall')['til'].unique().tolist()
            else:
                top_områder = df_rel.nlargest(MAX_ANDRE_NODER, 'antall')['fra'].unique().tolist()
            andre = [o for o in andre if o in top_områder][:MAX_ANDRE_NODER]

    alle_noder.extend(andre)
    node_dict = {node: idx for idx, node in enumerate(alle_noder)}

    sources = []
    targets = []
    values = []
    colors = []

    for r in reiser_ut:
        if r['til'] in node_dict:
            sources.append(node_dict[st.session_state.valgt_område])
            targets.append(node_dict[r['til']])
            values.append(r['antall'])
            colors.append('rgba(255, 99, 71, 0.4)')

    for r in reiser_inn:
        if r['fra'] in node_dict:
            sources.append(node_dict[r['fra']])
            targets.append(node_dict[st.session_state.valgt_område])
            values.append(r['antall'])
            colors.append('rgba(100, 149, 237, 0.4)')

    if sources:
        fig_sankey = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=25,
                line=dict(color="black", width=0.5),
                label=alle_noder,
                color=['#FF6347' if n == st.session_state.valgt_område else '#6495ED'
                       for n in alle_noder]
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=colors
            ),
            textfont=dict(size=14, color='black', family='Arial')
        )])

        fig_sankey.update_layout(
            height=450,
            font=dict(size=14, family='Arial, sans-serif'),
            margin=dict(l=0, r=0, t=20, b=0)
        )

        if len(andre) > MAX_ANDRE_NODER:
            st.caption(f"Viser topp {MAX_ANDRE_NODER} forbindelser av {len(områder_liste) - 1}")

        st.plotly_chart(fig_sankey, use_container_width=True)
    else:
        st.info("Ingen reisestrømmer å vise")

# === DETALJERT DATA ===
st.markdown("---")
st.subheader("📊 Detaljert oversikt")

tab1, tab2, tab3 = st.tabs(["Utgående reiser", "Innkommende reiser", "Alle områder"])

with tab1:
    if reiser_ut:
        df_ut = pd.DataFrame(reiser_ut).sort_values('antall', ascending=False)
        df_ut['andel'] = (df_ut['antall'] / df_ut['antall'].sum() * 100).round(1)
        st.dataframe(
            df_ut.rename(columns={
                'til': 'Destinasjon',
                'antall': 'Antall reiser',
                'andel': 'Andel (%)'
            }),
            use_container_width=True,
            hide_index=True
        )

        # Last ned knapp
        csv = df_ut.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Last ned data (CSV)",
            data=csv,
            file_name=f"reiser_ut_{st.session_state.valgt_område}.csv",
            mime="text/csv"
        )
    else:
        st.info("Ingen utgående reiser")

with tab2:
    if reiser_inn:
        df_inn = pd.DataFrame(reiser_inn).sort_values('antall', ascending=False)
        df_inn['andel'] = (df_inn['antall'] / df_inn['antall'].sum() * 100).round(1)
        st.dataframe(
            df_inn.rename(columns={
                'fra': 'Opprinnelse',
                'antall': 'Antall reiser',
                'andel': 'Andel (%)'
            }),
            use_container_width=True,
            hide_index=True
        )

        # Last ned knapp
        csv = df_inn.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Last ned data (CSV)",
            data=csv,
            file_name=f"reiser_inn_{st.session_state.valgt_område}.csv",
            mime="text/csv"
        )
    else:
        st.info("Ingen innkommende reiser")

with tab3:
    # Oversikt over alle områder
    st.markdown("**Alle delområder i datasettet:**")

    område_stats = []
    for område in områder_liste:
        ut = sum([v for (f, t), v in od_data.items() if f == område])
        inn = sum([v for (f, t), v in od_data.items() if t == område])
        område_stats.append({
            'Område': område,
            'Reiser ut': ut,
            'Reiser inn': inn,
            'Totalt': ut + inn,
            'Netto': inn - ut
        })

    df_stats = pd.DataFrame(område_stats).sort_values('Totalt', ascending=False)

    st.dataframe(df_stats, use_container_width=True, hide_index=True)

    # Visualiser topp 10
    st.markdown("**Topp 10 områder etter totalt antall reiser:**")
    top10 = df_stats.head(10)

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        y=top10['Område'],
        x=top10['Reiser ut'],
        name='Reiser ut',
        orientation='h',
        marker=dict(color='rgba(255, 99, 71, 0.6)')
    ))
    fig_bar.add_trace(go.Bar(
        y=top10['Område'],
        x=top10['Reiser inn'],
        name='Reiser inn',
        orientation='h',
        marker=dict(color='rgba(100, 149, 237, 0.6)')
    ))

    fig_bar.update_layout(
        barmode='group',
        height=400,
        xaxis_title="Antall reiser",
        yaxis_title="",
        yaxis={'categoryorder': 'total ascending'}
    )

    st.plotly_chart(fig_bar, use_container_width=True)

# Footer
st.markdown("---")
st.caption(f"💡 Shapefil: {SHAPEFIL_PATH.split('/')[-1]} | "
           f"{len(områder_liste)} områder | "
           f"{len(od_data):,} forbindelser | "
           f"Tilfeldig genererte data for demonstrasjon")