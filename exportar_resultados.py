"""
Reajusta os modelos do notebook (ingênuo e ajustado, para novas contas e para receita) e salva os
resultados em resultados/*.csv para o app Streamlit ler (o app NÃO roda MCMC ao vivo).

Além do que o notebook mostra, exporta:
  - decomposição do baseline em controles (coeficientes + contribuição ao longo do tempo)
  - curvas de resposta até 3x o investimento atual (para o simulador de verba)
  - simulação de CRONOGRAMA: mesma verba investida de formas diferentes no tempo
    ("bomba" vs. diluído; 1 mês seguido vs. distribuído), com IC e comparação com a verdade

Uso:  python exportar_resultados.py          (leva ~10 min em CPU)
Precisa de: pip install google-meridian
"""
import os, json, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import jax.numpy as jnp
from meridian.data import load
from meridian.model import model, spec, prior_distribution
from meridian.analysis import analyzer, visualizer, tensors

SEMANAS_TESTE = 20
SEED = 1
N_CHAINS, N_ADAPT, N_BURNIN, N_KEEP = 4, 500, 500, 500
OUT = "resultados"
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv("mmm_dados_sinteticos.csv")
verdade = json.load(open("verdade_conhecida.json"))
canais = ["google_search", "meta", "tiktok", "youtube", "afiliados", "display_programatico"]
N = len(df)
holdout = np.zeros(N, dtype=bool); holdout[-SEMANAS_TESTE:] = True

# ---------- calendário sazonal (igual ao notebook) ----------
df_aj = df.copy()
sem_ano = pd.to_datetime(df_aj["semana"]).dt.isocalendar().week.astype(int).values
for k in (1, 2):
    df_aj[f"sen_{k}"] = np.sin(2 * np.pi * k * sem_ano / 52.18)
    df_aj[f"cos_{k}"] = np.cos(2 * np.pi * k * sem_ano / 52.18)
mes = pd.to_datetime(df_aj["semana"]).dt.month
df_aj["mes_nov"] = (mes == 11).astype(int); df_aj["mes_dez"] = (mes == 12).astype(int)
ctrl_basicos = ["desemprego_pct", "ipca_12m_pct", "n_feriados_nacionais", "black_friday"]
ctrl_aj = ctrl_basicos + ["sen_1", "cos_1", "sen_2", "cos_2", "mes_nov", "mes_dez"]
# efeitos verdadeiros por unidade do controle (do gerador), só para os controles "originais"
EFEITO_VERDADE = {
    "novas_contas": {"desemprego_pct": -280, "ipca_12m_pct": -120, "n_feriados_nacionais": -450, "black_friday": 900, "desconto_medio_pct": 85},
    "receita_mil": {"desemprego_pct": -110, "ipca_12m_pct": -40, "n_feriados_nacionais": -160, "black_friday": 210, "desconto_medio_pct": 22},
}


def carregar(dados, kpi, tipo, controles):
    c2c = load.CoordToColumns(
        time="semana", kpi=kpi, controls=controles, non_media_treatments=["desconto_medio_pct"],
        media=[f"impressoes_{c}" for c in canais], media_spend=[f"gasto_{c}" for c in canais])
    return load.DataFrameDataLoader(
        df=dados, kpi_type=tipo, coord_to_columns=c2c,
        media_to_channel={f"impressoes_{c}": c for c in canais},
        media_spend_to_channel={f"gasto_{c}": c for c in canais}).load()


def ajustar(dados, sp):
    m = model.Meridian(input_data=dados, model_spec=sp)
    m.sample_prior(300)
    m.sample_posterior(n_chains=N_CHAINS, n_adapt=N_ADAPT, n_burnin=N_BURNIN, n_keep=N_KEEP, seed=SEED)
    return m


def adstock_geo(x, decay, L=8):
    w = decay ** np.arange(L); w = w / w.sum(); out = np.zeros(len(x))
    for t in range(len(x)):
        for l in range(L):
            if t - l >= 0: out[t] += w[l] * x[t - l]
    return out

def hill(x, ec, s): return x ** s / (x ** s + ec ** s)


