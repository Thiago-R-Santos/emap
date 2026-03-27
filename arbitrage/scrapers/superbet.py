"""
Superbet Brasil — API interna JSON.

A Superbet tem presença crescente no Brasil. Usa API REST interna.

Endpoint:
  GET https://superbet.com.br/api/offer/v2/events
      ?sportId={sportId}&leagueId={leagueId}&lang=pt-BR
"""
import asyncio
import logging

import httpx

from arbitrage.scrapers.base import BaseScraper, _browser_headers, _get_json, utc_now
from arbitrage.models import Event, Odd
from arbitrage.scrapers.betano import _parse_dt

logger = logging.getLogger(__name__)

_BASE = "https://superbet.com.br"
_REFERER = "https://superbet.com.br/apostas-esportivas/"

# (sport_id, league_id, display_name)
_LEAGUES = [
    (1, 1959, "Campeonato Brasileiro"),
    (1, 572,  "Copa do Brasil"),
    (1, 244,  "Copa Libertadores"),
    (1, 245,  "Copa Sudamericana"),
    (1, 1,    "Premier League"),
    (1, 8,    "Champions League"),
    (2, 149,  "NBA"),
]


class SuperbetScraper(BaseScraper):
    REQUEST_DELAY = 1.5

    @property
    def bookmaker_key(self) -> str:
        return "superbet"

    @property
    def bookmaker_name(self) -> str:
        return "Superbet"

    async def fetch_events(self, client: httpx.AsyncClient) -> list[Event]:
        events: list[Event] = []
        headers = _browser_headers(referer=_REFERER, extra={
            "Origin": _BASE,
            "X-Requested-With": "XMLHttpRequest",
        })

        for sport_id, league_id, display in _LEAGUES:
            data = await _get_json(
                client,
                f"{_BASE}/api/offer/v2/events",
                params={"sportId": sport_id, "leagueId": league_id, "lang": "pt-BR"},
                headers=headers,
            )

            if not data:
                # Tenta endpoint alternativo
                data = await _get_json(
                    client,
                    f"{_BASE}/api/v1/sports/{sport_id}/leagues/{league_id}/events",
                    params={"lang": "pt-BR"},
                    headers=headers,
                )

            if data:
                parsed = self._parse_response(data, display, sport_id)
                events.extend(parsed)

            await asyncio.sleep(self.REQUEST_DELAY)

        return events

    def _parse_response(self, data: dict | list, league_display: str, sport_id: int) -> list[Event]:
        sport_map = {1: "Futebol", 2: "Basquete"}
        sport_title = sport_map.get(sport_id, "Esportes")

        if isinstance(data, dict):
            events_raw = data.get("data") or data.get("events") or data.get("items") or []
        else:
            events_raw = data

        result: list[Event] = []
        for ev in events_raw:
            try:
                home = ev.get("homeTeam") or ev.get("home_team") or ev.get("team1") or ""
                away = ev.get("awayTeam") or ev.get("away_team") or ev.get("team2") or ""
                eid  = str(ev.get("id") or ev.get("eventId") or "")
                start = _parse_dt(ev.get("startDate") or ev.get("start") or ev.get("date"))

                if not home or not away:
                    continue

                odds: list[Odd] = []
                # Superbet agrupa odds em .markets ou .bets
                for market in (ev.get("markets") or ev.get("bets") or []):
                    mtype = str(market.get("type") or market.get("marketType") or "").lower()
                    if mtype and mtype not in ("1x2", "resultado_final", "moneyline", "1", "match_result"):
                        continue

                    for sel in (market.get("selections") or market.get("outcomes") or []):
                        name  = sel.get("name") or sel.get("label") or ""
                        price = sel.get("odds") or sel.get("price") or sel.get("value") or 0
                        try:
                            price = float(price)
                        except (TypeError, ValueError):
                            continue
                        if price <= 1.0:
                            continue

                        name_l = str(name).lower()
                        if name_l in ("empate", "draw", "x"):
                            outcome = "Draw"
                        elif name_l in ("1", "casa", "home") or name.lower() == home.lower():
                            outcome = home
                        elif name_l in ("2", "fora", "away") or name.lower() == away.lower():
                            outcome = away
                        else:
                            outcome = name

                        odds.append(Odd(
                            bookmaker=self.bookmaker_name,
                            bookmaker_key=self.bookmaker_key,
                            market="h2h",
                            outcome=outcome,
                            price=round(price, 3),
                            last_updated=utc_now(),
                        ))

                if len(odds) >= 2:
                    result.append(Event(
                        event_id=f"superbet-{eid}",
                        sport_key=f"sport_{sport_id}",
                        sport_title=sport_title,
                        league=league_display,
                        home_team=home,
                        away_team=away,
                        commence_time=start,
                        odds=odds,
                    ))

            except Exception as e:
                logger.debug("Superbet: erro ao parsear evento: %s", e)
                continue

        return result
