"""
App de portfólio: Marketing Mix Modeling com Meridian.
Lê resultados PRÉ-CALCULADOS (pasta resultados/, gerada por exportar_resultados.py).
Nenhum MCMC roda ao vivo aqui: o app é leve e abre em segundos.
Bilíngue (PT/EN): ?lang=en ou o seletor "Idioma / Language" na sidebar.
"""
import json, os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ------------------------------------------------------------------ idioma (PT / EN)
# O idioma vem do parâmetro ?lang=en (padrão: PT) e fica em st.session_state["lang"] (o rádio da sidebar usa essa chave).
# Toda a lógica usa chaves internas em português (dados/CSV); só o TEXTO exibido passa por T(pt, en).
if "lang" not in st.session_state:
    _q = st.query_params.get("lang", "pt")
    st.session_state["lang"] = "EN" if str(_q).strip().lower() == "en" else "PT"
LANG = st.session_state["lang"] if st.session_state["lang"] in ("PT", "EN") else "PT"

def T(pt, en):
    """Texto no idioma atual."""
    return en if LANG == "EN" else pt

# ------------------------------------------------------------------ configuração
NOME_PROJETO = "Prisma"
SUBTITULO = T("Quanto cada campanha de mídia realmente entrega?", "How much does each media campaign really deliver?")
# Link do Colab SOMENTE LEITURA: abre o notebook direto do GitHub numa cópia do visitante.
# Quem abre não consegue alterar o original (edições ficam na cópia dele). Requer repositório público.
COLAB_URL = "https://colab.research.google.com/github/GabiGattiRodrigues/prisma/blob/main/mmm_meridian.ipynb"
DOCS = {
    "home": "https://developers.google.com/meridian",
    "intro": "https://developers.google.com/meridian/docs/basics/meridian-introduction",
    "glossario": "https://developers.google.com/meridian/docs/basics/glossary",
    "adstock": "https://developers.google.com/meridian/docs/advanced-modeling/media-saturation-lagging",
    "priors": "https://developers.google.com/meridian/docs/advanced-modeling/intro-priors",
    "priors_padrao": "https://developers.google.com/meridian/docs/advanced-modeling/default-prior-distributions",
    "roi_priors": "https://developers.google.com/meridian/docs/advanced-modeling/roi-priors-and-calibration",
    "kpi_sem_receita": "https://developers.google.com/meridian/docs/advanced-modeling/unknown-revenue-kpi-default",
    "controles": "https://developers.google.com/meridian/docs/advanced-modeling/control-variables",
    "baseline": "https://developers.google.com/meridian/docs/post-modeling/baseline",
    "diagnosticos": "https://developers.google.com/meridian/docs/user-guide/model-diagnostics",
    "curvas": "https://developers.google.com/meridian/docs/post-modeling/roi-mroi-response-curves",
    "otimizacao": "https://developers.google.com/meridian/docs/user-guide/optimization-overview",
    "spec": "https://developers.google.com/meridian/docs/advanced-modeling/model-spec",
    "github": "https://github.com/google/meridian",
}
AQUI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(AQUI, "resultados")

AZUL, AZUL_ESC, AZUL_CLARO, CINZA, LARANJA = "#1f5fbf", "#0b2f6b", "#9dbdec", "#6b7280", "#e07b39"
CORES_CANAIS = {"google_search": "#0b2f6b", "meta": "#1f5fbf", "tiktok": "#4a86d6",
                "youtube": "#9dbdec", "afiliados": "#6b7280", "display_programatico": "#c7ccd4"}
CANAIS = list(CORES_CANAIS)
NOMES = {"google_search": "Google Search", "meta": "Meta", "tiktok": "TikTok", "youtube": "YouTube",
         "afiliados": T("Afiliados", "Affiliates"), "display_programatico": T("Display programático", "Programmatic display"),
         "baseline": "Baseline", "desconto_medio_pct": T("Desconto (promo)", "Discount (promo)")}
KPIS = {"contas": dict(rotulo=T("Novas contas", "New accounts"), unidade=T("contas", "accounts"), ing="ingenuo_contas", chave="novas_contas", volume=True),
        "receita": dict(rotulo=T("Receita", "Revenue"), unidade=T("R$ mil", "R$ k"), ing="ingenuo_receita", chave="receita_mil", volume=False)}
UN_SEM = T("/sem", "/wk")          # sufixo "por semana" nas unidades
KPI_FMT = lambda k: KPIS[k]["rotulo"]   # format_func dos rádios de KPI (as chaves internas são "contas"/"receita")

# Cronogramas (coluna `cenario` dos CSVs): a lógica usa SEMPRE o nome original em PT; só a exibição é traduzida.
CENARIOS_EN = {
    "Diluído: 13 semanas iguais": "Spread evenly: 13 equal weeks",
    "8 semanas seguidas": "8 weeks in a row",
    "1 mês seguido (4 semanas)": "1 month in a row (4 weeks)",
    "2 semanas seguidas": "2 weeks in a row",
    "Bomba: 1 semana só": "One-shot burst: 1 week only",
    "Pulsos: 1 semana sim, 1 não": "Pulses: 1 week on, 1 week off",
    "Diluído: 52 semanas iguais": "Spread evenly: 52 equal weeks",
    "Semestre seguido (26 semanas)": "6 months in a row (26 weeks)",
    "Trimestre seguido (13 semanas)": "1 quarter in a row (13 weeks)",
    "1 mês a cada trimestre": "1 month every quarter",
    "Meses alternados (4 sim, 4 não)": "Alternating months (4 on, 4 off)",
}
def cen(o): return T(o, CENARIOS_EN.get(o, o))

# Classes de saturação: chaves internas em PT (comparadas na lógica), rótulo traduzido só na exibição.
SAT_EN = {"saturada": "saturated", "atenção": "watch", "com espaço": "room to grow"}
def sat_rot(k): return T(k, SAT_EN[k])

# "R$ ... R$" num mesmo texto vira fórmula LaTeX no markdown do Streamlit: escapo o cifrão nas chamadas de texto.
# O módulo `st` persiste entre execuções do script, então só aplico o patch uma vez (senão o escape se acumula).
if not getattr(st, "_mmm_patch", False):
    def _mk(orig):
        return lambda s, *a, **k: orig(s.replace("$", "\\$") if isinstance(s, str) else s, *a, **k)
    st.markdown, st.caption, st.info, st.warning = (_mk(st.markdown), _mk(st.caption), _mk(st.info), _mk(st.warning))
    st._mmm_patch = True

st.set_page_config(page_title=T(f"{NOME_PROJETO} · Marketing Mix Modeling", f"{NOME_PROJETO} · Marketing Mix Modeling"), page_icon="📈", layout="wide")


# ------------------------------------------------------------------ carga de dados
@st.cache_data
def ler(nome):
    return pd.read_csv(os.path.join(RES, nome))

@st.cache_data
def dados():
    return pd.read_csv(os.path.join(AQUI, "mmm_dados_sinteticos.csv"))

@st.cache_data
def verdade():
    return json.load(open(os.path.join(AQUI, "verdade_conhecida.json"), encoding="utf-8"))

@st.cache_data
def meta():
    return json.load(open(os.path.join(RES, "meta.json")))

def mostrar(fig, altura=None):
    fig.update_layout(template="plotly_white", font=dict(size=12), margin=dict(l=10, r=10, t=50, b=10),
                      colorway=[AZUL, LARANJA, CINZA])
    if altura: fig.update_layout(height=altura)
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:                       # versões antigas do Streamlit
        st.plotly_chart(fig, use_container_width=True)

# Formatação numérica: PT = 1.234,5 · EN = 1,234.5 (centralizada aqui; nada de .replace() espalhado pelo código)
def _loc(s):
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if LANG == "PT" else s
def pct(v, d=1): return _loc(f"{v:.{d}f}%")
def num(v, d=0, sign=False, grp=True):
    """sign=True força o sinal (+/-); grp=False remove o separador de milhar."""
    return _loc(f"{v:{'+' if sign else ''}{',' if grp else ''}.{d}f}")

def classe_saturacao(r):
    return "saturada" if r < 0.40 else ("atenção" if r <= 0.50 else "com espaço")   # regra prática do projeto

df = dados(); V = verdade(); M = meta()
N_SEM = len(df)

GRUPO_CONTROLE = {"desemprego_pct": T("Economia", "Economy"), "ipca_12m_pct": T("Economia", "Economy"),
                  "n_feriados_nacionais": T("Calendário e eventos", "Calendar and events"), "black_friday": T("Calendário e eventos", "Calendar and events"),
                  "sen_1": T("Sazonalidade", "Seasonality"), "cos_1": T("Sazonalidade", "Seasonality"), "sen_2": T("Sazonalidade", "Seasonality"), "cos_2": T("Sazonalidade", "Seasonality"),
                  "mes_nov": T("Sazonalidade", "Seasonality"), "mes_dez": T("Sazonalidade", "Seasonality")}
NOME_CONTROLE = {"desemprego_pct": T("Desemprego (%)", "Unemployment (%)"), "ipca_12m_pct": T("IPCA 12 meses (%)", "IPCA 12-month (%)"),
                 "n_feriados_nacionais": T("Feriados nacionais na semana", "National holidays in the week"), "black_friday": T("Semana da Black Friday", "Black Friday week"),
                 "sen_1": T("Sazonalidade: seno anual", "Seasonality: annual sine"), "cos_1": T("Sazonalidade: cosseno anual", "Seasonality: annual cosine"),
                 "sen_2": T("Sazonalidade: seno semestral", "Seasonality: semiannual sine"), "cos_2": T("Sazonalidade: cosseno semestral", "Seasonality: semiannual cosine"),
                 "mes_nov": T("Novembro (0/1)", "November (0/1)"), "mes_dez": T("Dezembro (0/1)", "December (0/1)"),
                 "desconto_medio_pct": T("Desconto médio diário (%)", "Average daily discount (%)")}

def link(rotulo, url): return f"[{rotulo}]({url})"


