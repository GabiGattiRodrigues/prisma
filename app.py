"""
App de portfólio: Marketing Mix Modeling com Meridian.
Lê resultados PRÉ-CALCULADOS (pasta resultados/, gerada por exportar_resultados.py).
Nenhum MCMC roda ao vivo aqui: o app é leve e abre em segundos.
"""
import json, os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ------------------------------------------------------------------ configuração
NOME_PROJETO = "Prisma"
SUBTITULO = "Quanto cada campanha de mídia realmente entrega?"
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
         "afiliados": "Afiliados", "display_programatico": "Display programático",
         "baseline": "Baseline", "desconto_medio_pct": "Desconto (promo)"}
KPIS = {"contas": dict(rotulo="Novas contas", unidade="contas", ing="ingenuo_contas", chave="novas_contas", volume=True),
        "receita": dict(rotulo="Receita", unidade="R$ mil", ing="ingenuo_receita", chave="receita_mil", volume=False)}

# "R$ ... R$" num mesmo texto vira fórmula LaTeX no markdown do Streamlit: escapo o cifrão nas chamadas de texto.
# O módulo `st` persiste entre execuções do script, então só aplico o patch uma vez (senão o escape se acumula).
if not getattr(st, "_mmm_patch", False):
    def _mk(orig):
        return lambda s, *a, **k: orig(s.replace("$", "\\$") if isinstance(s, str) else s, *a, **k)
    st.markdown, st.caption, st.info, st.warning = (_mk(st.markdown), _mk(st.caption), _mk(st.info), _mk(st.warning))
    st._mmm_patch = True

st.set_page_config(page_title=f"{NOME_PROJETO} · Marketing Mix Modeling", page_icon="📈", layout="wide")


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

def pct(v, d=1): return f"{v:.{d}f}%".replace(".", ",")
def num(v, d=0):
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def classe_saturacao(r):
    return "saturada" if r < 0.40 else ("atenção" if r <= 0.50 else "com espaço")   # regra prática do projeto

df = dados(); V = verdade(); M = meta()
N_SEM = len(df)

GRUPO_CONTROLE = {"desemprego_pct": "Economia", "ipca_12m_pct": "Economia",
                  "n_feriados_nacionais": "Calendário e eventos", "black_friday": "Calendário e eventos",
                  "sen_1": "Sazonalidade", "cos_1": "Sazonalidade", "sen_2": "Sazonalidade", "cos_2": "Sazonalidade",
                  "mes_nov": "Sazonalidade", "mes_dez": "Sazonalidade"}
NOME_CONTROLE = {"desemprego_pct": "Desemprego (%)", "ipca_12m_pct": "IPCA 12 meses (%)",
                 "n_feriados_nacionais": "Feriados nacionais na semana", "black_friday": "Semana da Black Friday",
                 "sen_1": "Sazonalidade: seno anual", "cos_1": "Sazonalidade: cosseno anual",
                 "sen_2": "Sazonalidade: seno semestral", "cos_2": "Sazonalidade: cosseno semestral",
                 "mes_nov": "Novembro (0/1)", "mes_dez": "Dezembro (0/1)", "desconto_medio_pct": "Desconto médio diário (%)"}

def link(rotulo, url): return f"[{rotulo}]({url})"


# ------------------------------------------------------------------ gráficos reutilizáveis
def fig_fit(nome, titulo, unidade):
    f = ler(f"fit_{nome}.csv"); f["semana"] = pd.to_datetime(f["semana"])
    f["ic_lo"] = f["ic_lo"].clip(lower=0)                        # KPI não é negativo: corta a banda em zero
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=f["semana"], y=f["ic_hi"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=f["semana"], y=f["ic_lo"], fill="tonexty", fillcolor="rgba(157,189,236,.5)",
                             line=dict(width=0), name="predito (IC 90%)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=f["semana"], y=f["predito"], name="predito", line=dict(color=AZUL, width=2)))
    fig.add_trace(go.Scatter(x=f["semana"], y=f["baseline"], name="baseline", line=dict(color=CINZA, dash="dash")))
    fig.add_trace(go.Scatter(x=f["semana"], y=f["real"], name="realizado", line=dict(color=LARANJA, width=1.6)))
    ini = f.loc[f["teste"], "semana"].min()
    fig.add_vrect(x0=ini, x1=f["semana"].max(), fillcolor="#e5e7eb", opacity=.5, line_width=0,
                  annotation_text="teste (holdout)", annotation_position="top left")
    fig.update_layout(title=titulo, yaxis_title=unidade, legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(rangemode="tozero")                          # eixo Y começa em zero
    return fig

def fig_contrib(nome, titulo):
    c = ler(f"contrib_{nome}.csv").sort_values("pct_of_contribution")
    cores = [CINZA if x == "baseline" else (LARANJA if x == "desconto_medio_pct" else AZUL) for x in c["channel"]]
    fig = go.Figure(go.Bar(x=c["pct_of_contribution"] * 100, y=[NOMES.get(x, x) for x in c["channel"]],
                           orientation="h", marker_color=cores,
                           text=[pct(v * 100) for v in c["pct_of_contribution"]], textposition="outside"))
    fig.update_layout(title=titulo, xaxis_title="% do KPI explicado", xaxis_range=[0, c["pct_of_contribution"].max() * 118])
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
    fig.update_layout(title=titulo + " (média móvel de 4 semanas)", yaxis_title=unidade, legend=dict(orientation="h", y=-0.15))
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
                                 line=dict(width=0), name="IC 90%", showlegend=(i == 0), hoverinfo="skip"), row=r, col=k)
        fig.add_trace(go.Scatter(x=d["gasto_mil"], y=d["est"], line=dict(color=AZUL, width=2.2), name="estimada",
                                 showlegend=(i == 0)), row=r, col=k)
        if com_verdade:
            fig.add_trace(go.Scatter(x=d["gasto_mil"], y=d["verdade"], line=dict(color=LARANJA, dash="dash", width=2),
                                     name="verdade", showlegend=(i == 0)), row=r, col=k)
        atual = d.loc[(d["multiplicador"] - 1).abs().idxmin()]
        fig.add_trace(go.Scatter(x=[atual["gasto_mil"]], y=[atual["est"]], mode="markers", marker=dict(color=CINZA, size=9),
                                 name="investimento atual", showlegend=(i == 0)), row=r, col=k)
        fig.update_xaxes(title_text="R$ mil" if r == 2 else None, row=r, col=k)
    fig.update_layout(legend=dict(orientation="h", y=-0.12), height=560)
    fig.update_yaxes(title_text=unidade, col=1)
    return fig

