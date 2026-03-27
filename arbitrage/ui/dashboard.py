"""
Dashboard terminal usando Rich.
Exibe em tempo real:
  1. Oportunidades de arbitragem (painel principal)
  2. Todas as odds disponíveis
"""
from datetime import datetime, timezone
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.rule import Rule
from rich import box
from arbitrage.models import ArbitrageOpportunity, Event
from arbitrage import config


console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hyperlink(label: str, url: str) -> Text:
    """Texto clicável usando OSC 8 (suportado por iTerm2, Kitty, WezTerm, GNOME Terminal ≥3.26)."""
    t = Text()
    t.append_text(Text.from_markup(f"[link={url}][bold cyan]{label}[/][/link]"))
    return t


def _fmt_time(dt: datetime) -> str:
    now = datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = dt - now
    hours = diff.total_seconds() / 3600
    if hours < 0:
        return "[red]AO VIVO[/]"
    elif hours < 1:
        return f"[yellow]{int(diff.total_seconds()/60)}min[/]"
    elif hours < 24:
        return f"[white]{hours:.1f}h[/]"
    else:
        return f"[dim]{dt.strftime('%d/%m %H:%M')}[/]"


def _fmt_odds(price: float) -> str:
    return f"[bold]{price:.2f}[/]"


def _quality_tag(quality: str) -> str:
    colors = {
        "EXCELENTE": "bold green",
        "ÓTIMA":     "green",
        "BOA":       "yellow",
        "MARGINAL":  "dim yellow",
    }
    color = colors.get(quality, "white")
    return f"[{color}]{quality}[/]"


# ─────────────────────────────────────────────────────────────────────────────
# Tabela de arbitragens
# ─────────────────────────────────────────────────────────────────────────────

def build_arbitrage_table(opportunities: list[ArbitrageOpportunity]) -> Table:
    table = Table(
        box=box.ROUNDED,
        border_style="bright_green",
        show_header=True,
        header_style="bold bright_white on dark_green",
        expand=True,
        title=f"[bold bright_green] ARBITRAGENS ENCONTRADAS: {len(opportunities)} [/]",
        title_style="bold",
        caption=(
            "[dim]Stake ideal por perna já calculada para capital configurado. "
            "Clique no nome da casa para abrir.[/]"
        ),
    )

    table.add_column("Evento",        style="white",        no_wrap=False, min_width=24)
    table.add_column("Liga",          style="dim white",    no_wrap=True,  max_width=20)
    table.add_column("Início",        style="white",        no_wrap=True,  max_width=10, justify="center")
    table.add_column("Lucro",         style="bold",         no_wrap=True,  max_width=8,  justify="right")
    table.add_column("Qualidade",     no_wrap=True,         max_width=12,  justify="center")
    table.add_column("Casa",          no_wrap=True,         max_width=16)
    table.add_column("Resultado",     style="cyan",         no_wrap=True,  max_width=20)
    table.add_column("Odd",           justify="center",     max_width=7)
    table.add_column("Impl.%",        justify="center",     max_width=8,   style="dim")
    table.add_column(f"Stake (R$)",   justify="right",      max_width=10)
    table.add_column(f"Retorno (R$)", justify="right",      max_width=12)
    table.add_column("Link",          no_wrap=True,         max_width=18)

    for opp in opportunities:
        profit_color = opp.quality_color
        profit_str = f"[{profit_color}]{opp.profit_pct:.2f}%[/]"
        quality_str = _quality_tag(opp.quality)
        event_str   = f"[bold]{opp.event.home_team}[/] [dim]vs[/] [bold]{opp.event.away_team}[/]"
        time_str    = _fmt_time(opp.event.commence_time)

        for i, leg in enumerate(opp.legs):
            link_text = _hyperlink(config.get_bookmaker_name(leg.bookmaker_key), leg.link)

            if i == 0:
                # Primeira perna: mostrar dados do evento
                table.add_row(
                    Text.from_markup(event_str),
                    opp.event.league,
                    Text.from_markup(time_str),
                    Text.from_markup(profit_str),
                    Text.from_markup(quality_str),
                    Text.from_markup(f"[cyan]{leg.bookmaker}[/]"),
                    leg.outcome,
                    Text.from_markup(_fmt_odds(leg.odds)),
                    f"{leg.implied_prob:.1f}%",
                    f"R$ {leg.stake:,.2f}",
                    f"R$ {leg.return_amount:,.2f}",
                    link_text,
                )
            else:
                # Pernas seguintes: omitir colunas do evento para clareza
                table.add_row(
                    "",
                    "",
                    "",
                    "",
                    "",
                    Text.from_markup(f"[cyan]{leg.bookmaker}[/]"),
                    leg.outcome,
                    Text.from_markup(_fmt_odds(leg.odds)),
                    f"{leg.implied_prob:.1f}%",
                    f"R$ {leg.stake:,.2f}",
                    f"R$ {leg.return_amount:,.2f}",
                    link_text,
                )

        # Linha de resumo do lucro garantido
        table.add_row(
            "",
            "",
            "",
            "",
            Text.from_markup(f"[dim]Lucro garan.:[/]"),
            "",
            "",
            "",
            "",
            Text.from_markup(
                f"[bold]R$ {opp.total_stake:,.2f}[/] total"
            ),
            Text.from_markup(
                f"[bold green]+R$ {opp.guaranteed_profit:,.2f}[/]"
            ),
            "",
            style="on grey7",
        )
        table.add_section()

    if not opportunities:
        table.add_row(
            Text.from_markup("[dim italic]Nenhuma arbitragem detectada no momento...[/]"),
            *[""] * 11,
        )

    return table


