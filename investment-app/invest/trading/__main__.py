"""Ejecuta un ciclo del bot desde la línea de comandos (lo usa el temporizador de la Raspberry).

    python -m invest.trading            # un ciclo
    python -m invest.trading --estado   # muestra el estado sin analizar
"""

import argparse
import json
import sys

from .engine import Engine


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot de inversión")
    parser.add_argument("--estado", action="store_true", help="Muestra el estado y sale")
    parser.add_argument("--revisar", action="store_true", help="Revisión semanal: evalúa decisiones y propone una estrategia mejorada")
    args = parser.parse_args()
    engine = Engine()
    if args.revisar:
        from .learning import review

        try:
            result = review(engine)
        except Exception as exc:
            engine.store.log("error", f"La revisión de estrategia falló: {type(exc).__name__}: {exc}")
            print(f"Error: {exc}")
            return 1
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if args.estado:
        print(json.dumps({
            "modo": engine.cfg.modo,
            "asesor": engine.cfg.asesor,
            "detenido": engine.store.paused,
            "pendientes": len(engine.store.proposals("pendiente")),
            "ultimo_ciclo": engine.store.get("last_cycle"),
        }, indent=2, ensure_ascii=False))
        return 0
    result = engine.run_cycle()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