def tabela_retorno(nome, kpi):
    r = ler(f"retorno_{nome}.csv").set_index("canal")
    r["mroi/roi"] = r["mroi"] / r["roi"]
    out = pd.DataFrame({
        "Canal": [NOMES[c] for c in r.index],
        "Investimento (R$ mil)": [num(x) for x in r["gasto_mil"]],
        "ROI (IC 90%)": [f"{num(a,2)} ({num(b,2)} a {num(c,2)})" for a, b, c in zip(r["roi"], r["roi_lo"], r["roi_hi"])],
        "ROI marginal": [num(x, 2) for x in r["mroi"]],
        "mROI/ROI": [num(x, 2) for x in r["mroi/roi"]],
        "Saturação": [classe_saturacao(x) for x in r["mroi/roi"]],
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
    st.markdown(f"## {NOME_PROJETO}")
    st.caption("Marketing Mix Modeling com **Meridian** (Google)")
    st.markdown(
        "Reconstrução pública, em cenário de fintech e com **dados sintéticos**, de um projeto real que fiz no varejo. "
        "Como a verdade é conhecida, dá para conferir se o modelo a recuperou.")
    st.link_button("Abrir notebook no Colab (somente leitura)", COLAB_URL)
    st.link_button("Documentação do Meridian (Google)", DOCS["home"])
    st.caption("O link do Colab abre uma **cópia** do notebook direto do GitHub: quem abre pode rodar e editar a própria cópia, "
               "mas não altera o original.")
    st.divider()
    st.caption(f"{N_SEM} semanas · teste = últimas {M['semanas_teste']} · Meridian {M['meridian']} · "
               f"{M['chains']} cadeias × {M['keep']} amostras")

# ------------------------------------------------------------------ cabeçalho
st.title(f"{NOME_PROJETO}: {SUBTITULO}")
# Ordem de exibição: resultados e decisões primeiro, explicações (parâmetros, dados, conceitos) no final.
# O restante do código usa os índices originais, então mapeio pelo nome.
_ORIG = ["O projeto", "Conceitos", "Dados e controles", "Por que ajustar?", "Novas contas", "Receita",
         "Verdade vs. estimado", "Quanto e onde investir", "Quando investir", "Parâmetros", "Recomendações"]
_EXIB = ["O projeto", "Novas contas", "Receita", "Verdade vs. estimado", "Quanto e onde investir", "Quando investir",
         "Recomendações", "Parâmetros", "Dados e controles", "Por que ajustar?", "Conceitos"]
_t = dict(zip(_EXIB, st.tabs(_EXIB)))
abas = [_t[n] for n in _ORIG]

# ================================================================== O PROJETO
with abas[0]:
    st.markdown(
        "Um **MMM (Marketing Mix Modeling)** estima **quanto de cada resultado vem de cada canal de mídia**, separando o que a mídia "
        "causou do que aconteceria de qualquer jeito (sazonalidade, promoção, economia). O difícil é que o modelo pode "
        "**ajustar muito bem e ainda assim atribuir errado**. Foi esse o principal problema do projeto original, e é o que este app mostra.")
    st.markdown(
        "Aqui há **dois modelos independentes**, um para cada resultado que a mídia tenta explicar: **novas contas abertas** "
        "(KPI de volume, sem valor em R$) e **receita gerada** (KPI monetário). Para cada um, comparo uma primeira tentativa "
        "(**ingênuo**) com uma versão **ajustada**. A aba *Conceitos* explica cada termo e a aba *Por que ajustar?* detalha os parâmetros.")
    c_link1, c_link2, _ = st.columns([1.4, 1.4, 3])
    c_link1.link_button("Notebook no Colab (somente leitura)", COLAB_URL)
    c_link2.link_button("Documentação do Meridian", DOCS["home"])

    kpi_p = st.radio("Números do modelo de:", ["Novas contas", "Receita"], horizontal=True, key="kp")
    kk = "contas" if kpi_p == "Novas contas" else "receita"
    info = KPIS[kk]
    a_i, a_j = ler(f"acc_{info['ing']}.csv").iloc[0], ler(f"acc_{kk}.csv").iloc[0]
    e_i, mid_i = erro_atribuicao(info["ing"]); e_j, mid_j = erro_atribuicao(kk)
    mid_v = sum(V[info["chave"]]["canais"][c]["contribuicao_pct"] * 100 for c in CANAIS)
    st.markdown(f"##### KPI analisado: **{info['rotulo']}** ({'volume' if info['volume'] else 'monetário'})")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("MAPE no teste: ingênuo", pct(a_i["mape_teste"] * 100), help="Erro percentual médio nas 20 semanas que o modelo não viu.")
    k2.metric("Erro de atribuição: ingênuo", f"{num(e_i,1)} p.p.",
              help="Média, nos 6 canais, da diferença absoluta entre a contribuição estimada e a verdadeira (em pontos percentuais do KPI). "
                   "Só dá para medir porque o dado é sintético e a verdade é conhecida.")
    k3.metric("MAPE no teste: ajustado", pct(a_j["mape_teste"] * 100))
    k4.metric("Erro de atribuição: ajustado", f"{num(e_j,1)} p.p.", delta=f"{num(e_j - e_i,1)} p.p.", delta_color="inverse")
    tab_res = pd.DataFrame({
        "Modelo": ["Ingênuo", "Ajustado"],
        "MAPE treino": [pct(a_i["mape_treino"] * 100), pct(a_j["mape_treino"] * 100)],
        "MAPE teste": [pct(a_i["mape_teste"] * 100), pct(a_j["mape_teste"] * 100)],
        "R² teste": [num(a_i["r2_teste"], 2), num(a_j["r2_teste"], 2)],
        "Erro de atribuição (p.p.)": [num(e_i, 1), num(e_j, 1)],
        "Mídia paga total (% do KPI)": [pct(mid_i), pct(mid_j)],
        "Verdade: mídia total (% do KPI)": [pct(mid_v), pct(mid_v)]})
    st.dataframe(tab_res, hide_index=True)

    st.markdown("### O que este projeto tem de diferente de um MMM de livro")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            "**1. O KPI nem sempre é dinheiro.** No original o alvo eram *vidas trazidas para um programa de saúde*. "
            "Aqui rodo dois modelos: **novas contas** (volume) e **receita** (monetário). Os rankings de canais não são iguais.\n\n"
            "**2. Promoções em dias variados.** A promo pode cair na segunda, na quarta e na sexta. O modelo recebe o "
            "**desconto médio diário da semana** (dias sem promo contam zero).")
    with c2:
        st.markdown(
            "**3. Economia e calendário como controle:** desemprego, IPCA, feriados, Black Friday e sazonalidade do ano.\n\n"
            "**4. Curva de resposta com sentido de negócio.** MAPE baixo não basta: o modelo ingênuo de novas contas tinha ~"
            f"{pct(ler('acc_ingenuo_contas.csv').iloc[0]['mape_teste']*100,0)} de erro no teste e ainda atribuía "
            f"~{pct(ler('retorno_ingenuo_contas.csv').set_index('canal').loc['google_search','contrib_pct'],0)} das contas ao Google Search "
            f"(a verdade é ~{pct(V['novas_contas']['canais']['google_search']['contribuicao_pct']*100,0)}).")
    st.markdown("### Além de medir: o que fazer com o resultado")
    st.markdown(
        "- **Quanto e onde investir:** dada uma verba, como dividir entre as campanhas.\n"
        "- **Quando investir:** vale mais uma \"bomba\" de uma vez ou diluir ao longo das semanas? Tudo em 1 mês ou espalhado no ano? "
        "Respondido no geral e por campanha, e conferido contra a verdade.")

# ================================================================== CONCEITOS
with abas[1]:
    st.markdown(f"Cada termo usado no projeto, em linguagem simples. Para a referência oficial, veja a {link('documentação do Meridian', DOCS['home'])} "
                f"e o {link('glossário', DOCS['glossario'])}.")
    def conceito(titulo, corpo, aqui=None, doc=None):
        st.markdown(f"#### {titulo}")
        st.markdown(corpo)
        if aqui: st.markdown(f"**Neste projeto:** {aqui}")
        if doc: st.markdown(f"Saiba mais: {link('documentação do Meridian', doc)}")
        st.divider()

    conceito("MMM (Marketing Mix Modeling)",
             "Modelo estatístico que usa dados **agregados por semana** (quanto se investiu em cada canal e quanto de resultado apareceu) para "
             "estimar o quanto cada canal contribuiu. Não precisa de dado individual de usuário, então funciona mesmo sem cookies. "
             "A ideia central: resultado = o que teria acontecido sem mídia (**baseline**) + efeito de cada canal + efeito de promoção e fatores externos.",
             "6 canais, 156 semanas, dois KPIs (novas contas e receita).", DOCS["intro"])
    conceito("KPI e tipo de KPI",
             "**KPI** é o resultado que o modelo tenta explicar. Se o KPI é **monetário** (receita), o ROI vem em R$ por R$ investido. Se é de **volume** "
             "(contas, vidas, pedidos) e não se sabe o valor de cada unidade, o Meridian trata como KPI \"sem receita\": o retorno vem em unidades do KPI por real investido, "
             "e o prior padrão passa a ser sobre a *contribuição total da mídia*.",
             "**Novas contas** = KPI de volume (retorno em contas por R$ 1 mil; o inverso é o CAC). **Receita** = KPI monetário (R$ por R$ 1).",
             DOCS["kpi_sem_receita"])
    conceito("Mídia: impressões vs. investimento",
             "O Meridian modela o efeito da **exposição** (impressões), não do dinheiro. O **investimento** entra depois, só para transformar o efeito em ROI. "
             "Isso importa porque o mesmo real compra mais ou menos impressões conforme o CPM.",
             "Cada canal tem uma coluna de impressões (entra no modelo) e uma de gasto em R$ mil (usada no ROI).")

    st.markdown("#### Adstock (efeito acumulado e defasado)")
    st.markdown(
        "O anúncio de hoje continua fazendo efeito nas semanas seguintes, com força decrescente. No Meridian o adstock é **geométrico**: o peso da semana *l* depois "
        "é proporcional a `decay^l`. **Decay baixo** = efeito quase imediato (ex.: busca paga). **Decay alto** = efeito longo (ex.: vídeo, marca). "
        "`max_lag` é quantas semanas para trás o efeito ainda conta (aqui, 8).")
    dcy = st.slider("decay", 0.05, 0.95, 0.5, 0.05, key="cd")
    sem = np.arange(0, 9); w = dcy ** sem; w = w / w.sum()
    fig = go.Figure(go.Bar(x=sem, y=w, marker_color=AZUL, text=[pct(x * 100, 0) for x in w], textposition="outside"))
    fig.update_layout(title="De cada 100 de efeito de 1 semana de mídia, quanto aparece em cada semana", xaxis_title="semanas depois do anúncio",
                      yaxis_title="peso", yaxis_range=[0, 1.1])
    mostrar(fig, 300)
    st.markdown(f"**Neste projeto:** o decay de cada canal é estimado pelo modelo (veja as abas de resultado). Saiba mais: {link('adstock e saturação', DOCS['adstock'])}")
    st.divider()

    st.markdown("#### Saturação (curva de Hill)")
    st.markdown(
        "Dobrar o investimento **não** dobra o resultado: cada real adicional rende menos. A curva de Hill descreve isso com dois parâmetros: "
        "**`ec`** (o nível de mídia em que se chega à metade do efeito máximo) e **`slope`** (o quão \"em S\" é a curva). "
        "O retorno do *próximo* real é o **ROI marginal (mROI)**: quanto mais perto do platô, menor ele fica.")
    s1, s2 = st.columns(2)
    ec = s1.slider("ec", 0.3, 2.0, 1.0, 0.1, key="ce"); sl = s2.slider("slope", 0.5, 3.0, 1.0, 0.1, key="cs")
    x = np.linspace(0, 3, 150)
    fig = go.Figure(go.Scatter(x=x, y=x ** sl / (x ** sl + ec ** sl), line=dict(color=AZUL, width=3)))
    fig.update_layout(title="Efeito (0 a 1) em função do nível de mídia", xaxis_title="mídia (1 = média histórica do canal)", yaxis_title="fração do efeito máximo")
    mostrar(fig, 300)
    st.markdown("**Neste projeto:** o `ec` é estimado por canal. O `slope` fica **fixo em 1** (padrão do Meridian); os dados foram gerados com slopes entre 1,1 e 2,0, "
                "então há uma pequena diferença entre a curva verdadeira e a estimada.")
    st.divider()

    conceito("Baseline, tendência e sazonalidade",
             "**Baseline** é o que teria acontecido **sem** mídia paga e sem promoção: a base orgânica. Ele reúne o nível médio do KPI, a **tendência** "
             "(crescimento ao longo do tempo), a **sazonalidade** (ondas do ano, como fim de ano) e o efeito dos **controles**. "
             "A tendência é modelada por *knots* (nós): com `knots=2` ela é uma reta; com um nó por semana (padrão) ela vira uma curva totalmente livre, "
             "o que dá liberdade demais ao baseline.",
             "Ingênuo: 1 nó por semana. Ajustado: `knots=2` + sazonalidade explícita.", DOCS["baseline"])
    conceito("Controles e tratamento não-mídia",
             "**Controles** são variáveis que afetam o KPI mas **não são mídia** (economia, feriados, sazonalidade). Entram no baseline. "
             "**Tratamento não-mídia** é algo que a empresa controla e cuja contribuição queremos **medir separadamente** (aqui, o desconto).",
             "Controles e comportamento de cada um na aba *Dados e controles*.", DOCS["controles"])
    conceito("Sazonalidade por Fourier",
             "Um par seno/cosseno com período de 1 ano desenha uma onda suave; somar um segundo par com período de meio ano permite formatos mais realistas "
             "(dois picos, por exemplo). Cada termo sozinho não tem leitura; **juntos** desenham o formato sazonal.",
             "2 harmônicos anuais + marcadores de novembro e dezembro.")
    conceito("Contribuição e KPI incremental",
             "**KPI incremental** de um canal é o quanto do resultado só existiu por causa dele. **Contribuição** é isso como % do KPI total. "
             "Baseline + canais + promoção somam 100%.",
             "Gráficos de barras horizontais e de área ao longo do tempo nas abas de resultado.")
    conceito("ROI, ROI marginal, CAC e alerta de saturação",
             "**ROI** = resultado incremental por real investido (médio). **mROI** = o resultado do *próximo* real. **CAC** = custo por conta (1000 ÷ ROI, "
             "quando o ROI é em contas por R$ 1 mil). O alerta de saturação usa a razão **mROI/ROI**: abaixo de 0,40 = saturada; 0,40 a 0,50 = atenção; "
             "acima de 0,50 = com espaço. É uma **regra prática deste projeto**, não um teste estatístico.",
             "Tabelas de retorno por canal.", DOCS["curvas"])
    conceito("Bayesiano: prior, posterior e intervalo de credibilidade",
             "O Meridian é bayesiano. O **prior** é o que se acredita *antes* de ver os dados (por exemplo, \"o ROI de um canal está entre 1 e 25\"). "
             "A **posterior** é a crença *depois* de ver os dados. Em vez de um número único, ele devolve uma distribuição; o **IC 90%** (intervalo de credibilidade) "
             "é a faixa que contém o valor com 90% de probabilidade. Intervalo largo = pouca certeza.",
             "Os dois modelos diferem, entre outras coisas, nos priors de ROI.", DOCS["priors"])
    conceito("MCMC, cadeias e R-hat",
             "A posterior é calculada por simulação (**MCMC**): várias **cadeias** independentes exploram os valores possíveis dos parâmetros. Cada cadeia tem uma fase de "
             "**adaptação** e de **burn-in** (aquecimento, descartadas) e depois guarda **amostras**. O **R-hat** compara as cadeias: perto de 1 = todas concordam "
             "(convergiu); acima de ~1,1 = a estimativa não é confiável.",
             f"{M['chains']} cadeias, {M['adapt']} de adaptação, {M['burnin']} de burn-in e {M['keep']} amostras mantidas por cadeia.", DOCS["diagnosticos"])
    conceito("Treino, teste (holdout), MAPE e R²",
             "O modelo é ajustado numa parte dos dados (**treino**) e avaliado em semanas que **nunca viu** (**teste** ou holdout). "
             "**MAPE** é o erro percentual médio entre previsto e realizado (quanto menor, melhor). **R²** é a fração da variação do KPI explicada pelo modelo. "
             "Bom no treino e ruim no teste = overfitting.",
             f"Teste = últimas {M['semanas_teste']} semanas da série.")
    conceito("Multicolinearidade e VIF",
             "Quando dois fatores sobem e descem juntos (por exemplo, mídia que acompanha promoção), o modelo não consegue separar o efeito de cada um. "
             "O **VIF** mede isso: acima de ~5 é preocupante. É o maior risco de um MMM e a razão de calibrar com experimentos (geo-lift).",
             "O investimento sobe junto com desconto e Black Friday no dado (plantado de propósito).")
    conceito("Dado sintético e \"verdade conhecida\"",
             "Os dados foram **gerados por simulação** com valores conhecidos de adstock, saturação e força de cada canal. Assim dá para conferir se o modelo os recuperou, "
             "algo impossível com dado real, onde nunca se conhece a verdade.",
             "A verdade só é usada para conferir; o modelo nunca a vê.")
    st.markdown(f"Mais: {link('repositório do Meridian no GitHub', DOCS['github'])} · {link('especificação do modelo', DOCS['spec'])} · "
                f"{link('priors padrão', DOCS['priors_padrao'])} · {link('otimização de orçamento', DOCS['otimizacao'])}")

# ================================================================== DADOS E CONTROLES
with abas[2]:
    st.markdown("Dados **sintéticos** semanais, gerados com a verdade plantada (adstock, saturação e força de cada canal).")
    d = df.copy(); d["semana"] = pd.to_datetime(d["semana"])
    kpi_sel = st.radio("KPI", ["Novas contas", "Receita (R$ mil)"], horizontal=True)
    col = "novas_contas" if kpi_sel.startswith("Novas") else "receita_mil"
    fig = go.Figure(go.Scatter(x=d["semana"], y=d[col], line=dict(color=AZUL, width=2), name=kpi_sel))
    for s in d.loc[d["black_friday"] == 1, "semana"]:
        fig.add_vline(x=s, line_color=LARANJA, opacity=.6)
    fig.update_layout(title=f"{kpi_sel} por semana (linhas laranja = Black Friday)")
    fig.update_yaxes(rangemode="tozero")
    mostrar(fig, 340)
    a, b = st.columns(2)
    with a:
        fig = go.Figure()
        for c in CANAIS:
            fig.add_trace(go.Scatter(x=d["semana"], y=d[f"gasto_{c}"], name=NOMES[c], stackgroup="g",
                                     line=dict(width=.5, color="white"), fillcolor=CORES_CANAIS[c]))
        fig.update_layout(title="Investimento semanal por canal (R$ mil)", legend=dict(orientation="h", y=-0.2))
        mostrar(fig, 360)
    with b:
        fig = go.Figure(go.Bar(x=d["semana"], y=d["desconto_medio_pct"], marker_color=LARANJA))
        fig.update_layout(title="Desconto médio diário na semana (%)")
        mostrar(fig, 360)
        st.caption("Promo em dias diferentes vira uma média semanal: 2 dias a 20% dão 5,7%. Black Friday = 30% a semana toda.")

    st.markdown("### Controles usados nos modelos")
    st.markdown(
        "Controles são fatores que mexem no KPI mas **não são mídia**. O **ingênuo** usa só os 4 primeiros; o **ajustado** usa os 10. "
        "O desconto **não é controle**: é um *tratamento não-mídia*, medido em separado.")
    def stat(c, u=""):
        x = df[c]
        return f"mín {num(x.min(),1)}{u} · média {num(x.mean(),1)}{u} · máx {num(x.max(),1)}{u}"
    ctrl_tab = pd.DataFrame([
        ["Desemprego (%)", "Economia", "Ingênuo e ajustado", stat("desemprego_pct", "%"),
         "Cai devagar ao longo dos 3 anos (de ~8,8% para ~6,4%). Efeito esperado: **negativo** (mais desemprego, menos contas/receita). "
         "Cuidado: como cai de forma contínua, anda junto com a tendência e é difícil isolar seu efeito."],
        ["IPCA 12 meses (%)", "Economia", "Ingênuo e ajustado", stat("ipca_12m_pct", "%"),
         "Oscila entre ~3,8% e ~6,2%, sem tendência clara. Efeito esperado: **negativo** (menos poder de compra)."],
        ["Feriados nacionais na semana", "Calendário e eventos", "Ingênuo e ajustado", "0, 1 ou 2 por semana",
         "Semanas com feriado têm menos dias úteis. Efeito esperado: **negativo**."],
        ["Semana da Black Friday", "Calendário e eventos", "Ingênuo e ajustado", f"1 em {int(df['black_friday'].sum())} semanas, 0 no resto",
         "Pico de demanda. Efeito esperado: **positivo**, e forte. Acontece junto com desconto de 30% e mídia em alta."],
        ["Sazonalidade anual (seno e cosseno, 2 harmônicos)", "Sazonalidade", "Só ajustado", "4 termos, valores entre -1 e 1",
         "Ondas suaves com período de 1 ano e de meio ano. Juntas desenham o formato sazonal do ano; sozinhas não têm leitura."],
        ["Novembro e dezembro (0/1)", "Sazonalidade", "Só ajustado", "1 nos meses de novembro e dezembro",
         "Marcadores do fim de ano, que a onda suave não captura bem. Efeito esperado: **positivo**."],
        ["Desconto médio diário (%)", "Tratamento não-mídia", "Ingênuo e ajustado", stat("desconto_medio_pct", "%"),
         "Média dos 7 dias da semana, com dias sem promo valendo zero. Efeito esperado: **positivo**. Entra separado para medir sua contribuição."]],
        columns=["Variável", "Grupo", "Em qual modelo", "Como se comporta nos dados", "Leitura"])
    st.table(ctrl_tab.replace(r"\*\*", "", regex=True).set_index("Variável"))

    fig = make_subplots(rows=2, cols=2, subplot_titles=["Desemprego (%)", "IPCA 12 meses (%)", "Feriados nacionais na semana", "Black Friday (0/1)"], vertical_spacing=.18)
    fig.add_trace(go.Scatter(x=d["semana"], y=d["desemprego_pct"], line=dict(color=AZUL)), 1, 1)
    fig.add_trace(go.Scatter(x=d["semana"], y=d["ipca_12m_pct"], line=dict(color=AZUL)), 1, 2)
    fig.add_trace(go.Bar(x=d["semana"], y=d["n_feriados_nacionais"], marker_color=AZUL), 2, 1)
    fig.add_trace(go.Bar(x=d["semana"], y=d["black_friday"], marker_color=LARANJA), 2, 2)
    fig.update_layout(showlegend=False, height=460)
    mostrar(fig)

    st.markdown("#### Multicolinearidade: o risco nº 1 de um MMM")
    cols_x = [f"gasto_{c}" for c in CANAIS] + ["desconto_medio_pct", "black_friday", "n_feriados_nacionais", "desemprego_pct", "ipca_12m_pct"]
    corr = df[cols_x].corr()
    vif = pd.Series(np.diag(np.linalg.inv(corr.values)), index=cols_x)
    rot = [NOMES[c.replace("gasto_", "")] if c.startswith("gasto_") else NOME_CONTROLE.get(c, c) for c in cols_x]
    h1, h2 = st.columns([3, 2])
    with h1:
        fig = go.Figure(go.Heatmap(z=corr.values, x=rot, y=rot, zmin=-1, zmax=1, colorscale="Blues",
                                   text=np.round(corr.values, 1), texttemplate="%{text}"))
        fig.update_layout(title="Correlação entre investimento, promoção e controles", yaxis_autorange="reversed")
        mostrar(fig, 520)
    with h2:
        st.dataframe(pd.DataFrame({"Variável": rot, "VIF": vif.round(2).values}), hide_index=True, height=420)
        st.caption("VIF acima de ~5 é preocupante. O investimento sobe junto com desconto e Black Friday (plantado de propósito): "
                   "parte do que a mídia leva de crédito pode ser efeito da promoção. Por isso a promo entra no modelo como variável própria.")

# ================================================================== POR QUE AJUSTAR?
with abas[3]:
    st.markdown("### Qual é o objetivo desta aba?")
    st.markdown(
        "É um **experimento de propósito**, que reproduz o problema do projeto original: um primeiro modelo com **MAPE bom** mas com "
        "**atribuição de canais errada**. Comparo duas configurações do **mesmo Meridian, dos mesmos dados e do mesmo período de teste**, "
        "mudando só as decisões de modelagem. Assim fica claro que o MAPE sozinho não valida um MMM, e o que cada decisão muda.")
    kv = st.radio("KPI", ["Novas contas", "Receita"], horizontal=True, key="kpi_ing")
    kk = "contas" if kv == "Novas contas" else "receita"; info = KPIS[kk]
    st.markdown("### Como cada modelo está configurado")
    prior_ing = ("Prior de **contribuição total da mídia**: média 40%, desvio 20% (padrão do Meridian para KPI sem receita)"
                 if info["volume"] else "Prior de **ROI** por canal: LogNormal(0,2; 0,9), ~95% entre 0,2 e 7,1 R$ por R$ 1 (padrão do Meridian)")
    prior_aj = ("Prior de **ROI** por canal: LogNormal com 95% entre 1 e 25 contas por R$ 1 mil"
                if info["volume"] else "Prior de **ROI** por canal: LogNormal com 95% entre 0,3 e 8 R$ por R$ 1")
    cfg = pd.DataFrame([
        ["Dados, canais e KPI", "Os mesmos", "Os mesmos", "Igual, para a comparação ser justa"],
        ["Controles", "4: desemprego, IPCA, feriados, Black Friday", "10: os 4 + seno/cosseno anual e semestral + novembro e dezembro",
         "A sazonalidade passa a ser **informada** ao modelo, em vez de ele ter que descobri-la"],
        ["Tendência (knots)", "1 nó por semana (156): baseline totalmente livre", "2 nós: uma reta",
         "Com tendência livre o baseline consegue explicar qualquer oscilação e distribui mal o crédito"],
        ["Prior do ROI / mídia", prior_ing.replace("**", ""), prior_aj.replace("**", ""),
         "O ajustado diz ao modelo uma faixa plausível de negócio (larga, só corta o absurdo)"],
        ["Adstock (decay)", "Uniform(0; 1) por canal, `max_lag` = 8", "Igual", "Mantido"],
        ["Saturação (Hill)", "`ec` ~ Normal truncada(0,8; 0,8), `slope` fixo em 1", "Igual", "Mantido"],
        ["Teste (holdout)", f"Últimas {M['semanas_teste']} semanas", "Igual", "Mantido"],
        ["MCMC", f"{M['chains']} cadeias, {M['adapt']}/{M['burnin']}/{M['keep']} (adapt/burn-in/mantidas)", "Igual", "Mantido"]],
        columns=["Item", "Ingênuo", "Ajustado", "Por que mudei"])
    st.table(cfg.replace(r"\*\*", "", regex=True).set_index("Item"))
    st.caption(f"Priors padrão do Meridian: {link('documentação', DOCS['priors_padrao'])}. Detalhes do prior para KPI sem receita: {link('documentação', DOCS['kpi_sem_receita'])}.")

    st.markdown("### O que muda no resultado")
    a_i, a_j = ler(f"acc_{info['ing']}.csv").iloc[0], ler(f"acc_{kk}.csv").iloc[0]
    ac = pd.DataFrame({"": ["MAPE treino", "MAPE teste", "R² treino", "R² teste"],
                       "Ingênuo": [pct(a_i["mape_treino"] * 100), pct(a_i["mape_teste"] * 100), num(a_i["r2_treino"], 2), num(a_i["r2_teste"], 2)],
                       "Ajustado": [pct(a_j["mape_treino"] * 100), pct(a_j["mape_teste"] * 100), num(a_j["r2_treino"], 2), num(a_j["r2_teste"], 2)]})
    ri = ler(f"retorno_{info['ing']}.csv").set_index("canal"); rj = ler(f"retorno_{kk}.csv").set_index("canal")
    ca, cb = st.columns([1, 2])
    with ca:
        st.markdown("##### Acurácia")
        st.dataframe(ac, hide_index=True)
        st.caption("Olhando só o MAPE, os dois parecem razoáveis. A diferença aparece na atribuição.")
    with cb:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[ri.loc[c, "contrib_verdade"] for c in CANAIS], name="verdade", marker_color=LARANJA))
        fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[ri.loc[c, "contrib_pct"] for c in CANAIS], name="ingênuo", marker_color=CINZA))
        fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[rj.loc[c, "contrib_pct"] for c in CANAIS], name="ajustado", marker_color=AZUL))
        fig.update_layout(title=f"Contribuição por canal (% de {info['rotulo'].lower()})", barmode="group", legend=dict(orientation="h", y=-0.2))
        mostrar(fig, 380)
    erro = pd.DataFrame({"Canal": [NOMES[c] for c in CANAIS],
                         "Erro ingênuo (p.p.)": [abs(ri.loc[c, "contrib_pct"] - ri.loc[c, "contrib_verdade"]) for c in CANAIS],
                         "Erro ajustado (p.p.)": [abs(rj.loc[c, "contrib_pct"] - rj.loc[c, "contrib_verdade"]) for c in CANAIS]})
    erro.loc[len(erro)] = ["Média", erro.iloc[:, 1].mean(), erro.iloc[:, 2].mean()]
    st.dataframe(erro.style.format({"Erro ingênuo (p.p.)": "{:.1f}", "Erro ajustado (p.p.)": "{:.1f}"}), hide_index=True)
    worst = (ri["contrib_pct"] - ri["contrib_verdade"]).abs().idxmax()
    st.markdown(
        f"> No modelo ingênuo de {info['rotulo'].lower()}, o maior desvio é **{NOMES[worst]}**: atribui **{pct(ri.loc[worst,'contrib_pct'])}** contra "
        f"**{pct(ri.loc[worst,'contrib_verdade'])}** de verdade. A mídia total atribuída é {pct(ri['contrib_pct'].sum())} no ingênuo, "
        f"{pct(rj['contrib_pct'].sum())} no ajustado e {pct(ri['contrib_verdade'].sum())} na verdade. "
        "**Ajuste bom, atribuição errada:** com tendência livre e priors abertos, o modelo tem liberdade demais para distribuir crédito.")
    x1, x2 = st.columns(2)
    with x1: mostrar(fig_fit(info["ing"], "Ingênuo: predito vs. realizado", info["unidade"]), 360)
    with x2: mostrar(fig_fit(kk, "Ajustado: predito vs. realizado", info["unidade"]), 360)

