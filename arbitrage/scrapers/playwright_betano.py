"""
Betano Brasil — Scraper via Playwright.

A Betano usa Cloudflare e JavaScript SPA (Kaizen Gaming platform).
Interceptamos as chamadas XHR que o próprio frontend faz para a API interna.

URLs de API interna observadas via DevTools:
  /api/sports/futebol/regions/brasil/leagues/{slug}/events/
  /api/sports/{sport}/events/?... (listagem genérica)
  /pt/sports/futebol/{liga}/ (página renderizada — fonte alternativa)

Estratégia:
  1. Abre a página do Campeonato Brasileiro
  2. Intercepta chamadas JSON com "events" ou "odds" na resposta
  3. Parseia os dados capturados
"""
import logging
from datetime import datetime, timezone

from arbitrage.scrapers.playwright_base import PlaywrightBaseScraper, utc_now
from arbitrage.models import Event, Odd

logger = logging.getLogger(__name__)

# Ligas que serão navegadas (uma por vez para capturar as chamadas de API)
_LEAGUE_URLS = [
    ("https://br.betano.com/sport/futebol/brasil/campeonato-brasileiro-serie-a/", "Campeonato Brasileiro"),
    ("https://br.betano.com/sport/futebol/copa-libertadores/", "Copa Libertadores"),
    ("https://br.betano.com/sport/basquete/nba/", "NBA"),
]


def _parse_dt(value) -> datetime:
    if not value:
        return utc_now()
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return utc_now()


def _extract_events_from_body(body: dict | list, league_display: str) -> list[Event]:
    """Tenta extrair eventos de qualquer estrutura JSON da Betano."""
    if isinstance(body, dict):
        # Possíveis chaves onde os eventos estão
        candidates = [
            body.get("data", {}).get("events") if isinstance(body.get("data"), dict) else None,
            body.get("events"),
            body.get("data") if isinstance(body.get("data"), list) else None,
            body.get("items"),
            body.get("results"),
        ]
        events_raw = next((c for c in candidates if isinstance(c, list)), [])
    elif isinstance(body, list):
        events_raw = body
    else:
        return []

    result: list[Event] = []
    for ev in events_raw:
        if not isinstance(ev, dict):
            continue
        try:
            home = (ev.get("home_team") or ev.get("homeName")
                    or (ev.get("home") or {}).get("name", ""))
            away = (ev.get("away_team") or ev.get("awayName")
                    or (ev.get("away") or {}).get("name", ""))
            eid  = str(ev.get("id") or ev.get("event_id") or "")
            start = _parse_dt(ev.get("start_time") or ev.get("startTime") or ev.get("date"))

            if not home or not away:
                continue

            odds: list[Odd] = []
            for market in (ev.get("markets") or ev.get("odds") or []):
                mtype = str(market.get("market_type") or market.get("type") or "").lower()
                if mtype and not any(k in mtype for k in ("1x2", "result", "moneyline", "vencedor")):
                    continue
                for sel in (market.get("selections") or market.get("outcomes") or []):
                    name  = str(sel.get("name") or sel.get("label") or "")
                    price = sel.get("odds") or sel.get("price") or 0
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
                        bookmaker="Betano",
                        bookmaker_key="betano",
                        market="h2h",
                        outcome=outcome,
                        price=round(price, 3),
                        last_updated=utc_now(),
                    ))

            if len(odds) >= 2:
                result.append(Event(
                    event_id=f"betano-pw-{eid}",
                    sport_key="soccer",
                    sport_title="Futebol",
                    league=league_display,
                    home_team=home,
                    away_team=away,
                    commence_time=start,
                    odds=odds,
                ))
        except Exception as e:
            logger.debug("Betano PW: erro ao parsear evento: %s", e)

    return result


class PlaywrightBetanoScraper(PlaywrightBaseScraper):
    """Scraper Betano usando browser real — contorna Cloudflare."""

    @property
    def bookmaker_key(self) -> str:
        return "betano"

    @property
    def bookmaker_name(self) -> str:
        return "Betano"

    @property
    def start_url(self) -> str:
        # Começa pela página principal de futebol brasileiro
        return "https://br.betano.com/sport/futebol/brasil/campeonato-brasileiro-serie-a/"

    def is_odds_response(self, url: str, content_type: str) -> bool:
        url_l = url.lower()
        return (
            "betano.com" in url_l
            and any(k in url_l for k in ("/api/", "/events", "/leagues", "/sports"))
            and "json" in content_type
        )

    def parse_response(self, url: str, body: dict | list) -> list[Event]:
        # Tenta identificar a liga pelo URL
        league = "Campeonato Brasileiro"
        if "libertadores" in url.lower():
            league = "Copa Libertadores"
        elif "nba" in url.lower() or "basquete" in url.lower():
            league = "NBA"
        elif "copa-do-brasil" in url.lower():
            league = "Copa do Brasil"
        return _extract_events_from_body(body, league)

    async def fetch_events(self) -> list[Event]:
        """Navega por cada liga e coleta os eventos."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright não instalado: pip install playwright && playwright install chromium")
            return []

        all_events: list[Event] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

            for url, league_name in _LEAGUE_URLS:
                page_events: list[Event] = []

                async def on_response(response, lg=league_name):
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" not in ct:
                            return
                        if not self.is_odds_response(response.url, ct):
                            return
                        body = await response.json()
                        evs = _extract_events_from_body(body, lg)
                        page_events.extend(evs)
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
                    logger.warning("Betano PW: erro em %s: %s", url, e)
                finally:
                    await page.close()

                all_events.extend(page_events)
                logger.info("Betano PW [%s]: %d eventos", league_name, len(page_events))

            await browser.close()

        return all_events
