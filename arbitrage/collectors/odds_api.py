import asyncio
import httpx
from datetime import datetime, timezone
from arbitrage.collectors.base import BaseCollector
from arbitrage.models import Event, Odd
from arbitrage import config


class OddsApiCollector(BaseCollector):
    """
    Coleta odds via The Odds API (https://the-odds-api.com).
    Plano gratuito: 500 requisições/mês.
    """

    def __init__(self):
        self._requests_remaining: int = -1
        self._requests_used: int = 0

    def name(self) -> str:
        return "The Odds API"

    @property
    def requests_remaining(self) -> int:
        return self._requests_remaining

    async def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = [
                self._fetch_sport(client, sport)
                for sport in config.SPORTS
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    events.extend(result)
        return events

    async def _fetch_sport(self, client: httpx.AsyncClient, sport: str) -> list[Event]:
        url = f"{config.ODDS_API_BASE_URL}/sports/{sport}/odds"
        params = {
            "apiKey": config.ODDS_API_KEY,
            "regions": config.REGIONS,
            "markets": config.MARKETS,
            "oddsFormat": config.ODDS_FORMAT,
            "dateFormat": "iso",
        }
        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 401:
                raise ValueError("Chave de API inválida. Verifique ODDS_API_KEY no .env")
            if resp.status_code == 422:
                return []  # esporte sem odds disponíveis
            resp.raise_for_status()

            # Atualiza quota restante
            remaining = resp.headers.get("x-requests-remaining")
            used = resp.headers.get("x-requests-used")
            if remaining:
                self._requests_remaining = int(remaining)
            if used:
                self._requests_used = int(used)

            return self._parse_response(resp.json(), sport)

        except httpx.HTTPStatusError:
            return []
        except Exception:
            return []

    def _parse_response(self, data: list, sport_key: str) -> list[Event]:
        events: list[Event] = []
        for item in data:
            try:
                commence_time = datetime.fromisoformat(
                    item["commence_time"].replace("Z", "+00:00")
                ).replace(tzinfo=timezone.utc)

                event = Event(
                    event_id=item["id"],
                    sport_key=sport_key,
                    sport_title=item.get("sport_title", sport_key),
                    league=item.get("sport_title", sport_key),
                    home_team=item["home_team"],
                    away_team=item["away_team"],
                    commence_time=commence_time,
                    odds=[],
                )

                for bookmaker in item.get("bookmakers", []):
                    bk_key = bookmaker["key"]
                    bk_title = bookmaker.get("title", bk_key)
                    last_updated_str = bookmaker.get("last_update", "")
                    try:
                        last_updated = datetime.fromisoformat(
                            last_updated_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        last_updated = datetime.utcnow()

                    for market in bookmaker.get("markets", []):
                        if market["key"] != "h2h":
                            continue
                        for outcome in market.get("outcomes", []):
                            event.odds.append(
                                Odd(
                                    bookmaker=bk_title,
                                    bookmaker_key=bk_key,
                                    market="h2h",
                                    outcome=outcome["name"],
                                    price=float(outcome["price"]),
                                    last_updated=last_updated,
                                )
                            )

                if event.odds:
                    events.append(event)

            except (KeyError, ValueError):
                continue

        return events
