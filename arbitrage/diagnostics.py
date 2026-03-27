"""
Script de diagnóstico — testa cada scraper individualmente e reporta status.

Uso:
  python arbitrage/diagnostics.py              # testa todos (httpx + playwright)
  python arbitrage/diagnostics.py --http-only  # só scrapers httpx (mais rápido)
  python arbitrage/diagnostics.py --pw-only    # só scrapers Playwright
  python arbitrage/diagnostics.py --fix        # mostra como corrigir falhas

O diagnóstico identifica:
  ✅ Scraper funcionando e quantos eventos retornou
  ⚠️  Scraper respondeu mas sem dados (possível mudança de endpoint)
  ❌ Scraper com erro (403, timeout, estrutura JSON mudou)
  🔧 Sugestão de como corrigir cada falha
"""
import sys
import os
import asyncio
import argparse
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Diagnóstico de scrapers httpx
# ─────────────────────────────────────────────────────────────────────────────

async def test_http_scrapers() -> list[dict]:
    from arbitrage.scrapers.pinnacle    import PinnacleScraper
    from arbitrage.scrapers.betano      import BetanoScraper
    from arbitrage.scrapers.onexbet     import OneXBetScraper
    from arbitrage.scrapers.sportingbet import SportingbetScraper
    from arbitrage.scrapers.superbet    import SuperbetScraper
    from arbitrage.scrapers.betsul      import BetsulScraper

    scrapers = [
        PinnacleScraper(),
        BetanoScraper(),
        OneXBetScraper(),
        SportingbetScraper(),
        SuperbetScraper(),
        BetsulScraper(),
    ]

    results = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        for s in scrapers:
            start = time.perf_counter()
            try:
                events = await s.fetch_events(client)
                elapsed = time.perf_counter() - start
                n = len(events)

                sample = ""
                if events:
                    e = events[0]
                    o = e.odds[0] if e.odds else None
                    sample = f"{e.home_team} vs {e.away_team}"
                    if o:
                        sample += f" | {o.outcome}={o.price}"

                results.append({
                    "name":    s.bookmaker_name,
                    "type":    "httpx",
                    "status":  "ok" if n > 0 else "empty",
                    "events":  n,
                    "elapsed": elapsed,
                    "sample":  sample,
                    "error":   None,
                })
            except Exception as ex:
                elapsed = time.perf_counter() - start
                results.append({
                    "name":    s.bookmaker_name,
                    "type":    "httpx",
                    "status":  "error",
                    "events":  0,
                    "elapsed": elapsed,
                    "sample":  "",
                    "error":   str(ex)[:120],
                })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Diagnóstico de scrapers Playwright
# ─────────────────────────────────────────────────────────────────────────────

async def test_playwright_scrapers() -> list[dict]:
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        return [{
            "name": "Playwright",
            "type": "playwright",
            "status": "error",
            "events": 0,
            "elapsed": 0,
            "sample": "",
            "error": "Não instalado. Execute: pip install playwright && playwright install chromium",
        }]

    from arbitrage.scrapers.playwright_betano      import PlaywrightBetanoScraper
    from arbitrage.scrapers.playwright_sportingbet import PlaywrightSportingbetScraper
    from arbitrage.scrapers.playwright_superbet    import PlaywrightSuperbetScraper

    scrapers = [
        PlaywrightBetanoScraper(),
        PlaywrightSportingbetScraper(),
        PlaywrightSuperbetScraper(),
    ]

    results = []
    for s in scrapers:
        start = time.perf_counter()
        try:
            events = await s.fetch_events()
            elapsed = time.perf_counter() - start
            n = len(events)
            sample = ""
            if events:
                e = events[0]
                o = e.odds[0] if e.odds else None
                sample = f"{e.home_team} vs {e.away_team}"
                if o:
                    sample += f" | {o.outcome}={o.price}"
            results.append({
                "name":    s.bookmaker_name,
                "type":    "playwright",
                "status":  "ok" if n > 0 else "empty",
                "events":  n,
                "elapsed": elapsed,
                "sample":  sample,
                "error":   None,
            })
        except Exception as ex:
            elapsed = time.perf_counter() - start
            results.append({
                "name":    s.bookmaker_name,
                "type":    "playwright",
                "status":  "error",
                "events":  0,
                "elapsed": elapsed,
                "sample":  "",
                "error":   str(ex)[:120],
            })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Sugestões de correção
# ─────────────────────────────────────────────────────────────────────────────

