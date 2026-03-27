"""
Sportingbet Brasil — Scraper via Playwright.

A Sportingbet usa plataforma SBTech. O browser real contorna a proteção.
Interceptamos as chamadas JSON internas que carregam eventos e odds.

URLs observadas via DevTools:
  /pt-br/api/sportsbook/v2/api/getEvents?...
  /pt-br/api/sportsbook/v2/api/getLeagueEvents?leagueId=...
"""
import logging
from datetime import datetime, timezone

from arbitrage.scrapers.playwright_base import PlaywrightBaseScraper, utc_now
from arbitrage.models import Event, Odd

logger = logging.getLogger(__name__)

_LEAGUE_URLS = [
    ("https://www.sportingbet.com/pt-br/sports/futebol/brasil/campeonato-brasileiro", "Campeonato Brasileiro"),
    ("https://www.sportingbet.com/pt-br/sports/futebol/copa-libertadores",            "Copa Libertadores"),
    ("https://www.sportingbet.com/pt-br/sports/basquete/nba",                         "NBA"),
]


def _parse_dt(value) -> datetime:
    if not value:
        return utc_now()
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 1e10 else value, tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return utc_now()


def _parse_sbtech_body(body: dict | list, league_display: str) -> list[Event]:
    """Parseia formato SBTech (Events[], Markets[], Selections[])."""
    if isinstance(body, dict):
        events_raw = (body.get("Events") or body.get("events")
                      or body.get("data", {}).get("events", [])
                      if isinstance(body.get("data"), dict) else body.get("data") or [])
    elif isinstance(body, list):
        events_raw = body
    else:
        return []

    result: list[Event] = []
    for ev in (events_raw if isinstance(events_raw, list) else []):
        if not isinstance(ev, dict):
            continue
        try:
            home = ev.get("HomeTeam") or ev.get("homeName") or ev.get("home", {}).get("name", "")
            away = ev.get("AwayTeam") or ev.get("awayName") or ev.get("away", {}).get("name", "")
            eid  = str(ev.get("Id") or ev.get("id") or ev.get("EventId") or "")
            start = _parse_dt(ev.get("EventDate") or ev.get("startTime") or ev.get("date"))

            if not home or not away:
                continue

            odds: list[Odd] = []
            for market in (ev.get("Markets") or ev.get("markets") or []):
                mname = str(market.get("Name") or market.get("name") or "").lower()
                mid   = market.get("MarketTypeId") or market.get("marketTypeId")
                # Aceita mercados 1X2, moneyline, ou MarketTypeId=1
                if mid not in (1, None) and not any(k in mname for k in ("1x2", "resultado", "vencedor", "moneyline")):
                    continue
                for sel in (market.get("Selections") or market.get("selections") or []):
                    name  = str(sel.get("Name") or sel.get("name") or "")
                    price = sel.get("Price") or sel.get("price") or sel.get("Odds") or 0
                    try:
                        price = float(price)
                    except (TypeError, ValueError):
                        continue
                    if price <= 1.0:
                        continue
                    name_l = name.lower()
                    if name_l in ("empate", "draw", "x"):
                        outcome = "Draw"
                    elif name_l in ("1",) or name.lower() == home.lower():
                        outcome = home
                    elif name_l in ("2",) or name.lower() == away.lower():
                        outcome = away
                    else:
                        outcome = name
                    odds.append(Odd(
                        bookmaker="Sportingbet",
                        bookmaker_key="sportingbet",
                        market="h2h",
                        outcome=outcome,
                        price=round(price, 3),
                        last_updated=utc_now(),
                    ))

            if len(odds) >= 2:
                result.append(Event(
                    event_id=f"sportingbet-pw-{eid}",
                    sport_key="soccer",
                    sport_title="Futebol",
                    league=league_display,
                    home_team=home,
                    away_team=away,
                    commence_time=start,
                    odds=odds,
                ))
        except Exception as e:
            logger.debug("Sportingbet PW: erro ao parsear: %s", e)

    return result


class PlaywrightSportingbetScraper(PlaywrightBaseScraper):

    @property
    def bookmaker_key(self) -> str:
        return "sportingbet"

    @property
    def bookmaker_name(self) -> str:
        return "Sportingbet"

    @property
    def start_url(self) -> str:
        return "https://www.sportingbet.com/pt-br/sports/futebol/brasil/campeonato-brasileiro"

    def is_odds_response(self, url: str, content_type: str) -> bool:
        url_l = url.lower()
        return (
            "sportingbet.com" in url_l
            and any(k in url_l for k in ("/api/", "getevents", "getleague", "events"))
            and "json" in content_type
        )

    def parse_response(self, url: str, body: dict | list) -> list[Event]:
        league = "Campeonato Brasileiro"
        if "libertadores" in url.lower():
            league = "Copa Libertadores"
        elif "nba" in url.lower() or "basquete" in url.lower():
            league = "NBA"
        return _parse_sbtech_body(body, league)

    async def fetch_events(self) -> list[Event]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright não instalado.")
            return []

        all_events: list[Event] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                locale="pt-BR",
            )

            for url, league_name in _LEAGUE_URLS:
                page_events: list[Event] = []

                async def on_response(response, lg=league_name):
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" not in ct or not self.is_odds_response(response.url, ct):
                            return
                        body = await response.json()
                        page_events.extend(_parse_sbtech_body(body, lg))
                    except Exception:
                        pass

                page = await context.new_page()
                page.on("response", on_response)
                try:
                    await page.goto(url, timeout=self.NAV_TIMEOUT, wait_until="domcontentloaded")
                    await page.wait_for_timeout(self.SETTLE_TIME)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1500)
                except Exception as e:
                    logger.warning("Sportingbet PW: erro em %s: %s", url, e)
                finally:
                    await page.close()

                all_events.extend(page_events)
                logger.info("Sportingbet PW [%s]: %d eventos", league_name, len(page_events))

            await browser.close()

        return all_events
