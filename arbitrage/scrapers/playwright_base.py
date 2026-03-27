"""
Base para scrapers Playwright.

Playwright lança um browser Chromium real — passa por Cloudflare,
JavaScript SPA, e qualquer proteção que bloqueie httpx puro.

Estratégia de captura de dados:
  1. Abre o browser headless
  2. Intercepta requisições de rede (route interception)
  3. Captura respostas JSON das chamadas internas de odds
  4. Fecha o browser

Instalação:
  pip install playwright
  playwright install chromium
"""
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from arbitrage.models import Event

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class PlaywrightBaseScraper(ABC):
    """Base para scrapers que precisam de browser real."""

    # Timeout máximo de navegação em ms
    NAV_TIMEOUT = 20_000
    # Tempo de espera após carregar a página (JS renderizar)
    SETTLE_TIME = 4_000

    @property
    @abstractmethod
    def bookmaker_key(self) -> str: ...

    @property
    @abstractmethod
    def bookmaker_name(self) -> str: ...

    @property
    @abstractmethod
    def start_url(self) -> str:
        """URL inicial para abrir no browser."""
        ...

    @abstractmethod
    def is_odds_response(self, url: str, content_type: str) -> bool:
        """Retorna True se essa resposta de rede contém odds."""
        ...

    @abstractmethod
    def parse_response(self, url: str, body: dict | list) -> list[Event]:
        """Parseia uma resposta JSON capturada e retorna eventos."""
        ...

    async def fetch_events(self) -> list[Event]:
        """Abre o browser, intercepta chamadas de odds e retorna eventos."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "Playwright não instalado. Execute:\n"
                "  pip install playwright && playwright install chromium"
            )
            return []

        captured_events: list[Event] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )

            # Remove fingerprints de automação
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en'] });
            """)

            page = await context.new_page()

            # Intercepta respostas de rede
            async def on_response(response):
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" not in ct:
                        return
                    if not self.is_odds_response(response.url, ct):
                        return
                    body = await response.json()
                    events = self.parse_response(response.url, body)
                    captured_events.extend(events)
                    logger.debug(
                        "%s: capturou %d eventos de %s",
                        self.bookmaker_name, len(events), response.url[:80]
                    )
                except Exception as e:
                    logger.debug("Erro ao processar resposta: %s", e)

            page.on("response", on_response)

            try:
                await page.goto(
                    self.start_url,
                    timeout=self.NAV_TIMEOUT,
                    wait_until="domcontentloaded",
                )
                # Aguarda o JavaScript carregar os dados
                await page.wait_for_timeout(self.SETTLE_TIME)

                # Scroll para forçar carregamento lazy de mais eventos
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

            except Exception as e:
                logger.warning("%s: erro de navegação: %s", self.bookmaker_name, e)
            finally:
                await browser.close()

        logger.info("%s: total %d eventos capturados", self.bookmaker_name, len(captured_events))
        return captured_events