# ------------------------------------------------------------------ gráficos reutilizáveis
def fig_fit(nome, titulo, unidade):
    f = ler(f"fit_{nome}.csv"); f["semana"] = pd.to_datetime(f["semana"])
    f["ic_lo"] = f["ic_lo"].clip(lower=0)                        # KPI não é negativo: corta a banda em zero
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=f["semana"], y=f["ic_hi"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=f["semana"], y=f["ic_lo"], fill="tonexty", fillcolor="rgba(157,189,236,.5)",
                             line=dict(width=0), name=T("predito (IC 90%)", "predicted (90% CI)"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=f["semana"], y=f["predito"], name=T("predito", "predicted"), line=dict(color=AZUL, width=2)))
    fig.add_trace(go.Scatter(x=f["semana"], y=f["baseline"], name="baseline", line=dict(color=CINZA, dash="dash")))
    fig.add_trace(go.Scatter(x=f["semana"], y=f["real"], name=T("realizado", "actual"), line=dict(color=LARANJA, width=1.6)))
    ini = f.loc[f["teste"], "semana"].min()
    fig.add_vrect(x0=ini, x1=f["semana"].max(), fillcolor="#e5e7eb", opacity=.5, line_width=0,
                  annotation_text=T("teste (holdout)", "test (holdout)"), annotation_position="top left")
    fig.update_layout(title=titulo, yaxis_title=unidade, legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(rangemode="tozero")                          # eixo Y começa em zero
    return fig

def fig_contrib(nome, titulo):
    c = ler(f"contrib_{nome}.csv").sort_values("pct_of_contribution")
    cores = [CINZA if x == "baseline" else (LARANJA if x == "desconto_medio_pct" else AZUL) for x in c["channel"]]
    fig = go.Figure(go.Bar(x=c["pct_of_contribution"] * 100, y=[NOMES.get(x, x) for x in c["channel"]],
                           orientation="h", marker_color=cores,
                           text=[pct(v * 100) for v in c["pct_of_contribution"]], textposition="outside"))
    fig.update_layout(title=titulo, xaxis_title=T("% do KPI explicado", "% of KPI explained"), xaxis_range=[0, c["pct_of_contribution"].max() * 118])
    return fig

def fig_tempo(nome, titulo, unidade):
    t = ler(f"contrib_tempo_{nome}.csv"); t["semana"] = pd.to_datetime(t["semana"])
    f = ler(f"fit_{nome}.csv"); f["semana"] = pd.to_datetime(f["semana"])
    t = t.merge(f[["semana", "baseline"]], on="semana")
    cols = ["baseline"] + CANAIS + ["desconto_medio_pct"]
    t[cols] = t[cols].rolling(4, min_periods=1).mean()          # média móvel de 4 semanas, só p/ leitura
    cores = {"baseline": "#e5e7eb", "desconto_medio_pct": LARANJA, **CORES_CANAIS}
    fig = go.Figure()
    for c in cols:
        fig.add_trace(go.Scatter(x=t["semana"], y=t[c], name=NOMES[c], stackgroup="a", line=dict(width=.5, color="white"),
                                 fillcolor=cores[c]))
    fig.update_layout(title=titulo + T(" (média móvel de 4 semanas)", " (4-week moving average)"), yaxis_title=unidade, legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(rangemode="tozero")
    return fig

def fig_curvas(nome, unidade, com_verdade, mult_max=2.0):
    c = ler(f"curvas_{nome}.csv"); c = c[c["multiplicador"] <= mult_max + 1e-9]
    fig = make_subplots(rows=2, cols=3, subplot_titles=[NOMES[x] for x in CANAIS], vertical_spacing=.16)
    for i, canal in enumerate(CANAIS):
        r, k = i // 3 + 1, i % 3 + 1
        d = c[c["canal"] == canal]
        fig.add_trace(go.Scatter(x=d["gasto_mil"], y=d["hi"], line=dict(width=0), showlegend=False, hoverinfo="skip"), row=r, col=k)
        fig.add_trace(go.Scatter(x=d["gasto_mil"], y=d["lo"], fill="tonexty", fillcolor="rgba(157,189,236,.5)",
                                 line=dict(width=0), name=T("IC 90%", "90% CI"), showlegend=(i == 0), hoverinfo="skip"), row=r, col=k)
        fig.add_trace(go.Scatter(x=d["gasto_mil"], y=d["est"], line=dict(color=AZUL, width=2.2), name=T("estimada", "estimated"),
                                 showlegend=(i == 0)), row=r, col=k)
        if com_verdade:
            fig.add_trace(go.Scatter(x=d["gasto_mil"], y=d["verdade"], line=dict(color=LARANJA, dash="dash", width=2),
                                     name=T("verdade", "ground truth"), showlegend=(i == 0)), row=r, col=k)
        atual = d.loc[(d["multiplicador"] - 1).abs().idxmin()]
        fig.add_trace(go.Scatter(x=[atual["gasto_mil"]], y=[atual["est"]], mode="markers", marker=dict(color=CINZA, size=9),
                                 name=T("investimento atual", "current investment"), showlegend=(i == 0)), row=r, col=k)
        fig.update_xaxes(title_text=T("R$ mil", "R$ k") if r == 2 else None, row=r, col=k)
    fig.update_layout(legend=dict(orientation="h", y=-0.12), height=560)
    fig.update_yaxes(title_text=unidade, col=1)
    return fig

def tabela_retorno(nome, kpi):
    r = ler(f"retorno_{nome}.csv").set_index("canal")
    r["mroi/roi"] = r["mroi"] / r["roi"]
    a_ = T("a", "to")
    out = pd.DataFrame({
        T("Canal", "Channel"): [NOMES[c] for c in r.index],
        T("Investimento (R$ mil)", "Investment (R$ k)"): [num(x) for x in r["gasto_mil"]],
        T("ROI (IC 90%)", "ROI (90% CI)"): [f"{num(a,2)} ({num(b,2)} {a_} {num(c,2)})" for a, b, c in zip(r["roi"], r["roi_lo"], r["roi_hi"])],
        T("ROI marginal", "Marginal ROI"): [num(x, 2) for x in r["mroi"]],
        "mROI/ROI": [num(x, 2) for x in r["mroi/roi"]],
        T("Saturação", "Saturation"): [sat_rot(classe_saturacao(x)) for x in r["mroi/roi"]],
    })
    if kpi == "contas":
        out["CAC (R$)"] = [num(1000 / x, 0) for x in r["roi"]]
    return out

def erro_atribuicao(nome_retorno):
    r = ler(f"retorno_{nome_retorno}.csv").set_index("canal")
    return (r["contrib_pct"] - r["contrib_verdade"]).abs().mean(), r["contrib_pct"].sum()

def dp_grupo(bt, cols):
    return float(bt[cols].sum(axis=1).std())


# ------------------------------------------------------------------ sidebar
logo = os.path.join(AQUI, "assets", "logo.png")
with st.sidebar:
    if os.path.exists(logo):
        try:
            st.image(logo, width="stretch")
        except TypeError:
            st.image(logo, use_container_width=True)
    # seletor de idioma: a chave "lang" é a mesma lida no topo do script (persiste nos reruns)
    st.radio("Idioma / Language", ["PT", "EN"], horizontal=True, key="lang")
    st.query_params["lang"] = LANG.lower()
    st.markdown(f"## {NOME_PROJETO}")
    st.caption(T("Marketing Mix Modeling com **Meridian** (Google)", "Marketing Mix Modeling with **Meridian** (Google)"))
    st.markdown(T(
        "Reconstrução pública, em cenário de fintech e com **dados sintéticos**, de um projeto real que fiz no varejo. "
        "Como a verdade é conhecida, dá para conferir se o modelo a recuperou.",
        "A public rebuild, in a fintech scenario and with **synthetic data**, of a real project I did in retail. "
        "Because the ground truth is known, we can check whether the model recovered it."))
    st.link_button(T("Abrir notebook no Colab (somente leitura)", "Open notebook in Colab (read-only)"), COLAB_URL)
    st.link_button(T("Documentação do Meridian (Google)", "Meridian documentation (Google)"), DOCS["home"])
    st.caption(T(
        "O link do Colab abre uma **cópia** do notebook direto do GitHub: quem abre pode rodar e editar a própria cópia, "
        "mas não altera o original.",
        "The Colab link opens a **copy** of the notebook straight from GitHub: visitors can run and edit their own copy, "
        "but they cannot change the original."))
    st.divider()
    st.caption(T(
        f"{N_SEM} semanas · teste = últimas {M['semanas_teste']} · Meridian {M['meridian']} · "
        f"{M['chains']} cadeias × {M['keep']} amostras",
        f"{N_SEM} weeks · test = last {M['semanas_teste']} · Meridian {M['meridian']} · "
        f"{M['chains']} chains × {M['keep']} samples"))

# ------------------------------------------------------------------ cabeçalho
st.title(f"{NOME_PROJETO}: {SUBTITULO}")
# Ordem de exibição: resultados e decisões primeiro, explicações (parâmetros, dados, conceitos) no final.
# O restante do código usa os índices originais, então mapeio pelo nome (chaves internas em PT; o rótulo exibido passa por T).
_ORIG = ["O projeto", "Conceitos", "Dados e controles", "Por que ajustar?", "Novas contas", "Receita",
         "Verdade vs. estimado", "Quanto e onde investir", "Quando investir", "Parâmetros", "Recomendações"]
_EXIB = ["O projeto", "Novas contas", "Receita", "Verdade vs. estimado", "Quanto e onde investir", "Quando investir",
         "Recomendações", "Parâmetros", "Dados e controles", "Por que ajustar?", "Conceitos"]
_TAB_EN = {"O projeto": "The project", "Conceitos": "Concepts", "Dados e controles": "Data and controls",
           "Por que ajustar?": "Why tune?", "Novas contas": "New accounts", "Receita": "Revenue",
           "Verdade vs. estimado": "Ground truth vs. estimated", "Quanto e onde investir": "How much and where to invest",
           "Quando investir": "When to invest", "Parâmetros": "Parameters", "Recomendações": "Recommendations"}
_t = dict(zip(_EXIB, st.tabs([T(n, _TAB_EN[n]) for n in _EXIB])))
abas = [_t[n] for n in _ORIG]

# ================================================================== O PROJETO
with abas[0]:
    st.markdown(T(
        "Um **MMM (Marketing Mix Modeling)** estima **quanto de cada resultado vem de cada canal de mídia**, separando o que a mídia "
        "causou do que aconteceria de qualquer jeito (sazonalidade, promoção, economia). O difícil é que o modelo pode "
        "**ajustar muito bem e ainda assim atribuir errado**. Foi esse o principal problema do projeto original, e é o que este app mostra.",
        "An **MMM (Marketing Mix Modeling)** estimates **how much of each outcome comes from each media channel**, separating what media "
        "caused from what would have happened anyway (seasonality, promotions, the economy). The hard part is that a model can "
        "**fit very well and still attribute wrongly**. That was the main problem in the original project, and it is what this app shows."))
    st.markdown(T(
        "Aqui há **dois modelos independentes**, um para cada resultado que a mídia tenta explicar: **novas contas abertas** "
        "(KPI de volume, sem valor em R$) e **receita gerada** (KPI monetário). Para cada um, comparo uma primeira tentativa "
        "(**ingênuo**) com uma versão **ajustada**. A aba *Conceitos* explica cada termo e a aba *Por que ajustar?* detalha os parâmetros.",
        "There are **two independent models** here, one for each outcome the media tries to explain: **new accounts opened** "
        "(a volume KPI, with no R$ value) and **revenue generated** (a monetary KPI). For each one, I compare a first attempt "
        "(**naive**) with a **tuned** version. The *Concepts* tab explains each term and the *Why tune?* tab details the parameters."))
    c_link1, c_link2, _ = st.columns([1.4, 1.4, 3])
    c_link1.link_button(T("Notebook no Colab (somente leitura)", "Notebook on Colab (read-only)"), COLAB_URL)
    c_link2.link_button(T("Documentação do Meridian", "Meridian documentation"), DOCS["home"])

    kk = st.radio(T("Números do modelo de:", "Model numbers for:"), ["contas", "receita"], format_func=KPI_FMT, horizontal=True, key="kp")
    info = KPIS[kk]
    a_i, a_j = ler(f"acc_{info['ing']}.csv").iloc[0], ler(f"acc_{kk}.csv").iloc[0]
    e_i, mid_i = erro_atribuicao(info["ing"]); e_j, mid_j = erro_atribuicao(kk)
    mid_v = sum(V[info["chave"]]["canais"][c]["contribuicao_pct"] * 100 for c in CANAIS)
    st.markdown(T(f"##### KPI analisado: **{info['rotulo']}** ({'volume' if info['volume'] else 'monetário'})",
                  f"##### KPI analyzed: **{info['rotulo']}** ({'volume' if info['volume'] else 'monetary'})"))
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(T("MAPE no teste: ingênuo", "Test MAPE: naive"), pct(a_i["mape_teste"] * 100),
              help=T("Erro percentual médio nas 20 semanas que o modelo não viu.", "Mean percentage error over the 20 weeks the model did not see."))
    k2.metric(T("Erro de atribuição: ingênuo", "Attribution error: naive"), f"{num(e_i,1)} p.p.",
              help=T("Média, nos 6 canais, da diferença absoluta entre a contribuição estimada e a verdadeira (em pontos percentuais do KPI). "
                     "Só dá para medir porque o dado é sintético e a verdade é conhecida.",
                     "Average, across the 6 channels, of the absolute difference between the estimated and the true contribution (in percentage points of the KPI). "
                     "It can only be measured because the data is synthetic and the ground truth is known."))
    k3.metric(T("MAPE no teste: ajustado", "Test MAPE: tuned"), pct(a_j["mape_teste"] * 100))
    k4.metric(T("Erro de atribuição: ajustado", "Attribution error: tuned"), f"{num(e_j,1)} p.p.", delta=f"{num(e_j - e_i,1)} p.p.", delta_color="inverse")
    tab_res = pd.DataFrame({
        T("Modelo", "Model"): [T("Ingênuo", "Naive"), T("Ajustado", "Tuned")],
        T("MAPE treino", "Train MAPE"): [pct(a_i["mape_treino"] * 100), pct(a_j["mape_treino"] * 100)],
        T("MAPE teste", "Test MAPE"): [pct(a_i["mape_teste"] * 100), pct(a_j["mape_teste"] * 100)],
        T("R² teste", "Test R²"): [num(a_i["r2_teste"], 2), num(a_j["r2_teste"], 2)],
        T("Erro de atribuição (p.p.)", "Attribution error (p.p.)"): [num(e_i, 1), num(e_j, 1)],
        T("Mídia paga total (% do KPI)", "Total paid media (% of KPI)"): [pct(mid_i), pct(mid_j)],
        T("Verdade: mídia total (% do KPI)", "Ground truth: total media (% of KPI)"): [pct(mid_v), pct(mid_v)]})
    st.dataframe(tab_res, hide_index=True)

    st.markdown(T("### O que este projeto tem de diferente de um MMM de livro", "### What sets this project apart from a textbook MMM"))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(T(
            "**1. O KPI nem sempre é dinheiro.** No original o alvo eram *vidas trazidas para um programa de saúde*. "
            "Aqui rodo dois modelos: **novas contas** (volume) e **receita** (monetário). Os rankings de canais não são iguais.\n\n"
            "**2. Promoções em dias variados.** A promo pode cair na segunda, na quarta e na sexta. O modelo recebe o "
            "**desconto médio diário da semana** (dias sem promo contam zero).",
            "**1. The KPI is not always money.** In the original, the target was *lives brought into a health program*. "
            "Here I run two models: **new accounts** (volume) and **revenue** (monetary). The channel rankings are not the same.\n\n"
            "**2. Promotions on varying days.** A promo can fall on Monday, Wednesday and Friday. The model receives the "
            "**average daily discount of the week** (days without a promo count as zero)."))
    with c2:
        st.markdown(T(
            "**3. Economia e calendário como controle:** desemprego, IPCA, feriados, Black Friday e sazonalidade do ano.\n\n"
            "**4. Curva de resposta com sentido de negócio.** MAPE baixo não basta: o modelo ingênuo de novas contas tinha ~"
            f"{pct(ler('acc_ingenuo_contas.csv').iloc[0]['mape_teste']*100,0)} de erro no teste e ainda atribuía "
            f"~{pct(ler('retorno_ingenuo_contas.csv').set_index('canal').loc['google_search','contrib_pct'],0)} das contas ao Google Search "
            f"(a verdade é ~{pct(V['novas_contas']['canais']['google_search']['contribuicao_pct']*100,0)}).",
            "**3. The economy and the calendar as controls:** unemployment, IPCA (Brazilian CPI), holidays, Black Friday and yearly seasonality.\n\n"
            "**4. A response curve that makes business sense.** A low MAPE is not enough: the naive new-accounts model had ~"
            f"{pct(ler('acc_ingenuo_contas.csv').iloc[0]['mape_teste']*100,0)} test error and still attributed "
            f"~{pct(ler('retorno_ingenuo_contas.csv').set_index('canal').loc['google_search','contrib_pct'],0)} of accounts to Google Search "
            f"(the ground truth is ~{pct(V['novas_contas']['canais']['google_search']['contribuicao_pct']*100,0)})."))
    st.markdown(T("### Além de medir: o que fazer com o resultado", "### Beyond measuring: what to do with the result"))
    st.markdown(T(
        "- **Quanto e onde investir:** dada uma verba, como dividir entre as campanhas.\n"
        "- **Quando investir:** vale mais uma \"bomba\" de uma vez ou diluir ao longo das semanas? Tudo em 1 mês ou espalhado no ano? "
        "Respondido no geral e por campanha, e conferido contra a verdade.",
        "- **How much and where to invest:** given a budget, how to split it across campaigns.\n"
        "- **When to invest:** is a one-shot burst worth more, or spreading it over the weeks? All in 1 month or spread across the year? "
        "Answered overall and per campaign, and checked against the ground truth."))

# ================================================================== CONCEITOS
with abas[1]:
    st.markdown(T(
        f"Cada termo usado no projeto, em linguagem simples. Para a referência oficial, veja a {link('documentação do Meridian', DOCS['home'])} "
        f"e o {link('glossário', DOCS['glossario'])}.",
        f"Every term used in the project, in plain language. For the official reference, see the {link('Meridian documentation', DOCS['home'])} "
        f"and the {link('glossary', DOCS['glossario'])}."))
    def conceito(titulo, corpo, aqui=None, doc=None):
        st.markdown(f"#### {titulo}")
        st.markdown(corpo)
        if aqui: st.markdown(T(f"**Neste projeto:** {aqui}", f"**In this project:** {aqui}"))
        if doc: st.markdown(T(f"Saiba mais: {link('documentação do Meridian', doc)}", f"Learn more: {link('Meridian documentation', doc)}"))
        st.divider()

    conceito(T("MMM (Marketing Mix Modeling)", "MMM (Marketing Mix Modeling)"),
             T("Modelo estatístico que usa dados **agregados por semana** (quanto se investiu em cada canal e quanto de resultado apareceu) para "
               "estimar o quanto cada canal contribuiu. Não precisa de dado individual de usuário, então funciona mesmo sem cookies. "
               "A ideia central: resultado = o que teria acontecido sem mídia (**baseline**) + efeito de cada canal + efeito de promoção e fatores externos.",
               "A statistical model that uses **weekly aggregated** data (how much was invested in each channel and how much outcome showed up) to "
               "estimate how much each channel contributed. It needs no user-level data, so it works even without cookies. "
               "The core idea: outcome = what would have happened without media (**baseline**) + the effect of each channel + the effect of promotions and external factors."),
             T("6 canais, 156 semanas, dois KPIs (novas contas e receita).", "6 channels, 156 weeks, two KPIs (new accounts and revenue)."), DOCS["intro"])
    conceito(T("KPI e tipo de KPI", "KPI and KPI type"),
             T("**KPI** é o resultado que o modelo tenta explicar. Se o KPI é **monetário** (receita), o ROI vem em R$ por R$ investido. Se é de **volume** "
               "(contas, vidas, pedidos) e não se sabe o valor de cada unidade, o Meridian trata como KPI \"sem receita\": o retorno vem em unidades do KPI por real investido, "
               "e o prior padrão passa a ser sobre a *contribuição total da mídia*.",
               "The **KPI** is the outcome the model tries to explain. If the KPI is **monetary** (revenue), ROI comes in R$ per R$ invested. If it is a **volume** KPI "
               "(accounts, lives, orders) and the value of each unit is unknown, Meridian treats it as a \"non-revenue\" KPI: the return comes in KPI units per real invested, "
               "and the default prior becomes a prior on the *total media contribution*."),
             T("**Novas contas** = KPI de volume (retorno em contas por R$ 1 mil; o inverso é o CAC). **Receita** = KPI monetário (R$ por R$ 1).",
               "**New accounts** = volume KPI (return in accounts per R$ 1k; the inverse is the CAC). **Revenue** = monetary KPI (R$ per R$ 1)."),
             DOCS["kpi_sem_receita"])
    conceito(T("Mídia: impressões vs. investimento", "Media: impressions vs. spend"),
             T("O Meridian modela o efeito da **exposição** (impressões), não do dinheiro. O **investimento** entra depois, só para transformar o efeito em ROI. "
               "Isso importa porque o mesmo real compra mais ou menos impressões conforme o CPM.",
               "Meridian models the effect of **exposure** (impressions), not of money. The **spend** comes in afterwards, only to turn the effect into ROI. "
               "This matters because the same real buys more or fewer impressions depending on the CPM."),
             T("Cada canal tem uma coluna de impressões (entra no modelo) e uma de gasto em R$ mil (usada no ROI).",
               "Each channel has an impressions column (goes into the model) and a spend column in R$ k (used for ROI)."))

    st.markdown(T("#### Adstock (efeito acumulado e defasado)", "#### Adstock (accumulated and lagged effect)"))
    st.markdown(T(
        "O anúncio de hoje continua fazendo efeito nas semanas seguintes, com força decrescente. No Meridian o adstock é **geométrico**: o peso da semana *l* depois "
        "é proporcional a `decay^l`. **Decay baixo** = efeito quase imediato (ex.: busca paga). **Decay alto** = efeito longo (ex.: vídeo, marca). "
        "`max_lag` é quantas semanas para trás o efeito ainda conta (aqui, 8).",
        "Today's ad keeps having an effect in the following weeks, with decreasing strength. In Meridian the adstock is **geometric**: the weight of week *l* afterwards "
        "is proportional to `decay^l`. **Low decay** = nearly immediate effect (e.g. paid search). **High decay** = long effect (e.g. video, brand). "
        "`max_lag` is how many weeks back the effect still counts (here, 8)."))
    dcy = st.slider("decay", 0.05, 0.95, 0.5, 0.05, key="cd")
    sem = np.arange(0, 9); w = dcy ** sem; w = w / w.sum()
    fig = go.Figure(go.Bar(x=sem, y=w, marker_color=AZUL, text=[pct(x * 100, 0) for x in w], textposition="outside"))
    fig.update_layout(title=T("De cada 100 de efeito de 1 semana de mídia, quanto aparece em cada semana", "Of every 100 units of effect from 1 week of media, how much shows up in each week"),
                      xaxis_title=T("semanas depois do anúncio", "weeks after the ad"),
                      yaxis_title=T("peso", "weight"), yaxis_range=[0, 1.1])
    mostrar(fig, 300)
    st.markdown(T(f"**Neste projeto:** o decay de cada canal é estimado pelo modelo (veja as abas de resultado). Saiba mais: {link('adstock e saturação', DOCS['adstock'])}",
                  f"**In this project:** each channel's decay is estimated by the model (see the result tabs). Learn more: {link('adstock and saturation', DOCS['adstock'])}"))
    st.divider()

    st.markdown(T("#### Saturação (curva de Hill)", "#### Saturation (Hill curve)"))
    st.markdown(T(
        "Dobrar o investimento **não** dobra o resultado: cada real adicional rende menos. A curva de Hill descreve isso com dois parâmetros: "
        "**`ec`** (o nível de mídia em que se chega à metade do efeito máximo) e **`slope`** (o quão \"em S\" é a curva). "
        "O retorno do *próximo* real é o **ROI marginal (mROI)**: quanto mais perto do platô, menor ele fica.",
        "Doubling the spend does **not** double the result: each additional real yields less. The Hill curve describes this with two parameters: "
        "**`ec`** (the media level at which half of the maximum effect is reached) and **`slope`** (how \"S-shaped\" the curve is). "
        "The return on the *next* real is the **marginal ROI (mROI)**: the closer to the plateau, the smaller it gets."))
    s1, s2 = st.columns(2)
    ec = s1.slider("ec", 0.3, 2.0, 1.0, 0.1, key="ce"); sl = s2.slider("slope", 0.5, 3.0, 1.0, 0.1, key="cs")
    x = np.linspace(0, 3, 150)
    fig = go.Figure(go.Scatter(x=x, y=x ** sl / (x ** sl + ec ** sl), line=dict(color=AZUL, width=3)))
    fig.update_layout(title=T("Efeito (0 a 1) em função do nível de mídia", "Effect (0 to 1) as a function of the media level"),
                      xaxis_title=T("mídia (1 = média histórica do canal)", "media (1 = the channel's historical average)"),
                      yaxis_title=T("fração do efeito máximo", "fraction of the maximum effect"))
    mostrar(fig, 300)
    st.markdown(T("**Neste projeto:** o `ec` é estimado por canal. O `slope` fica **fixo em 1** (padrão do Meridian); os dados foram gerados com slopes entre 1,1 e 2,0, "
                  "então há uma pequena diferença entre a curva verdadeira e a estimada.",
                  "**In this project:** `ec` is estimated per channel. `slope` is **fixed at 1** (the Meridian default); the data was generated with slopes between 1.1 and 2.0, "
                  "so there is a small difference between the true and the estimated curve."))
    st.divider()

    conceito(T("Baseline, tendência e sazonalidade", "Baseline, trend and seasonality"),
             T("**Baseline** é o que teria acontecido **sem** mídia paga e sem promoção: a base orgânica. Ele reúne o nível médio do KPI, a **tendência** "
               "(crescimento ao longo do tempo), a **sazonalidade** (ondas do ano, como fim de ano) e o efeito dos **controles**. "
               "A tendência é modelada por *knots* (nós): com `knots=2` ela é uma reta; com um nó por semana (padrão) ela vira uma curva totalmente livre, "
               "o que dá liberdade demais ao baseline.",
               "The **baseline** is what would have happened **without** paid media and without promotion: the organic base. It combines the KPI's average level, the **trend** "
               "(growth over time), the **seasonality** (waves through the year, like year-end) and the effect of the **controls**. "
               "The trend is modeled with *knots*: with `knots=2` it is a straight line; with one knot per week (the default) it becomes a fully free curve, "
               "which gives the baseline too much freedom."),
             T("Ingênuo: 1 nó por semana. Ajustado: `knots=2` + sazonalidade explícita.", "Naive: 1 knot per week. Tuned: `knots=2` + explicit seasonality."), DOCS["baseline"])
    conceito(T("Controles e tratamento não-mídia", "Controls and non-media treatment"),
             T("**Controles** são variáveis que afetam o KPI mas **não são mídia** (economia, feriados, sazonalidade). Entram no baseline. "
               "**Tratamento não-mídia** é algo que a empresa controla e cuja contribuição queremos **medir separadamente** (aqui, o desconto).",
               "**Controls** are variables that affect the KPI but are **not media** (economy, holidays, seasonality). They go into the baseline. "
               "A **non-media treatment** is something the company controls and whose contribution we want to **measure separately** (here, the discount)."),
             T("Controles e comportamento de cada um na aba *Dados e controles*.", "The controls and how each one behaves are in the *Data and controls* tab."), DOCS["controles"])
    conceito(T("Sazonalidade por Fourier", "Fourier seasonality"),
             T("Um par seno/cosseno com período de 1 ano desenha uma onda suave; somar um segundo par com período de meio ano permite formatos mais realistas "
               "(dois picos, por exemplo). Cada termo sozinho não tem leitura; **juntos** desenham o formato sazonal.",
               "A sine/cosine pair with a 1-year period draws a smooth wave; adding a second pair with a half-year period allows more realistic shapes "
               "(two peaks, for example). Each term alone has no interpretation; **together** they draw the seasonal shape."),
             T("2 harmônicos anuais + marcadores de novembro e dezembro.", "2 annual harmonics + November and December markers."))
    conceito(T("Contribuição e KPI incremental", "Contribution and incremental KPI"),
             T("**KPI incremental** de um canal é o quanto do resultado só existiu por causa dele. **Contribuição** é isso como % do KPI total. "
               "Baseline + canais + promoção somam 100%.",
               "A channel's **incremental KPI** is how much of the outcome existed only because of it. **Contribution** is that as a % of the total KPI. "
               "Baseline + channels + promotion add up to 100%."),
             T("Gráficos de barras horizontais e de área ao longo do tempo nas abas de resultado.", "Horizontal bar charts and area charts over time in the result tabs."))
    conceito(T("ROI, ROI marginal, CAC e alerta de saturação", "ROI, marginal ROI, CAC and saturation alert"),
             T("**ROI** = resultado incremental por real investido (médio). **mROI** = o resultado do *próximo* real. **CAC** = custo por conta (1000 ÷ ROI, "
               "quando o ROI é em contas por R$ 1 mil). O alerta de saturação usa a razão **mROI/ROI**: abaixo de 0,40 = saturada; 0,40 a 0,50 = atenção; "
               "acima de 0,50 = com espaço. É uma **regra prática deste projeto**, não um teste estatístico.",
               "**ROI** = incremental outcome per real invested (average). **mROI** = the outcome of the *next* real. **CAC** = cost per account (1000 ÷ ROI, "
               "when ROI is in accounts per R$ 1k). The saturation alert uses the **mROI/ROI** ratio: below 0.40 = saturated; 0.40 to 0.50 = watch; "
               "above 0.50 = room to grow. This is a **rule of thumb of this project**, not a statistical test."),
             T("Tabelas de retorno por canal.", "Return tables per channel."), DOCS["curvas"])
    conceito(T("Bayesiano: prior, posterior e intervalo de credibilidade", "Bayesian: prior, posterior and credible interval"),
             T("O Meridian é bayesiano. O **prior** é o que se acredita *antes* de ver os dados (por exemplo, \"o ROI de um canal está entre 1 e 25\"). "
               "A **posterior** é a crença *depois* de ver os dados. Em vez de um número único, ele devolve uma distribuição; o **IC 90%** (intervalo de credibilidade) "
               "é a faixa que contém o valor com 90% de probabilidade. Intervalo largo = pouca certeza.",
               "Meridian is Bayesian. The **prior** is what is believed *before* seeing the data (for example, \"a channel's ROI is between 1 and 25\"). "
               "The **posterior** is the belief *after* seeing the data. Instead of a single number, it returns a distribution; the **90% CI** (credible interval) "
               "is the range that contains the value with 90% probability. Wide interval = little certainty."),
             T("Os dois modelos diferem, entre outras coisas, nos priors de ROI.", "The two models differ, among other things, in their ROI priors."), DOCS["priors"])
    conceito(T("MCMC, cadeias e R-hat", "MCMC, chains and R-hat"),
             T("A posterior é calculada por simulação (**MCMC**): várias **cadeias** independentes exploram os valores possíveis dos parâmetros. Cada cadeia tem uma fase de "
               "**adaptação** e de **burn-in** (aquecimento, descartadas) e depois guarda **amostras**. O **R-hat** compara as cadeias: perto de 1 = todas concordam "
               "(convergiu); acima de ~1,1 = a estimativa não é confiável.",
               "The posterior is computed by simulation (**MCMC**): several independent **chains** explore the possible parameter values. Each chain has an "
               "**adaptation** phase and a **burn-in** phase (warm-up, discarded) and then keeps **samples**. **R-hat** compares the chains: close to 1 = they all agree "
               "(converged); above ~1.1 = the estimate is not reliable."),
             T(f"{M['chains']} cadeias, {M['adapt']} de adaptação, {M['burnin']} de burn-in e {M['keep']} amostras mantidas por cadeia.",
               f"{M['chains']} chains, {M['adapt']} adaptation, {M['burnin']} burn-in and {M['keep']} samples kept per chain."), DOCS["diagnosticos"])
    conceito(T("Treino, teste (holdout), MAPE e R²", "Train, test (holdout), MAPE and R²"),
             T("O modelo é ajustado numa parte dos dados (**treino**) e avaliado em semanas que **nunca viu** (**teste** ou holdout). "
               "**MAPE** é o erro percentual médio entre previsto e realizado (quanto menor, melhor). **R²** é a fração da variação do KPI explicada pelo modelo. "
               "Bom no treino e ruim no teste = overfitting.",
               "The model is fitted on one part of the data (**train**) and evaluated on weeks it has **never seen** (**test** or holdout). "
               "**MAPE** is the mean percentage error between predicted and actual (the lower, the better). **R²** is the fraction of the KPI's variation explained by the model. "
               "Good on train and bad on test = overfitting."),
             T(f"Teste = últimas {M['semanas_teste']} semanas da série.", f"Test = last {M['semanas_teste']} weeks of the series."))
    conceito(T("Multicolinearidade e VIF", "Multicollinearity and VIF"),
             T("Quando dois fatores sobem e descem juntos (por exemplo, mídia que acompanha promoção), o modelo não consegue separar o efeito de cada um. "
               "O **VIF** mede isso: acima de ~5 é preocupante. É o maior risco de um MMM e a razão de calibrar com experimentos (geo-lift).",
               "When two factors rise and fall together (for example, media that follows promotion), the model cannot separate the effect of each. "
               "The **VIF** measures this: above ~5 is concerning. It is the biggest risk of an MMM and the reason to calibrate with experiments (geo-lift)."),
             T("O investimento sobe junto com desconto e Black Friday no dado (plantado de propósito).", "Spend rises together with discount and Black Friday in the data (planted on purpose)."))
    conceito(T("Dado sintético e \"verdade conhecida\"", "Synthetic data and \"known ground truth\""),
             T("Os dados foram **gerados por simulação** com valores conhecidos de adstock, saturação e força de cada canal. Assim dá para conferir se o modelo os recuperou, "
               "algo impossível com dado real, onde nunca se conhece a verdade.",
               "The data was **generated by simulation** with known values for each channel's adstock, saturation and strength. That way we can check whether the model recovered them, "
               "something impossible with real data, where the truth is never known."),
             T("A verdade só é usada para conferir; o modelo nunca a vê.", "The ground truth is only used for checking; the model never sees it."))
    st.markdown(T(
        f"Mais: {link('repositório do Meridian no GitHub', DOCS['github'])} · {link('especificação do modelo', DOCS['spec'])} · "
        f"{link('priors padrão', DOCS['priors_padrao'])} · {link('otimização de orçamento', DOCS['otimizacao'])}",
        f"More: {link('Meridian repository on GitHub', DOCS['github'])} · {link('model specification', DOCS['spec'])} · "
        f"{link('default priors', DOCS['priors_padrao'])} · {link('budget optimization', DOCS['otimizacao'])}"))

# ================================================================== DADOS E CONTROLES
with abas[2]:
    st.markdown(T("Dados **sintéticos** semanais, gerados com a verdade plantada (adstock, saturação e força de cada canal).",
                  "Weekly **synthetic** data, generated with the planted ground truth (each channel's adstock, saturation and strength)."))
    d = df.copy(); d["semana"] = pd.to_datetime(d["semana"])
    _rot_kd = {"contas": T("Novas contas", "New accounts"), "receita": T("Receita (R$ mil)", "Revenue (R$ k)")}
    kd = st.radio("KPI", ["contas", "receita"], format_func=_rot_kd.get, horizontal=True, key="kd")
    kpi_sel = _rot_kd[kd]
    col = "novas_contas" if kd == "contas" else "receita_mil"
    fig = go.Figure(go.Scatter(x=d["semana"], y=d[col], line=dict(color=AZUL, width=2), name=kpi_sel))
    for s in d.loc[d["black_friday"] == 1, "semana"]:
        fig.add_vline(x=s, line_color=LARANJA, opacity=.6)
    fig.update_layout(title=T(f"{kpi_sel} por semana (linhas laranja = Black Friday)", f"{kpi_sel} per week (orange lines = Black Friday)"))
    fig.update_yaxes(rangemode="tozero")
    mostrar(fig, 340)
    a, b = st.columns(2)
    with a:
        fig = go.Figure()
        for c in CANAIS:
            fig.add_trace(go.Scatter(x=d["semana"], y=d[f"gasto_{c}"], name=NOMES[c], stackgroup="g",
                                     line=dict(width=.5, color="white"), fillcolor=CORES_CANAIS[c]))
        fig.update_layout(title=T("Investimento semanal por canal (R$ mil)", "Weekly spend per channel (R$ k)"), legend=dict(orientation="h", y=-0.2))
        mostrar(fig, 360)
    with b:
        fig = go.Figure(go.Bar(x=d["semana"], y=d["desconto_medio_pct"], marker_color=LARANJA))
        fig.update_layout(title=T("Desconto médio diário na semana (%)", "Average daily discount in the week (%)"))
        mostrar(fig, 360)
        st.caption(T("Promo em dias diferentes vira uma média semanal: 2 dias a 20% dão 5,7%. Black Friday = 30% a semana toda.",
                     "A promo on different days becomes a weekly average: 2 days at 20% give 5.7%. Black Friday = 30% all week."))

    st.markdown(T("### Controles usados nos modelos", "### Controls used in the models"))
    st.markdown(T(
        "Controles são fatores que mexem no KPI mas **não são mídia**. O **ingênuo** usa só os 4 primeiros; o **ajustado** usa os 10. "
        "O desconto **não é controle**: é um *tratamento não-mídia*, medido em separado.",
        "Controls are factors that move the KPI but are **not media**. The **naive** model uses only the first 4; the **tuned** one uses all 10. "
        "The discount is **not a control**: it is a *non-media treatment*, measured separately."))
    def stat(c, u=""):
        x = df[c]
        return T(f"mín {num(x.min(),1)}{u} · média {num(x.mean(),1)}{u} · máx {num(x.max(),1)}{u}",
                 f"min {num(x.min(),1)}{u} · mean {num(x.mean(),1)}{u} · max {num(x.max(),1)}{u}")
    _ambos, _so_aj = T("Ingênuo e ajustado", "Naive and tuned"), T("Só ajustado", "Tuned only")
    _c_var = T("Variável", "Variable")
    ctrl_tab = pd.DataFrame([
        [NOME_CONTROLE["desemprego_pct"], GRUPO_CONTROLE["desemprego_pct"], _ambos, stat("desemprego_pct", "%"),
         T("Cai devagar ao longo dos 3 anos (de ~8,8% para ~6,4%). Efeito esperado: **negativo** (mais desemprego, menos contas/receita). "
           "Cuidado: como cai de forma contínua, anda junto com a tendência e é difícil isolar seu efeito.",
           "Falls slowly over the 3 years (from ~8.8% to ~6.4%). Expected effect: **negative** (more unemployment, fewer accounts/less revenue). "
           "Caution: because it falls steadily, it moves together with the trend and its effect is hard to isolate.")],
        [NOME_CONTROLE["ipca_12m_pct"], GRUPO_CONTROLE["ipca_12m_pct"], _ambos, stat("ipca_12m_pct", "%"),
         T("Oscila entre ~3,8% e ~6,2%, sem tendência clara. Efeito esperado: **negativo** (menos poder de compra).",
           "Fluctuates between ~3.8% and ~6.2%, with no clear trend. Expected effect: **negative** (less purchasing power).")],
        [NOME_CONTROLE["n_feriados_nacionais"], GRUPO_CONTROLE["n_feriados_nacionais"], _ambos, T("0, 1 ou 2 por semana", "0, 1 or 2 per week"),
         T("Semanas com feriado têm menos dias úteis. Efeito esperado: **negativo**.",
           "Weeks with a holiday have fewer working days. Expected effect: **negative**.")],
        [NOME_CONTROLE["black_friday"], GRUPO_CONTROLE["black_friday"], _ambos,
         T(f"1 em {int(df['black_friday'].sum())} semanas, 0 no resto", f"1 in {int(df['black_friday'].sum())} weeks, 0 in the rest"),
         T("Pico de demanda. Efeito esperado: **positivo**, e forte. Acontece junto com desconto de 30% e mídia em alta.",
           "Demand peak. Expected effect: **positive**, and strong. It happens together with a 30% discount and high media spend.")],
        [T("Sazonalidade anual (seno e cosseno, 2 harmônicos)", "Annual seasonality (sine and cosine, 2 harmonics)"), T("Sazonalidade", "Seasonality"), _so_aj,
         T("4 termos, valores entre -1 e 1", "4 terms, values between -1 and 1"),
         T("Ondas suaves com período de 1 ano e de meio ano. Juntas desenham o formato sazonal do ano; sozinhas não têm leitura.",
           "Smooth waves with a period of 1 year and of half a year. Together they draw the year's seasonal shape; alone they have no interpretation.")],
        [T("Novembro e dezembro (0/1)", "November and December (0/1)"), T("Sazonalidade", "Seasonality"), _so_aj,
         T("1 nos meses de novembro e dezembro", "1 in the months of November and December"),
         T("Marcadores do fim de ano, que a onda suave não captura bem. Efeito esperado: **positivo**.",
           "Year-end markers, which the smooth wave does not capture well. Expected effect: **positive**.")],
        [NOME_CONTROLE["desconto_medio_pct"], T("Tratamento não-mídia", "Non-media treatment"), _ambos, stat("desconto_medio_pct", "%"),
         T("Média dos 7 dias da semana, com dias sem promo valendo zero. Efeito esperado: **positivo**. Entra separado para medir sua contribuição.",
           "Average of the 7 days of the week, with days without a promo counting as zero. Expected effect: **positive**. It enters separately so its contribution can be measured.")]],
        columns=[_c_var, T("Grupo", "Group"), T("Em qual modelo", "In which model"), T("Como se comporta nos dados", "How it behaves in the data"), T("Leitura", "Interpretation")])
    st.table(ctrl_tab.replace(r"\*\*", "", regex=True).set_index(_c_var))

    fig = make_subplots(rows=2, cols=2, subplot_titles=[NOME_CONTROLE["desemprego_pct"], NOME_CONTROLE["ipca_12m_pct"], NOME_CONTROLE["n_feriados_nacionais"], "Black Friday (0/1)"], vertical_spacing=.18)
    fig.add_trace(go.Scatter(x=d["semana"], y=d["desemprego_pct"], line=dict(color=AZUL)), 1, 1)
    fig.add_trace(go.Scatter(x=d["semana"], y=d["ipca_12m_pct"], line=dict(color=AZUL)), 1, 2)
    fig.add_trace(go.Bar(x=d["semana"], y=d["n_feriados_nacionais"], marker_color=AZUL), 2, 1)
    fig.add_trace(go.Bar(x=d["semana"], y=d["black_friday"], marker_color=LARANJA), 2, 2)
    fig.update_layout(showlegend=False, height=460)
    mostrar(fig)

    st.markdown(T("#### Multicolinearidade: o risco nº 1 de um MMM", "#### Multicollinearity: the #1 risk of an MMM"))
    cols_x = [f"gasto_{c}" for c in CANAIS] + ["desconto_medio_pct", "black_friday", "n_feriados_nacionais", "desemprego_pct", "ipca_12m_pct"]
    corr = df[cols_x].corr()
    vif = pd.Series(np.diag(np.linalg.inv(corr.values)), index=cols_x)
    rot = [NOMES[c.replace("gasto_", "")] if c.startswith("gasto_") else NOME_CONTROLE.get(c, c) for c in cols_x]
    h1, h2 = st.columns([3, 2])
    with h1:
        fig = go.Figure(go.Heatmap(z=corr.values, x=rot, y=rot, zmin=-1, zmax=1, colorscale="Blues",
                                   text=np.round(corr.values, 1), texttemplate="%{text}"))
        fig.update_layout(title=T("Correlação entre investimento, promoção e controles", "Correlation between spend, promotion and controls"), yaxis_autorange="reversed")
        mostrar(fig, 520)
    with h2:
        st.dataframe(pd.DataFrame({_c_var: rot, "VIF": vif.round(2).values}), hide_index=True, height=420)
        st.caption(T("VIF acima de ~5 é preocupante. O investimento sobe junto com desconto e Black Friday (plantado de propósito): "
                     "parte do que a mídia leva de crédito pode ser efeito da promoção. Por isso a promo entra no modelo como variável própria.",
                     "A VIF above ~5 is concerning. Spend rises together with discount and Black Friday (planted on purpose): "
                     "part of the credit media gets may actually be the effect of the promotion. That is why the promo enters the model as its own variable."))

# ================================================================== POR QUE AJUSTAR?
with abas[3]:
    st.markdown(T("### Qual é o objetivo desta aba?", "### What is the goal of this tab?"))
    st.markdown(T(
        "É um **experimento de propósito**, que reproduz o problema do projeto original: um primeiro modelo com **MAPE bom** mas com "
        "**atribuição de canais errada**. Comparo duas configurações do **mesmo Meridian, dos mesmos dados e do mesmo período de teste**, "
        "mudando só as decisões de modelagem. Assim fica claro que o MAPE sozinho não valida um MMM, e o que cada decisão muda.",
        "It is a **deliberate experiment** that reproduces the problem of the original project: a first model with a **good MAPE** but with "
        "**wrong channel attribution**. I compare two configurations of the **same Meridian, the same data and the same test period**, "
        "changing only the modeling decisions. This makes it clear that MAPE alone does not validate an MMM, and what each decision changes."))
    kk = st.radio("KPI", ["contas", "receita"], format_func=KPI_FMT, horizontal=True, key="kpi_ing")
    info = KPIS[kk]
    st.markdown(T("### Como cada modelo está configurado", "### How each model is configured"))
    prior_ing = (T("Prior de **contribuição total da mídia**: média 40%, desvio 20% (padrão do Meridian para KPI sem receita)",
                   "**Total media contribution** prior: mean 40%, standard deviation 20% (the Meridian default for a non-revenue KPI)")
                 if info["volume"] else
                 T("Prior de **ROI** por canal: LogNormal(0,2; 0,9), ~95% entre 0,2 e 7,1 R$ por R$ 1 (padrão do Meridian)",
                   "Per-channel **ROI** prior: LogNormal(0.2, 0.9), ~95% between 0.2 and 7.1 R$ per R$ 1 (the Meridian default)"))
    prior_aj = (T("Prior de **ROI** por canal: LogNormal com 95% entre 1 e 25 contas por R$ 1 mil",
                  "Per-channel **ROI** prior: LogNormal with 95% between 1 and 25 accounts per R$ 1k")
                if info["volume"] else
                T("Prior de **ROI** por canal: LogNormal com 95% entre 0,3 e 8 R$ por R$ 1",
                  "Per-channel **ROI** prior: LogNormal with 95% between 0.3 and 8 R$ per R$ 1"))
    _c_item = T("Item", "Item")
    cfg = pd.DataFrame([
        [T("Dados, canais e KPI", "Data, channels and KPI"), T("Os mesmos", "The same"), T("Os mesmos", "The same"),
         T("Igual, para a comparação ser justa", "Identical, so the comparison is fair")],
        [T("Controles", "Controls"), T("4: desemprego, IPCA, feriados, Black Friday", "4: unemployment, IPCA, holidays, Black Friday"),
         T("10: os 4 + seno/cosseno anual e semestral + novembro e dezembro", "10: the 4 + annual and semiannual sine/cosine + November and December"),
         T("A sazonalidade passa a ser **informada** ao modelo, em vez de ele ter que descobri-la",
           "Seasonality is now **given** to the model, instead of it having to discover it")],
        [T("Tendência (knots)", "Trend (knots)"), T("1 nó por semana (156): baseline totalmente livre", "1 knot per week (156): fully free baseline"),
         T("2 nós: uma reta", "2 knots: a straight line"),
         T("Com tendência livre o baseline consegue explicar qualquer oscilação e distribui mal o crédito",
           "With a free trend the baseline can explain any fluctuation and misallocates the credit")],
        [T("Prior do ROI / mídia", "ROI / media prior"), prior_ing.replace("**", ""), prior_aj.replace("**", ""),
         T("O ajustado diz ao modelo uma faixa plausível de negócio (larga, só corta o absurdo)",
           "The tuned model is given a plausible business range (wide; it only rules out the absurd)")],
        [T("Adstock (decay)", "Adstock (decay)"), T("Uniform(0; 1) por canal, `max_lag` = 8", "Uniform(0, 1) per channel, `max_lag` = 8"), T("Igual", "Same"), T("Mantido", "Kept")],
        [T("Saturação (Hill)", "Saturation (Hill)"), T("`ec` ~ Normal truncada(0,8; 0,8), `slope` fixo em 1", "`ec` ~ Truncated Normal(0.8, 0.8), `slope` fixed at 1"), T("Igual", "Same"), T("Mantido", "Kept")],
        [T("Teste (holdout)", "Test (holdout)"), T(f"Últimas {M['semanas_teste']} semanas", f"Last {M['semanas_teste']} weeks"), T("Igual", "Same"), T("Mantido", "Kept")],
        ["MCMC", T(f"{M['chains']} cadeias, {M['adapt']}/{M['burnin']}/{M['keep']} (adapt/burn-in/mantidas)",
                   f"{M['chains']} chains, {M['adapt']}/{M['burnin']}/{M['keep']} (adapt/burn-in/kept)"), T("Igual", "Same"), T("Mantido", "Kept")]],
        columns=[_c_item, T("Ingênuo", "Naive"), T("Ajustado", "Tuned"), T("Por que mudei", "Why I changed it")])
    st.table(cfg.replace(r"\*\*", "", regex=True).set_index(_c_item))
    st.caption(T(f"Priors padrão do Meridian: {link('documentação', DOCS['priors_padrao'])}. Detalhes do prior para KPI sem receita: {link('documentação', DOCS['kpi_sem_receita'])}.",
                 f"Meridian default priors: {link('documentation', DOCS['priors_padrao'])}. Details of the prior for a non-revenue KPI: {link('documentation', DOCS['kpi_sem_receita'])}."))

    st.markdown(T("### O que muda no resultado", "### What changes in the result"))
    a_i, a_j = ler(f"acc_{info['ing']}.csv").iloc[0], ler(f"acc_{kk}.csv").iloc[0]
    ac = pd.DataFrame({"": [T("MAPE treino", "Train MAPE"), T("MAPE teste", "Test MAPE"), T("R² treino", "Train R²"), T("R² teste", "Test R²")],
                       T("Ingênuo", "Naive"): [pct(a_i["mape_treino"] * 100), pct(a_i["mape_teste"] * 100), num(a_i["r2_treino"], 2), num(a_i["r2_teste"], 2)],
                       T("Ajustado", "Tuned"): [pct(a_j["mape_treino"] * 100), pct(a_j["mape_teste"] * 100), num(a_j["r2_treino"], 2), num(a_j["r2_teste"], 2)]})
    ri = ler(f"retorno_{info['ing']}.csv").set_index("canal"); rj = ler(f"retorno_{kk}.csv").set_index("canal")
    ca, cb = st.columns([1, 2])
    with ca:
        st.markdown(T("##### Acurácia", "##### Accuracy"))
        st.dataframe(ac, hide_index=True)
        st.caption(T("Olhando só o MAPE, os dois parecem razoáveis. A diferença aparece na atribuição.",
                     "Looking at MAPE alone, both look reasonable. The difference shows up in the attribution."))
    with cb:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[ri.loc[c, "contrib_verdade"] for c in CANAIS], name=T("verdade", "ground truth"), marker_color=LARANJA))
        fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[ri.loc[c, "contrib_pct"] for c in CANAIS], name=T("ingênuo", "naive"), marker_color=CINZA))
        fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[rj.loc[c, "contrib_pct"] for c in CANAIS], name=T("ajustado", "tuned"), marker_color=AZUL))
        fig.update_layout(title=T(f"Contribuição por canal (% de {info['rotulo'].lower()})", f"Contribution per channel (% of {info['rotulo'].lower()})"),
                          barmode="group", legend=dict(orientation="h", y=-0.2))
        mostrar(fig, 380)
    _e_ing, _e_aj = T("Erro ingênuo (p.p.)", "Naive error (p.p.)"), T("Erro ajustado (p.p.)", "Tuned error (p.p.)")
    erro = pd.DataFrame({T("Canal", "Channel"): [NOMES[c] for c in CANAIS],
                         _e_ing: [abs(ri.loc[c, "contrib_pct"] - ri.loc[c, "contrib_verdade"]) for c in CANAIS],
                         _e_aj: [abs(rj.loc[c, "contrib_pct"] - rj.loc[c, "contrib_verdade"]) for c in CANAIS]})
    erro.loc[len(erro)] = [T("Média", "Average"), erro.iloc[:, 1].mean(), erro.iloc[:, 2].mean()]
    st.dataframe(erro.style.format({_e_ing: "{:.1f}", _e_aj: "{:.1f}"}), hide_index=True)
    worst = (ri["contrib_pct"] - ri["contrib_verdade"]).abs().idxmax()
    st.markdown(T(
        f"> No modelo ingênuo de {info['rotulo'].lower()}, o maior desvio é **{NOMES[worst]}**: atribui **{pct(ri.loc[worst,'contrib_pct'])}** contra "
        f"**{pct(ri.loc[worst,'contrib_verdade'])}** de verdade. A mídia total atribuída é {pct(ri['contrib_pct'].sum())} no ingênuo, "
        f"{pct(rj['contrib_pct'].sum())} no ajustado e {pct(ri['contrib_verdade'].sum())} na verdade. "
        "**Ajuste bom, atribuição errada:** com tendência livre e priors abertos, o modelo tem liberdade demais para distribuir crédito.",
        f"> In the naive {info['rotulo'].lower()} model, the largest deviation is **{NOMES[worst]}**: it attributes **{pct(ri.loc[worst,'contrib_pct'])}** versus "
        f"**{pct(ri.loc[worst,'contrib_verdade'])}** in the ground truth. Total attributed media is {pct(ri['contrib_pct'].sum())} in the naive model, "
        f"{pct(rj['contrib_pct'].sum())} in the tuned one and {pct(ri['contrib_verdade'].sum())} in the ground truth. "
        "**Good fit, wrong attribution:** with a free trend and open priors, the model has too much freedom to distribute credit."))
    x1, x2 = st.columns(2)
    with x1: mostrar(fig_fit(info["ing"], T("Ingênuo: predito vs. realizado", "Naive: predicted vs. actual"), info["unidade"]), 360)
    with x2: mostrar(fig_fit(kk, T("Ajustado: predito vs. realizado", "Tuned: predicted vs. actual"), info["unidade"]), 360)