_FIX_HINTS: dict[str, str] = {
    "Pinnacle": (
        "Verifique o X-Api-Key em scrapers/pinnacle.py.\n"
        "Teste manual: curl 'https://guest.api.arcadia.pinnacle.com/0.1/sports' "
        "-H 'X-Api-Key: CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'\n"
        "Se 401: a chave mudou. Abra pinnacle.com, F12 → Network, filtre 'arcadia' e copie o header X-Api-Key."
    ),
    "Betano": (
        "Betano usa Cloudflare — use o scraper Playwright (playwright_betano.py).\n"
        "Se Playwright também falhar: F12 no Chrome → Network → XHR → acesse a página do Brasileirão\n"
        "Procure requisição com 'events' na URL e JSON com lista de partidas. Copie a URL."
    ),
    "1xBet": (
        "Verifique os champIds em scrapers/onexbet.py.\n"
        "Teste manual: https://1xbet.com/LineFeed/GetSportsShortList?lng=por&tf=2200000\n"
        "Se mudou: abra 1xbet.com/pt/line/, F12 → Network → filtre 'LineFeed' → atualize os IDs."
    ),
    "Sportingbet": (
        "Sportingbet usa SBTech — use o scraper Playwright (playwright_sportingbet.py).\n"
        "Se Playwright falhar: F12 → Network → XHR → navegue para o Brasileirão\n"
        "Procure 'getLeagueEvents' ou 'getEvents' na URL. Copie e atualize o scraper."
    ),
    "Superbet": (
        "Use o scraper Playwright (playwright_superbet.py).\n"
        "Se falhar: F12 → Network → XHR → /api/offer/ ou /api/v2/events são os padrões comuns."
    ),
    "Betsul": (
        "Verifique a URL base em scrapers/betsul.py.\n"
        "Teste: https://www.betsul.com/api/sports/events?sportId=1&competitionId=45\n"
        "Se 404: F12 → Network → XHR no site da Betsul e encontre o endpoint correto."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Exibição
# ─────────────────────────────────────────────────────────────────────────────

def _render_results(results: list[dict], show_fix: bool) -> None:
    table = Table(
        box=box.ROUNDED,
        title="[bold]Diagnóstico de Scrapers[/]",
        show_header=True,
        header_style="bold white on dark_blue",
        expand=True,
    )
    table.add_column("Casa",      min_width=14)
    table.add_column("Tipo",      max_width=10, justify="center")
    table.add_column("Status",    max_width=10, justify="center")
    table.add_column("Eventos",   max_width=8,  justify="right")
    table.add_column("Tempo",     max_width=8,  justify="right")
    table.add_column("Amostra / Erro", no_wrap=False)

    for r in results:
        status = r["status"]
        if status == "ok":
            status_str = "[bold green]✅ OK[/]"
        elif status == "empty":
            status_str = "[yellow]⚠️  VAZIO[/]"
        else:
            status_str = "[bold red]❌ ERRO[/]"

        detail = r["sample"] if r["status"] == "ok" else (r["error"] or "sem dados")

        table.add_row(
            r["name"],
            f"[dim]{r['type']}[/]",
            Text.from_markup(status_str),
            str(r["events"]) if r["events"] else "[dim]0[/]",
            f"{r['elapsed']:.1f}s",
            f"[dim]{detail}[/]",
        )

    console.print(table)

    if show_fix:
        console.print()
        for r in results:
            if r["status"] != "ok":
                hint = _FIX_HINTS.get(r["name"], "Verifique os logs com --debug.")
                console.print(Panel(
                    hint,
                    title=f"[bold yellow]🔧 Como corrigir: {r['name']}[/]",
                    border_style="yellow",
                ))


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Diagnóstico de scrapers de odds")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--http-only", action="store_true", help="Testa só scrapers httpx")
    g.add_argument("--pw-only",   action="store_true", help="Testa só scrapers Playwright")
    p.add_argument("--fix",  action="store_true", help="Mostra sugestões de correção")
    p.add_argument("--debug", action="store_true", help="Logs detalhados")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    results: list[dict] = []

    if not args.pw_only:
        console.print("[dim]Testando scrapers httpx...[/]")
        results.extend(await test_http_scrapers())

    if not args.http_only:
        console.print("[dim]Testando scrapers Playwright (abre browser, demora ~30s)...[/]")
        results.extend(await test_playwright_scrapers())

    _render_results(results, show_fix=args.fix)

    ok    = sum(1 for r in results if r["status"] == "ok")
    empty = sum(1 for r in results if r["status"] == "empty")
    err   = sum(1 for r in results if r["status"] == "error")
    total_events = sum(r["events"] for r in results)

    console.print(
        f"\n[bold]Resumo:[/] {ok} OK  |  {empty} vazios  |  {err} com erro  |  "
        f"[bold green]{total_events} eventos coletados[/]"
    )

    if err > 0 or empty > 0:
        console.print("[dim]Execute com [bold]--fix[/] para ver sugestões de correção.[/]")


if __name__ == "__main__":
    asyncio.run(main())
