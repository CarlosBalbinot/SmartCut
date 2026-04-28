def peso_para_metros(
    peso_kg: float,
    gramatura_g_m2: float,
    largura_util_cm: float,
) -> float:
    """Converte peso em kg para metros lineares de tecido.

    Formula: metros = peso_kg * 1000 / (gramatura_g_m2 * largura_util_cm / 100)
    """
    return peso_kg * 1000 / (gramatura_g_m2 * largura_util_cm / 100)


def metros_para_peso(
    metros: float,
    gramatura_g_m2: float,
    largura_util_cm: float,
) -> float:
    """Converte metros lineares para peso em kg."""
    return metros * gramatura_g_m2 * largura_util_cm / 100 / 1000


def aplicar_encolhimento(comp_minimo: float, encolhimento_pct: float) -> float:
    """Aplica folga de encolhimento ao comprimento mínimo do enfesto."""
    return comp_minimo * (1 + encolhimento_pct / 100)


def calcular_custo(peso_kg: float, valor_por_kg: float) -> float:
    """Calcula custo total do tecido consumido."""
    return peso_kg * valor_por_kg