# ================================================================== MODELOS AJUSTADOS
def aba_modelo(nome, kpi):
    info = KPIS[kpi]; ac = ler(f"acc_{nome}.csv").iloc[0]
    st.markdown(T(f"Modelo ajustado para **{info['rotulo']}** ({'KPI de volume' if info['volume'] else 'KPI monetário'}). "
                  "Configuração completa na aba *Por que ajustar?*.",
                  f"Tuned model for **{info['rotulo']}** ({'volume KPI' if info['volume'] else 'monetary KPI'}). "
                  "Full configuration in the *Why tune?* tab."))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(T("MAPE treino", "Train MAPE"), pct(ac["mape_treino"] * 100)); m2.metric(T("MAPE teste", "Test MAPE"), pct(ac["mape_teste"] * 100))
    m3.metric(T("R² teste", "Test R²"), num(ac["r2_teste"], 2)); m4.metric(T("Maior R-hat", "Max R-hat"), num(ac["max_rhat"], 3),
                                                                            help=T("Convergência do MCMC: ideal < 1,1", "MCMC convergence: ideal < 1.1"))
    mostrar(fig_fit(nome, T(f"{info['rotulo']}: predito vs. realizado", f"{info['rotulo']}: predicted vs. actual"), info["unidade"]), 380)
    st.caption(T("Eixo começando em zero. A banda de incerteza é cortada em zero, já que o KPI não é negativo.",
                 "Axis starting at zero. The uncertainty band is clipped at zero, since the KPI is not negative."))

    st.markdown(T("#### De onde vem o KPI", "#### Where the KPI comes from"))
    a, b = st.columns(2)
    with a: mostrar(fig_contrib(nome, T("Contribuição por componente", "Contribution by component")), 400)
    with b: mostrar(fig_tempo(nome, T("Contribuição ao longo do tempo", "Contribution over time"), info["unidade"]), 400)
    bs = ler(f"baseline_{nome}.csv").set_index("metric")
    st.info(T(
        f"**Baseline segundo o Meridian:** {pct(bs.loc['mean','posterior'])} do KPI (IC 90%: {pct(bs.loc['ci_lo','posterior'])} a "
        f"{pct(bs.loc['ci_hi','posterior'])}). Antes de ver os dados (prior), o modelo esperava {pct(bs.loc['mean','prior'])}. "
        f"Na verdade, a soma de tudo que **não** é mídia paga (baseline + desconto) é {pct(100 - V[info['chave']]['midia_total'] / V[info['chave']]['y_total'] * 100)}.",
        f"**Baseline according to Meridian:** {pct(bs.loc['mean','posterior'])} of the KPI (90% CI: {pct(bs.loc['ci_lo','posterior'])} to "
        f"{pct(bs.loc['ci_hi','posterior'])}). Before seeing the data (prior), the model expected {pct(bs.loc['mean','prior'])}. "
        f"In the ground truth, the sum of everything that is **not** paid media (baseline + discount) is {pct(100 - V[info['chave']]['midia_total'] / V[info['chave']]['y_total'] * 100)}."))

    st.markdown(T("#### Dentro do baseline: os controles", "#### Inside the baseline: the controls"))
    st.markdown(T(
        "O Meridian entrega o baseline inteiro. Para ver **quem está dentro dele**, calculei a contribuição de cada controle a partir dos "
        f"coeficientes da posterior (não é uma saída pronta do Meridian; ver {link('documentação do baseline', DOCS['baseline'])}). "
        "Os controles são centrados, então cada contribuição é o **desvio em relação ao nível médio**: positiva quando o fator empurra o KPI para cima naquela semana, negativa quando puxa para baixo.",
        "Meridian delivers the baseline as a whole. To see **what is inside it**, I computed each control's contribution from the "
        f"posterior coefficients (this is not a ready-made Meridian output; see the {link('baseline documentation', DOCS['baseline'])}). "
        "The controls are centered, so each contribution is the **deviation from the average level**: positive when the factor pushes the KPI up in that week, negative when it pulls it down."))
    bt = ler(f"baseline_tempo_{nome}.csv"); bt["semana"] = pd.to_datetime(bt["semana"])
    grupos = {T("Sazonalidade", "Seasonality"): ["sen_1", "cos_1", "sen_2", "cos_2", "mes_nov", "mes_dez"],
              T("Economia (desemprego + IPCA)", "Economy (unemployment + IPCA)"): ["desemprego_pct", "ipca_12m_pct"],
              T("Calendário e eventos (feriados + Black Friday)", "Calendar and events (holidays + Black Friday)"): ["n_feriados_nacionais", "black_friday"]}
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.45, .55], vertical_spacing=.08,
                        subplot_titles=[T("Baseline = nível + tendência + efeito dos controles", "Baseline = level + trend + effect of the controls"),
                                        T("Efeito de cada grupo de controles (desvio do nível médio)", "Effect of each control group (deviation from the average level)")])
    fig.add_trace(go.Scatter(x=bt["semana"], y=bt["baseline"], name=T("baseline total", "total baseline"), line=dict(color=CINZA, width=2)), 1, 1)
    fig.add_trace(go.Scatter(x=bt["semana"], y=bt["nivel_tendencia"], name=T("só nível + tendência", "level + trend only"), line=dict(color=AZUL, dash="dash")), 1, 1)
    for (g, cs), cor in zip(grupos.items(), [AZUL_ESC, LARANJA, AZUL_CLARO]):
        fig.add_trace(go.Scatter(x=bt["semana"], y=bt[cs].sum(axis=1), name=g, line=dict(color=cor)), 2, 1)
    fig.add_hline(y=0, line_color="#999", line_width=1, row=2, col=1)
    fig.update_yaxes(title_text=info["unidade"], row=1, col=1); fig.update_yaxes(title_text=info["unidade"], row=2, col=1)
    fig.update_layout(legend=dict(orientation="h", y=-0.12))
    mostrar(fig, 560)

    st.caption(T(
        "Atenção ao gráfico de cima: a linha tracejada (só nível + tendência) pode ficar quase plana enquanto o efeito de *Economia* sobe ou desce de forma contínua. "
        "Como o desemprego cai devagar durante os 3 anos, **tendência de crescimento e efeito do desemprego são praticamente indistinguíveis**: o modelo estima bem o baseline total, "
        "mas a divisão entre os dois é incerta (veja o intervalo largo do desemprego na tabela).",
        "Note the top chart: the dashed line (level + trend only) can stay almost flat while the *Economy* effect rises or falls steadily. "
        "Since unemployment falls slowly over the 3 years, **the growth trend and the unemployment effect are practically indistinguishable**: the model estimates the total baseline well, "
        "but the split between the two is uncertain (see the wide unemployment interval in the table)."))
    _c_grupo = T("Grupo", "Group")
    amp = pd.DataFrame({_c_grupo: list(grupos), "amp": [dp_grupo(bt, cs) for cs in grupos.values()]}).sort_values("amp")
    ca, cb = st.columns([2, 3])
    with ca:
        fig = go.Figure(go.Bar(x=amp["amp"], y=amp[_c_grupo], orientation="h", marker_color=AZUL,
                               text=[num(v) for v in amp["amp"]], textposition="outside"))
        fig.update_layout(title=T(f"Quanto cada grupo move o KPI ({info['unidade']}/semana)", f"How much each group moves the KPI ({info['unidade']}/week)"),
                          xaxis_range=[0, amp["amp"].max() * 1.25])
        mostrar(fig, 300)
        st.caption(T("Amplitude = desvio-padrão da contribuição semanal do grupo.", "Amplitude = standard deviation of the group's weekly contribution."))
    with cb:
        ct = ler(f"controles_{nome}.csv")
        linhas = []
        _un_pt = {"desemprego_pct": "por +1 p.p.", "ipca_12m_pct": "por +1 p.p.", "n_feriados_nacionais": "por feriado",
                  "black_friday": "na semana de BF", "mes_nov": "no mês", "mes_dez": "no mês", "desconto_medio_pct": "por +1 p.p. de desconto"}
        _un_en = {"desemprego_pct": "per +1 p.p.", "ipca_12m_pct": "per +1 p.p.", "n_feriados_nacionais": "per holiday",
                  "black_friday": "in BF week", "mes_nov": "in the month", "mes_dez": "in the month", "desconto_medio_pct": "per +1 p.p. of discount"}
        for _, r in ct.iterrows():
            un = T(_un_pt.get(r["controle"], "por +1 unidade da onda"), _un_en.get(r["controle"], "per +1 wave unit"))
            sinal = T("sinal incerto", "uncertain sign") if (r["efeito_un_lo"] < 0 < r["efeito_un_hi"]) else \
                (T("positivo", "positive") if r["efeito_un"] > 0 else T("negativo", "negative"))
            linhas.append({T("Variável", "Variable"): NOME_CONTROLE[r["controle"]],
                           T("Efeito estimado (IC 90%)", "Estimated effect (90% CI)"):
                               f"{num(r['efeito_un'],1)} ({num(r['efeito_un_lo'],1)} {T('a', 'to')} {num(r['efeito_un_hi'],1)}) {info['unidade']}{UN_SEM} {un}",
                           T("Leitura do sinal", "Sign reading"): sinal,
                           T("Efeito verdadeiro", "True effect"): "-" if pd.isna(r["efeito_un_verdade"]) else f"{num(r['efeito_un_verdade'],1)}"})
        st.dataframe(pd.DataFrame(linhas), hide_index=True, height=430)
    st.caption(T("\"Sinal incerto\" = o intervalo de 90% inclui zero: o modelo não consegue afirmar se o efeito é positivo ou negativo. "
                 "O desemprego costuma cair nessa categoria porque cai de forma contínua e se confunde com a tendência (multicolinearidade).",
                 "\"Uncertain sign\" = the 90% interval includes zero: the model cannot say whether the effect is positive or negative. "
                 "Unemployment usually falls into this category because it falls steadily and gets confused with the trend (multicollinearity)."))

    st.markdown(T("#### Retorno por canal", "#### Return per channel"))
    if info["volume"]:
        st.caption(T("ROI = novas contas por R$ 1 mil investido; CAC = 1000 ÷ ROI. **mROI/ROI** baixo indica saturação: "
                     "< 0,40 saturada, 0,40 a 0,50 atenção, > 0,50 com espaço (regra prática do projeto).",
                     "ROI = new accounts per R$ 1k invested; CAC = 1000 ÷ ROI. A low **mROI/ROI** indicates saturation: "
                     "< 0.40 saturated, 0.40 to 0.50 watch, > 0.50 room to grow (rule of thumb of the project)."))
    else:
        st.caption(T("ROI = R$ de receita por R$ 1 investido. **mROI/ROI** baixo indica saturação: "
                     "< 0,40 saturada, 0,40 a 0,50 atenção, > 0,50 com espaço (regra prática do projeto).",
                     "ROI = R$ of revenue per R$ 1 invested. A low **mROI/ROI** indicates saturation: "
                     "< 0.40 saturated, 0.40 to 0.50 watch, > 0.50 room to grow (rule of thumb of the project)."))
    st.dataframe(tabela_retorno(nome, kpi), hide_index=True)
    st.warning(T("Repare nos intervalos: canal com IC largo não deve ter decisão tomada só pelo ponto.",
                 "Look at the intervals: a channel with a wide CI should not have a decision made on the point estimate alone."))

    st.markdown(T("#### Curvas de resposta", "#### Response curves"))
    st.caption(T("KPI incremental em função do investimento total. Ponto cinza = investimento atual. Curva ainda subindo = há espaço; achatando = saturação.",
                 "Incremental KPI as a function of total spend. Gray dot = current spend. Curve still rising = room to grow; flattening = saturation."))
    mostrar(fig_curvas(nome, info["unidade"], com_verdade=False), 580)

    st.markdown(T("#### Decay do adstock estimado", "#### Estimated adstock decay"))
    r = ler(f"retorno_{nome}.csv").set_index("canal")
    sem = np.arange(0, 9)
    fig = go.Figure()
    for c in CANAIS:
        w = r.loc[c, "decay_estimado"] ** sem; w = w / w.sum()
        fig.add_trace(go.Scatter(x=sem, y=w, name=NOMES[c], mode="lines+markers", line=dict(color=CORES_CANAIS[c] if c != "display_programatico" else CINZA)))
    fig.update_layout(title=T("Peso do efeito de 1 semana de mídia nas semanas seguintes", "Weight of the effect of 1 week of media in the following weeks"),
                      xaxis_title=T("semanas depois", "weeks after"), yaxis_title=T("peso", "weight"))
    mostrar(fig, 340)