# ================================================================== MODELOS AJUSTADOS
def aba_modelo(nome, kpi):
    info = KPIS[kpi]; ac = ler(f"acc_{nome}.csv").iloc[0]
    st.markdown(f"Modelo ajustado para **{info['rotulo']}** ({'KPI de volume' if info['volume'] else 'KPI monetário'}). "
                "Configuração completa na aba *Por que ajustar?*.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("MAPE treino", pct(ac["mape_treino"] * 100)); m2.metric("MAPE teste", pct(ac["mape_teste"] * 100))
    m3.metric("R² teste", num(ac["r2_teste"], 2)); m4.metric("Maior R-hat", num(ac["max_rhat"], 3), help="Convergência do MCMC: ideal < 1,1")
    mostrar(fig_fit(nome, f"{info['rotulo']}: predito vs. realizado", info["unidade"]), 380)
    st.caption("Eixo começando em zero. A banda de incerteza é cortada em zero, já que o KPI não é negativo.")

    st.markdown("#### De onde vem o KPI")
    a, b = st.columns(2)
    with a: mostrar(fig_contrib(nome, "Contribuição por componente"), 400)
    with b: mostrar(fig_tempo(nome, "Contribuição ao longo do tempo", info["unidade"]), 400)
    bs = ler(f"baseline_{nome}.csv").set_index("metric")
    st.info(f"**Baseline segundo o Meridian:** {pct(bs.loc['mean','posterior'])} do KPI (IC 90%: {pct(bs.loc['ci_lo','posterior'])} a "
            f"{pct(bs.loc['ci_hi','posterior'])}). Antes de ver os dados (prior), o modelo esperava {pct(bs.loc['mean','prior'])}. "
            f"Na verdade, a soma de tudo que **não** é mídia paga (baseline + desconto) é {pct(100 - V[info['chave']]['midia_total'] / V[info['chave']]['y_total'] * 100)}.")

    st.markdown("#### Dentro do baseline: os controles")
    st.markdown(
        "O Meridian entrega o baseline inteiro. Para ver **quem está dentro dele**, calculei a contribuição de cada controle a partir dos "
        f"coeficientes da posterior (não é uma saída pronta do Meridian; ver {link('documentação do baseline', DOCS['baseline'])}). "
        "Os controles são centrados, então cada contribuição é o **desvio em relação ao nível médio**: positiva quando o fator empurra o KPI para cima naquela semana, negativa quando puxa para baixo.")
    bt = ler(f"baseline_tempo_{nome}.csv"); bt["semana"] = pd.to_datetime(bt["semana"])
    grupos = {"Sazonalidade": ["sen_1", "cos_1", "sen_2", "cos_2", "mes_nov", "mes_dez"],
              "Economia (desemprego + IPCA)": ["desemprego_pct", "ipca_12m_pct"],
              "Calendário e eventos (feriados + Black Friday)": ["n_feriados_nacionais", "black_friday"]}
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.45, .55], vertical_spacing=.08,
                        subplot_titles=["Baseline = nível + tendência + efeito dos controles", "Efeito de cada grupo de controles (desvio do nível médio)"])
    fig.add_trace(go.Scatter(x=bt["semana"], y=bt["baseline"], name="baseline total", line=dict(color=CINZA, width=2)), 1, 1)
    fig.add_trace(go.Scatter(x=bt["semana"], y=bt["nivel_tendencia"], name="só nível + tendência", line=dict(color=AZUL, dash="dash")), 1, 1)
    for (g, cs), cor in zip(grupos.items(), [AZUL_ESC, LARANJA, AZUL_CLARO]):
        fig.add_trace(go.Scatter(x=bt["semana"], y=bt[cs].sum(axis=1), name=g, line=dict(color=cor)), 2, 1)
    fig.add_hline(y=0, line_color="#999", line_width=1, row=2, col=1)
    fig.update_yaxes(title_text=info["unidade"], row=1, col=1); fig.update_yaxes(title_text=info["unidade"], row=2, col=1)
    fig.update_layout(legend=dict(orientation="h", y=-0.12))
    mostrar(fig, 560)

    st.caption("Atenção ao gráfico de cima: a linha tracejada (só nível + tendência) pode ficar quase plana enquanto o efeito de *Economia* sobe ou desce de forma contínua. "
               "Como o desemprego cai devagar durante os 3 anos, **tendência de crescimento e efeito do desemprego são praticamente indistinguíveis**: o modelo estima bem o baseline total, "
               "mas a divisão entre os dois é incerta (veja o intervalo largo do desemprego na tabela).")
    amp = pd.DataFrame({"Grupo": list(grupos), "amp": [dp_grupo(bt, cs) for cs in grupos.values()]}).sort_values("amp")
    ca, cb = st.columns([2, 3])
    with ca:
        fig = go.Figure(go.Bar(x=amp["amp"], y=amp["Grupo"], orientation="h", marker_color=AZUL,
                               text=[num(v) for v in amp["amp"]], textposition="outside"))
        fig.update_layout(title=f"Quanto cada grupo move o KPI ({info['unidade']}/semana)", xaxis_range=[0, amp["amp"].max() * 1.25])
        mostrar(fig, 300)
        st.caption("Amplitude = desvio-padrão da contribuição semanal do grupo.")
    with cb:
        ct = ler(f"controles_{nome}.csv")
        linhas = []
        for _, r in ct.iterrows():
            un = {"desemprego_pct": "por +1 p.p.", "ipca_12m_pct": "por +1 p.p.", "n_feriados_nacionais": "por feriado",
                  "black_friday": "na semana de BF", "mes_nov": "no mês", "mes_dez": "no mês", "desconto_medio_pct": "por +1 p.p. de desconto"}.get(r["controle"], "por +1 unidade da onda")
            sinal = "sinal incerto" if (r["efeito_un_lo"] < 0 < r["efeito_un_hi"]) else ("positivo" if r["efeito_un"] > 0 else "negativo")
            linhas.append({"Variável": NOME_CONTROLE[r["controle"]], "Efeito estimado (IC 90%)": f"{num(r['efeito_un'],1)} ({num(r['efeito_un_lo'],1)} a {num(r['efeito_un_hi'],1)}) {info['unidade']}/sem {un}",
                           "Leitura do sinal": sinal,
                           "Efeito verdadeiro": "-" if pd.isna(r["efeito_un_verdade"]) else f"{num(r['efeito_un_verdade'],1)}"})
        st.dataframe(pd.DataFrame(linhas), hide_index=True, height=430)
    st.caption("\"Sinal incerto\" = o intervalo de 90% inclui zero: o modelo não consegue afirmar se o efeito é positivo ou negativo. "
               "O desemprego costuma cair nessa categoria porque cai de forma contínua e se confunde com a tendência (multicolinearidade).")

    st.markdown("#### Retorno por canal")
    if info["volume"]:
        st.caption("ROI = novas contas por R$ 1 mil investido; CAC = 1000 ÷ ROI. **mROI/ROI** baixo indica saturação: "
                   "< 0,40 saturada, 0,40 a 0,50 atenção, > 0,50 com espaço (regra prática do projeto).")
    else:
        st.caption("ROI = R$ de receita por R$ 1 investido. **mROI/ROI** baixo indica saturação: "
                   "< 0,40 saturada, 0,40 a 0,50 atenção, > 0,50 com espaço (regra prática do projeto).")
    st.dataframe(tabela_retorno(nome, kpi), hide_index=True)
    st.warning("Repare nos intervalos: canal com IC largo não deve ter decisão tomada só pelo ponto.")

    st.markdown("#### Curvas de resposta")
    st.caption("KPI incremental em função do investimento total. Ponto cinza = investimento atual. Curva ainda subindo = há espaço; achatando = saturação.")
    mostrar(fig_curvas(nome, info["unidade"], com_verdade=False), 580)

    st.markdown("#### Decay do adstock estimado")
    r = ler(f"retorno_{nome}.csv").set_index("canal")
    sem = np.arange(0, 9)
    fig = go.Figure()
    for c in CANAIS:
        w = r.loc[c, "decay_estimado"] ** sem; w = w / w.sum()
        fig.add_trace(go.Scatter(x=sem, y=w, name=NOMES[c], mode="lines+markers", line=dict(color=CORES_CANAIS[c] if c != "display_programatico" else CINZA)))
    fig.update_layout(title="Peso do efeito de 1 semana de mídia nas semanas seguintes", xaxis_title="semanas depois", yaxis_title="peso")
    mostrar(fig, 340)

