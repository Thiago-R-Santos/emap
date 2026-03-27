"""
KTO Brasil — API interna JSON.

KTO é uma casa popular no Brasil, com boas odds em futebol.
Usa plataforma própria com API REST.

Endpoint observado:
  GET https://www.kto.com/api/sportsbook/events
      ?sportId=1&competitionId=...&lang=pt-BR
"""
import asyncio
import logging

import httpx

from arbitrage.scrapers.base import BaseScraper, _browser_headers, _get_json, utc_now
from arbitrage.models import Event, Odd
from arbitrage.scrapers.betano import _parse_dt

logger = logging.getLogger(__name__)

_BASE = "https://www.kto.com"
_REFERER = "https://www.kto.com/pt-br/sports"

# (sport_id, competition_id, display_name)
# IDs KTO para mercado brasileiro
_LEAGUES = [
    (1, 325,  "Campeonato Brasileiro"),
    (1, 326,  "Copa do Brasil"),
    (1, 568,  "Copa Libertadores"),
    (1, 569,  "Copa Sudamericana"),
    (1, 10,   "Premier League"),
    (1, 13,   "Champions League"),
    (2, 240,  "NBA"),
]


class KTOScraper(BaseScraper):
    REQUEST_DELAY = 1.5

    @property
    def bookmaker_key(self) -> str:
        return "kto"

    @property
    def bookmaker_name(self) -> str:
        return "KTO"

    async def fetch_events(self, client: httpx.AsyncClient) -> list[Event]:
        events: list[Event] = []
        headers = _browser_headers(referer=_REFERER, extra={
            "Origin": _BASE,
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": "pt-BR,pt;q=0.9",
        })

        for sport_id, comp_id, display in _LEAGUES:
            # Tenta endpoint principal
            data = await _get_json(
                client,
                f"{_BASE}/api/sportsbook/events",
                params={
                    "sportId": sport_id,
                    "competitionId": comp_id,
                    "lang": "pt-BR",
                    "marketType": "1x2",
                },
                headers=headers,
            )

            if not data:
                # Fallback: endpoint alternativo da plataforma EveryMatrix
                data = await _get_json(
                    client,
                    f"{_BASE}/api/v2/sports/{sport_id}/competitions/{comp_id}/events",
                    params={"lang": "pt-BR", "marketTypes": "MATCH_ODDS"},
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
            events_raw = (
                data.get("events") or data.get("data") or
                data.get("result") or data.get("items") or []
            )
        else:
            events_raw = data

        if not isinstance(events_raw, list):
            return []

        result: list[Event] = []
        for ev in events_raw:
            if not isinstance(ev, dict):
                continue
            try:
                home = (
                    ev.get("homeTeam") or ev.get("home_team") or
                    ev.get("home", {}).get("name", "")
                )
                away = (
                    ev.get("awayTeam") or ev.get("away_team") or
                    ev.get("away", {}).get("name", "")
                )
                eid  = str(ev.get("id") or ev.get("eventId") or "")
                start = _parse_dt(
                    ev.get("startDate") or ev.get("start_time") or
                    ev.get("startTime") or ev.get("date")
                )

                if not home or not away:
                    continue

                odds: list[Odd] = []
                for market in (ev.get("markets") or ev.get("bets") or ev.get("odds") or []):
                    mname = str(
                        market.get("name") or market.get("type") or
                        market.get("marketType") or ""
                    ).lower()
                    mid = market.get("marketTypeId") or market.get("id")

                    # Aceita apenas mercados 1X2 / moneyline
                    if mid not in (1, None) and not any(
                        k in mname for k in ("1x2", "resultado", "moneyline", "vencedor", "match")
                    ):
                        continue

                    for sel in (market.get("selections") or market.get("outcomes") or []):
                        name  = str(sel.get("name") or sel.get("label") or "")
                        price = (
                            sel.get("odds") or sel.get("price") or
                            sel.get("value") or sel.get("decimal") or 0
                        )
                        try:
                            price = float(price)
                        except (TypeError, ValueError):
                            continue
                        if price <= 1.0:
                            continue

                        name_l = name.lower()
                        if name_l in ("empate", "draw", "x", "empate/draw"):
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
                        event_id=f"kto-{eid}",
                        sport_key=f"sport_{sport_id}",
                        sport_title=sport_title,
                        league=league_display,
                        home_team=home,
                        away_team=away,
                        commence_time=start,
                        odds=odds,
                    ))

            except Exception as e:
                logger.debug("KTO: erro ao parsear evento: %s", e)

        return result