# =====================================================================================
# decomposição do baseline em controles
# =====================================================================================
def exportar_controles(m, nome, use_kpi, chave, dados_ctrl):
    """
    O Meridian não devolve a contribuição de cada controle pronta, mas ela sai dos coeficientes da posterior:
      contribuição_t(controle k) = desvio-padrão do KPI * gamma_k * controle_padronizado_t
    (padronizado = (x - média) / desvio). Como o controle é centrado, a contribuição é o DESVIO em relação ao
    nível médio. O que sobra do baseline (nível + tendência) = baseline do Meridian - soma dos controles.
    """
    a = analyzer.Analyzer(m)
    post = m.inference_data.posterior
    kt = m.kpi_transformer
    sd_kpi = float(np.asarray(kt.population_scaled_stdev).ravel()[0])
    z = np.asarray(m.controls_scaled)[0]                                   # (tempo, controles)
    g = np.asarray(post["gamma_gc"].values)[:, :, 0, :]                   # (cadeia, draw, controle)
    contrib = sd_kpi * np.einsum("cdk,tk->cdkt", g, z)                     # (cadeia, draw, controle, tempo)
    # coeficientes por unidade original do controle
    linhas = []
    for k, c in enumerate(dados_ctrl):
        x = df_aj[c].values.astype(float)
        sd_c = float(np.std(x)) if np.std(x) > 0 else 1.0
        sl = np.polyfit(x, z[:, k], 1)[0]; sd_c = 1.0 / sl                 # desvio-padrão usado pelo Meridian
        efeito_dp = sd_kpi * g[:, :, k].ravel()                            # KPI por +1 desvio-padrão do controle
        efeito_un = efeito_dp / sd_c                                       # KPI por +1 unidade do controle
        linhas.append(dict(controle=c, sd_controle=sd_c,
                           efeito_dp=efeito_dp.mean(), efeito_dp_lo=np.quantile(efeito_dp, .05), efeito_dp_hi=np.quantile(efeito_dp, .95),
                           efeito_un=efeito_un.mean(), efeito_un_lo=np.quantile(efeito_un, .05), efeito_un_hi=np.quantile(efeito_un, .95),
                           efeito_un_verdade=EFEITO_VERDADE[chave].get(c, np.nan)))
    # tratamento não-mídia (desconto): efeito por 1 p.p. de desconto, via contribuição incremental total
    x = df["desconto_medio_pct"].values.astype(float)
    inc = np.asarray(a.incremental_outcome(use_kpi=use_kpi, include_non_paid_channels=True,
                                           aggregate_geos=True, aggregate_times=True))[:, :, -1].ravel()
    ef = inc / x.sum()
    linhas.append(dict(controle="desconto_medio_pct", sd_controle=float(np.std(x)), efeito_dp=np.nan, efeito_dp_lo=np.nan, efeito_dp_hi=np.nan,
                       efeito_un=ef.mean(), efeito_un_lo=np.quantile(ef, .05), efeito_un_hi=np.quantile(ef, .95),
                       efeito_un_verdade=EFEITO_VERDADE[chave]["desconto_medio_pct"]))
    pd.DataFrame(linhas).to_csv(f"{OUT}/controles_{nome}.csv", index=False)
    # série temporal: baseline = nível/tendência + controles
    ev = a.expected_vs_actual_data(aggregate_geos=True, use_kpi=use_kpi)
    base = ev.baseline.sel(metric="mean").values
    c_med = contrib.mean(axis=(0, 1))                                      # (controle, tempo)
    t = pd.DataFrame(c_med.T, columns=dados_ctrl)
    t.insert(0, "nivel_tendencia", base - c_med.sum(axis=0))
    t.insert(0, "baseline", base)
    t.insert(0, "semana", df["semana"].values)
    t.to_csv(f"{OUT}/baseline_tempo_{nome}.csv", index=False)


