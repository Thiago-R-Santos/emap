"""
Pinnacle — API Arcadia (não-oficial mas estável e bem conhecida).

Pinnacle é a referência do mercado: não bloqueia arbitrageiros,
tem as melhores odds e a API interna é JSON puro.

Endpoints usados:
  /0.1/sports                          — lista esportes
  /0.1/sports/{sportId}/leagues        — ligas por esporte
  /0.1/leagues/{leagueId}/matchups     — jogos/matchups
  /0.1/leagues/{leagueId}/markets/straight — odds moneyline

IDs de esportes relevantes:
  29 = Soccer  |  4 = Basketball  |  3 = Baseball
  12 = Tennis  |  15 = MMA        |  18 = American Football
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from arbitrage.scrapers.base import BaseScraper, _browser_headers, _get_json, utc_now
from arbitrage.models import Event, Odd

logger = logging.getLogger(__name__)

_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
_REFERER = "https://www.pinnacle.com/"

# Esportes monitorados: (sportId, nome_display)
_SPORTS = [
    (29, "Futebol"),
    (4,  "Basquete"),
    (12, "Tênis"),
    (15, "MMA"),
]

# Ligas brasileiras e relevantes por esporte (liga ID Pinnacle)
# Atualizado periodicamente — Pinnacle mantém IDs estáveis por anos
_SOCCER_LEAGUE_IDS = [
    1980,   # Brazil Série A (Campeonato Brasileiro)
    2627,   # Brazil Série B
    2196,   # Brazil Copa do Brasil
    2190,   # CONMEBOL Copa Libertadores
    2191,   # CONMEBOL Copa Sudamericana
    1980,   # Brasileirão Série A
    2271,   # Premier League
    2276,   # La Liga
    2374,   # Champions League
]

_NBA_LEAGUE_IDS = [487]  # NBA


def _parse_datetime(s: str | None) -> datetime:
    if not s:
        return utc_now()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return utc_now()


class PinnacleScraper(BaseScraper):
    REQUEST_DELAY = 0.5  # Pinnacle tolera requisições mais frequentes

    @property
    def bookmaker_key(self) -> str:
        return "pinnacle"

    @property
    def bookmaker_name(self) -> str:
        return "Pinnacle"

    async def fetch_events(self, client: httpx.AsyncClient) -> list[Event]:
        headers = _browser_headers(referer=_REFERER, extra={
            "X-Api-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R",  # chave pública conhecida
            "Origin": "https://www.pinnacle.com",
        })

        # Busca ligas de futebol e basquete em paralelo
        soccer_task = self._fetch_sport_events(client, headers, sport_id=29, league_ids=_SOCCER_LEAGUE_IDS)
        basket_task = self._fetch_sport_events(client, headers, sport_id=4, league_ids=_NBA_LEAGUE_IDS)

        results = await asyncio.gather(soccer_task, basket_task, return_exceptions=True)

        events: list[Event] = []
        for r in results:
            if isinstance(r, list):
                events.extend(r)

        return events

    async def _fetch_sport_events(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        sport_id: int,
        league_ids: list[int],
    ) -> list[Event]:
        events: list[Event] = []

        for league_id in set(league_ids):
            # Matchups (jogos)
            matchups_data = await _get_json(
                client,
                f"{_BASE}/leagues/{league_id}/matchups",
                params={"withSpecials": "false", "brandId": "0"},
                headers=headers,
            )
            if not matchups_data:
                continue

            # Odds straight (moneyline / 1X2)
            odds_data = await _get_json(
                client,
                f"{_BASE}/leagues/{league_id}/markets/straight",
                params={"brandId": "0"},
                headers=headers,
            )

            league_events = self._parse_league(matchups_data, odds_data, sport_id, league_id)
            events.extend(league_events)
            await asyncio.sleep(self.REQUEST_DELAY)

        return events

    def _parse_league(
        self,
        matchups: list,
        odds_raw: list | None,
        sport_id: int,
        league_id: int,
    ) -> list[Event]:
        # Indexar odds por matchupId → {outcome_type: price}
        # Pinnacle odds format: [{ matchupId, prices: [{designation, price}] }]
        odds_index: dict[int, dict[str, float]] = {}
        if odds_raw:
            for market in odds_raw:
                mid = market.get("matchupId") or market.get("id")
                if not mid:
                    continue
                prices = market.get("prices", [])
                outcome_map: dict[str, float] = {}
                for p in prices:
                    designation = p.get("designation", "").lower()  # home/away/draw
                    price = p.get("price")
                    if designation and price:
                        outcome_map[designation] = float(price)
                if outcome_map:
                    odds_index[mid] = outcome_map

        sport_name_map = {29: "Futebol", 4: "Basquete", 12: "Tênis", 15: "MMA"}
        sport_title = sport_name_map.get(sport_id, str(sport_id))

        events: list[Event] = []
        for m in matchups:
            # Pula eventos especiais/props
            if m.get("type") not in ("matchup", None):
                continue
            if m.get("isLive"):
                continue  # ao vivo tem lógica diferente

            mid = m.get("id")
            home = m.get("home", {}).get("name", "")
            away = m.get("away", {}).get("name", "")
            league_name = m.get("league", {}).get("name", f"Liga {league_id}")
            start_time = _parse_datetime(m.get("startTime"))

            if not home or not away or not mid:
                continue

            outcome_map = odds_index.get(mid, {})
            if not outcome_map:
                continue

            # Mapeia designações Pinnacle → nomes de outcome padronizados
            # home/away/draw  →  home_team/away_team/Draw
            designation_to_name = {
                "home": home,
                "away": away,
                "draw": "Draw",
            }

            odds: list[Odd] = []
            for desig, price in outcome_map.items():
                outcome_name = designation_to_name.get(desig, desig)
                if price > 1.0:
                    odds.append(Odd(
                        bookmaker=self.bookmaker_name,
                        bookmaker_key=self.bookmaker_key,
                        market="h2h",
                        outcome=outcome_name,
                        price=round(price, 3),
                        last_updated=utc_now(),
                    ))

            if len(odds) >= 2:
                events.append(Event(
                    event_id=f"pinnacle-{mid}",
                    sport_key=f"sport_{sport_id}",
                    sport_title=sport_title,
                    league=league_name,
                    home_team=home,
                    away_team=away,
                    commence_time=start_time,
                    odds=odds,
                ))

        return events
