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
    args = parser.parse_args()
    engine = Engine()
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
