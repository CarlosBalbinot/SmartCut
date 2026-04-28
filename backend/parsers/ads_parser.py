from typing import Any


def parse_ads(caminho: str) -> list[dict[str, Any]]:
    """Lê arquivo ADS (Accumark Design System) e extrai geometria.

    Retorna uma peça placeholder pois o formato proprietário ainda não
    foi implementado. O usuário deve verificar e ajustar a geometria.

    TODO: Implementar parser do formato binário/texto ADS.
          Documentação de referência: formato proprietário Gerber/Accumark.
    """
    return [
        {
            "nome_sugerido": "Peça ADS (verificar geometria)",
            "geometria_json": {
                "type": "Polygon",
                "coordinates": [
                    [[0, 0], [10, 0], [10, 15], [0, 15], [0, 0]]
                ],
            },
            "area_cm2": 150.0,
        }
    ]
