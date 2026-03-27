import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE_URL: str = "https://api.the-odds-api.com/v4"

# ---------------------------------------------------------------------------
# Comportamento
# ---------------------------------------------------------------------------
REFRESH_INTERVAL: int = int(os.getenv("REFRESH_INTERVAL", "30"))
MIN_PROFIT_PCT: float = float(os.getenv("MIN_PROFIT_PCT", "0.5"))
TOTAL_STAKE: float = float(os.getenv("TOTAL_STAKE", "1000"))
USE_MOCK: bool = os.getenv("USE_MOCK", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Alertas Telegram
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_MIN_PROFIT: float = float(os.getenv("TELEGRAM_MIN_PROFIT", "1.0"))
ALERT_COOLDOWN_MINUTES: int = int(os.getenv("ALERT_COOLDOWN_MINUTES", "5"))

# ---------------------------------------------------------------------------
# Esportes monitorados (regiões: br = casas brasileiras, eu = europeias)
# ---------------------------------------------------------------------------
SPORTS = [
    "soccer_brazil_campeonato",
    "soccer_brazil_copa_do_brasil",
    "soccer_conmebol_copa_libertadores",
    "soccer_conmebol_copa_sudamericana",
    "soccer_fifa_world_cup",
    "soccer_epl",
    "soccer_spain_la_liga",
    "basketball_nba",
    "basketball_ncaab",
    "tennis_atp_french_open",
]

REGIONS = "br,eu,us"
MARKETS = "h2h"  # head-to-head (moneyline / 1X2)
ODDS_FORMAT = "decimal"

# ---------------------------------------------------------------------------
# Links das casas de apostas (deeplinks para a seção de esportes)
# ---------------------------------------------------------------------------
BOOKMAKER_LINKS: dict[str, str] = {
    "betano":         "https://br.betano.com/sport/",
    "sportingbet":    "https://www.sportingbet.com/pt-br/sports",
    "bet365":         "https://www.bet365.com/#/AS/B1/",
    "bet365_br":      "https://www.bet365.com.br/#/AS/B1/",
    "1xbet":          "https://1xbet.com/pt/line/",
    "pinnacle":       "https://www.pinnacle.com/pt/odds/",
    "superbet":       "https://superbet.com.br/apostas-esportivas/",
    "betsul":         "https://www.betsul.com/sports",
    "parimatch":      "https://parimatch.com.br/pt/sport/",
    "kto":            "https://www.kto.com/pt-br/sports",
    "novibet":        "https://www.novibet.com.br/apostas/",
    "betfair":        "https://www.betfair.com/sport/",
    "betfair_ex_br":  "https://www.betfair.com/exchange/plus/football/",
    "vaidebet":       "https://vaidebet.com/sports/",
    "galera_bet":     "https://www.galerabet.com/sports/",
    "estrela_bet":    "https://www.estrelabet.com/pt/sports/",
    "mr_jack":        "https://www.mrjack.bet/sports/",
    "blaze":          "https://blaze.com/pt-BR/sports/",
    "br4bet":         "https://www.br4bet.com.br/sports/",
    "sportsbet_io":   "https://sportsbet.io/pt/sports/",
    "draftkings":     "https://www.draftkings.com/sports/",
    "fanduel":        "https://www.fanduel.com/sports",
    "unibet":         "https://www.unibet.com/betting/sports/",
    "williamhill":    "https://www.williamhill.com/sports/",
    "ladbrokes":      "https://www.ladbrokes.com/sports/",
    "draftkings":     "https://www.draftkings.com/sports/",
    "mybookie_ag":    "https://mybookie.ag/sportsbook/",
    "bovada_us":      "https://www.bovada.lv/sports/",
    "lowvig_ag":      "https://www.lowvig.ag/",
    "betonlineag":    "https://www.betonline.ag/sportsbook/",
    "matchbook":      "https://www.matchbook.com/sport/",
}

# Nomes amigáveis para exibição
BOOKMAKER_NAMES: dict[str, str] = {
    "betano":         "Betano",
    "sportingbet":    "Sportingbet",
    "bet365":         "Bet365",
    "bet365_br":      "Bet365 BR",
    "1xbet":          "1xBet",
    "pinnacle":       "Pinnacle",
    "superbet":       "Superbet",
    "betsul":         "Betsul",
    "parimatch":      "Parimatch",
    "kto":            "KTO",
    "novibet":        "Novibet",
    "betfair":        "Betfair",
    "betfair_ex_br":  "Betfair Exchange",
    "vaidebet":       "VaideBet",
    "galera_bet":     "GaleraBet",
    "estrela_bet":    "EstrelaBet",
    "mr_jack":        "Mr.Jack",
    "blaze":          "Blaze",
    "br4bet":         "BR4Bet",
    "sportsbet_io":   "Sportsbet.io",
    "draftkings":     "DraftKings",
    "fanduel":        "FanDuel",
    "unibet":         "Unibet",
    "williamhill":    "William Hill",
    "ladbrokes":      "Ladbrokes",
    "mybookie_ag":    "MyBookie",
    "bovada_us":      "Bovada",
    "lowvig_ag":      "LowVig",
    "betonlineag":    "BetOnline",
    "matchbook":      "Matchbook",
}


def get_bookmaker_link(bookmaker_key: str) -> str:
    return BOOKMAKER_LINKS.get(bookmaker_key, f"https://www.google.com/search?q={bookmaker_key}+apostas")


def get_bookmaker_name(bookmaker_key: str) -> str:
    return BOOKMAKER_NAMES.get(bookmaker_key, bookmaker_key.replace("_", " ").title())
