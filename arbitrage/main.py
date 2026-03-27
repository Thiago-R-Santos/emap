"""
Detector de Arbitragem de Apostas Esportivas — Brasil
=====================================================
Uso:
  python arbitrage/main.py                  # dashboard live (API real)
  python arbitrage/main.py --mock           # dashboard live (dados simulados)
  python arbitrage/main.py --stake 500      # define capital em R$
  python arbitrage/main.py --min-profit 1.0 # define lucro mínimo em %
  python arbitrage/main.py --once           # roda uma vez e sai
  python arbitrage/main.py --interval 60    # intervalo de atualização (seg)
"""
import sys
import asyncio
import argparse
from datetime import datetime

# Garante que o pacote 'arbitrage' seja importável quando
# o script é executado de qualquer diretório.
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.live import Live
from rich.console import Console
from rich.text import Text

from arbitrage import config
from arbitrage.collectors.odds_api import OddsApiCollector
from arbitrage.collectors.mock import MockCollector
from arbitrage.arbitrage import find_arbitrage
from arbitrage.ui import dashboard

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Argparse
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Detector de arbitragem de apostas esportivas (Brasil)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--mock", action="store_true",
        help="Usar dados simulados (não requer chave de API)",
    )
    p.add_argument(
        "--stake", type=float, default=None,
        metavar="R$",
        help=f"Capital total para calcular stakes (padrão: R$ {config.TOTAL_STAKE:,.2f})",
    )
    p.add_argument(
        "--min-profit", type=float, default=None,
        metavar="%",
        help=f"Lucro mínimo para exibir arbitragem (padrão: {config.MIN_PROFIT_PCT}%%)",
    )
    p.add_argument(
        "--interval", type=int, default=None,
        metavar="SEG",
        help=f"Intervalo de atualização em segundos (padrão: {config.REFRESH_INTERVAL}s)",
    )
    p.add_argument(
        "--once", action="store_true",
        help="Executar uma única coleta e exibir resultado (sem live updates)",
    )
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Loop principal
# ─────────────────────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    # Sobrescreve configs via CLI se fornecidos
    stake       = args.stake       if args.stake       is not None else config.TOTAL_STAKE
    min_profit  = args.min_profit  if args.min_profit  is not None else config.MIN_PROFIT_PCT
    interval    = args.interval    if args.interval    is not None else config.REFRESH_INTERVAL
    use_mock    = args.mock or config.USE_MOCK or not config.ODDS_API_KEY

    # Seleciona coletor
    if use_mock:
        collector = MockCollector()
        console.print(
            "[bold yellow]⚠  Modo simulado ativado.[/] "
            "Os dados são fictícios apenas para demonstração."
        )
    else:
        if not config.ODDS_API_KEY:
            console.print(
                "[bold red]Erro:[/] ODDS_API_KEY não configurada.\n"
                "Configure no arquivo [bold].env[/] ou use [bold]--mock[/] para dados simulados.\n"
                "Obtenha uma chave gratuita em [link=https://the-odds-api.com]https://the-odds-api.com[/link]"
            )
            sys.exit(1)
        collector = OddsApiCollector()

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
        dashboard.render_once(
            events=events,
            opportunities=opps,
            last_update=datetime.utcnow(),
            source_name=collector.name(),
            requests_remaining=requests_remaining,
            refresh_interval=interval,
            total_stake=stake,
        )
        return

    # ── Modo live ────────────────────────────────────────────────────────────
    events, opps = await fetch_and_detect()

    with Live(
        dashboard.render(
            events=events,
            opportunities=opps,
            last_update=datetime.utcnow(),
            source_name=collector.name(),
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
                console.print(f"[bold red]Erro na coleta:[/] {exc}")
                continue

            live.update(
                dashboard.render(
                    events=events,
                    opportunities=opps,
                    last_update=datetime.utcnow(),
                    source_name=collector.name(),
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
