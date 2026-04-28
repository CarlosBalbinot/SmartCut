import math
from typing import Any


def criar_zona_exclusao(
    x_cm: float, y_cm: float, raio_cm: float, num_pontos: int = 32
) -> dict[str, Any]:
    """Gera um polígono circular de exclusão a partir de coordenadas e raio.

    Retorna a geometria como dicionário compatível com o campo geometria_json
    do encaixe, no formato GeoJSON-like.
    """
    pontos = [
        [
            x_cm + raio_cm * math.cos(2 * math.pi * i / num_pontos),
            y_cm + raio_cm * math.sin(2 * math.pi * i / num_pontos),
        ]
        for i in range(num_pontos)
    ]
    pontos.append(pontos[0])  # fechar o polígono

    return {
        "type": "Polygon",
        "coordinates": [pontos],
        "center": [x_cm, y_cm],
        "raio_cm": raio_cm,
    }


def listar_zonas_exclusao(defeitos: list[dict]) -> list[dict[str, Any]]:
    """Converte lista de defeitos em zonas de exclusão para o nesting."""
    return [
        criar_zona_exclusao(
            x_cm=d["x_cm"],
            y_cm=d["y_cm"],
            raio_cm=d.get("raio_cm", 5.0),
        )
        for d in defeitos
    ]