# ─────────────────────────────────────────────────────────────────────────────
# Tabela de todas as apostas
# ─────────────────────────────────────────────────────────────────────────────

def build_bets_table(events: list[Event]) -> Table:
    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="bright_blue",
        show_header=True,
        header_style="bold bright_white on dark_blue",
        expand=True,
        title=f"[bold bright_blue] TODAS AS APOSTAS DISPONÍVEIS [/]",
        title_style="bold",
    )

    table.add_column("Evento",     no_wrap=False, min_width=22)
    table.add_column("Liga",       no_wrap=True,  max_width=20, style="dim")
    table.add_column("Início",     no_wrap=True,  max_width=10, justify="center")
    table.add_column("Casa",       no_wrap=True,  max_width=14)
    table.add_column("Resultado",  no_wrap=True,  max_width=22, style="cyan")
    table.add_column("Odd",        justify="center", max_width=8)
    table.add_column("Impl.%",     justify="center", max_width=8, style="dim")
    table.add_column("Link",       no_wrap=True,  max_width=18)

    for event in events:
        event_str = f"{event.home_team} vs {event.away_team}"
        time_str  = _fmt_time(event.commence_time)

        # Agrupar odds do mesmo bookmaker juntas
        bk_outcomes: dict[str, list] = {}
        for odd in event.odds:
            bk_outcomes.setdefault(odd.bookmaker_key, []).append(odd)

        first_event = True
        for bk_key, odds in bk_outcomes.items():
            bk_name = config.get_bookmaker_name(bk_key)
            link_url = config.get_bookmaker_link(bk_key)
            link_text = _hyperlink(bk_name, link_url)

            for j, odd in enumerate(sorted(odds, key=lambda o: o.price, reverse=True)):
                if first_event and j == 0:
                    table.add_row(
                        Text.from_markup(f"[bold]{event_str}[/]"),
                        event.league,
                        Text.from_markup(time_str),
                        link_text,
                        odd.outcome,
                        Text.from_markup(_fmt_odds(odd.price)),
                        f"{odd.implied_prob * 100:.1f}%",
                        link_text,
                    )
                    first_event = False
                else:
                    table.add_row(
                        "" if j > 0 else "",
                        "",
                        "",
                        Text.from_markup(f"[dim]{bk_name}[/]") if j == 0 else "",
                        odd.outcome,
                        Text.from_markup(_fmt_odds(odd.price)),
                        f"{odd.implied_prob * 100:.1f}%",
                        link_text if j == 0 else "",
                    )

        table.add_section()

    if not events:
        table.add_row(
            Text.from_markup("[dim italic]Nenhum evento disponível...[/]"),
            *[""] * 7,
        )

    return table


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

def build_header(
    last_update: datetime,
    source_name: str,
    requests_remaining: int,
    refresh_interval: int,
    total_stake: float,
    n_events: int,
    n_arbs: int,
) -> Panel:
    now_str = last_update.strftime("%d/%m/%Y %H:%M:%S")
    req_str = f"{requests_remaining}" if requests_remaining >= 0 else "∞"

    lines = Text()
    lines.append("  ARBITRAGEM DE APOSTAS ESPORTIVAS — BRASIL  ", style="bold white on dark_green")
    lines.append("\n")
    lines.append(f"  Fonte: {source_name}  |  ", style="dim")
    lines.append(f"Atualizado: {now_str}  |  ", style="dim")
    lines.append(f"Req. restantes: {req_str}  |  ", style="dim")
    lines.append(f"Capital: R$ {total_stake:,.2f}  |  ", style="dim")
    lines.append(f"Refresh: {refresh_interval}s  |  ", style="dim")
    lines.append(f"Eventos: {n_events}  |  ", style="dim")
    lines.append(f"Arbitragens: ", style="dim")
    lines.append(str(n_arbs), style="bold green" if n_arbs > 0 else "dim")

    return Panel(
        Align.center(lines),
        border_style="bright_green",
        padding=(0, 1),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Render completo (para uso com Rich Live)
# ─────────────────────────────────────────────────────────────────────────────

def render(
    events: list[Event],
    opportunities: list[ArbitrageOpportunity],
    last_update: datetime,
    source_name: str,
    requests_remaining: int,
    refresh_interval: int,
    total_stake: float,
) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="body"),
    )
    layout["body"].split_column(
        Layout(name="arb",  ratio=3),
        Layout(name="rule", size=1),
        Layout(name="bets", ratio=4),
    )

    layout["header"].update(
        build_header(
            last_update=last_update,
            source_name=source_name,
            requests_remaining=requests_remaining,
            refresh_interval=refresh_interval,
            total_stake=total_stake,
            n_events=len(events),
            n_arbs=len(opportunities),
        )
    )
    layout["arb"].update(build_arbitrage_table(opportunities))
    layout["rule"].update(Rule(style="dim"))
    layout["bets"].update(build_bets_table(events))

    return layout


def render_once(
    events: list[Event],
    opportunities: list[ArbitrageOpportunity],
    last_update: datetime,
    source_name: str,
    requests_remaining: int,
    refresh_interval: int,
    total_stake: float,
) -> None:
    """Imprime o dashboard uma única vez (modo --once)."""
    console.print(
        build_header(
            last_update=last_update,
            source_name=source_name,
            requests_remaining=requests_remaining,
            refresh_interval=refresh_interval,
            total_stake=total_stake,
            n_events=len(events),
            n_arbs=len(opportunities),
        )
    )
    console.print(build_arbitrage_table(opportunities))
    console.print(Rule(style="dim"))
    console.print(build_bets_table(events))
