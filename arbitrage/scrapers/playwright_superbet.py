"""
Superbet Brasil — Scraper via Playwright.

A Superbet tem proteção Cloudflare básica. O browser real passa sem problemas.
Interceptamos as chamadas à API interna que retornam eventos e odds.
"""
import logging
from datetime import datetime, timezone

from arbitrage.scrapers.playwright_base import PlaywrightBaseScraper, utc_now
from arbitrage.models import Event, Odd

logger = logging.getLogger(__name__)

_LEAGUE_URLS = [
    ("https://superbet.com.br/apostas-esportivas/futebol/brasil/campeonato-brasileiro", "Campeonato Brasileiro"),
    ("https://superbet.com.br/apostas-esportivas/futebol/copa-libertadores",            "Copa Libertadores"),
    ("https://superbet.com.br/apostas-esportivas/basquete/nba",                         "NBA"),
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


def _parse_superbet_body(body: dict | list, league_display: str) -> list[Event]:
    if isinstance(body, dict):
        raw = (body.get("data") or body.get("events") or body.get("items") or [])
        if isinstance(raw, dict):
            raw = raw.get("events") or raw.get("items") or []
    elif isinstance(body, list):
        raw = body
    else:
        return []

    result: list[Event] = []
    for ev in (raw if isinstance(raw, list) else []):
        if not isinstance(ev, dict):
            continue
        try:
            home = ev.get("homeTeam") or ev.get("team1") or ev.get("home", {}).get("name", "")
            away = ev.get("awayTeam") or ev.get("team2") or ev.get("away", {}).get("name", "")
            eid  = str(ev.get("id") or ev.get("eventId") or "")
            start = _parse_dt(ev.get("startDate") or ev.get("startTime") or ev.get("date"))

            if not home or not away:
                continue

            odds: list[Odd] = []
            for market in (ev.get("markets") or ev.get("bets") or []):
                mtype = str(market.get("type") or market.get("marketType") or "").lower()
                if mtype and not any(k in mtype for k in ("1x2", "resultado", "moneyline", "vencedor", "match")):
                    continue
                for sel in (market.get("selections") or market.get("outcomes") or []):
                    name  = str(sel.get("name") or sel.get("label") or "")
                    price = sel.get("odds") or sel.get("price") or sel.get("value") or 0
                    try:
                        price = float(price)
                    except (TypeError, ValueError):
                        continue
                    if price <= 1.0:
                        continue
                    name_l = name.lower()
                    if name_l in ("empate", "draw", "x"):
                        outcome = "Draw"
                    elif name_l in ("1", "casa") or name.lower() == home.lower():
                        outcome = home
                    elif name_l in ("2", "fora") or name.lower() == away.lower():
                        outcome = away
                    else:
                        outcome = name
                    odds.append(Odd(
                        bookmaker="Superbet",
                        bookmaker_key="superbet",
                        market="h2h",
                        outcome=outcome,
                        price=round(price, 3),
                        last_updated=utc_now(),
                    ))

            if len(odds) >= 2:
                result.append(Event(
                    event_id=f"superbet-pw-{eid}",
                    sport_key="soccer",
                    sport_title="Futebol",
                    league=league_display,
                    home_team=home,
                    away_team=away,
                    commence_time=start,
                    odds=odds,
                ))
        except Exception as e:
            logger.debug("Superbet PW: erro: %s", e)

    return result


class PlaywrightSuperbetScraper(PlaywrightBaseScraper):

    @property
    def bookmaker_key(self) -> str:
        return "superbet"

    @property
    def bookmaker_name(self) -> str:
        return "Superbet"

    @property
    def start_url(self) -> str:
        return "https://superbet.com.br/apostas-esportivas/futebol/brasil/campeonato-brasileiro"

    def is_odds_response(self, url: str, content_type: str) -> bool:
        url_l = url.lower()
        return (
            "superbet.com" in url_l
            and any(k in url_l for k in ("/api/", "/events", "/offer", "/v1", "/v2"))
            and "json" in content_type
        )

    def parse_response(self, url: str, body: dict | list) -> list[Event]:
        league = "Campeonato Brasileiro"
        if "libertadores" in url.lower():
            league = "Copa Libertadores"
        elif "nba" in url.lower():
            league = "NBA"
        return _parse_superbet_body(body, league)

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
                        page_events.extend(_parse_superbet_body(body, lg))
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
                    logger.warning("Superbet PW: erro em %s: %s", url, e)
                finally:
                    await page.close()

                all_events.extend(page_events)

            await browser.close()

        return all_events
