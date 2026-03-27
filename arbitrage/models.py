from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Odd:
    bookmaker: str
    bookmaker_key: str
    market: str        # h2h, spreads, totals
    outcome: str       # home_team, away_team, Draw
    price: float
    last_updated: datetime

    @property
    def implied_prob(self) -> float:
        return 1.0 / self.price if self.price > 0 else 1.0


@dataclass
class Event:
    event_id: str
    sport_key: str
    sport_title: str
    league: str
    home_team: str
    away_team: str
    commence_time: datetime
    odds: list = field(default_factory=list)

    @property
    def title(self) -> str:
        return f"{self.home_team} vs {self.away_team}"

    @property
    def is_live(self) -> bool:
        return self.commence_time <= datetime.utcnow()


@dataclass
class ArbitrageLeg:
    bookmaker: str
    bookmaker_key: str
    outcome: str
    odds: float
    stake: float        # stake ótima para garantir lucro
    return_amount: float  # retorno bruto se essa perna ganhar
    implied_prob: float
    link: str           # link direto para a casa de apostas


@dataclass
class ArbitrageOpportunity:
    event: Event
    legs: list          # list[ArbitrageLeg]
    total_stake: float
    guaranteed_profit: float
    profit_pct: float   # lucro garantido em %
    sum_implied: float  # soma das probabilidades implícitas (< 1.0)
    found_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def quality(self) -> str:
        if self.profit_pct >= 3.0:
            return "EXCELENTE"
        elif self.profit_pct >= 1.5:
            return "ÓTIMA"
        elif self.profit_pct >= 0.5:
            return "BOA"
        else:
            return "MARGINAL"

    @property
    def quality_color(self) -> str:
        if self.profit_pct >= 3.0:
            return "bold green"
        elif self.profit_pct >= 1.5:
            return "green"
        elif self.profit_pct >= 0.5:
            return "yellow"
        else:
            return "dim yellow"
