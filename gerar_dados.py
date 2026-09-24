"""
Gerador de dados sintéticos para o projeto de MMM (Meridian).

Ideia: a gente CONHECE a verdade (adstock, saturação, contribuição de cada canal),
então dá pra checar no final se o Meridian recuperou o que foi plantado.
Cenário: fintech. KPI 1 = novas contas abertas; KPI 2 = receita gerada (R$).
Granularidade: semanal, nacional, 3 anos (156 semanas).
"""
import json
import numpy as np
import pandas as pd
from datetime import date, timedelta
from dateutil.easter import easter

SEED = 42
rng = np.random.default_rng(SEED)
N = 156
datas = pd.date_range("2023-01-02", periods=N, freq="W-MON")  # semanas começando na segunda

# ---------------------------------------------------------------- feriados nacionais
def feriados_nacionais(anos):
    fer = set()
    for a in anos:
        pascoa = easter(a)
        fixos = [(1,1),(4,21),(5,1),(9,7),(10,12),(11,2),(11,15),(12,25)]
        if a >= 2024: fixos.append((11,20))
        fer |= {date(a,m,d) for m,d in fixos}
        fer |= {pascoa - timedelta(days=2),   # sexta santa
                pascoa - timedelta(days=48),  # segunda de carnaval
                pascoa - timedelta(days=47),  # terça de carnaval
                pascoa + timedelta(days=60)}  # corpus christi
    return fer
FER = feriados_nacionais({2023, 2024, 2025, 2026})
n_feriados = np.array([sum((d.date() + timedelta(days=i)) in FER for i in range(7)) for d in datas])

# ---------------------------------------------------------------- calendário de promoções
# Promo pode cair em QUALQUER dia da semana -> o que entra no modelo é o desconto médio
# diário da semana (dias sem promo = 0). Ex.: 2 dias a 20% => 20*2/7 = 5.7%.
desc_diario = np.zeros((N, 7))
for w in range(N):
    if rng.random() < 0.45:                       # semana com alguma promo
        k = rng.choice([1, 2, 3], p=[.5, .35, .15])
        dias = rng.choice(7, size=k, replace=False)
        desc_diario[w, dias] = rng.choice([10, 15, 20, 25, 30], size=k)
mes = datas.month.values
black_friday = np.array([1 if (d.month == 11 and 22 <= d.day + 6 and d.day >= 20 and d.day <= 28) else 0 for d in datas])
for w in np.where(black_friday == 1)[0]:
    desc_diario[w, :] = 30.0                      # Black Friday: 30% a semana toda
desconto_medio = desc_diario.mean(axis=1)         # % médio de desconto na semana
promo_ativa = (desconto_medio > 0).astype(float)

# ---------------------------------------------------------------- macro
t = np.arange(N)
desemprego = 8.8 - 2.4 * (t / N) + 0.25 * np.sin(t / 9) + np.cumsum(rng.normal(0, .03, N)) * .5
desemprego = np.round(desemprego, 2)
ipca = 5.2 + 1.0 * np.sin(t / 30) + np.cumsum(rng.normal(0, .04, N)) * .6
ipca = np.round(ipca, 2)

# ---------------------------------------------------------------- mídia
# canal: (gasto médio semanal R$ mil, CPM R$, decay adstock, ec (rel. à média), slope)
CANAIS = {
    "google_search":   dict(gasto=90,  cpm=45, decay=0.20, ec=1.0, slope=1.6, flight=0.05),
    "meta":            dict(gasto=120, cpm=28, decay=0.45, ec=1.2, slope=1.4, flight=0.15),
    "tiktok":          dict(gasto=60,  cpm=18, decay=0.50, ec=0.9, slope=2.0, flight=0.30),
    "youtube":         dict(gasto=80,  cpm=22, decay=0.65, ec=1.4, slope=1.3, flight=0.35),
    "afiliados":       dict(gasto=50,  cpm=35, decay=0.15, ec=0.8, slope=1.1, flight=0.10),
    "display_programatico": dict(gasto=40, cpm=9, decay=0.40, ec=0.7, slope=1.2, flight=0.20),
}
# efeito máx. semanal (contas) e (R$ mil de receita) na saturação total — DIFERENTE por KPI de propósito:
# afiliados traz muita conta mas pouca receita; youtube o contrário.
BETA_CONTAS  = dict(google_search=1700, meta=1500, tiktok=900, youtube=700, afiliados=1300, display_programatico=350)
BETA_RECEITA = dict(google_search=560,  meta=380,  tiktok=190, youtube=520, afiliados=150, display_programatico=90)
MAX_LAG = 8

def adstock(x, decay, L=MAX_LAG):
    w = decay ** np.arange(L)
    w = w / w.sum()                                # pesos normalizados (como o Meridian)
    out = np.zeros_like(x)
    for i in range(len(x)):
        for l in range(L):
            if i - l >= 0: out[i] += w[l] * x[i - l]
    return out
def hill(x, ec, slope):
    return x**slope / (x**slope + ec**slope)

