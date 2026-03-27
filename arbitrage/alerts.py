"""
Sistema de alertas — notifica quando uma nova oportunidade de arbitragem é encontrada.

Suporte:
  - Telegram Bot (recomendado para uso no celular)
  - Log para arquivo JSON (histórico persistente)

Configuração Telegram (.env):
  TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
  TELEGRAM_CHAT_ID=-100123456789   (ou seu chat_id pessoal)

Para obter o token:
  1. Abra @BotFather no Telegram → /newbot
  2. Copie o token e coloque em TELEGRAM_BOT_TOKEN no .env

Para obter o chat_id:
  1. Inicie uma conversa com seu bot ou adicione-o a um grupo
  2. Acesse: https://api.telegram.org/bot<TOKEN>/getUpdates
  3. Procure "chat":{"id":...} na resposta
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from arbitrage.models import ArbitrageOpportunity
from arbitrage import config

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / "arbitrages.json"


# ─────────────────────────────────────────────────────────────────────────────
# Formatação de mensagem Telegram
# ─────────────────────────────────────────────────────────────────────────────

def _format_telegram_message(opp: ArbitrageOpportunity) -> str:
    """Monta mensagem Markdown para Telegram."""
    quality_emoji = {
        "EXCELENTE": "🔥",
        "ÓTIMA":     "✅",
        "BOA":       "💛",
        "MARGINAL":  "⚠️",
    }.get(opp.quality, "📊")

    lines = [
        f"{quality_emoji} *ARBITRAGEM {opp.quality}* — {opp.profit_pct:.2f}%",
        f"",
        f"*{opp.event.home_team} vs {opp.event.away_team}*",
        f"🏆 {opp.event.league}",
        f"💰 Lucro garantido: R$ {opp.guaranteed_profit:,.2f} "
        f"(capital R$ {opp.total_stake:,.2f})",
        f"",
        "*Pernas:*",
    ]

    for leg in opp.legs:
        lines.append(
            f"  • *{leg.bookmaker}* — {leg.outcome} @ {leg.odds:.2f} "
            f"→ Stake R$ {leg.stake:,.2f} | [Abrir]({leg.link})"
        )

    lines += [
        f"",
        f"🕐 {datetime.now(tz=timezone.utc).strftime('%d/%m %H:%M')} UTC",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Envio Telegram
# ─────────────────────────────────────────────────────────────────────────────

async def send_telegram(message: str) -> bool:
    """Envia mensagem via Telegram Bot API. Retorna True se enviou com sucesso."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Alerta Telegram enviado com sucesso")
                return True
            else:
                logger.warning("Falha no Telegram: %s %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("Erro ao enviar Telegram: %s", e)

    return False


async def alert_opportunities(
    new_opps: list[ArbitrageOpportunity],
    *,
    min_profit_for_alert: float | None = None,
) -> None:
    """
    Envia alerta Telegram para cada nova oportunidade acima do threshold.
    Chame apenas com oportunidades que ainda não foram alertadas.
    """
    threshold = min_profit_for_alert if min_profit_for_alert is not None else config.MIN_PROFIT_PCT

    for opp in new_opps:
        if opp.profit_pct < threshold:
            continue
        msg = _format_telegram_message(opp)
        sent = await send_telegram(msg)
        if sent:
            logger.info("Alerta enviado: %s %.2f%%", opp.event.title, opp.profit_pct)


# ─────────────────────────────────────────────────────────────────────────────
# Histórico em arquivo JSON
# ─────────────────────────────────────────────────────────────────────────────

def _opp_to_dict(opp: ArbitrageOpportunity) -> dict:
    """Serializa oportunidade para JSON."""
    return {
        "found_at":         opp.found_at.isoformat(),
        "event":            opp.event.title,
        "league":           opp.event.league,
        "commence_time":    opp.event.commence_time.isoformat(),
        "profit_pct":       opp.profit_pct,
        "guaranteed_profit": opp.guaranteed_profit,
        "total_stake":      opp.total_stake,
        "quality":          opp.quality,
        "sum_implied":      opp.sum_implied,
        "legs": [
            {
                "bookmaker":     leg.bookmaker,
                "outcome":       leg.outcome,
                "odds":          leg.odds,
                "stake":         leg.stake,
                "return_amount": leg.return_amount,
                "implied_prob":  leg.implied_prob,
                "link":          leg.link,
            }
            for leg in opp.legs
        ],
    }


def log_opportunities(opportunities: list[ArbitrageOpportunity]) -> None:
    """
    Appenda as oportunidades ao arquivo de log JSON.
    Cria o arquivo/diretório se necessário.
    Ignora silenciosamente erros de I/O.
    """
    if not opportunities:
        return

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Carrega histórico existente
        existing: list[dict] = []
        if LOG_FILE.exists():
            try:
                existing = json.loads(LOG_FILE.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []

        # Adiciona novas entradas
        new_entries = [_opp_to_dict(opp) for opp in opportunities]
        existing.extend(new_entries)

        # Mantém apenas as últimas 1000 entradas (evita crescimento ilimitado)
        if len(existing) > 1000:
            existing = existing[-1000:]

        LOG_FILE.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug("Log: %d oportunidades salvas em %s", len(new_entries), LOG_FILE)

    except Exception as e:
        logger.warning("Erro ao salvar log: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Deduplicação — evita alertar a mesma arb repetidamente
# ─────────────────────────────────────────────────────────────────────────────

def _opp_key(opp: ArbitrageOpportunity) -> str:
    """Chave única de uma oportunidade para deduplicação."""
    bookmakers = "|".join(sorted(leg.bookmaker_key for leg in opp.legs))
    return f"{opp.event.event_id}::{bookmakers}"


class AlertTracker:
    """
    Mantém em memória quais oportunidades já foram alertadas nesta sessão.
    Filtra duplicatas para não spammar o Telegram.
    """

    def __init__(self, cooldown_minutes: int = 5):
        self._seen: dict[str, datetime] = {}
        self._cooldown_minutes = cooldown_minutes

    def filter_new(self, opportunities: list[ArbitrageOpportunity]) -> list[ArbitrageOpportunity]:
        """Retorna apenas oportunidades que ainda não foram alertadas (ou expiraram o cooldown)."""
        now = datetime.now(tz=timezone.utc)
        new: list[ArbitrageOpportunity] = []

        for opp in opportunities:
            key = _opp_key(opp)
            last_seen = self._seen.get(key)

            if last_seen is None:
                new.append(opp)
                self._seen[key] = now
            else:
                elapsed = (now - last_seen).total_seconds() / 60
                if elapsed >= self._cooldown_minutes:
                    new.append(opp)
                    self._seen[key] = now

        # Limpa entradas antigas (>1h)
        cutoff = now
        self._seen = {
            k: v for k, v in self._seen.items()
            if (cutoff - v).total_seconds() < 3600
        }

        return new
