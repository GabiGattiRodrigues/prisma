"""
Calibração do MMM com um experimento (lift test) simulado.

Ideia: o MMM só vê dado observacional. Quando um canal sobe junto com outra coisa (promoção, demanda),
o modelo não consegue separar quem causou o quê. Um experimento separa: liga/desliga o canal de propósito
e mede o efeito direto. Esse resultado entra no Meridian como PRIOR DE ROI do canal.

Como o dado é sintético, dá para simular o experimento usando a fórmula verdadeira do gerador:
  - escolho uma janela de 6 semanas no período de treino
  - "desligo" o canal nessas semanas e calculo quantas contas (ou R$) deixam de existir, incluindo o efeito
    que continuaria nas semanas seguintes (adstock)
  - ROI do experimento = efeito perdido / verba que deixou de ser gasta
  - somo um erro de medição de 15% (experimento real também tem incerteza)

Depois reajusto o modelo AJUSTADO trocando só o prior de ROI do canal testado:
  - canal testado: LogNormal com 95% em ROI_experimento ± 1,96 x erro
  - demais canais: o mesmo prior do modelo ajustado

Canais testados: o canal que o modelo ajustado mais erra em cada KPI (Meta em novas contas, YouTube em receita).

Uso:  python calibrar.py      (~5 min em CPU)
"""
import json
import numpy as np
import pandas as pd
from exportar_resultados import (df, df_aj, verdade, canais, holdout, ctrl_aj, carregar, ajustar, exportar,
                                 exportar_parametros, adstock_geo, hill, spec, prior_distribution, OUT)

JANELA = (60, 66)          # semanas 60 a 65 (dentro do treino)
CARRY = 8                  # semanas depois da janela em que o efeito ainda aparece
ERRO_REL = 0.15            # erro-padrão do experimento, relativo ao efeito
rng = np.random.default_rng(7)


def experimento(canal):
    """Efeito verdadeiro de desligar o canal na janela, com erro de medição."""
    p = verdade_chave[canal]; g = df[f"gasto_{canal}"].values.astype(float); m = g.mean()
    def contrib(gasto): return p["beta"] * hill(adstock_geo(gasto / m, p["decay"]), p["ec"], p["slope"])
    desligado = g.copy(); desligado[JANELA[0]:JANELA[1]] = 0
    fim = JANELA[1] + CARRY
    efeito = (contrib(g) - contrib(desligado))[JANELA[0]:fim].sum()
    verba = g[JANELA[0]:JANELA[1]].sum()
    roi_real = efeito / verba
    roi_medido = roi_real * (1 + rng.normal(0, ERRO_REL))
    ep = ERRO_REL * roi_medido
    return dict(canal=canal, semana_ini=JANELA[0], semana_fim=JANELA[1] - 1, verba_mil=verba, efeito_real=efeito,
                roi_janela_real=roi_real, roi_medido=roi_medido, erro_padrao=ep,
                ic95_lo=roi_medido - 1.96 * ep, ic95_hi=roi_medido + 1.96 * ep,
                roi_verdade_periodo=verdade_chave[canal]["roi"])


if __name__ == "__main__":
    tipos = [("novas_contas", "contas", "non_revenue", True, "meta", (1, 25)),
             ("receita_mil", "receita", "revenue", False, "youtube", (0.3, 8))]
    for chave, nome, tipo, use_kpi, canal_teste, faixa in tipos:
        verdade_chave = verdade[chave]["canais"]
        exp = experimento(canal_teste)
        pd.DataFrame([exp]).to_csv(f"{OUT}/experimento_{nome}.csv", index=False)
        print(nome, {k: round(v, 3) if isinstance(v, float) else v for k, v in exp.items()}, flush=True)
        lo = [max(exp["ic95_lo"], 0.05) if c == canal_teste else faixa[0] for c in canais]
        hi = [exp["ic95_hi"] if c == canal_teste else faixa[1] for c in canais]
        prior = prior_distribution.PriorDistribution(roi_m=prior_distribution.lognormal_dist_from_range(lo, hi))
        m = ajustar(carregar(df_aj, chave, tipo, ctrl_aj),
                    spec.ModelSpec(prior=prior, max_lag=8, knots=2, holdout_id=holdout))
        exportar(m, f"calib_{nome}", use_kpi, chave)
        exportar_parametros(m, f"calib_{nome}", chave)
        print("ok", nome, flush=True)
