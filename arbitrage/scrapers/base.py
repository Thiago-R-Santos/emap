"""
Base para todos os scrapers.
Fornece: headers realistas, retry com backoff, rate limiting leve.
"""
import asyncio
import random
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx

from arbitrage.models import Event

logger = logging.getLogger(__name__)

# User-agents reais de Chrome/Firefox para não ser bloqueado trivialmente
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _browser_headers(referer: str = "", extra: dict | None = None) -> dict:
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    if extra:
        headers.update(extra)
    return headers


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    retries: int = 3,
    timeout: float = 15.0,
) -> Any | None:
    """GET com retry exponencial. Retorna JSON ou None em caso de falha."""
    for attempt in range(retries):
        try:
            resp = await client.get(
                url,
                params=params,
                headers=headers or _browser_headers(),
                timeout=timeout,
            )
            if resp.status_code == 429:
                # Rate limited — espera e tenta novamente
                wait = 2 ** (attempt + 1)
                logger.warning("Rate limited em %s, aguardando %ss", url, wait)
                await asyncio.sleep(wait)
                continue
            if resp.status_code in (403, 401):
                logger.warning("Acesso negado em %s (status %s)", url, resp.status_code)
                return None
            if resp.status_code >= 400:
                logger.debug("HTTP %s em %s", resp.status_code, url)
                return None
            return resp.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                logger.debug("Timeout/erro em %s, tentativa %d/%d: %s", url, attempt + 1, retries, e)
                await asyncio.sleep(wait)
            else:
                logger.warning("Falha definitiva em %s: %s", url, e)
    return None


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class BaseScraper(ABC):
    """Interface base para todos os scrapers de casas de apostas."""

    # Pausa mínima entre requisições ao mesmo domínio (segundos)
    REQUEST_DELAY: float = 1.0

    @property
    @abstractmethod
    def bookmaker_key(self) -> str:
        """Chave única da casa (ex: 'betano', 'pinnacle')."""
        ...

    @property
    @abstractmethod
    def bookmaker_name(self) -> str:
        """Nome de exibição (ex: 'Betano', 'Pinnacle')."""
        ...

    @abstractmethod
    async def fetch_events(self, client: httpx.AsyncClient) -> list[Event]:
        """Busca eventos com odds. Deve retornar lista vazia em caso de erro."""
        ...