# =====================================================================================
# cronogramas: mesma verba, jeitos diferentes de distribuir no tempo
# =====================================================================================
def cenarios(T):
    """Devolve {nome: vetor de pesos (len T, soma 1)}. T = horizonte da verba em semanas."""
    def blocos(on, off):
        v = np.zeros(T); i = 0
        while i < T:
            v[i:i + on] = 1; i += on + off
        return v / v.sum()
    def primeiras(n):
        v = np.zeros(T); v[:n] = 1; return v / v.sum()
    if T == 13:      # pergunta 1: "bomba" ou diluído, dentro de um trimestre
        return {"Diluído: 13 semanas iguais": primeiras(13), "8 semanas seguidas": primeiras(8),
                "1 mês seguido (4 semanas)": primeiras(4), "2 semanas seguidas": primeiras(2),
                "Bomba: 1 semana só": primeiras(1), "Pulsos: 1 semana sim, 1 não": blocos(1, 1)}
    else:            # pergunta 2: tudo em 1 mês ou diluído ao longo do ano (52 semanas)
        return {"Diluído: 52 semanas iguais": primeiras(52), "Semestre seguido (26 semanas)": primeiras(26),
                "Trimestre seguido (13 semanas)": primeiras(13), "1 mês seguido (4 semanas)": primeiras(4),
                "1 mês a cada trimestre": blocos(4, 9), "Meses alternados (4 sim, 4 não)": blocos(4, 4)}


def exportar_cronogramas(m, nome, use_kpi, chave):
    a = analyzer.Analyzer(m)
    v = verdade[chave]["canais"]
    gasto_sem = {c: df[f"gasto_{c}"].mean() for c in canais}                          # R$ mil/semana normal
    imp_por_mil = {c: df[f"impressoes_{c}"].sum() / df[f"gasto_{c}"].sum() for c in canais}
    gasto_max = {c: df[f"gasto_{c}"].max() for c in canais}
    INI = 30                                                                           # semana em que a verba começa
    linhas = []
    for T in (13, 52):
        for cen, pesos in cenarios(T).items():
            media = np.zeros((1, N, len(canais)))
            verd_c, pico_c = {}, {}
            for j, c in enumerate(canais):
                s = gasto_sem[c] * T * pesos                                           # R$ mil por semana do cenário
                media[0, INI:INI + T, j] = s * imp_por_mil[c]
                serie = np.zeros(N); serie[INI:INI + T] = s
                xa = adstock_geo(serie / gasto_sem[c], v[c]["decay"])
                verd_c[c] = float((v[c]["beta"] * hill(xa, v[c]["ec"], v[c]["slope"])).sum())
                pico_c[c] = float(s.max() / gasto_max[c])
            inc = np.asarray(a.incremental_outcome(new_data=tensors.DataTensors(media=jnp.asarray(media)), use_kpi=use_kpi,
                                                   aggregate_geos=True, aggregate_times=True,
                                                   include_non_paid_channels=False))   # (cadeia, draw, canal)
            inc = inc.reshape(-1, len(canais))
            for j, c in enumerate(canais):
                linhas.append(dict(horizonte=T, cenario=cen, canal=c, est=inc[:, j].mean(), lo=np.quantile(inc[:, j], .05),
                                   hi=np.quantile(inc[:, j], .95), verdade=verd_c[c], pico_vs_historico=pico_c[c]))
            tot = inc.sum(axis=1)
            linhas.append(dict(horizonte=T, cenario=cen, canal="TOTAL", est=tot.mean(), lo=np.quantile(tot, .05), hi=np.quantile(tot, .95),
                               verdade=sum(verd_c.values()), pico_vs_historico=max(pico_c.values())))
            # razão contra o cenário "diluído" (1º de cada horizonte), por draw, para o total
            if cen.startswith("Diluído"):
                dil, dil_ch = tot, inc
            razao = tot / dil
            for j, c in enumerate(canais):
                rc_ = inc[:, j] / dil_ch[:, j]
                linhas.append(dict(horizonte=T, cenario=cen, canal=f"RAZAO_{c}", est=rc_.mean(), lo=np.quantile(rc_, .05),
                                   hi=np.quantile(rc_, .95), verdade=np.nan, pico_vs_historico=np.nan))
            linhas.append(dict(horizonte=T, cenario=cen, canal="RAZAO_TOTAL", est=razao.mean(), lo=np.quantile(razao, .05),
                               hi=np.quantile(razao, .95), verdade=np.nan, pico_vs_historico=np.nan))
    pd.DataFrame(linhas).to_csv(f"{OUT}/cronogramas_{nome}.csv", index=False)


