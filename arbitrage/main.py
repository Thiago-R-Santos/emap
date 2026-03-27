"""
Detector de Arbitragem de Apostas Esportivas — Brasil
=====================================================
Uso:
  python arbitrage/main.py                  # dashboard live (scrapers reais, grátis)
  python arbitrage/main.py --mock           # dashboard live (dados simulados)
  python arbitrage/main.py --odds-api       # usa The Odds API (requer chave no .env)
  python arbitrage/main.py --stake 500      # define capital em R$
  python arbitrage/main.py --min-profit 1.0 # define lucro mínimo em %
  python arbitrage/main.py --once           # roda uma vez e sai
  python arbitrage/main.py --interval 120   # intervalo de atualização (seg)
  python arbitrage/main.py --debug          # exibe logs de scraping
"""
import sys
import asyncio
import argparse
import logging
from datetime import datetime

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.live import Live
from rich.console import Console

from arbitrage import config
from arbitrage.collectors.odds_api import OddsApiCollector
from arbitrage.collectors.mock import MockCollector
from arbitrage.scrapers.coordinator import ScraperCoordinator
from arbitrage.arbitrage import find_arbitrage
from arbitrage.ui import dashboard

console = Console()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Detector de arbitragem de apostas esportivas (Brasil)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--mock",     action="store_true", help="Usar dados simulados")
    mode.add_argument("--odds-api", action="store_true", help="Usar The Odds API (requer chave)")

    p.add_argument("--stake",      type=float, default=None, metavar="R$",
                   help=f"Capital total (padrão: R$ {config.TOTAL_STAKE:,.2f})")
    p.add_argument("--min-profit", type=float, default=None, metavar="%",
                   help=f"Lucro mínimo %% (padrão: {config.MIN_PROFIT_PCT}%%)")
    p.add_argument("--interval",   type=int,   default=None, metavar="SEG",
                   help=f"Intervalo de atualização em segundos (padrão: {config.REFRESH_INTERVAL}s)")
    p.add_argument("--once",       action="store_true",
                   help="Executar uma vez e sair (sem live)")
    p.add_argument("--debug",      action="store_true",
                   help="Exibir logs de scraping no terminal")
    return p.parse_args()


def _build_collector(args: argparse.Namespace):
    """Escolhe o coletor conforme argumentos e disponibilidade."""
    if args.mock or config.USE_MOCK:
        console.print(
            "[bold yellow]⚠  Modo simulado.[/] "
            "Os dados são fictícios para demonstração."
        )
        return MockCollector()

    if args.odds_api:
        if not config.ODDS_API_KEY:
            console.print(
                "[bold red]Erro:[/] ODDS_API_KEY não configurada no .env\n"
                "Obtenha gratuitamente em [link=https://the-odds-api.com]"
                "https://the-odds-api.com[/link]"
            )
            sys.exit(1)
        console.print("[dim]Usando The Odds API...[/]")
        return OddsApiCollector()

    # Padrão: scrapers web gratuitos
    coordinator = ScraperCoordinator()
    console.print(
        "[bold green]Scrapers ativos:[/] "
        + ", ".join(s.bookmaker_name for s in coordinator.scrapers)
    )
    return coordinator


async def run(args: argparse.Namespace) -> None:
    stake      = args.stake      if args.stake      is not None else config.TOTAL_STAKE
    min_profit = args.min_profit if args.min_profit is not None else config.MIN_PROFIT_PCT
    interval   = args.interval   if args.interval   is not None else config.REFRESH_INTERVAL

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    collector = _build_collector(args)

    requests_remaining = -1

    async def fetch_and_detect():
        nonlocal requests_remaining
        events = await collector.fetch_events()
        opps   = find_arbitrage(events, total_stake=stake, min_profit_pct=min_profit)
        if hasattr(collector, "requests_remaining"):
            requests_remaining = collector.requests_remaining
        return events, opps

    # ── Modo --once ──────────────────────────────────────────────────────────
    if args.once:
        console.print("[dim]Coletando dados...[/]")
        events, opps = await fetch_and_detect()
        source_name = collector.name() if hasattr(collector, "name") else "Scrapers"
        dashboard.render_once(
            events=events,
            opportunities=opps,
            last_update=datetime.utcnow(),
            source_name=source_name,
            requests_remaining=requests_remaining,
            refresh_interval=interval,
            total_stake=stake,
        )
        return

    # ── Modo live ────────────────────────────────────────────────────────────
    console.print(f"[dim]Primeira coleta... (intervalo: {interval}s)[/]")
    events, opps = await fetch_and_detect()
    source_name = collector.name() if hasattr(collector, "name") else "Scrapers"

    with Live(
        dashboard.render(
            events=events,
            opportunities=opps,
            last_update=datetime.utcnow(),
            source_name=source_name,
            requests_remaining=requests_remaining,
            refresh_interval=interval,
            total_stake=stake,
        ),
        console=console,
        refresh_per_second=1,
        screen=True,
    ) as live:
        while True:
            await asyncio.sleep(interval)
            try:
                events, opps = await fetch_and_detect()
            except Exception as exc:
                console.log(f"[bold red]Erro na coleta:[/] {exc}")
                continue

            live.update(
                dashboard.render(
                    events=events,
                    opportunities=opps,
                    last_update=datetime.utcnow(),
                    source_name=source_name,
                    requests_remaining=requests_remaining,
                    refresh_interval=interval,
                    total_stake=stake,
                )
            )


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        console.print("\n[dim]Encerrado pelo usuário.[/]")


if __name__ == "__main__":
    main()