with abas[4]:
    aba_modelo("contas", "contas")
with abas[5]:
    aba_modelo("receita", "receita")
    comp = pd.DataFrame({
        "Canal": [NOMES[c] for c in CANAIS],
        "Novas contas (% do KPI)": [ler("retorno_contas.csv").set_index("canal").loc[c, "contrib_pct"] for c in CANAIS],
        "Receita (% do KPI)": [ler("retorno_receita.csv").set_index("canal").loc[c, "contrib_pct"] for c in CANAIS]})
    fig = go.Figure()
    fig.add_trace(go.Bar(x=comp["Canal"], y=comp.iloc[:, 1], name="novas contas", marker_color=AZUL))
    fig.add_trace(go.Bar(x=comp["Canal"], y=comp.iloc[:, 2], name="receita", marker_color=AZUL_CLARO))
    fig.update_layout(title="O mesmo canal pode ser bom para conta e fraco para receita", barmode="group",
                      yaxis_title="% do KPI explicado", legend=dict(orientation="h", y=-0.2))
    mostrar(fig, 380)

# ================================================================== VERDADE vs ESTIMADO
with abas[6]:
    st.markdown("Como o dado é sintético, temos o **gabarito**. O modelo nunca viu esses números.")
    kpi_v = st.radio("KPI", ["Novas contas", "Receita"], horizontal=True, key="kv")
    nome_v = "contas" if kpi_v == "Novas contas" else "receita"
    r = ler(f"retorno_{nome_v}.csv").set_index("canal")
    x = [NOMES[c] for c in CANAIS]
    f = make_subplots(rows=1, cols=3, subplot_titles=["Contribuição (% do KPI)", "ROI", "Decay do adstock"])
    f.add_trace(go.Bar(x=x, y=[r.loc[c, "contrib_verdade"] for c in CANAIS], marker_color=LARANJA, name="verdade"), 1, 1)
    f.add_trace(go.Bar(x=x, y=[r.loc[c, "contrib_pct"] for c in CANAIS], marker_color=AZUL, name="estimado (IC 90%)",
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
    st.markdown(f"**Canais cujo IC 90% de contribuição não contém a verdade:** {', '.join(excl) if excl else 'nenhum'}.")

    st.markdown("#### Controles e promoção: efeito estimado vs. verdadeiro (por unidade)")
    ct = ler(f"controles_{nome_v}.csv"); ct = ct[ct["efeito_un_verdade"].notna()]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[NOME_CONTROLE[c] for c in ct["controle"]], y=ct["efeito_un_verdade"], marker_color=LARANJA, name="verdade"))
    fig.add_trace(go.Bar(x=[NOME_CONTROLE[c] for c in ct["controle"]], y=ct["efeito_un"], marker_color=AZUL, name="estimado (IC 90%)",
                         error_y=dict(type="data", symmetric=False, array=(ct["efeito_un_hi"] - ct["efeito_un"]).values,
                                      arrayminus=(ct["efeito_un"] - ct["efeito_un_lo"]).values)))
    fig.update_layout(barmode="group", yaxis_title=f"{KPIS[nome_v]['unidade']}/semana por unidade", legend=dict(orientation="h", y=-0.25))
    mostrar(fig, 380)
    st.caption("Desemprego e Black Friday têm intervalos largos: o desemprego se confunde com a tendência, e a Black Friday são só 3 semanas.")

    st.markdown(
        "**Onde o modelo errou e por quê.** O investimento em **Meta** sobe junto com promoção e Black Friday (plantei essa "
        "multicolinearidade de propósito), e o modelo não consegue separar totalmente os dois: um intervalo de credibilidade "
        "pode estar bem calibrado no modelo e ainda assim errado se a estrutura do dado confunde causas. O **decay do adstock** "
        "também é mal identificado com 3 anos semanais. ROI e contribuição saem melhores que o decay. "
        "O remédio direto é **calibrar com experimentos de incrementalidade (geo-lift)** e usar o resultado como prior de ROI.")
    st.markdown("#### Curvas de resposta: estimada vs. verdadeira")
    mostrar(fig_curvas(nome_v, KPIS[nome_v]["unidade"], com_verdade=True), 580)

