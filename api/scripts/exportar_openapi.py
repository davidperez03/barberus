"""Vuelca el schema OpenAPI de la app a un archivo JSON, sin levantar un servidor HTTP.

Soporte de tooling para `frontend/` (pipeline `pnpm generar-tipos-api`, ver
`frontend/package.json` y `frontend/README.md`): en vez de exigir `uvicorn` corriendo
manualmente y pegarle a `/openapi.json` por red, importa la instancia real de `app`
(`main.py`) y llama a `app.openapi()` -- FastAPI ya construye ese dict en memoria a partir
de los routers/esquemas Pydantic montados, así que esto es sencillamente volcarlo a disco.

No es parte de la app en runtime (no lo importa `main.py` ni ningún router) -- es un script
standalone, ejecutado vía `uv run python scripts/exportar_openapi.py` desde `api/`.

Requiere las mismas variables de entorno que la app (`.env`, ver `.env.example`) porque
`main.py` construye `ConfiguracionApp` al importarse -- no hace ninguna llamada de red a
Supabase, solo necesita que las variables estén *presentes* para pasar la validación de
`pydantic-settings`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DIRECTORIO_API = Path(__file__).resolve().parent.parent
if str(DIRECTORIO_API) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_API))


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--salida",
        type=Path,
        default=DIRECTORIO_API / "openapi.json",
        help="Ruta del archivo JSON de salida (default: api/openapi.json).",
    )
    argumentos = analizador.parse_args()

    from main import app  # import tardío: recién acá se necesita configuración/env cargado

    esquema = app.openapi()
    argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.salida.write_text(json.dumps(esquema, indent=2, ensure_ascii=False) + "\n")
    print(f"OpenAPI schema exportado a {argumentos.salida}")


if __name__ == "__main__":
    main()