# =====================================================================================
def exportar_parametros(m, nome, chave):
    """Parâmetros de cada canal na posterior (média e IC 90%) ao lado do gabarito do gerador.
    alpha = decay do adstock; ec = ponto de meia-saturação (mídia dividida pela mediana); slope = inclinação do Hill;
    roi_m = ROI do canal; beta_m = coeficiente da mídia (escala do KPI padronizado)."""
    post = m.inference_data.posterior
    v = verdade[chave]["canais"]
    linhas = []
    for var, rot in [("alpha_m", "decay"), ("ec_m", "ec"), ("slope_m", "slope"), ("roi_m", "roi"), ("beta_m", "beta")]:
        if var not in post: continue
        x = post[var].values.reshape(-1, len(canais))            # (amostras, canais)
        for i, c in enumerate(canais):
            linhas.append({"parametro": rot, "canal": c, "media": x[:, i].mean(), "lo": np.percentile(x[:, i], 5),
                           "hi": np.percentile(x[:, i], 95), "sd": x[:, i].std(),
                           "verdade": v[c].get(rot if rot != "beta" else "beta", np.nan) if rot in ("decay", "ec", "slope", "roi") else np.nan})
    pd.DataFrame(linhas).to_csv(f"{OUT}/parametros_{nome}.csv", index=False)


def exportar(m, nome, use_kpi, chave, com_curvas=True):
    a = analyzer.Analyzer(m)
    acc = a.predictive_accuracy().to_dataframe().reset_index().pivot(index="metric", columns="evaluation_set", values="value")
    rh = a.rhat_summary()["max_r_hat"].max()
    pd.DataFrame({"modelo": nome, "mape_treino": acc.loc["MAPE", "Train"], "mape_teste": acc.loc["MAPE", "Test"],
                  "mape_total": acc.loc["MAPE", "All Data"], "r2_treino": acc.loc["R_Squared", "Train"],
                  "r2_teste": acc.loc["R_Squared", "Test"], "max_rhat": rh}, index=[0]).to_csv(f"{OUT}/acc_{nome}.csv", index=False)
    ev = a.expected_vs_actual_data(aggregate_geos=True, use_kpi=use_kpi)
    pd.DataFrame({
        "semana": ev.time.values, "real": ev.actual.values,
        "predito": ev.expected.sel(metric="mean").values, "ic_lo": ev.expected.sel(metric="ci_lo").values,
        "ic_hi": ev.expected.sel(metric="ci_hi").values, "baseline": ev.baseline.sel(metric="mean").values,
        "teste": holdout}).to_csv(f"{OUT}/fit_{nome}.csv", index=False)
    ms = visualizer.MediaSummary(m, use_kpi=use_kpi)
    cm = ms.contribution_metrics(include_non_paid=True)[["channel", "incremental_outcome", "pct_of_contribution"]]
    cm.to_csv(f"{OUT}/contrib_{nome}.csv", index=False)
    # contribuição do baseline com intervalo (saída do Meridian)
    bs = a.baseline_summary_metrics(use_kpi=use_kpi)
    pd.DataFrame({"metric": bs.metric.values,
                  **{f"{d}": bs["pct_of_contribution"].sel(distribution=d).values for d in bs.distribution.values}}
                 ).to_csv(f"{OUT}/baseline_{nome}.csv", index=False)
    sm = a.summary_metrics(use_kpi=use_kpi)
    post = lambda var, met: sm[var].sel(metric=met, distribution="posterior").to_series()
    v = verdade[chave]["canais"]
    if not com_curvas:
        cmi = cm.set_index("channel")
        pd.DataFrame({"canal": canais, "contrib_pct": [cmi.loc[c, "pct_of_contribution"] * 100 for c in canais],
                      "contrib_verdade": [v[c]["contribuicao_pct"] * 100 for c in canais]}).to_csv(f"{OUT}/retorno_{nome}.csv", index=False)
        return a
    tab = pd.DataFrame({"gasto_mil": sm["spend"].to_series(), "roi": post("roi", "mean"), "roi_lo": post("roi", "ci_lo"),
                        "roi_hi": post("roi", "ci_hi"), "mroi": post("mroi", "mean"),
                        "contrib_pct": post("pct_of_contribution", "mean"), "contrib_lo": post("pct_of_contribution", "ci_lo"),
                        "contrib_hi": post("pct_of_contribution", "ci_hi")}).drop(index="All Channels", errors="ignore")
    alpha = m.inference_data.posterior["alpha_m"].mean(dim=["chain", "draw"]).to_series()
    alpha.index = [canais[i] if isinstance(i, (int, np.integer)) else i for i in alpha.index]
    tab["contrib_verdade"] = [v[c]["contribuicao_pct"] * 100 for c in tab.index]
    tab["roi_verdade"] = [v[c]["roi"] for c in tab.index]
    tab["decay_verdade"] = [v[c]["decay"] for c in tab.index]
    tab["decay_estimado"] = alpha.reindex(tab.index).values
    tab.index.name = "canal"; tab.to_csv(f"{OUT}/retorno_{nome}.csv")
    # curvas de resposta até 3x o investimento atual (verdade incluída)
    mult = list(np.round(np.arange(0, 3.01, 0.1), 1))
    rc = a.response_curves(use_kpi=use_kpi, spend_multipliers=mult)
    linhas = []
    for c in canais:
        gasto_c = df[f"gasto_{c}"].values; media = gasto_c.mean(); vv = v[c]
        for k, mu in enumerate(rc.spend_multiplier.values):
            xa = adstock_geo(mu * gasto_c / media, vv["decay"])
            linhas.append(dict(canal=c, multiplicador=float(mu), gasto_mil=float(rc.spend.sel(channel=c).values[k]),
                               est=float(rc.incremental_outcome.sel(channel=c, metric="mean").values[k]),
                               lo=float(rc.incremental_outcome.sel(channel=c, metric="ci_lo").values[k]),
                               hi=float(rc.incremental_outcome.sel(channel=c, metric="ci_hi").values[k]),
                               verdade=float((vv["beta"] * hill(xa, vv["ec"], vv["slope"])).sum())))
    pd.DataFrame(linhas).to_csv(f"{OUT}/curvas_{nome}.csv", index=False)
    inc = a.incremental_outcome(aggregate_times=False, aggregate_geos=True, use_kpi=use_kpi, include_non_paid_channels=True)
    arr = np.asarray(inc).mean(axis=(0, 1))
    t = pd.DataFrame(arr, columns=canais + ["desconto_medio_pct"]); t.insert(0, "semana", df["semana"].values[-arr.shape[0]:])
    t.to_csv(f"{OUT}/contrib_tempo_{nome}.csv", index=False)
    exportar_controles(m, nome, use_kpi, chave, ctrl_aj)
    exportar_cronogramas(m, nome, use_kpi, chave)
    return a