# ================================================================== QUANTO E ONDE INVESTIR
with abas[7]:
    st.markdown(
        "**Dada uma verba X por semana, como dividir entre as campanhas?** O princípio: colocar o próximo real onde o **retorno marginal** é maior, "
        "até igualar o retorno marginal entre os canais. As curvas de resposta estimadas dizem onde cada canal está nessa curva.")
    kpi_s = st.radio("KPI a maximizar", ["Novas contas", "Receita"], horizontal=True, key="ks")
    ns = "contas" if kpi_s == "Novas contas" else "receita"; unid = KPIS[ns]["unidade"]
    curvas = ler(f"curvas_{ns}.csv")

    def _g(canal):
        d = curvas[curvas["canal"] == canal].sort_values("multiplicador"); return d
    G = {c: _g(c) for c in CANAIS}
    atual_sem = {c: float(G[c].loc[(G[c]["multiplicador"] - 1).abs().idxmin(), "gasto_mil"]) / N_SEM for c in CANAIS}
    def resposta(canal, gasto_sem, col="est"):
        d = G[canal]; return float(np.interp(gasto_sem * N_SEM, d["gasto_mil"], d[col])) / N_SEM
    total_atual = sum(atual_sem.values())

    st.markdown("### 1. Verba total")
    pct_x = st.slider("Verba semanal total (100% = o que foi investido em média)", 50, 250, 100, 5, format="%d%%", key=f"x_{ns}")
    X = total_atual * pct_x / 100
    st.caption(f"Verba semanal: **R$ {num(X,1)} mil** (atual: R$ {num(total_atual,1)} mil). Cada canal pode ir de 0 a 3x o que investiu; acima de 2x o modelo extrapola além do que viu nos dados.")

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
    k1.metric(f"{KPIS[ns]['rotulo']}/semana, mantendo a proporção atual", num(total(prop)))
    k2.metric(f"{KPIS[ns]['rotulo']}/semana, alocação sugerida", num(total(otimo)), delta=f"{total(otimo) - total(prop):+,.0f}".replace(",", "."))
    k3.metric("Sugerida vs. proporcional, na verdade", f"{total(otimo,'verdade') - total(prop,'verdade'):+,.0f}".replace(",", "."),
              help="Mesma comparação, mas calculada nas curvas VERDADEIRAS do gerador. Mostra se a sugestão do modelo realmente ajuda.")

    dif_v = total(otimo, "verdade") - total(prop, "verdade")
    if dif_v < 0:
        st.error(f"**Nas curvas verdadeiras, a sugestão rende {num(abs(dif_v))} {unid}/semana a MENOS que manter a proporção atual.** "
                 "Isso acontece porque as curvas estimadas divergem das verdadeiras em alguns canais (por exemplo, o Meta superestimado) e a otimização confia nelas. "
                 "É exatamente o risco de otimizar em cima de uma curva incerta.")
    else:
        st.success(f"Nas curvas verdadeiras, a sugestão também rende {num(dif_v)} {unid}/semana a mais que manter a proporção atual.")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[prop[c] for c in CANAIS], name="proporção atual", marker_color=CINZA))
    fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=[otimo[c] for c in CANAIS], name="sugerida", marker_color=AZUL))
    fig.update_layout(title="Investimento semanal por canal (R$ mil)", barmode="group", legend=dict(orientation="h", y=-0.2))
    mostrar(fig, 340)
    tab = pd.DataFrame({
        "Canal": [NOMES[c] for c in CANAIS],
        "Proporção atual (R$ mil/sem)": [prop[c] for c in CANAIS],
        "Sugerida (R$ mil/sem)": [otimo[c] for c in CANAIS],
        "% da verba (sugerida)": [otimo[c] / X * 100 for c in CANAIS],
        "x o investimento atual": [otimo[c] / atual_sem[c] for c in CANAIS],
        f"{unid}/sem (sugerida)": [resposta(c, otimo[c]) for c in CANAIS],
        "Retorno marginal (por R$ 1 mil)": [marg(c, otimo[c]) for c in CANAIS]})
    st.dataframe(tab.style.format({"Proporção atual (R$ mil/sem)": "{:.1f}", "Sugerida (R$ mil/sem)": "{:.1f}", "% da verba (sugerida)": "{:.0f}%",
                                   "x o investimento atual": "{:.2f}x", f"{unid}/sem (sugerida)": "{:,.0f}", "Retorno marginal (por R$ 1 mil)": "{:.2f}"}), hide_index=True)
    fora = [NOMES[c] for c in CANAIS if otimo[c] > 2 * atual_sem[c]]
    if fora: st.warning(f"Acima de 2x o investimento atual (fora da faixa que o modelo observou): {', '.join(fora)}. Trate como hipótese a testar.")
    st.markdown("Repare que, na sugestão, o **retorno marginal fica parecido entre os canais** que recebem verba: é o sinal de que não vale mover mais nada.")
    st.warning("Use como **direção**, não como ordem. As curvas têm incerteza grande (veja os ICs) e a otimização não a leva em conta. "
               "Se o modelo superestima um canal (como o Meta neste dado), a sugestão empurra verba para ele. Valide com um teste de incrementalidade antes de mexer no orçamento de verdade.")

    with st.expander("2. Testar sua própria alocação (sliders por canal)"):
        cols = st.columns(3); mult = {}
        for i, c in enumerate(CANAIS):
            with cols[i % 3]:
                mult[c] = st.slider(f"{NOMES[c]}: {num(atual_sem[c],1)} mil/sem", 0, 300, 100, 5, format="%d%%", key=f"sl_{ns}_{c}") / 100
        gs = {c: atual_sem[c] * mult[c] for c in CANAIS}
        u1, u2, u3 = st.columns(3)
        u1.metric(f"{KPIS[ns]['rotulo']}/semana", num(total(gs)), delta=f"{total(gs) - total(atual_sem):+,.0f}".replace(",", "."))
        u2.metric("Investimento/semana (R$ mil)", num(sum(gs.values()), 1))
        u3.metric("Retorno médio", num(total(gs) / max(sum(gs.values()), 1e-9), 2))