sazon = 1 + 0.10 * np.sin(2 * np.pi * (t - 8) / 52) + 0.08 * (mes == 11) + 0.05 * (mes == 12) - 0.05 * (mes == 2)
spend, impr = {}, {}
for c, p in CANAIS.items():
    # flighting: canal liga/desliga em blocos (dá variação pro modelo aprender a curva)
    ligado = np.ones(N); i = 0
    while i < N:
        dur = rng.integers(3, 9)
        if rng.random() < p["flight"] * 2:
            ligado[i:i+dur] = rng.uniform(0.0, 0.35)
        i += dur
    ruido = np.exp(rng.normal(0, 0.18, N))
    # multicolinearidade: mídia sobe junto com promoção e Black Friday (o problema clássico)
    alavanca = 1 + 0.012 * desconto_medio * 3 + 0.5 * black_friday
    s = p["gasto"] * sazon * ligado * ruido * alavanca * (1 + 0.15 * t / N)
    spend[c] = np.round(s, 2)
    cpm = p["cpm"] * np.exp(rng.normal(0, 0.06, N)) * (1 + 0.1 * t / N)
    impr[c] = np.round(s * 1000 / cpm * 1000).astype(np.int64)  # impressões = R$ mil*1000 / CPM * 1000

# ---------------------------------------------------------------- KPI
def contribuicoes(beta):
    out = {}
    for c, p in CANAIS.items():
        m = spend[c].mean()
        xa = adstock(spend[c] / m, p["decay"])
        out[c] = beta[c] * hill(xa, p["ec"], p["slope"]) 
    return out

def gerar_kpi(base0, cresc, beta, coefs, ruido_cv, escala_receita=1.0):
    contrib = contribuicoes(beta)
    baseline = base0 * (1 + cresc * t / N) * sazon
    macro = coefs["desemp"] * (desemprego - desemprego.mean()) + coefs["ipca"] * (ipca - ipca.mean())
    promo = coefs["desc"] * desconto_medio
    fer = coefs["fer"] * n_feriados + coefs["bf"] * black_friday
    mu = baseline + macro + promo + fer + sum(contrib.values())
    y = mu * np.exp(rng.normal(0, ruido_cv, N))
    return y, contrib, dict(baseline=baseline, macro=macro, promo=promo, feriados=fer)

y_contas, c_contas, o_contas = gerar_kpi(
    5200, 0.25, BETA_CONTAS, dict(desemp=-280, ipca=-120, desc=85, fer=-450, bf=900), 0.035)
y_rec, c_rec, o_rec = gerar_kpi(
    2100, 0.30, BETA_RECEITA, dict(desemp=-110, ipca=-40, desc=22, fer=-160, bf=210), 0.04)

df = pd.DataFrame({"semana": datas.strftime("%Y-%m-%d"),
                   "novas_contas": np.round(y_contas).astype(int),
                   "receita_mil": np.round(y_rec, 1)})
for c in CANAIS:
    df[f"impressoes_{c}"] = impr[c]
for c in CANAIS:
    df[f"gasto_{c}"] = spend[c]
df["desconto_medio_pct"] = np.round(desconto_medio, 2)
df["desemprego_pct"] = desemprego
df["ipca_12m_pct"] = ipca
df["n_feriados_nacionais"] = n_feriados
df["black_friday"] = black_friday
df.to_csv("mmm_dados_sinteticos.csv", index=False)

# ---------------------------------------------------------------- verdade conhecida
def resumo(contrib, outros, y):
    tot_media = sum(v.sum() for v in contrib.values())
    res = {"y_total": float(y.sum()), "midia_total": float(tot_media),
           "baseline_pct_total": float(outros["baseline"].sum() / y.sum())}
    res["canais"] = {c: dict(contribuicao_total=float(v.sum()),
                             contribuicao_pct=float(v.sum() / y.sum()),
                             gasto_total_mil=float(spend[c].sum()),
                             roi=float(v.sum() / spend[c].sum()),
                             beta=float((BETA_CONTAS if contrib is c_contas else BETA_RECEITA)[c]),
                             decay=CANAIS[c]["decay"], ec=CANAIS[c]["ec"], slope=CANAIS[c]["slope"])
                     for c, v in contrib.items()}
    return res
verdade = {"novas_contas": resumo(c_contas, o_contas, y_contas),
           "receita_mil": resumo(c_rec, o_rec, y_rec)}
json.dump(verdade, open("verdade_conhecida.json", "w"), indent=2, ensure_ascii=False)

if __name__ == "__main__":
    print(df.describe().T[["mean", "min", "max"]].round(1))
    for k, v in verdade.items():
        print("\n==", k, "| baseline %:", round(v["baseline_pct_total"] * 100, 1), "| mídia %:", round(v["midia_total"] / v["y_total"] * 100, 1))
        for c, d in v["canais"].items():
            print(f"  {c:22s} contrib {d['contribuicao_pct']*100:5.1f}%  ROI {d['roi']:.3f}")
    print("corr(desconto, gasto meta):", np.corrcoef(desconto_medio, spend["meta"])[0, 1].round(2))
