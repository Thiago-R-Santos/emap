"""
Betsul — API interna JSON.

Casa brasileira popular, API relativamente acessível.
Endpoint:
  GET https://www.betsul.com/api/sports/events?sportId=1&competitionId=...
"""
import asyncio
import logging

import httpx

from arbitrage.scrapers.base import BaseScraper, _browser_headers, _get_json, utc_now
from arbitrage.models import Event, Odd
from arbitrage.scrapers.betano import _parse_dt

logger = logging.getLogger(__name__)

_BASE = "https://www.betsul.com"
_REFERER = "https://www.betsul.com/sports"

_LEAGUES = [
    (1, 45,  "Campeonato Brasileiro"),
    (1, 46,  "Copa do Brasil"),
    (1, 544, "Copa Libertadores"),
    (1, 545, "Copa Sudamericana"),
    (1, 8,   "Premier League"),
    (3, 249, "NBA"),
]


class BetsulScraper(BaseScraper):
    REQUEST_DELAY = 1.5

    @property
    def bookmaker_key(self) -> str:
        return "betsul"

    @property
    def bookmaker_name(self) -> str:
        return "Betsul"

    async def fetch_events(self, client: httpx.AsyncClient) -> list[Event]:
        events: list[Event] = []
        headers = _browser_headers(referer=_REFERER)

        for sport_id, comp_id, display in _LEAGUES:
            data = await _get_json(
                client,
                f"{_BASE}/api/sports/events",
                params={"sportId": sport_id, "competitionId": comp_id, "lang": "pt"},
                headers=headers,
            )
            if data:
                events.extend(self._parse_response(data, display, sport_id))
            await asyncio.sleep(self.REQUEST_DELAY)

        return events

    def _parse_response(self, data: dict | list, league_display: str, sport_id: int) -> list[Event]:
        sport_map = {1: "Futebol", 3: "Basquete"}
        sport_title = sport_map.get(sport_id, "Esportes")

        if isinstance(data, dict):
            events_raw = data.get("data") or data.get("events") or []
        else:
            events_raw = data

        result: list[Event] = []
        for ev in events_raw:
            try:
                home = ev.get("homeTeam") or ev.get("homeName") or ""
                away = ev.get("awayTeam") or ev.get("awayName") or ""
                eid  = str(ev.get("id") or ev.get("eventId") or "")
                start = _parse_dt(ev.get("startDate") or ev.get("eventDate") or ev.get("date"))

                if not home or not away:
                    continue

                odds: list[Odd] = []
                for market in (ev.get("markets") or ev.get("odds") or []):
                    mname = str(market.get("name") or "").lower()
                    if mname and "1x2" not in mname and "resultado" not in mname and "moneyline" not in mname:
                        continue

                    for sel in (market.get("selections") or market.get("outcomes") or []):
                        name  = sel.get("name") or ""
                        price = sel.get("odds") or sel.get("price") or 0
                        try:
                            price = float(price)
                        except (TypeError, ValueError):
                            continue
                        if price <= 1.0:
                            continue

                        name_l = str(name).lower()
                        if name_l in ("empate", "draw", "x"):
                            outcome = "Draw"
                        elif name_l in ("1",) or name.lower() == home.lower():
                            outcome = home
                        elif name_l in ("2",) or name.lower() == away.lower():
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
                        event_id=f"betsul-{eid}",
                        sport_key=f"sport_{sport_id}",
                        sport_title=sport_title,
                        league=league_display,
                        home_team=home,
                        away_team=away,
                        commence_time=start,
                        odds=odds,
                    ))
            except Exception as e:
                logger.debug("Betsul: erro: %s", e)
        return result