with abas[4]:
    aba_modelo("contas", "contas")
with abas[5]:
    aba_modelo("receita", "receita")
    comp = pd.DataFrame({
        T("Canal", "Channel"): [NOMES[c] for c in CANAIS],
        T("Novas contas (% do KPI)", "New accounts (% of KPI)"): [ler("retorno_contas.csv").set_index("canal").loc[c, "contrib_pct"] for c in CANAIS],
        T("Receita (% do KPI)", "Revenue (% of KPI)"): [ler("retorno_receita.csv").set_index("canal").loc[c, "contrib_pct"] for c in CANAIS]})
    fig = go.Figure()
    fig.add_trace(go.Bar(x=comp.iloc[:, 0], y=comp.iloc[:, 1], name=T("novas contas", "new accounts"), marker_color=AZUL))
    fig.add_trace(go.Bar(x=comp.iloc[:, 0], y=comp.iloc[:, 2], name=T("receita", "revenue"), marker_color=AZUL_CLARO))
    fig.update_layout(title=T("O mesmo canal pode ser bom para conta e fraco para receita", "The same channel can be good for accounts and weak for revenue"), barmode="group",
                      yaxis_title=T("% do KPI explicado", "% of KPI explained"), legend=dict(orientation="h", y=-0.2))
    mostrar(fig, 380)