# ================================================================== QUANDO INVESTIR
with abas[8]:
    st.markdown(
        "Duas perguntas do projeto original, respondidas com o modelo ajustado: **(1)** vale mais investir uma \"bomba\" de uma vez ou aos poucos ao longo das semanas? "
        "**(2)** é melhor investir tudo em 1 mês ou diluir em outros meses? Cada uma no **geral** (todas as campanhas) e **por campanha**.")
    with st.expander("Como a simulação funciona"):
        st.markdown(
            "Fixo uma **verba** (a média semanal normal de cada canal × o número de semanas do período) e comparo **cronogramas** diferentes para gastar exatamente "
            "essa verba: diluída, em blocos, em pulsos, ou toda de uma vez. Para cada cronograma, o Meridian calcula o KPI incremental usando as "
            "**2.000 amostras da posterior**, então cada resultado vem com intervalo. O cenário **diluído** é o 100 de referência. "
            "Como o dado é sintético, calculo também o resultado **verdadeiro** de cada cronograma com a fórmula do gerador, para conferir o ranking.\n\n"
            "**Por que diluir tende a ganhar:** a saturação (curva de Hill) faz cada real a mais render menos, então concentrar verba empurra o canal para o platô. "
            "O adstock espalha parte do efeito no tempo, mas não compensa isso.\n\n"
            "**Limites:** o modelo assume que o efeito de uma impressão é o mesmo em qualquer época do ano e que o CPM não muda (na Black Friday ele sobe). "
            "Ou seja, **não** avalia se vale concentrar verba em uma época de demanda alta. E cenários com pico muito acima do máximo semanal já observado "
            "são **extrapolação** (marcados abaixo).")
    kw = st.radio("KPI", ["Novas contas", "Receita"], horizontal=True, key="kw")
    nw = "contas" if kw == "Novas contas" else "receita"; unw = KPIS[nw]["unidade"]
    cr = ler(f"cronogramas_{nw}.csv")
    perg = st.radio("Pergunta", ["1. Bomba ou diluído? (verba de 1 trimestre, 13 semanas)", "2. Tudo em 1 mês ou diluído? (verba de 1 ano, 52 semanas)"], key="qp")
    T = 13 if perg.startswith("1") else 52
    visao = st.radio("Visão", ["Geral (todas as campanhas)"] + [NOMES[c] for c in CANAIS], horizontal=True, key="qv")
    chave_canal = "TOTAL" if visao.startswith("Geral") else [c for c in CANAIS if NOMES[c] == visao][0]
    sub = cr[cr["horizonte"] == T]
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
    fig.add_trace(go.Bar(x=ordem, y=idx, marker_color=cores, name="estimado (IC 90%)",
                         error_y=dict(type="data", symmetric=False, array=(hi - idx).values, arrayminus=(idx - lo).values),
                         text=[f"{v:.0f}" for v in idx], textposition="inside", insidetextanchor="start", textfont=dict(color="white")))
    fig.add_trace(go.Scatter(x=ordem, y=idx_v, mode="markers", marker=dict(color=LARANJA, size=12, symbol="diamond"), name="verdade"))
    fig.add_hline(y=100, line_dash="dot", line_color=CINZA)
    fig.update_layout(title=f"Resultado incremental por cronograma, {visao.lower() if not visao.startswith('Geral') else 'todas as campanhas'} (diluído = 100)",
                      yaxis_title="índice (diluído = 100)", legend=dict(orientation="h", y=-0.25), yaxis_range=[0, max(130, float(hi.max()) * 1.1)])
    mostrar(fig, 420)
    st.caption("Barras em azul claro = cronograma com pico de investimento semanal acima de 1,5x o máximo histórico do canal (extrapolação, baixa confiança).")

    melhor = idx.idxmax(); pior = idx.idxmin()
    st.markdown(f"> **Leitura:** para {('as campanhas juntas' if chave_canal == 'TOTAL' else NOMES[chave_canal])}, o melhor cronograma estimado é "
                f"**{melhor}** e o pior é **{pior}**, que rende **{idx[pior]:.0f}%** do diluído ({num(100 - idx[pior], 0)} p.p. a menos, IC 90% de {lo[pior]:.0f}% a {hi[pior]:.0f}%). "
                f"Na verdade do gerador, o pior rende {idx_v[pior]:.0f}% do diluído.")
    tab = pd.DataFrame({
        "Cronograma": ordem,
        f"{unw} incremental (IC 90%)": [f"{num(base.loc[o,'est'])} ({num(base.loc[o,'lo'])} a {num(base.loc[o,'hi'])})" for o in ordem],
        "Índice (diluído = 100)": [f"{idx[o]:.0f}" for o in ordem],
        "Índice verdadeiro": [f"{idx_v[o]:.0f}" for o in ordem],
        "Pico semanal vs. máximo histórico": [f"{pico[o]:.1f}x" for o in ordem],
        "Confiança": ["extrapolação" if extrap[o] else "dentro do observado" for o in ordem]})
    st.dataframe(tab, hide_index=True)

    if chave_canal == "TOTAL":
        st.markdown("#### Comparação entre campanhas")
        st.caption("O mesmo cronograma \"tudo em 1 mês\" (ou bomba) penaliza mais quem satura mais rápido: quanto menor o índice, mais o canal perde ao concentrar a verba.")
        pior_cen = ordem[-1] if T == 13 else "1 mês seguido (4 semanas)"
        pior_cen = [o for o in ordem if o.startswith("Bomba")][0] if T == 13 else [o for o in ordem if o.startswith("1 mês seguido")][0]
        rows = []
        for c in CANAIS:
            rr = sub[(sub["canal"] == f"RAZAO_{c}") & (sub["cenario"] == pior_cen)].iloc[0]
            rows.append((NOMES[c], rr["est"] * 100, rr["lo"] * 100, rr["hi"] * 100))
        rows.sort(key=lambda t: t[1])
        fig = go.Figure(go.Bar(x=[r[1] for r in rows], y=[r[0] for r in rows], orientation="h", marker_color=AZUL,
                               error_x=dict(type="data", symmetric=False, array=[r[3] - r[1] for r in rows], arrayminus=[r[1] - r[2] for r in rows]),
                               text=[f"{r[1]:.0f}" for r in rows], textposition="inside", insidetextanchor="start", textfont=dict(color="white")))
        fig.update_layout(title=f"Índice do cronograma \"{pior_cen}\" por campanha (diluído = 100)", xaxis_range=[0, 110])
        mostrar(fig, 340)