if __name__ == "__main__":
    tipos = [("novas_contas", "contas", "non_revenue", True, prior_distribution.lognormal_dist_from_range(1, 25)),
             ("receita_mil", "receita", "revenue", False, prior_distribution.lognormal_dist_from_range(0.3, 8))]
    for chave, nome, tipo, use_kpi, roi_prior in tipos:
        print(f"[{nome}] modelo ingênuo...")
        m0 = ajustar(carregar(df, chave, tipo, ctrl_basicos), spec.ModelSpec(max_lag=8, holdout_id=holdout))
        exportar(m0, f"ingenuo_{nome}", use_kpi, chave, com_curvas=False)
        exportar_parametros(m0, f"ingenuo_{nome}", chave)
        print(f"[{nome}] modelo ajustado...")
        m1 = ajustar(carregar(df_aj, chave, tipo, ctrl_aj),
                     spec.ModelSpec(prior=prior_distribution.PriorDistribution(roi_m=roi_prior), max_lag=8, knots=2, holdout_id=holdout))
        exportar(m1, nome, use_kpi, chave)
        exportar_parametros(m1, nome, chave)
    import meridian
    json.dump({"meridian": meridian.__version__, "semanas": N, "semanas_teste": SEMANAS_TESTE,
               "chains": N_CHAINS, "adapt": N_ADAPT, "burnin": N_BURNIN, "keep": N_KEEP,
               "midia_total_verdade_contas": verdade["novas_contas"]["midia_total"] / verdade["novas_contas"]["y_total"] * 100},
              open(f"{OUT}/meta.json", "w"), indent=2)
    print("ok ->", OUT)
