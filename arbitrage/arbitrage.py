"""
Motor de detecção de arbitragem.

Fórmulas:
  sum_implied = Σ(1/odd_i)   ← soma das probabilidades implícitas

  Arbitragem existe quando: sum_implied < 1.0
  Lucro %  = (1/sum_implied - 1) × 100
  Stake_i  = total_stake × (1/odd_i) / sum_implied
  Retorno  = Stake_i × odd_i  (idêntico para todas as pernas)
"""
from datetime import datetime
from arbitrage.models import Event, ArbitrageLeg, ArbitrageOpportunity
from arbitrage import config


def find_arbitrage(
    events: list[Event],
    total_stake: float | None = None,
    min_profit_pct: float | None = None,
) -> list[ArbitrageOpportunity]:
    """
    Varre uma lista de eventos e retorna todas as oportunidades de arbitragem
    ordenadas por lucro decrescente.

    Estratégia: usa a **melhor odd disponível** para cada resultado entre
    todas as casas monitoradas, combinando o mercado h2h.
    """
    stake = total_stake if total_stake is not None else config.TOTAL_STAKE
    min_pct = min_profit_pct if min_profit_pct is not None else config.MIN_PROFIT_PCT

    opportunities: list[ArbitrageOpportunity] = []

    for event in events:
        # Filtra somente mercado h2h
        h2h_odds = [o for o in event.odds if o.market == "h2h"]
        if not h2h_odds:
            continue

        # Melhor odd por resultado: {outcome -> (bookmaker_key, bookmaker, price)}
        best: dict[str, tuple[str, str, float]] = {}
        for odd in h2h_odds:
            if odd.outcome not in best or odd.price > best[odd.outcome][2]:
                best[odd.outcome] = (odd.bookmaker_key, odd.bookmaker, odd.price)

        # Precisa de pelo menos 2 resultados distintos
        if len(best) < 2:
            continue

        # Soma das probabilidades implícitas
        sum_implied = sum(1.0 / price for _, _, price in best.values())

        # Arbitragem existe apenas se sum < 1
        if sum_implied >= 1.0:
            continue

        profit_pct = (1.0 / sum_implied - 1.0) * 100.0
        if profit_pct < min_pct:
            continue

        # Monta as pernas
        legs: list[ArbitrageLeg] = []
        for outcome, (bk_key, bk_name, price) in best.items():
            leg_stake = stake * (1.0 / price) / sum_implied
            leg_return = leg_stake * price  # = stake / sum_implied (garantido)
            legs.append(ArbitrageLeg(
                bookmaker=bk_name,
                bookmaker_key=bk_key,
                outcome=outcome,
                odds=price,
                stake=round(leg_stake, 2),
                return_amount=round(leg_return, 2),
                implied_prob=round(1.0 / price * 100, 2),
                link=config.get_bookmaker_link(bk_key),
            ))

        # Ordena pernas: home, draw, away (ordem natural do futebol)
        _ORDER = {event.home_team: 0, "Draw": 1, event.away_team: 2}
        legs.sort(key=lambda l: _ORDER.get(l.outcome, 99))

        opportunities.append(ArbitrageOpportunity(
            event=event,
            legs=legs,
            total_stake=round(stake, 2),
            guaranteed_profit=round(stake * (1.0 / sum_implied - 1.0), 2),
            profit_pct=round(profit_pct, 3),
            sum_implied=round(sum_implied, 6),
            found_at=datetime.utcnow(),
        ))

    return sorted(opportunities, key=lambda o: o.profit_pct, reverse=True)