# ================================================================== PARÂMETROS
with abas[9]:
    st.markdown(
        "Aqui estão **todos os números que definem os modelos**: os que **eu escolhi** (configuração e priors) e os que o modelo **aprendeu dos dados** "
        "(decay, saturação, ROI e efeito dos controles), cada um com o **gabarito** do gerador ao lado quando existe. "
        f"Documentação: {link('parâmetros do ModelSpec', DOCS['spec'])} · {link('priors padrão', DOCS['priors_padrao'])} · {link('adstock e saturação', DOCS['adstock'])}.")

    st.markdown("### 1. Configuração escolhida (não vem dos dados)")
    cfg = pd.DataFrame([
        ["Semanas de dados / teste (holdout)", f"{M['semanas']} / {M['semanas_teste']}", "igual"],
        ["max_lag (semanas de memória do adstock)", "8", "igual"],
        ["MCMC: cadeias × (adaptação + burn-in + amostras)", f"{M['chains']} × ({M['adapt']} + {M['burnin']} + {M['keep']})", "igual"],
        ["Controles", "4: desemprego, IPCA, feriados, Black Friday", "10: os 4 + seno/cosseno anual e semestral + novembro + dezembro"],
        ["Promoção", "desconto médio como tratamento não-mídia", "igual"],
        ["knots (flexibilidade da tendência no tempo)", "1 por semana (padrão)", "2 (tendência suave)"],
        ["Prior de ROI (novas contas)", "LogNormal(0,2; 0,9) padrão", "LogNormal com 95% em [1; 25] contas por R$ mil"],
        ["Prior de ROI (receita)", "LogNormal(0,2; 0,9) padrão", "LogNormal com 95% em [0,3; 8] R$ por R$ 1"],
        ["Prior do decay (alpha)", "Uniform(0, 1)", "igual"],
        ["Prior do ponto de saturação (ec)", "TruncNormal(0,8; 0,8; 0,1; 10)", "igual"],
        ["Prior da inclinação do Hill (slope)", "fixa em 1", "igual (fixa em 1)"]],
        columns=["Parâmetro", "Modelo ingênuo", "Modelo ajustado"])
    st.table(cfg)
    st.caption("A inclinação fica fixa em 1 (padrão do Meridian), mas o gerador usa valores entre 1,1 e 2,0: é uma simplificação que o modelo faz e que aparece nas curvas.")

    st.markdown("### 2. O que o modelo aprendeu, por canal")
    p1, p2 = st.columns(2)
    kpi_p = p1.radio("KPI", ["Novas contas", "Receita"], horizontal=True, key="pm_kpi")
    mod_p = p2.radio("Modelo", ["Ajustado", "Ingênuo"], horizontal=True, key="pm_mod")
    np_ = "contas" if kpi_p == "Novas contas" else "receita"
    arq = f"parametros_{'ingenuo_' if mod_p == 'Ingênuo' else ''}{np_}.csv"
    if not os.path.exists(os.path.join(RES, arq)):
        st.warning("Parâmetros ainda não exportados: rode `exportar_resultados.py`.")
    else:
        P = ler(arq)
        DESC = {"decay": ("Decay do adstock (alpha)", "Fração do efeito que sobra de uma semana para a seguinte. 0,5 = metade. Perto de 0 o efeito é imediato; perto de 1, dura semanas."),
                "ec": ("Ponto de meia-saturação (ec)", "Nível de mídia (relativo à mediana) em que o canal chega à metade do efeito máximo. Menor = satura mais cedo. No gerador, relativo à média em vez da mediana, então compare a ordem de grandeza."),
                "slope": ("Inclinação do Hill (slope)", "Quão brusca é a curva. Perto de 1 é uma curva suave; valores altos formam um S com limiar."),
                "roi": ("ROI", "Retorno médio por R$ 1 mil investido, no período todo."),
                "beta": ("Coeficiente da mídia (beta)", "Efeito máximo do canal na escala interna do modelo (KPI padronizado). Não tem gabarito comparável direto; use para ver o tamanho relativo entre canais.")}
        u_roi = "contas por R$ mil" if np_ == "contas" else "R$ por R$ 1"
        for par in ["roi", "decay", "ec", "slope", "beta"]:
            d = P[P["parametro"] == par].set_index("canal").reindex(CANAIS)
            if d.empty: continue
            tit, expl = DESC[par]
            st.markdown(f"**{tit}**" + (f" ({u_roi})" if par == "roi" else ""))
            st.caption(expl)
            tem_v = d["verdade"].notna().any()
            fig = go.Figure()
            if tem_v:
                fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=d["verdade"], name="verdade", marker_color=LARANJA))
            fig.add_trace(go.Bar(x=[NOMES[c] for c in CANAIS], y=d["media"], name="estimado (IC 90%)", marker_color=AZUL,
                                 error_y=dict(type="data", symmetric=False, array=(d["hi"] - d["media"]).values, arrayminus=(d["media"] - d["lo"]).values)))
            fig.update_layout(barmode="group", legend=dict(orientation="h", y=-0.25))
            mostrar(fig, 300)
        tb = pd.DataFrame({"Canal": [NOMES[c] for c in CANAIS]})
        for par, rot in [("roi", "ROI"), ("decay", "Decay"), ("ec", "ec"), ("slope", "Slope")]:
            d = P[P["parametro"] == par].set_index("canal").reindex(CANAIS)
            if d.empty: continue
            tb[f"{rot} estimado"] = [f"{a:.2f} ({b:.2f} a {c:.2f})".replace(".", ",") for a, b, c in zip(d["media"], d["lo"], d["hi"])]
            if d["verdade"].notna().any(): tb[f"{rot} verdade"] = [f"{v:.2f}".replace(".", ",") for v in d["verdade"]]
        st.markdown("**Tabela resumo** (média e IC 90%)")
        st.table(tb)
        if mod_p == "Ingênuo":
            st.info("No modelo ingênuo a inclinação é fixa em 1 e o ROI usa o prior padrão, por isso os intervalos são largos e o ROI de alguns canais foge do gabarito.")

    st.markdown("### 3. Controles e promoção: quanto cada um vale")
    st.caption("Efeito de +1 unidade do controle no KPI da semana (média e IC 90%). Os controles foram centrados, então seus efeitos são desvios em torno do nível médio do baseline.")
    c1, c2 = st.columns(2)
    for col_, nm, rot in [(c1, "contas", "Novas contas"), (c2, "receita", "Receita")]:
        with col_:
            ct = ler(f"controles_{nm}.csv")
            t = pd.DataFrame({"Controle": [NOME_CONTROLE.get(c, c) for c in ct["controle"]],
                              "Efeito por unidade (IC 90%)": [f"{a:,.1f} ({b:,.1f} a {c:,.1f})".replace(",", "X").replace(".", ",").replace("X", ".")
                                                             for a, b, c in zip(ct["efeito_un"], ct["efeito_un_lo"], ct["efeito_un_hi"])],
                              "Verdade": ["" if pd.isna(v) else num(v, 0) for v in ct["efeito_un_verdade"]]})
            st.markdown(f"**{rot}**"); st.table(t)
    st.caption("Black Friday são só 3 semanas e ficou confundida com a mídia que sobe junto: o efeito estimado pode sair com sinal errado (aconteceu na receita). Sazonalidade (seno/cosseno/meses) não tem gabarito por unidade: o gerador usa uma forma sazonal única, aproximada pelo modelo com esses termos.")


