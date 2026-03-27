"""
1xBet — API interna JSON.

A 1xBet expõe uma API relativamente aberta. O endpoint principal
retorna todos os eventos de uma liga com odds incluídas.

Endpoints:
  GET https://1xbet.com/LineFeed/GetGamesList
      ?sport={sportId}&champId={champId}&count=50&lng=por&tf=2200000
      &tz=3&gr=6&isNewBuilder=true

Sport IDs usados:
  1  = Futebol
  2  = Hóquei
  3  = Basquete
  4  = Beisebol

Champ IDs relevantes (ligas brasileiras):
  Os IDs são descobertos via:
  GET https://1xbet.com/LineFeed/GetSportsShortList?lng=por&tf=2200000
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from arbitrage.scrapers.base import BaseScraper, _browser_headers, _get_json, utc_now
from arbitrage.models import Event, Odd

logger = logging.getLogger(__name__)

_BASE = "https://1xbet.com"
_REFERER = "https://1xbet.com/pt/line/"

# (sport_id, champ_id, display_name)
# IDs verificados para o mercado brasileiro
_LEAGUES = [
    (1, 131386, "Campeonato Brasileiro"),   # Série A
    (1, 131387, "Brasileirão Série B"),
    (1, 119057, "Copa do Brasil"),
    (1, 118593, "Copa Libertadores"),
    (1, 118594, "Copa Sudamericana"),
    (1, 118587, "Premier League"),
    (1, 127641, "La Liga"),
    (1, 118567, "Champions League"),
    (3, 123523, "NBA"),
]


def _parse_ts(ts: int | float | None) -> datetime:
    if not ts:
        return utc_now()
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return utc_now()


class OneXBetScraper(BaseScraper):
    REQUEST_DELAY = 1.5

    @property
    def bookmaker_key(self) -> str:
        return "1xbet"

    @property
    def bookmaker_name(self) -> str:
        return "1xBet"

    async def fetch_events(self, client: httpx.AsyncClient) -> list[Event]:
        events: list[Event] = []
        headers = _browser_headers(referer=_REFERER)

        for sport_id, champ_id, display in _LEAGUES:
            data = await _get_json(
                client,
                f"{_BASE}/LineFeed/GetGamesList",
                params={
                    "sport": sport_id,
                    "champId": champ_id,
                    "count": 50,
                    "lng": "por",
                    "tf": 2200000,
                    "tz": 3,
                    "gr": 6,
                    "isNewBuilder": "true",
                },
                headers=headers,
            )

            if data:
                parsed = self._parse_response(data, display, sport_id)
                events.extend(parsed)

            await asyncio.sleep(self.REQUEST_DELAY)

        return events

    def _parse_response(self, data: dict, league_display: str, sport_id: int) -> list[Event]:
        sport_map = {1: "Futebol", 3: "Basquete", 4: "Beisebol"}
        sport_title = sport_map.get(sport_id, str(sport_id))

        # 1xBet retorna {"Value": [...games...]}
        games = data.get("Value") or data.get("value") or []
        if not isinstance(games, list):
            return []

        result: list[Event] = []
        for game in games:
            try:
                game_id = str(game.get("Id") or game.get("id", ""))
                home = game.get("O1") or game.get("home", "")  # O1 = home team
                away = game.get("O2") or game.get("away", "")  # O2 = away team
                ts   = game.get("S")                           # S = start timestamp

                if not home or not away:
                    continue

                start = _parse_ts(ts)
                odds: list[Odd] = []

                # Eventos 1xBet têm odds em .E[] (events/odds array)
                # Cada elemento tem: T (type), C (coefficient/odd), G (group)
                # Para moneyline futebol: T=1 (home), T=2 (draw), T=3 (away)
                # Para basquete 2-vias:   T=1 (home), T=2 (away)
                e_list = game.get("E") or []
                for e in e_list:
                    t = e.get("T")  # tipo do outcome
                    c = e.get("C")  # coeficiente (odd)
                    if not t or not c:
                        continue
                    try:
                        price = float(c)
                    except (TypeError, ValueError):
                        continue
                    if price <= 1.0:
                        continue

                    if sport_id == 1:  # Futebol
                        if t == 1:
                            outcome = home
                        elif t == 2:
                            outcome = "Draw"
                        elif t == 3:
                            outcome = away
                        else:
                            continue
                    elif sport_id == 3:  # Basquete
                        if t == 1:
                            outcome = home
                        elif t == 2:
                            outcome = away
                        else:
                            continue
                    else:
                        continue

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
                        event_id=f"1xbet-{game_id}",
                        sport_key=f"sport_{sport_id}",
                        sport_title=sport_title,
                        league=league_display,
                        home_team=home,
                        away_team=away,
                        commence_time=start,
                        odds=odds,
                    ))

            except Exception as e:
                logger.debug("1xBet: erro ao parsear jogo: %s", e)
                continue

        return result