# ================================================================== VERDADE vs ESTIMADO
with abas[6]:
    st.markdown(T("Como o dado é sintético, temos o **gabarito**. O modelo nunca viu esses números.",
                  "Because the data is synthetic, we have the **answer key**. The model never saw these numbers."))
    nome_v = st.radio("KPI", ["contas", "receita"], format_func=KPI_FMT, horizontal=True, key="kv")
    r = ler(f"retorno_{nome_v}.csv").set_index("canal")
    x = [NOMES[c] for c in CANAIS]
    _n_ver, _n_est = T("verdade", "ground truth"), T("estimado (IC 90%)", "estimated (90% CI)")
    f = make_subplots(rows=1, cols=3, subplot_titles=[T("Contribuição (% do KPI)", "Contribution (% of KPI)"), "ROI", T("Decay do adstock", "Adstock decay")])
    f.add_trace(go.Bar(x=x, y=[r.loc[c, "contrib_verdade"] for c in CANAIS], marker_color=LARANJA, name=_n_ver), 1, 1)
    f.add_trace(go.Bar(x=x, y=[r.loc[c, "contrib_pct"] for c in CANAIS], marker_color=AZUL, name=_n_est,
                       error_y=dict(type="data", symmetric=False, array=[r.loc[c, "contrib_hi"] - r.loc[c, "contrib_pct"] for c in CANAIS],
                                    arrayminus=[r.loc[c, "contrib_pct"] - r.loc[c, "contrib_lo"] for c in CANAIS])), 1, 1)
    f.add_trace(go.Bar(x=x, y=[r.loc[c, "roi_verdade"] for c in CANAIS], marker_color=LARANJA, showlegend=False), 1, 2)
    f.add_trace(go.Bar(x=x, y=[r.loc[c, "roi"] for c in CANAIS], marker_color=AZUL, showlegend=False,
                       error_y=dict(type="data", symmetric=False, array=[r.loc[c, "roi_hi"] - r.loc[c, "roi"] for c in CANAIS],
                                    arrayminus=[r.loc[c, "roi"] - r.loc[c, "roi_lo"] for c in CANAIS])), 1, 2)
    f.add_trace(go.Bar(x=x, y=[r.loc[c, "decay_verdade"] for c in CANAIS], marker_color=LARANJA, showlegend=False), 1, 3)
    f.add_trace(go.Bar(x=x, y=[r.loc[c, "decay_estimado"] for c in CANAIS], marker_color=AZUL, showlegend=False), 1, 3)
    f.update_layout(barmode="group", legend=dict(orientation="h", y=-0.25), height=420)
    mostrar(f)
    excl = [NOMES[c] for c in CANAIS if not (r.loc[c, "contrib_lo"] <= r.loc[c, "contrib_verdade"] <= r.loc[c, "contrib_hi"])]
    st.markdown(T(f"**Canais cujo IC 90% de contribuição não contém a verdade:** {', '.join(excl) if excl else 'nenhum'}.",
                  f"**Channels whose 90% contribution CI does not contain the ground truth:** {', '.join(excl) if excl else 'none'}."))

    st.markdown(T("#### Controles e promoção: efeito estimado vs. verdadeiro (por unidade)", "#### Controls and promotion: estimated vs. true effect (per unit)"))
    ct = ler(f"controles_{nome_v}.csv"); ct = ct[ct["efeito_un_verdade"].notna()]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[NOME_CONTROLE[c] for c in ct["controle"]], y=ct["efeito_un_verdade"], marker_color=LARANJA, name=_n_ver))
    fig.add_trace(go.Bar(x=[NOME_CONTROLE[c] for c in ct["controle"]], y=ct["efeito_un"], marker_color=AZUL, name=_n_est,
                         error_y=dict(type="data", symmetric=False, array=(ct["efeito_un_hi"] - ct["efeito_un"]).values,
                                      arrayminus=(ct["efeito_un"] - ct["efeito_un_lo"]).values)))
    fig.update_layout(barmode="group", yaxis_title=T(f"{KPIS[nome_v]['unidade']}/semana por unidade", f"{KPIS[nome_v]['unidade']}/week per unit"), legend=dict(orientation="h", y=-0.25))
    mostrar(fig, 380)
    st.caption(T("Desemprego e Black Friday têm intervalos largos: o desemprego se confunde com a tendência, e a Black Friday são só 3 semanas.",
                 "Unemployment and Black Friday have wide intervals: unemployment gets confused with the trend, and Black Friday is only 3 weeks."))

    st.markdown(T(
        "**Onde o modelo errou e por quê.** O investimento em **Meta** sobe junto com promoção e Black Friday (plantei essa "
        "multicolinearidade de propósito), e o modelo não consegue separar totalmente os dois: um intervalo de credibilidade "
        "pode estar bem calibrado no modelo e ainda assim errado se a estrutura do dado confunde causas. O **decay do adstock** "
        "também é mal identificado com 3 anos semanais. ROI e contribuição saem melhores que o decay. "
        "O remédio direto é **calibrar com experimentos de incrementalidade (geo-lift)** e usar o resultado como prior de ROI.",
        "**Where the model went wrong and why.** Spend on **Meta** rises together with promotion and Black Friday (I planted this "
        "multicollinearity on purpose), and the model cannot fully separate the two: a credible interval "
        "can be well calibrated within the model and still be wrong if the data's structure confounds causes. The **adstock decay** "
        "is also poorly identified with 3 years of weekly data. ROI and contribution come out better than the decay. "
        "The direct remedy is to **calibrate with incrementality experiments (geo-lift)** and use the result as an ROI prior."))
    st.markdown(T("#### Curvas de resposta: estimada vs. verdadeira", "#### Response curves: estimated vs. true"))
    mostrar(fig_curvas(nome_v, KPIS[nome_v]["unidade"], com_verdade=True), 580)