# ================================================================== RECOMENDAÇÕES
with abas[10]:
    st.markdown(
        "Resumo acionável, **calculado a partir das simulações das outras abas** (cronogramas, curvas e retorno marginal). "
        "Cada recomendação traz o que o modelo estima **e** se a verdade do gerador confirma. Trate como hipóteses para validar com um teste, não como ordem.")
    kr = st.radio("KPI", ["Novas contas", "Receita"], horizontal=True, key="rec_kpi")
    nr = "contas" if kr == "Novas contas" else "receita"; ur = KPIS[nr]["unidade"]
    cr = ler(f"cronogramas_{nr}.csv"); ret = ler(f"retorno_{nr}.csv").set_index("canal"); curv = ler(f"curvas_{nr}.csv")

    # ---------- 1. quando investir
    st.markdown("### 1. Quando investir: diluir ou concentrar?")
    resumo = []
    for T, rot in [(13, "Verba de 1 trimestre (13 semanas)"), (52, "Verba de 1 ano (52 semanas)")]:
        sub = cr[cr["horizonte"] == T]; ordem = list(dict.fromkeys(sub["cenario"]))
        rz = sub[sub["canal"] == "RAZAO_TOTAL"].set_index("cenario"); bt = sub[sub["canal"] == "TOTAL"].set_index("cenario")
        idx = rz.loc[ordem, "est"] * 100; idv = bt.loc[ordem, "verdade"] / bt.loc[ordem[0], "verdade"] * 100
        ok = [o for o in ordem if bt.loc[o, "pico_vs_historico"] <= 1.5]
        melhor = max(ok, key=lambda o: idx[o]); pior = idx.idxmin()
        alt = [o for o in ok if o != ordem[0]]
        melhor_alt = max(alt, key=lambda o: idx[o]) if alt else None
        resumo.append((rot, melhor, idx[melhor], idv[melhor], pior, idx[pior], idv[pior], melhor_alt, sub, ordem))
    for rot, melhor, im, vm, pior, ip, vp, malt, sub, ordem in resumo:
        txt = (f"**{rot}:** o melhor cronograma dentro do que o modelo já viu é **{melhor}** (índice {im:.0f}, verdade {vm:.0f}). "
               f"O pior é **{pior}**, que rende {ip:.0f}% do diluído (verdade: {vp:.0f}%).")
        if malt and malt != melhor:
            txt += f" Se precisar concentrar, a alternativa menos custosa é **{malt}**."
        st.markdown("- " + txt)

    st.markdown("**Por campanha:** cronograma que menos perde ao concentrar (só dentro do observado) e quanto o pior custa")
    rows = []
    for c in CANAIS:
        perdas = {}
        for T in (13, 52):
            sub = cr[cr["horizonte"] == T]; ordem = list(dict.fromkeys(sub["cenario"]))
            rc = sub[sub["canal"] == f"RAZAO_{c}"].set_index("cenario"); bc = sub[sub["canal"] == c].set_index("cenario")
            alt = [o for o in ordem[1:] if bc.loc[o, "pico_vs_historico"] <= 1.5]
            mel = max(alt, key=lambda o: rc.loc[o, "est"]) if alt else None
            pio = rc.loc[ordem[1:], "est"].idxmin()
            perdas[T] = (mel, rc.loc[mel, "est"] * 100 if mel else np.nan, pio, rc.loc[pio, "est"] * 100)
        rows.append({"Campanha": NOMES[c],
                     "Trimestre: melhor alternativa": f"{perdas[13][0]} ({perdas[13][1]:.0f})" if perdas[13][0] else "sem alternativa dentro do observado",
                     "Trimestre: pior": f"{perdas[13][2]} ({perdas[13][3]:.0f})",
                     "Ano: melhor alternativa": f"{perdas[52][0]} ({perdas[52][1]:.0f})" if perdas[52][0] else "sem alternativa dentro do observado",
                     "Ano: pior": f"{perdas[52][2]} ({perdas[52][3]:.0f})"})
    st.table(pd.DataFrame(rows))
    st.caption("Entre parênteses: índice em relação ao diluído (= 100). Detalhe, IC 90% e verdade na aba Quando investir.")

    # ---------- 2. quanto e onde
    st.markdown("### 2. Quanto e onde investir")
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
    lin = []
    for pctv in (100, 130):
        X = tot_at * pctv / 100
        o = otim(X); pr = {c: atual[c] * pctv / 100 for c in CANAIS}
        te = lambda a, col: sum(resp(c, a[c], col) for c in CANAIS)
        lin.append({"Verba semanal": f"{pctv}% (R$ {num(X,1)} mil)",
                    "Estimado: sugerida vs. proporcional": f"{te(o,'est') - te(pr,'est'):+,.0f} {ur}/sem".replace(",", "."),
                    "Verdade: sugerida vs. proporcional": f"{te(o,'verdade') - te(pr,'verdade'):+,.0f} {ur}/sem".replace(",", "."),
                    "Sobe mais": ", ".join(NOMES[c] for c in sorted(CANAIS, key=lambda c: o[c] / max(pr[c], 1e-9), reverse=True)[:2]),
                    "Cai mais": ", ".join(NOMES[c] for c in sorted(CANAIS, key=lambda c: o[c] / max(pr[c], 1e-9))[:2])})
    st.table(pd.DataFrame(lin))
    ok_alloc = all(float(r["Verdade: sugerida vs. proporcional"].split()[0].replace(".", "").replace("+", "")) >= 0 for r in lin)
    if ok_alloc:
        st.markdown("- A realocação sugerida também melhora o resultado nas curvas verdadeiras: pode ser testada.")
    else:
        st.markdown("- **A realocação sugerida não é confirmada pela verdade.** Ela ganha nas curvas estimadas e perde (ou ganha bem menos) nas verdadeiras, porque as curvas de alguns canais estão superestimadas. Não mova o orçamento inteiro: teste mudanças **graduais** nos canais que o modelo mais mexe.")

    st.markdown("**Espaço de crescimento por canal** (retorno marginal ÷ retorno médio no investimento atual)")
    esp = pd.DataFrame({"Canal": [NOMES[c] for c in CANAIS],
                        "ROI (IC 90%)": [f"{ret.loc[c,'roi']:.1f} ({ret.loc[c,'roi_lo']:.1f} a {ret.loc[c,'roi_hi']:.1f})".replace(".", ",") for c in CANAIS],
                        "mROI/ROI": [ret.loc[c, "mroi"] / ret.loc[c, "roi"] for c in CANAIS],
                        "Situação": [classe_saturacao(ret.loc[c, "mroi"] / ret.loc[c, "roi"]) for c in CANAIS]}).sort_values("mROI/ROI", ascending=False)
    esp["mROI/ROI"] = esp["mROI/ROI"].map(lambda v: f"{v:.2f}".replace(".", ","))
    st.table(esp)
    com_esp = [NOMES[c] for c in CANAIS if classe_saturacao(ret.loc[c, "mroi"] / ret.loc[c, "roi"]) == "com espaço"]
    sat = [NOMES[c] for c in CANAIS if classe_saturacao(ret.loc[c, "mroi"] / ret.loc[c, "roi"]) == "saturada"]
    st.markdown(f"- Com espaço para crescer: **{', '.join(com_esp) if com_esp else 'nenhum'}**. Já saturados: **{', '.join(sat) if sat else 'nenhum'}**.")
    _exc_esp = [n for n in com_esp if n in [NOMES[c] for c in CANAIS if not (ret.loc[c, 'contrib_lo'] <= ret.loc[c, 'contrib_verdade'] <= ret.loc[c, 'contrib_hi'])]]
    if _exc_esp:
        st.markdown(f"- **Cuidado com {', '.join(_exc_esp)}:** aparece com espaço, mas é um canal que o modelo superestima (o IC não contém a verdade). Confirme com teste antes de aumentar.")

    # ---------- 3. o que fazer
    st.markdown("### 3. Plano prático")
    excl = [NOMES[c] for c in CANAIS if not (ret.loc[c, "contrib_lo"] <= ret.loc[c, "contrib_verdade"] <= ret.loc[c, "contrib_hi"])]
    st.markdown(
        "1. **Cronograma:** por padrão, **dilua** a verba; concentrar só se houver motivo de negócio (lançamento, sazonalidade), e nunca acima do pico já observado.\n"
        "2. **Alocação:** mova verba **aos poucos** dos canais saturados para os que têm espaço e meça o resultado antes de continuar.\n"
        f"3. **Calibração:** {('os canais com IC que não contém a verdade (' + ', '.join(excl) + ') são os primeiros candidatos a um teste de incrementalidade (geo-lift), usado depois como prior de ROI.') if excl else 'nenhum canal com viés claro neste KPI; ainda assim vale um geo-lift nos maiores canais.'}\n"
        "4. **Limites:** o modelo não vê sazonalidade de resposta nem mudança de CPM; a Black Friday, por exemplo, pode render diferente do que a simulação sugere.")
