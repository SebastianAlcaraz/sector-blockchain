"""Análisis de sentimiento de titulares y publicaciones.

Dos analizadores:
- LexiconAnalyzer: diccionario financiero en español e inglés. Gratis, sin conexión, aproximado.
- ClaudeAnalyzer: usa la API de Claude para entender cada texto en contexto (negaciones,
  ironía, "supera previsiones" frente a "no supera previsiones"). Requiere ANTHROPIC_API_KEY.

Ambos devuelven una puntuación por texto de -1 (muy negativo) a +1 (muy positivo).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

POSITIVE_LABEL, NEUTRAL_LABEL, NEGATIVE_LABEL = "Positivo", "Neutral", "Negativo"


@dataclass
class Scored:
    text: str
    score: float  # -1 .. +1
    label: str
    reason: str = ""


def label_for(score: float, threshold: float = 0.15) -> str:
    if score >= threshold:
        return POSITIVE_LABEL
    if score <= -threshold:
        return NEGATIVE_LABEL
    return NEUTRAL_LABEL


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


# Frases (se buscan antes que las palabras sueltas). Peso positivo = alcista.
PHRASES: dict[str, float] = {
    # inglés
    "beats estimates": 2.0, "beat estimates": 2.0, "tops estimates": 2.0, "better than expected": 2.0,
    "record high": 1.5, "all-time high": 1.5, "raises guidance": 2.0, "raised guidance": 2.0,
    "price target raised": 1.5, "raises price target": 1.5, "share buyback": 1.0, "dividend increase": 1.5,
    "misses estimates": -2.0, "missed estimates": -2.0, "worse than expected": -2.0, "cuts guidance": -2.0,
    "lowers guidance": -2.0, "price target cut": -1.5, "cuts price target": -1.5, "profit warning": -2.0,
    "sell-off": -1.5, "selloff": -1.5, "52-week low": -1.5, "rate hike": -0.5, "rate cut": 0.5,
    "to the moon": 1.5, "buy the dip": 1.0,
    # español
    "supera previsiones": 2.0, "supera las previsiones": 2.0, "supera expectativas": 2.0,
    "supera las expectativas": 2.0, "mejor de lo esperado": 2.0, "maximo historico": 1.5,
    "maximos historicos": 1.5, "eleva previsiones": 2.0, "mejora previsiones": 2.0, "eleva el precio objetivo": 1.5,
    "recompra de acciones": 1.0, "sube el dividendo": 1.5, "por debajo de lo esperado": -2.0,
    "peor de lo esperado": -2.0, "no alcanza": -1.5, "rebaja previsiones": -2.0, "recorta previsiones": -2.0,
    "rebaja el precio objetivo": -1.5, "recorta el precio objetivo": -1.5, "minimo anual": -1.5,
    "minimos anuales": -1.5, "subida de tipos": -0.5, "bajada de tipos": 0.5, "recogida de beneficios": -0.5,
}

WORDS: dict[str, float] = {
    # inglés
    "surge": 1.5, "surges": 1.5, "soar": 1.5, "soars": 1.5, "jump": 1.0, "jumps": 1.0, "rally": 1.2,
    "rallies": 1.2, "gain": 0.8, "gains": 0.8, "rise": 0.8, "rises": 0.8, "climb": 0.8, "climbs": 0.8,
    "upgrade": 1.5, "upgraded": 1.5, "outperform": 1.2, "bullish": 1.5, "strong": 0.8, "growth": 0.7,
    "profit": 0.6, "record": 0.8, "beat": 1.2, "beats": 1.2, "boost": 0.8, "boosts": 0.8, "optimism": 1.0,
    "rebound": 1.0, "recovery": 0.8, "buy": 0.8, "long": 0.5, "approval": 0.8, "approved": 0.8,
    "plunge": -1.8, "plunges": -1.8, "tumble": -1.5, "tumbles": -1.5, "crash": -2.0, "slump": -1.5,
    "slumps": -1.5, "fall": -0.8, "falls": -0.8, "drop": -0.8, "drops": -0.8, "decline": -0.8,
    "declines": -0.8, "downgrade": -1.5, "downgraded": -1.5, "underperform": -1.2, "bearish": -1.5,
    "weak": -0.8, "loss": -0.8, "losses": -0.8, "miss": -1.2, "misses": -1.2, "lawsuit": -1.0,
    "probe": -0.8, "investigation": -0.8, "fraud": -2.0, "bankruptcy": -2.0, "recession": -1.2,
    "fears": -1.0, "fear": -1.0, "concern": -0.6, "concerns": -0.6, "layoffs": -0.8, "sell": -0.8,
    "short": -0.5, "warning": -1.0, "inflation": -0.4, "tariffs": -0.6, "volatile": -0.4,
    # español
    "dispara": 1.5, "disparan": 1.5, "se dispara": 1.5, "sube": 0.8, "suben": 0.8, "subida": 0.8,
    "subidas": 0.8, "avanza": 0.8, "avanzan": 0.8, "gana": 0.8, "ganan": 0.8, "ganancias": 0.8,
    "repunta": 1.0, "repunte": 1.0, "rebota": 1.0, "rebote": 1.0, "beneficio": 0.6, "beneficios": 0.6,
    "record": 0.8, "crece": 0.7, "crecimiento": 0.7, "mejora": 0.8, "mejoran": 0.8, "optimismo": 1.0,
    "alcista": 1.5, "fuerte": 0.6, "solido": 0.6, "solidos": 0.6, "comprar": 0.8, "compra": 0.6,
    "recomendacion de compra": 1.2, "aprobacion": 0.8, "aprueba": 0.8, "impulsa": 0.8, "impulso": 0.6,
    "desploma": -1.8, "desploman": -1.8, "desplome": -1.8, "hunde": -1.5, "hunden": -1.5, "cae": -0.8,
    "caen": -0.8, "caida": -0.8, "caidas": -0.8, "baja": -0.6, "bajan": -0.6, "retrocede": -0.8,
    "retroceden": -0.8, "pierde": -0.8, "pierden": -0.8, "perdidas": -0.8, "rebaja": -1.0,
    "recorta": -0.8, "bajista": -1.5, "debil": -0.8, "debilidad": -0.8, "vender": -0.8, "venta": -0.4,
    "ventas masivas": -1.5, "demanda judicial": -1.0, "investigacion": -0.8, "fraude": -2.0,
    "quiebra": -2.0, "recesion": -1.2, "temor": -1.0, "temores": -1.0, "miedo": -1.0,
    "preocupacion": -0.6, "despidos": -0.8, "aranceles": -0.6, "inflacion": -0.4, "volatilidad": -0.4,
    "crisis": -1.2, "advierte": -0.8, "riesgo": -0.4, "eleva": 1.0, "elevan": 1.0, "rebajan": -1.0,
    "recortan": -0.8, "presiona": -0.8, "presionan": -0.8, "lastra": -0.8, "lastran": -0.8,
    "acuerdo": 0.4, "adquisicion": 0.3, "dividendo": 0.4, "sanciones": -0.8, "huelga": -0.8,
}

NEGATORS = {"no", "not", "never", "nunca", "sin", "without", "ni", "isn't", "doesn't", "won't", "fails", "fail"}

_TOKEN = re.compile(r"[a-z0-9'%+-]+")


class LexiconAnalyzer:
    name = "Diccionario financiero"

    def score_text(self, text: str) -> Scored:
        norm = _norm(text)
        total = 0.0
        hits: list[str] = []
        # Frases primero; se borran para no contarlas dos veces como palabras sueltas.
        for phrase, w in sorted(PHRASES.items(), key=lambda kv: -len(kv[0])):
            if phrase in norm:
                negated = re.search(r"\b(no|not|sin|without)\s+(\w+\s+){0,1}" + re.escape(phrase), norm)
                total += -w if negated else w
                hits.append(("no " if negated else "") + phrase)
                norm = norm.replace(phrase, " ")
        tokens = _TOKEN.findall(norm)
        for i, tok in enumerate(tokens):
            w = WORDS.get(tok)
            if w is None:
                continue
            negated = any(t in NEGATORS for t in tokens[max(0, i - 3) : i])
            total += -w if negated else w
            hits.append(("no " if negated else "") + tok)
        score = math.tanh(total / 2.5)
        reason = ("Palabras clave: " + ", ".join(hits[:6])) if hits else "Sin palabras clave de sentimiento."
        return Scored(text, score, label_for(score), reason)

    def score_many(self, texts: list[str], context: str = "") -> tuple[list[Scored], str]:
        return [self.score_text(t) for t in texts], ""


class ClaudeAnalyzer:
    """Clasifica un lote de textos con una sola llamada a la API de Claude."""

    name = "IA (Claude)"
    model = "claude-opus-5-5"

    def __init__(self, client=None):
        import anthropic

        self.client = client or anthropic.Anthropic()

    def score_many(self, texts: list[str], context: str = "") -> tuple[list[Scored], str]:
        from pydantic import BaseModel, Field

        class Item(BaseModel):
            indice: int
            sentimiento: str = Field(description="positivo, neutral o negativo para el precio del activo")
            puntuacion: float = Field(description="De -1 (muy negativo) a 1 (muy positivo)")
            motivo: str = Field(description="Motivo breve en español, máximo 15 palabras")

        class Result(BaseModel):
            items: list[Item]
            resumen: str = Field(description="Resumen en español de 2-3 frases del tono general y los temas principales")

        if not texts:
            return [], ""
        listing = "\n".join(f"{i}. {t}" for i, t in enumerate(texts))
        prompt = (
            f"Activo analizado: {context or 'mercado en general'}.\n\n"
            "Clasifica cada texto según cómo afecta previsiblemente al precio de ese activo "
            "(positivo, neutral o negativo) y dale una puntuación de -1 a 1. Ten en cuenta negaciones, "
            "ironía y si la noticia trata realmente de este activo; si no trata de él, es neutral. "
            "Devuelve un elemento por texto con su mismo índice, y un resumen general.\n\n"
            f"Textos:\n{listing}"
        )
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
            output_format=Result,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise RuntimeError("Claude no pudo analizar estos textos.")
        by_index = {it.indice: it for it in response.parsed_output.items}
        out = []
        for i, t in enumerate(texts):
            it = by_index.get(i)
            if it is None:
                out.append(Scored(t, 0.0, NEUTRAL_LABEL, "Sin clasificar"))
                continue
            score = max(-1.0, min(1.0, float(it.puntuacion)))
            out.append(Scored(t, score, label_for(score), it.motivo))
        return out, response.parsed_output.resumen


@dataclass
class Aggregate:
    score: float  # media ponderada, -1 .. +1
    label: str
    positive: int
    neutral: int
    negative: int

    @property
    def total(self) -> int:
        return self.positive + self.neutral + self.negative


def aggregate(scored: list[Scored], dates: list[datetime | None] | None = None, half_life_days: float = 3.0) -> Aggregate:
    """Media ponderada: las noticias recientes pesan más (vida media de `half_life_days`)."""
    if not scored:
        return Aggregate(0.0, "Sin datos", 0, 0, 0)
    now = datetime.now(timezone.utc)
    weights = []
    for i, _ in enumerate(scored):
        d = dates[i] if dates and i < len(dates) else None
        if d is None:
            weights.append(1.0)
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        age = max((now - d).total_seconds() / 86400, 0)
        weights.append(0.5 ** (age / half_life_days))
    wsum = sum(weights) or 1.0
    score = sum(s.score * w for s, w in zip(scored, weights)) / wsum
    counts = {POSITIVE_LABEL: 0, NEUTRAL_LABEL: 0, NEGATIVE_LABEL: 0}
    for s in scored:
        counts[s.label] += 1
    verdict = "Alcista" if score >= 0.15 else "Bajista" if score <= -0.15 else "Neutral"
    return Aggregate(score, verdict, counts[POSITIVE_LABEL], counts[NEUTRAL_LABEL], counts[NEGATIVE_LABEL])