# ================================================================== QUANTO E ONDE INVESTIR
with abas[7]:
    st.markdown(T(
        "**Dada uma verba X por semana, como dividir entre as campanhas?** O princípio: colocar o próximo real onde o **retorno marginal** é maior, "
        "até igualar o retorno marginal entre os canais. As curvas de resposta estimadas dizem onde cada canal está nessa curva.",
        "**Given a budget X per week, how should it be split across campaigns?** The principle: put the next real where the **marginal return** is highest, "
        "until the marginal return is equalized across channels. The estimated response curves say where each channel sits on that curve."))
    ns = st.radio(T("KPI a maximizar", "KPI to maximize"), ["contas", "receita"], format_func=KPI_FMT, horizontal=True, key="ks")
    unid = KPIS[ns]["unidade"]
    curvas = ler(f"curvas_{ns}.csv")

    def _g(canal):
        d = curvas[curvas["canal"] == canal].sort_values("multiplicador"); return d
    G = {c: _g(c) for c in CANAIS}
    atual_sem = {c: float(G[c].loc[(G[c]["multiplicador"] - 1).abs().idxmin(), "gasto_mil"]) / N_SEM for c in CANAIS}
    def resposta(canal, gasto_sem, col="est"):
        d = G[canal]; return float(np.interp(gasto_sem * N_SEM, d["gasto_mil"], d[col])) / N_SEM
    total_atual = sum(atual_sem.values())

    st.markdown(T("### 1. Verba total", "### 1. Total budget"))
    pct_x = st.slider(T("Verba semanal total (100% = o que foi investido em média)", "Total weekly budget (100% = what was invested on average)"),
                      50, 250, 100, 5, format="%d%%", key=f"x_{ns}")
    X = total_atual * pct_x / 100
    st.caption(T(f"Verba semanal: **R$ {num(X,1)} mil** (atual: R$ {num(total_atual,1)} mil). Cada canal pode ir de 0 a 3x o que investiu; acima de 2x o modelo extrapola além do que viu nos dados.",
                 f"Weekly budget: **R$ {num(X,1)}k** (current: R$ {num(total_atual,1)}k). Each channel can go from 0 to 3x what it invested; above 2x the model extrapolates beyond what it saw in the data."))

    def otimizar(X, col="est"):
        passo = X / 500; g = {c: 0.0 for c in CANAIS}
        for _ in range(500):
            melhor, gm = None, -1
            for c in CANAIS:
                if g[c] + passo > 3 * atual_sem[c]: continue
                ganho = resposta(c, g[c] + passo, col) - resposta(c, g[c], col)
                if ganho > gm: melhor, gm = c, ganho
            if melhor is None: break
            g[melhor] += passo
        return g
    otimo = otimizar(X)
    prop = {c: atual_sem[c] * pct_x / 100 for c in CANAIS}          # mantém a proporção atual
    def total(alv, col="est"): return sum(resposta(c, alv[c], col) for c in CANAIS)
    def marg(c, g):                                                  # retorno marginal por R$ 1 mil
        h = max(g * 0.01, 0.05); return (resposta(c, g + h) - resposta(c, max(g - h, 0))) / (g + h - max(g - h, 0)) if g + h > 0 else 0

    k1, k2, k3 = st.columns(3)
    k1.metric(T(f"{KPIS[ns]['rotulo']}/semana, mantendo a proporção atual", f"{KPIS[ns]['rotulo']}/week, keeping the current mix"), num(total(prop)))
    k2.metric(T(f"{KPIS[ns]['rotulo']}/semana, alocação sugerida", f"{KPIS[ns]['rotulo']}/week, suggested allocation"), num(total(otimo)),
              delta=num(total(otimo) - total(prop), 0, sign=True))
    k3.metric(T("Sugerida vs. proporcional, na verdade", "Suggested vs. proportional, in the ground truth"),
              num(total(otimo, 'verdade') - total(prop, 'verdade'), 0, sign=True),
              help=T("Mesma comparação, mas calculada nas curvas VERDADEIRAS do gerador. Mostra se a sugestão do modelo realmente ajuda.",
                     "Same comparison, but computed on the generator's TRUE curves. It shows whether the model's suggestion really helps."))

    dif_v = total(otimo, "verdade") - total(prop, "verdade")
    if dif_v < 0:
        st.error(T(f"**Nas curvas verdadeiras, a sugestão rende {num(abs(dif_v))} {unid}/semana a MENOS que manter a proporção atual.** "
                   "Isso acontece porque as curvas estimadas divergem das verdadeiras em alguns canais (por exemplo, o Meta superestimado) e a otimização confia nelas. "
                   "É exatamente o risco de otimizar em cima de uma curva incerta.",
                   f"**On the true curves, the suggestion yields {num(abs(dif_v))} {unid}/week LESS than keeping the current mix.** "
                   "This happens because the estimated curves diverge from the true ones in some channels (for example, the overestimated Meta) and the optimization trusts them. "
                   "This is exactly the risk of optimizing on top of an uncertain curve."))
    else:
        st.success(T(f"Nas curvas verdadeiras, a sugestão também rende {num(dif_v)} {unid}/semana a mais que manter a proporção atual.",
                     f"On the true curves, the suggestion also yields {num(dif_v)} {unid}/week more than keeping the current mix."))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[prop[c] for c in CANAIS], name=T("proporção atual", "current mix"), marker_color=CINZA))
    fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[otimo[c] for c in CANAIS], name=T("sugerida", "suggested"), marker_color=AZUL))
    fig.update_layout(title=T("Investimento semanal por canal (R$ mil)", "Weekly spend per channel (R$ k)"), barmode="group", legend=dict(orientation="h", y=-0.2))
    mostrar(fig, 340)
    _k_prop, _k_sug, _k_pct = T("Proporção atual (R$ mil/sem)", "Current mix (R$ k/wk)"), T("Sugerida (R$ mil/sem)", "Suggested (R$ k/wk)"), T("% da verba (sugerida)", "% of budget (suggested)")
    _k_x, _k_kpi, _k_marg = T("x o investimento atual", "x current spend"), T(f"{unid}/sem (sugerida)", f"{unid}/wk (suggested)"), T("Retorno marginal (por R$ 1 mil)", "Marginal return (per R$ 1k)")
    tab = pd.DataFrame({
        T("Canal", "Channel"): [NOMES[c] for c in CANAIS],
        _k_prop: [prop[c] for c in CANAIS],
        _k_sug: [otimo[c] for c in CANAIS],
        _k_pct: [otimo[c] / X * 100 for c in CANAIS],
        _k_x: [otimo[c] / atual_sem[c] for c in CANAIS],
        _k_kpi: [resposta(c, otimo[c]) for c in CANAIS],
        _k_marg: [marg(c, otimo[c]) for c in CANAIS]})
    st.dataframe(tab.style.format({_k_prop: "{:.1f}", _k_sug: "{:.1f}", _k_pct: "{:.0f}%",
                                   _k_x: "{:.2f}x", _k_kpi: "{:,.0f}", _k_marg: "{:.2f}"}), hide_index=True)
    fora = [NOMES[c] for c in CANAIS if otimo[c] > 2 * atual_sem[c]]
    if fora: st.warning(T(f"Acima de 2x o investimento atual (fora da faixa que o modelo observou): {', '.join(fora)}. Trate como hipótese a testar.",
                          f"Above 2x current spend (outside the range the model observed): {', '.join(fora)}. Treat as a hypothesis to test."))
    st.markdown(T("Repare que, na sugestão, o **retorno marginal fica parecido entre os canais** que recebem verba: é o sinal de que não vale mover mais nada.",
                  "Note that, in the suggestion, the **marginal return ends up similar across the channels** that receive budget: it is the sign that there is nothing more worth moving."))
    st.warning(T("Use como **direção**, não como ordem. As curvas têm incerteza grande (veja os ICs) e a otimização não a leva em conta. "
                 "Se o modelo superestima um canal (como o Meta neste dado), a sugestão empurra verba para ele. Valide com um teste de incrementalidade antes de mexer no orçamento de verdade.",
                 "Use it as a **direction**, not as an order. The curves carry large uncertainty (see the CIs) and the optimization does not account for it. "
                 "If the model overestimates a channel (like Meta in this data), the suggestion pushes budget to it. Validate with an incrementality test before touching the real budget."))

    with st.expander(T("2. Testar sua própria alocação (sliders por canal)", "2. Test your own allocation (sliders per channel)")):
        cols = st.columns(3); mult = {}
        for i, c in enumerate(CANAIS):
            with cols[i % 3]:
                mult[c] = st.slider(T(f"{NOMES[c]}: {num(atual_sem[c],1)} mil/sem", f"{NOMES[c]}: {num(atual_sem[c],1)}k/wk"),
                                    0, 300, 100, 5, format="%d%%", key=f"sl_{ns}_{c}") / 100
        gs = {c: atual_sem[c] * mult[c] for c in CANAIS}
        u1, u2, u3 = st.columns(3)
        u1.metric(T(f"{KPIS[ns]['rotulo']}/semana", f"{KPIS[ns]['rotulo']}/week"), num(total(gs)), delta=num(total(gs) - total(atual_sem), 0, sign=True))
        u2.metric(T("Investimento/semana (R$ mil)", "Spend/week (R$ k)"), num(sum(gs.values()), 1))
        u3.metric(T("Retorno médio", "Average return"), num(total(gs) / max(sum(gs.values()), 1e-9), 2))

