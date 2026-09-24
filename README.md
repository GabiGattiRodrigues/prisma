# Prisma: MMM com Meridian (fintech, dados sintéticos com verdade conhecida)

Reconstrução pública de um projeto real de Marketing Mix Modeling feito com a biblioteca [Meridian](https://developers.google.com/meridian) (Google).
Dois modelos, cada um com sua versão **ingênua** (configuração padrão) e **ajustada**:

- **Novas contas** (KPI de volume, `non_revenue`)
- **Receita** (KPI monetário, `revenue`)

Os dados são sintéticos e o gerador guarda a verdade (ROI, adstock, saturação de cada canal), então dá para conferir o que o modelo acerta e o que erra.

## O que o projeto mostra
- Modelo com MAPE bom e atribuição errada (o problema original) e como ajustar priors, controles e knots.
- Decomposição completa: canais + baseline + controles (sazonalidade, promoção, macro, feriados).
- Curvas de resposta e retorno marginal com regra de saturação.
- **Quanto e onde investir**: dada uma verba X, como distribuir entre canais (com checagem contra as curvas verdadeiras).
- **Parâmetros**: configuração escolhida e o que o modelo aprendeu (ROI, decay, saturação, controles), com o gabarito ao lado.
- **Recomendações**: resumo acionável dos melhores cenários das simulações (cronograma e alocação), com ressalvas.
- **Quando investir**: bomba de uma vez ou diluído? Tudo em 1 mês ou espalhado? No geral e por campanha, com IC 90% e verdade.

## Ver o app (Streamlit)
Dê dois cliques em `iniciar.bat` (instala as dependências e abre o app). O app lê os resultados pré-calculados em `resultados/`; nenhum modelo roda ao vivo.

## Notebook no Colab (somente leitura)
[Abrir no Colab](https://colab.research.google.com/github/GabiGattiRodrigues/prisma/blob/main/mmm_meridian.ipynb). O link abre uma cópia: o original no GitHub não é editado por quem abre. Requer o repositório público.
`RAPIDO = True` roda em ~2 min para testar; `False` (padrão) leva ~5 min em CPU.

## Arquivos
- `app.py`, `iniciar.bat`, `requirements.txt`, `.streamlit/`: app Streamlit
- `resultados/`: saídas dos modelos que o app lê (geradas por `exportar_resultados.py`)
- `mmm_meridian.ipynb`: notebook completo e comentado
- `exportar_resultados.py`: reajusta os 4 modelos e regrava `resultados/` (precisa de `pip install google-meridian`)
- `mmm_dados_sinteticos.csv` e `verdade_conhecida.json`: dados semanais (156 semanas) e parâmetros plantados
- `gerar_dados.py`: gerador dos dados (semente fixa)

## Limitações (deixadas visíveis de propósito)
Meta superestimado (IC exclui a verdade), decaimento mal identificado, desemprego confundido com tendência, e a sugestão de alocação pode ficar pior que a proporcional nas curvas verdadeiras.