# ================================================================== QUANDO INVESTIR
with abas[8]:
    st.markdown(T(
        "Duas perguntas do projeto original, respondidas com o modelo ajustado: **(1)** vale mais investir uma \"bomba\" de uma vez ou aos poucos ao longo das semanas? "
        "**(2)** é melhor investir tudo em 1 mês ou diluir em outros meses? Cada uma no **geral** (todas as campanhas) e **por campanha**.",
        "Two questions from the original project, answered with the tuned model: **(1)** is it worth more to invest a one-shot burst, or gradually over the weeks? "
        "**(2)** is it better to invest everything in 1 month or to spread it over other months? Each one **overall** (all campaigns) and **per campaign**."))
    with st.expander(T("Como a simulação funciona", "How the simulation works")):
        st.markdown(T(
            "Fixo uma **verba** (a média semanal normal de cada canal × o número de semanas do período) e comparo **cronogramas** diferentes para gastar exatamente "
            "essa verba: diluída, em blocos, em pulsos, ou toda de uma vez. Para cada cronograma, o Meridian calcula o KPI incremental usando as "
            "**2.000 amostras da posterior**, então cada resultado vem com intervalo. O cenário **diluído** é o 100 de referência. "
            "Como o dado é sintético, calculo também o resultado **verdadeiro** de cada cronograma com a fórmula do gerador, para conferir o ranking.\n\n"
            "**Por que diluir tende a ganhar:** a saturação (curva de Hill) faz cada real a mais render menos, então concentrar verba empurra o canal para o platô. "
            "O adstock espalha parte do efeito no tempo, mas não compensa isso.\n\n"
            "**Limites:** o modelo assume que o efeito de uma impressão é o mesmo em qualquer época do ano e que o CPM não muda (na Black Friday ele sobe). "
            "Ou seja, **não** avalia se vale concentrar verba em uma época de demanda alta. E cenários com pico muito acima do máximo semanal já observado "
            "são **extrapolação** (marcados abaixo).",
            "I fix a **budget** (each channel's normal weekly average × the number of weeks in the period) and compare different **schedules** for spending exactly "
            "that budget: spread evenly, in blocks, in pulses, or all at once. For each schedule, Meridian computes the incremental KPI using the "
            "**2,000 posterior samples**, so every result comes with an interval. The **spread-evenly** scenario is the reference 100. "
            "Since the data is synthetic, I also compute the **true** result of each schedule with the generator's formula, to check the ranking.\n\n"
            "**Why spreading tends to win:** saturation (the Hill curve) makes each extra real yield less, so concentrating budget pushes the channel toward the plateau. "
            "Adstock spreads part of the effect over time, but does not make up for it.\n\n"
            "**Limits:** the model assumes the effect of an impression is the same at any time of year and that the CPM does not change (on Black Friday it rises). "
            "In other words, it does **not** assess whether it is worth concentrating budget in a high-demand period. And scenarios with a peak far above the maximum weekly value already observed "
            "are **extrapolation** (flagged below)."))
    nw = st.radio("KPI", ["contas", "receita"], format_func=KPI_FMT, horizontal=True, key="kw")
    unw = KPIS[nw]["unidade"]
    cr = ler(f"cronogramas_{nw}.csv")
    _perg = {"q1": T("1. Bomba ou diluído? (verba de 1 trimestre, 13 semanas)", "1. One-shot burst or spread evenly? (1-quarter budget, 13 weeks)"),
             "q2": T("2. Tudo em 1 mês ou diluído? (verba de 1 ano, 52 semanas)", "2. All in 1 month or spread evenly? (1-year budget, 52 weeks)")}
    perg = st.radio(T("Pergunta", "Question"), ["q1", "q2"], format_func=_perg.get, key="qp")
    HZ = 13 if perg == "q1" else 52
    _visao = lambda k: T("Geral (todas as campanhas)", "Overall (all campaigns)") if k == "TOTAL" else NOMES[k]
    chave_canal = st.radio(T("Visão", "View"), ["TOTAL"] + CANAIS, format_func=_visao, horizontal=True, key="qv")
    sub = cr[cr["horizonte"] == HZ]
    ordem = list(dict.fromkeys(sub["cenario"]))
    base = sub[(sub["canal"] == chave_canal)].set_index("cenario")
    raz = sub[sub["canal"] == ("RAZAO_TOTAL" if chave_canal == "TOTAL" else f"RAZAO_{chave_canal}")].set_index("cenario")
    dil = ordem[0]
    idx = raz.loc[ordem, "est"] * 100
    lo = raz.loc[ordem, "lo"] * 100; hi = raz.loc[ordem, "hi"] * 100
    idx_v = base.loc[ordem, "verdade"] / base.loc[dil, "verdade"] * 100
    pico = base.loc[ordem, "pico_vs_historico"]
    extrap = pico > 1.5
    cores = [AZUL_CLARO if e else AZUL for e in extrap]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[cen(o) for o in ordem], y=idx, marker_color=cores, name=T("estimado (IC 90%)", "estimated (90% CI)"),
                         error_y=dict(type="data", symmetric=False, array=(hi - idx).values, arrayminus=(idx - lo).values),
                         text=[f"{v:.0f}" for v in idx], textposition="inside", insidetextanchor="start", textfont=dict(color="white")))
    fig.add_trace(go.Scatter(x=[cen(o) for o in ordem], y=idx_v, mode="markers", marker=dict(color=LARANJA, size=12, symbol="diamond"), name=T("verdade", "ground truth")))
    fig.add_hline(y=100, line_dash="dot", line_color=CINZA)
    _visao_txt = T("todas as campanhas", "all campaigns") if chave_canal == "TOTAL" else T(NOMES[chave_canal].lower(), NOMES[chave_canal])
    fig.update_layout(title=T(f"Resultado incremental por cronograma, {_visao_txt} (diluído = 100)", f"Incremental result per schedule, {_visao_txt} (spread evenly = 100)"),
                      yaxis_title=T("índice (diluído = 100)", "index (spread evenly = 100)"), legend=dict(orientation="h", y=-0.25), yaxis_range=[0, max(130, float(hi.max()) * 1.1)])
    mostrar(fig, 420)
    st.caption(T("Barras em azul claro = cronograma com pico de investimento semanal acima de 1,5x o máximo histórico do canal (extrapolação, baixa confiança).",
                 "Light-blue bars = schedule with a weekly spend peak above 1.5x the channel's historical maximum (extrapolation, low confidence)."))

    melhor = idx.idxmax(); pior = idx.idxmin()
    st.markdown(T(
        f"> **Leitura:** para {('as campanhas juntas' if chave_canal == 'TOTAL' else NOMES[chave_canal])}, o melhor cronograma estimado é "
        f"**{melhor}** e o pior é **{pior}**, que rende **{idx[pior]:.0f}%** do diluído ({num(100 - idx[pior], 0)} p.p. a menos, IC 90% de {lo[pior]:.0f}% a {hi[pior]:.0f}%). "
        f"Na verdade do gerador, o pior rende {idx_v[pior]:.0f}% do diluído.",
        f"> **Reading:** for {('the campaigns combined' if chave_canal == 'TOTAL' else NOMES[chave_canal])}, the best estimated schedule is "
        f"**{cen(melhor)}** and the worst is **{cen(pior)}**, which yields **{idx[pior]:.0f}%** of the spread-evenly scenario ({num(100 - idx[pior], 0)} p.p. less, 90% CI from {lo[pior]:.0f}% to {hi[pior]:.0f}%). "
        f"In the generator's ground truth, the worst yields {idx_v[pior]:.0f}% of the spread-evenly scenario."))
    tab = pd.DataFrame({
        T("Cronograma", "Schedule"): [cen(o) for o in ordem],
        T(f"{unw} incremental (IC 90%)", f"Incremental {unw} (90% CI)"):
            [f"{num(base.loc[o,'est'])} ({num(base.loc[o,'lo'])} {T('a', 'to')} {num(base.loc[o,'hi'])})" for o in ordem],
        T("Índice (diluído = 100)", "Index (spread evenly = 100)"): [f"{idx[o]:.0f}" for o in ordem],
        T("Índice verdadeiro", "True index"): [f"{idx_v[o]:.0f}" for o in ordem],
        T("Pico semanal vs. máximo histórico", "Weekly peak vs. historical maximum"): [f"{pico[o]:.1f}x" for o in ordem],
        T("Confiança", "Confidence"): [T("extrapolação", "extrapolation") if extrap[o] else T("dentro do observado", "within the observed range") for o in ordem]})
    st.dataframe(tab, hide_index=True)

    if chave_canal == "TOTAL":
        st.markdown(T("#### Comparação entre campanhas", "#### Comparison across campaigns"))
        st.caption(T("O mesmo cronograma \"tudo em 1 mês\" (ou bomba) penaliza mais quem satura mais rápido: quanto menor o índice, mais o canal perde ao concentrar a verba.",
                     "The same \"all in 1 month\" (or burst) schedule penalizes more the channels that saturate faster: the lower the index, the more the channel loses by concentrating the budget."))
        pior_cen = [o for o in ordem if o.startswith("Bomba")][0] if HZ == 13 else [o for o in ordem if o.startswith("1 mês seguido")][0]   # chaves originais em PT
        rows = []
        for c in CANAIS:
            rr = sub[(sub["canal"] == f"RAZAO_{c}") & (sub["cenario"] == pior_cen)].iloc[0]
            rows.append((NOMES[c], rr["est"] * 100, rr["lo"] * 100, rr["hi"] * 100))
        rows.sort(key=lambda t: t[1])
        fig = go.Figure(go.Bar(x=[r[1] for r in rows], y=[r[0] for r in rows], orientation="h", marker_color=AZUL,
                               error_x=dict(type="data", symmetric=False, array=[r[3] - r[1] for r in rows], arrayminus=[r[1] - r[2] for r in rows]),
                               text=[f"{r[1]:.0f}" for r in rows], textposition="inside", insidetextanchor="start", textfont=dict(color="white")))
        fig.update_layout(title=T(f"Índice do cronograma \"{cen(pior_cen)}\" por campanha (diluído = 100)", f"Index of the \"{cen(pior_cen)}\" schedule per campaign (spread evenly = 100)"),
                          xaxis_range=[0, 110])
        mostrar(fig, 340)


# ================================================================== PARÂMETROS
with abas[9]:
    st.markdown(T(
        "Aqui estão **todos os números que definem os modelos**: os que **eu escolhi** (configuração e priors) e os que o modelo **aprendeu dos dados** "
        "(decay, saturação, ROI e efeito dos controles), cada um com o **gabarito** do gerador ao lado quando existe. "
        f"Documentação: {link('parâmetros do ModelSpec', DOCS['spec'])} · {link('priors padrão', DOCS['priors_padrao'])} · {link('adstock e saturação', DOCS['adstock'])}.",
        "Here are **all the numbers that define the models**: the ones **I chose** (configuration and priors) and the ones the model **learned from the data** "
        "(decay, saturation, ROI and control effects), each with the generator's **answer key** alongside when one exists. "
        f"Documentation: {link('ModelSpec parameters', DOCS['spec'])} · {link('default priors', DOCS['priors_padrao'])} · {link('adstock and saturation', DOCS['adstock'])}."))

    st.markdown(T("### 1. Configuração escolhida (não vem dos dados)", "### 1. Chosen configuration (does not come from the data)"))
    _igual = T("igual", "same")
    cfg = pd.DataFrame([
        [T("Semanas de dados / teste (holdout)", "Weeks of data / test (holdout)"), f"{M['semanas']} / {M['semanas_teste']}", _igual],
        [T("max_lag (semanas de memória do adstock)", "max_lag (weeks of adstock memory)"), "8", _igual],
        [T("MCMC: cadeias × (adaptação + burn-in + amostras)", "MCMC: chains × (adaptation + burn-in + samples)"), f"{M['chains']} × ({M['adapt']} + {M['burnin']} + {M['keep']})", _igual],
        [T("Controles", "Controls"), T("4: desemprego, IPCA, feriados, Black Friday", "4: unemployment, IPCA, holidays, Black Friday"),
         T("10: os 4 + seno/cosseno anual e semestral + novembro + dezembro", "10: the 4 + annual and semiannual sine/cosine + November + December")],
        [T("Promoção", "Promotion"), T("desconto médio como tratamento não-mídia", "average discount as a non-media treatment"), _igual],
        [T("knots (flexibilidade da tendência no tempo)", "knots (flexibility of the trend over time)"), T("1 por semana (padrão)", "1 per week (default)"), T("2 (tendência suave)", "2 (smooth trend)")],
        [T("Prior de ROI (novas contas)", "ROI prior (new accounts)"), T("LogNormal(0,2; 0,9) padrão", "LogNormal(0.2, 0.9) default"),
         T("LogNormal com 95% em [1; 25] contas por R$ mil", "LogNormal with 95% in [1, 25] accounts per R$ k")],
        [T("Prior de ROI (receita)", "ROI prior (revenue)"), T("LogNormal(0,2; 0,9) padrão", "LogNormal(0.2, 0.9) default"),
         T("LogNormal com 95% em [0,3; 8] R$ por R$ 1", "LogNormal with 95% in [0.3, 8] R$ per R$ 1")],
        [T("Prior do decay (alpha)", "Decay prior (alpha)"), T("Uniform(0, 1)", "Uniform(0, 1)"), _igual],
        [T("Prior do ponto de saturação (ec)", "Saturation point prior (ec)"), T("TruncNormal(0,8; 0,8; 0,1; 10)", "TruncNormal(0.8, 0.8, 0.1, 10)"), _igual],
        [T("Prior da inclinação do Hill (slope)", "Hill slope prior (slope)"), T("fixa em 1", "fixed at 1"), T("igual (fixa em 1)", "same (fixed at 1)")]],
        columns=[T("Parâmetro", "Parameter"), T("Modelo ingênuo", "Naive model"), T("Modelo ajustado", "Tuned model")])
    st.table(cfg)
    st.caption(T("A inclinação fica fixa em 1 (padrão do Meridian), mas o gerador usa valores entre 1,1 e 2,0: é uma simplificação que o modelo faz e que aparece nas curvas.",
                 "The slope is fixed at 1 (the Meridian default), but the generator uses values between 1.1 and 2.0: it is a simplification the model makes and it shows up in the curves."))

    st.markdown(T("### 2. O que o modelo aprendeu, por canal", "### 2. What the model learned, per channel"))
    p1, p2 = st.columns(2)
    np_ = p1.radio("KPI", ["contas", "receita"], format_func=KPI_FMT, horizontal=True, key="pm_kpi")
    _mod_rot = {"ajustado": T("Ajustado", "Tuned"), "ingenuo": T("Ingênuo", "Naive")}
    mod_p = p2.radio(T("Modelo", "Model"), ["ajustado", "ingenuo"], format_func=_mod_rot.get, horizontal=True, key="pm_mod")
    arq = f"parametros_{'ingenuo_' if mod_p == 'ingenuo' else ''}{np_}.csv"
    if not os.path.exists(os.path.join(RES, arq)):
        st.warning(T("Parâmetros ainda não exportados: rode `exportar_resultados.py`.", "Parameters not exported yet: run `exportar_resultados.py`."))
    else:
        P = ler(arq)
        DESC = {"decay": (T("Decay do adstock (alpha)", "Adstock decay (alpha)"),
                          T("Fração do efeito que sobra de uma semana para a seguinte. 0,5 = metade. Perto de 0 o efeito é imediato; perto de 1, dura semanas.",
                            "Fraction of the effect that carries over from one week to the next. 0.5 = half. Near 0 the effect is immediate; near 1 it lasts weeks.")),
                "ec": (T("Ponto de meia-saturação (ec)", "Half-saturation point (ec)"),
                       T("Nível de mídia (relativo à mediana) em que o canal chega à metade do efeito máximo. Menor = satura mais cedo. No gerador, relativo à média em vez da mediana, então compare a ordem de grandeza.",
                         "Media level (relative to the median) at which the channel reaches half of its maximum effect. Lower = saturates earlier. In the generator it is relative to the mean instead of the median, so compare the order of magnitude.")),
                "slope": (T("Inclinação do Hill (slope)", "Hill slope (slope)"),
                          T("Quão brusca é a curva. Perto de 1 é uma curva suave; valores altos formam um S com limiar.",
                            "How abrupt the curve is. Near 1 it is a smooth curve; high values form an S with a threshold.")),
                "roi": ("ROI", T("Retorno médio por R$ 1 mil investido, no período todo.", "Average return per R$ 1k invested, over the whole period.")),
                "beta": (T("Coeficiente da mídia (beta)", "Media coefficient (beta)"),
                         T("Efeito máximo do canal na escala interna do modelo (KPI padronizado). Não tem gabarito comparável direto; use para ver o tamanho relativo entre canais.",
                           "Maximum effect of the channel on the model's internal scale (standardized KPI). It has no directly comparable answer key; use it to see the relative size across channels."))}
        u_roi = T("contas por R$ mil", "accounts per R$ k") if np_ == "contas" else T("R$ por R$ 1", "R$ per R$ 1")
        for par in ["roi", "decay", "ec", "slope", "beta"]:
            d = P[P["parametro"] == par].set_index("canal").reindex(CANAIS)
            if d.empty: continue
            tit, expl = DESC[par]
            st.markdown(f"**{tit}**" + (f" ({u_roi})" if par == "roi" else ""))
            st.caption(expl)
            tem_v = d["verdade"].notna().any()
            fig = go.Figure()
            if tem_v:
                fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=d["verdade"], name=T("verdade", "ground truth"), marker_color=LARANJA))
            fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=d["media"], name=T("estimado (IC 90%)", "estimated (90% CI)"), marker_color=AZUL,
                                 error_y=dict(type="data", symmetric=False, array=(d["hi"] - d["media"]).values, arrayminus=(d["media"] - d["lo"]).values)))
            fig.update_layout(barmode="group", legend=dict(orientation="h", y=-0.25))
            mostrar(fig, 300)
        tb = pd.DataFrame({T("Canal", "Channel"): [NOMES[c] for c in CANAIS]})
        for par, rot in [("roi", "ROI"), ("decay", "Decay"), ("ec", "ec"), ("slope", "Slope")]:
            d = P[P["parametro"] == par].set_index("canal").reindex(CANAIS)
            if d.empty: continue
            tb[T(f"{rot} estimado", f"Estimated {rot}")] = [f"{num(a,2,grp=False)} ({num(b,2,grp=False)} {T('a', 'to')} {num(c,2,grp=False)})" for a, b, c in zip(d["media"], d["lo"], d["hi"])]
            if d["verdade"].notna().any(): tb[T(f"{rot} verdade", f"Ground truth {rot}")] = [num(v, 2, grp=False) for v in d["verdade"]]
        st.markdown(T("**Tabela resumo** (média e IC 90%)", "**Summary table** (mean and 90% CI)"))
        st.table(tb)
        if mod_p == "ingenuo":
            st.info(T("No modelo ingênuo a inclinação é fixa em 1 e o ROI usa o prior padrão, por isso os intervalos são largos e o ROI de alguns canais foge do gabarito.",
                      "In the naive model the slope is fixed at 1 and the ROI uses the default prior, which is why the intervals are wide and some channels' ROI strays from the answer key."))

    st.markdown(T("### 3. Controles e promoção: quanto cada um vale", "### 3. Controls and promotion: what each one is worth"))
    st.caption(T("Efeito de +1 unidade do controle no KPI da semana (média e IC 90%). Os controles foram centrados, então seus efeitos são desvios em torno do nível médio do baseline.",
                 "Effect of +1 unit of the control on the week's KPI (mean and 90% CI). The controls were centered, so their effects are deviations around the baseline's average level."))
    c1, c2 = st.columns(2)
    for col_, nm in [(c1, "contas"), (c2, "receita")]:
        with col_:
            ct = ler(f"controles_{nm}.csv")
            t = pd.DataFrame({T("Controle", "Control"): [NOME_CONTROLE.get(c, c) for c in ct["controle"]],
                              T("Efeito por unidade (IC 90%)", "Effect per unit (90% CI)"): [f"{num(a,1)} ({num(b,1)} {T('a', 'to')} {num(c,1)})"
                                                                             for a, b, c in zip(ct["efeito_un"], ct["efeito_un_lo"], ct["efeito_un_hi"])],
                              T("Verdade", "Ground truth"): ["" if pd.isna(v) else num(v, 0) for v in ct["efeito_un_verdade"]]})
            st.markdown(f"**{KPIS[nm]['rotulo']}**"); st.table(t)
    st.caption(T("Black Friday são só 3 semanas e ficou confundida com a mídia que sobe junto: o efeito estimado pode sair com sinal errado (aconteceu na receita). Sazonalidade (seno/cosseno/meses) não tem gabarito por unidade: o gerador usa uma forma sazonal única, aproximada pelo modelo com esses termos.",
                 "Black Friday is only 3 weeks and got confounded with the media that rises alongside it: the estimated effect can come out with the wrong sign (this happened for revenue). Seasonality (sine/cosine/months) has no per-unit answer key: the generator uses a single seasonal shape, approximated by the model with these terms."))


# ================================================================== RECOMENDAÇÕES
with abas[10]:
    st.markdown(T(
        "Resumo acionável, **calculado a partir das simulações das outras abas** (cronogramas, curvas e retorno marginal). "
        "Cada recomendação traz o que o modelo estima **e** se a verdade do gerador confirma. Trate como hipóteses para validar com um teste, não como ordem.",
        "An actionable summary, **computed from the simulations in the other tabs** (schedules, curves and marginal return). "
        "Each recommendation shows what the model estimates **and** whether the generator's ground truth confirms it. Treat them as hypotheses to validate with a test, not as orders."))
    nr = st.radio("KPI", ["contas", "receita"], format_func=KPI_FMT, horizontal=True, key="rec_kpi")
    ur = KPIS[nr]["unidade"]
    cr = ler(f"cronogramas_{nr}.csv"); ret = ler(f"retorno_{nr}.csv").set_index("canal"); curv = ler(f"curvas_{nr}.csv")

    # ---------- 1. quando investir
    st.markdown(T("### 1. Quando investir: diluir ou concentrar?", "### 1. When to invest: spread or concentrate?"))
    resumo = []
    for HZ, rot in [(13, T("Verba de 1 trimestre (13 semanas)", "1-quarter budget (13 weeks)")), (52, T("Verba de 1 ano (52 semanas)", "1-year budget (52 weeks)"))]:
        sub = cr[cr["horizonte"] == HZ]; ordem = list(dict.fromkeys(sub["cenario"]))
        rz = sub[sub["canal"] == "RAZAO_TOTAL"].set_index("cenario"); bt = sub[sub["canal"] == "TOTAL"].set_index("cenario")
        idx = rz.loc[ordem, "est"] * 100; idv = bt.loc[ordem, "verdade"] / bt.loc[ordem[0], "verdade"] * 100
        ok = [o for o in ordem if bt.loc[o, "pico_vs_historico"] <= 1.5]
        melhor = max(ok, key=lambda o: idx[o]); pior = idx.idxmin()
        alt = [o for o in ok if o != ordem[0]]
        melhor_alt = max(alt, key=lambda o: idx[o]) if alt else None
        resumo.append((rot, melhor, idx[melhor], idv[melhor], pior, idx[pior], idv[pior], melhor_alt, sub, ordem))
    for rot, melhor, im, vm, pior, ip, vp, malt, sub, ordem in resumo:
        txt = T(f"**{rot}:** o melhor cronograma dentro do que o modelo já viu é **{melhor}** (índice {im:.0f}, verdade {vm:.0f}). "
                f"O pior é **{pior}**, que rende {ip:.0f}% do diluído (verdade: {vp:.0f}%).",
                f"**{rot}:** the best schedule within what the model has already seen is **{cen(melhor)}** (index {im:.0f}, ground truth {vm:.0f}). "
                f"The worst is **{cen(pior)}**, which yields {ip:.0f}% of the spread-evenly scenario (ground truth: {vp:.0f}%).")
        if malt and malt != melhor:
            txt += T(f" Se precisar concentrar, a alternativa menos custosa é **{malt}**.",
                     f" If you must concentrate, the least costly alternative is **{cen(malt)}**.")
        st.markdown("- " + txt)

    st.markdown(T("**Por campanha:** cronograma que menos perde ao concentrar (só dentro do observado) e quanto o pior custa",
                  "**Per campaign:** the schedule that loses least when concentrating (only within the observed range) and how much the worst one costs"))
    rows = []
    _sem_alt = T("sem alternativa dentro do observado", "no alternative within the observed range")
    for c in CANAIS:
        perdas = {}
        for HZ in (13, 52):
            sub = cr[cr["horizonte"] == HZ]; ordem = list(dict.fromkeys(sub["cenario"]))
            rc = sub[sub["canal"] == f"RAZAO_{c}"].set_index("cenario"); bc = sub[sub["canal"] == c].set_index("cenario")
            alt = [o for o in ordem[1:] if bc.loc[o, "pico_vs_historico"] <= 1.5]
            mel = max(alt, key=lambda o: rc.loc[o, "est"]) if alt else None
            pio = rc.loc[ordem[1:], "est"].idxmin()
            perdas[HZ] = (mel, rc.loc[mel, "est"] * 100 if mel else np.nan, pio, rc.loc[pio, "est"] * 100)
        rows.append({T("Campanha", "Campaign"): NOMES[c],
                     T("Trimestre: melhor alternativa", "Quarter: best alternative"): f"{cen(perdas[13][0])} ({perdas[13][1]:.0f})" if perdas[13][0] else _sem_alt,
                     T("Trimestre: pior", "Quarter: worst"): f"{cen(perdas[13][2])} ({perdas[13][3]:.0f})",
                     T("Ano: melhor alternativa", "Year: best alternative"): f"{cen(perdas[52][0])} ({perdas[52][1]:.0f})" if perdas[52][0] else _sem_alt,
                     T("Ano: pior", "Year: worst"): f"{cen(perdas[52][2])} ({perdas[52][3]:.0f})"})
    st.table(pd.DataFrame(rows))
    st.caption(T("Entre parênteses: índice em relação ao diluído (= 100). Detalhe, IC 90% e verdade na aba Quando investir.",
                 "In parentheses: index relative to the spread-evenly scenario (= 100). Details, 90% CI and ground truth in the When to invest tab."))

    # ---------- 2. quanto e onde
    st.markdown(T("### 2. Quanto e onde investir", "### 2. How much and where to invest"))
    Nn = len(df)
    G2 = {c: curv[curv["canal"] == c].sort_values("multiplicador") for c in CANAIS}
    atual = {c: float(G2[c].loc[(G2[c]["multiplicador"] - 1).abs().idxmin(), "gasto_mil"]) / Nn for c in CANAIS}
    def resp(c, g, col="est"):
        d = G2[c]; return float(np.interp(g * Nn, d["gasto_mil"], d[col])) / Nn
    def otim(X, col="est"):
        passo = X / 500; g = {c: 0.0 for c in CANAIS}
        for _ in range(500):
            mel, gm = None, -1
            for c in CANAIS:
                if g[c] + passo > 3 * atual[c]: continue
                gan = resp(c, g[c] + passo, col) - resp(c, g[c], col)
                if gan > gm: mel, gm = c, gan
            if mel is None: break
            g[mel] += passo
        return g
    tot_at = sum(atual.values())
    lin = []; dif_verdade = []
    _c_est, _c_ver = T("Estimado: sugerida vs. proporcional", "Estimated: suggested vs. proportional"), T("Verdade: sugerida vs. proporcional", "Ground truth: suggested vs. proportional")
    for pctv in (100, 130):
        X = tot_at * pctv / 100
        o = otim(X); pr = {c: atual[c] * pctv / 100 for c in CANAIS}
        te = lambda a, col: sum(resp(c, a[c], col) for c in CANAIS)
        dif_verdade.append(te(o, 'verdade') - te(pr, 'verdade'))
        lin.append({T("Verba semanal", "Weekly budget"): T(f"{pctv}% (R$ {num(X,1)} mil)", f"{pctv}% (R$ {num(X,1)}k)"),
                    _c_est: f"{num(te(o,'est') - te(pr,'est'), 0, sign=True)} {ur}{UN_SEM}",
                    _c_ver: f"{num(te(o,'verdade') - te(pr,'verdade'), 0, sign=True)} {ur}{UN_SEM}",
                    T("Sobe mais", "Rises most"): ", ".join(NOMES[c] for c in sorted(CANAIS, key=lambda c: o[c] / max(pr[c], 1e-9), reverse=True)[:2]),
                    T("Cai mais", "Falls most"): ", ".join(NOMES[c] for c in sorted(CANAIS, key=lambda c: o[c] / max(pr[c], 1e-9))[:2])})
    st.table(pd.DataFrame(lin))
    ok_alloc = all(round(v) >= 0 for v in dif_verdade)          # mesmo critério do valor exibido (arredondado a 0 casas)
    if ok_alloc:
        st.markdown(T("- A realocação sugerida também melhora o resultado nas curvas verdadeiras: pode ser testada.",
                      "- The suggested reallocation also improves the result on the true curves: it can be tested."))
    else:
        st.markdown(T("- **A realocação sugerida não é confirmada pela verdade.** Ela ganha nas curvas estimadas e perde (ou ganha bem menos) nas verdadeiras, porque as curvas de alguns canais estão superestimadas. Não mova o orçamento inteiro: teste mudanças **graduais** nos canais que o modelo mais mexe.",
                      "- **The suggested reallocation is not confirmed by the ground truth.** It wins on the estimated curves and loses (or gains much less) on the true ones, because some channels' curves are overestimated. Do not move the whole budget: test **gradual** changes in the channels the model moves the most."))

    st.markdown(T("**Espaço de crescimento por canal** (retorno marginal ÷ retorno médio no investimento atual)",
                  "**Room to grow per channel** (marginal return ÷ average return at current spend)"))
    _c_sit = T("Situação", "Status")
    esp = pd.DataFrame({T("Canal", "Channel"): [NOMES[c] for c in CANAIS],
                        T("ROI (IC 90%)", "ROI (90% CI)"): [f"{num(ret.loc[c,'roi'],1,grp=False)} ({num(ret.loc[c,'roi_lo'],1,grp=False)} {T('a', 'to')} {num(ret.loc[c,'roi_hi'],1,grp=False)})" for c in CANAIS],
                        "mROI/ROI": [ret.loc[c, "mroi"] / ret.loc[c, "roi"] for c in CANAIS],
                        _c_sit: [sat_rot(classe_saturacao(ret.loc[c, "mroi"] / ret.loc[c, "roi"])) for c in CANAIS]}).sort_values("mROI/ROI", ascending=False)
    esp["mROI/ROI"] = esp["mROI/ROI"].map(lambda v: num(v, 2, grp=False))
    st.table(esp)
    com_esp = [NOMES[c] for c in CANAIS if classe_saturacao(ret.loc[c, "mroi"] / ret.loc[c, "roi"]) == "com espaço"]
    sat = [NOMES[c] for c in CANAIS if classe_saturacao(ret.loc[c, "mroi"] / ret.loc[c, "roi"]) == "saturada"]
    st.markdown(T(f"- Com espaço para crescer: **{', '.join(com_esp) if com_esp else 'nenhum'}**. Já saturados: **{', '.join(sat) if sat else 'nenhum'}**.",
                  f"- Room to grow: **{', '.join(com_esp) if com_esp else 'none'}**. Already saturated: **{', '.join(sat) if sat else 'none'}**."))
    _exc_esp = [n for n in com_esp if n in [NOMES[c] for c in CANAIS if not (ret.loc[c, 'contrib_lo'] <= ret.loc[c, 'contrib_verdade'] <= ret.loc[c, 'contrib_hi'])]]
    if _exc_esp:
        st.markdown(T(f"- **Cuidado com {', '.join(_exc_esp)}:** aparece com espaço, mas é um canal que o modelo superestima (o IC não contém a verdade). Confirme com teste antes de aumentar.",
                      f"- **Be careful with {', '.join(_exc_esp)}:** it shows room to grow, but it is a channel the model overestimates (the CI does not contain the ground truth). Confirm with a test before increasing."))

    # ---------- 3. o que fazer
    st.markdown(T("### 3. Plano prático", "### 3. Practical plan"))
    excl = [NOMES[c] for c in CANAIS if not (ret.loc[c, "contrib_lo"] <= ret.loc[c, "contrib_verdade"] <= ret.loc[c, "contrib_hi"])]
    st.markdown(T(
        "1. **Cronograma:** por padrão, **dilua** a verba; concentrar só se houver motivo de negócio (lançamento, sazonalidade), e nunca acima do pico já observado.\n"
        "2. **Alocação:** mova verba **aos poucos** dos canais saturados para os que têm espaço e meça o resultado antes de continuar.\n"
        f"3. **Calibração:** {('os canais com IC que não contém a verdade (' + ', '.join(excl) + ') são os primeiros candidatos a um teste de incrementalidade (geo-lift), usado depois como prior de ROI.') if excl else 'nenhum canal com viés claro neste KPI; ainda assim vale um geo-lift nos maiores canais.'}\n"
        "4. **Limites:** o modelo não vê sazonalidade de resposta nem mudança de CPM; a Black Friday, por exemplo, pode render diferente do que a simulação sugere.",
        "1. **Schedule:** by default, **spread** the budget evenly; concentrate only if there is a business reason (launch, seasonality), and never above the peak already observed.\n"
        "2. **Allocation:** move budget **gradually** from saturated channels to the ones with room to grow, and measure the result before continuing.\n"
        f"3. **Calibration:** {('the channels whose CI does not contain the ground truth (' + ', '.join(excl) + ') are the first candidates for an incrementality test (geo-lift), later used as an ROI prior.') if excl else 'no channel with a clear bias for this KPI; even so, a geo-lift on the largest channels is worthwhile.'}\n"
        "4. **Limits:** the model does not see response seasonality or CPM changes; Black Friday, for example, may perform differently from what the simulation suggests."))
