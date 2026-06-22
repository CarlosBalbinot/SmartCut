from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.precificacao import ConfiguracaoEmpresa, ConfiguracaoCustosFixos, Precificacao


def get_ou_criar_config(db: Session) -> ConfiguracaoEmpresa:
    config = db.execute(select(ConfiguracaoEmpresa)).scalars().first()
    if config is None:
        config = ConfiguracaoEmpresa()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def get_ou_criar_custos(db: Session) -> ConfiguracaoCustosFixos:
    custos = db.execute(select(ConfiguracaoCustosFixos)).scalars().first()
    if custos is None:
        custos = ConfiguracaoCustosFixos()
        db.add(custos)
        db.commit()
        db.refresh(custos)
    return custos


def calcular_precificacao(
    prec: Precificacao,
    config: ConfiguracaoEmpresa,
    custos: ConfiguracaoCustosFixos,
) -> dict:
    # ── Custo tecido ──
    if prec.valor_kg_tecido and prec.pecas_por_kg and Decimal(str(prec.pecas_por_kg)) > 0:
        custo_tecido = Decimal(str(prec.valor_kg_tecido)) / Decimal(str(prec.pecas_por_kg))
    elif prec.usar_custo_encaixe:
        custo_tecido = Decimal(str(prec.custo_tecido_encaixe or 0))
    else:
        custo_tecido = Decimal(str(prec.custo_tecido_manual or 0))

    # ── Custo linha ──
    metros_overlock = Decimal(str(prec.metros_linha_overlock or 0))
    metros_reta = Decimal(str(prec.metros_linha_reta or 0))
    metros_rolo_ov = Decimal(str(custos.metros_rolo_overlock or 1))
    metros_rolo_re = Decimal(str(custos.metros_rolo_reta or 1))
    custo_metro_overlock = Decimal(str(custos.custo_rolo_overlock or 0)) / metros_rolo_ov if metros_rolo_ov > 0 else Decimal("0")
    custo_metro_reta = Decimal(str(custos.custo_rolo_reta or 0)) / metros_rolo_re if metros_rolo_re > 0 else Decimal("0")
    custo_overlock = metros_overlock * custo_metro_overlock
    custo_reta = metros_reta * custo_metro_reta

    # ── Custo gasolina ──
    custo_gasolina = Decimal("0")
    dist = Decimal(str(custos.distancia_costureira_km or 0))
    num_viagens = Decimal(str(custos.num_viagens or 2))
    consumo = Decimal(str(custos.consumo_veiculo_km_l or 0))
    preco_comb = Decimal(str(custos.preco_combustivel or 0))
    pecas_viagem = Decimal(str(prec.pecas_por_viagem or 50))
    if dist > 0 and consumo > 0 and preco_comb > 0 and pecas_viagem > 0:
        custo_gasolina = (dist * 2 * num_viagens / consumo) * preco_comb / pecas_viagem

    # ── Custo saquinho (automático, 1 por peça) ──
    unidades_saq = Decimal(str(custos.unidades_saquinho_lote or 1))
    custo_saquinho = Decimal(str(custos.custo_saquinho_lote or 0)) / unidades_saq if unidades_saq > 0 else Decimal("0")

    # ── Custo caixa (unitário) ──
    custo_caixa_unit = Decimal("0")
    if custos.custo_caixa and custos.pecas_por_caixa and custos.pecas_por_caixa > 0:
        custo_caixa_unit = Decimal(str(custos.custo_caixa)) / Decimal(str(custos.pecas_por_caixa))

    custo_costura = Decimal(str(prec.custo_costura or 0))
    custo_etiqueta = Decimal(str(config.custo_etiqueta or 0))

    custo_base = (
        custo_tecido + custo_costura + custo_overlock + custo_reta
        + custo_gasolina + custo_saquinho + custo_caixa_unit + custo_etiqueta
    )

    aliquota = Decimal(str(config.aliquota_simples)) / Decimal("100")
    margem = Decimal(str(prec.margem_desejada))
    denominador = Decimal("1") - aliquota - margem

    base_result = {
        "custo_tecido": float(custo_tecido.quantize(Decimal("0.0001"))),
        "custo_costura": float(custo_costura),
        "custo_overlock": float(custo_overlock.quantize(Decimal("0.0001"))),
        "custo_reta": float(custo_reta.quantize(Decimal("0.0001"))),
        "custo_gasolina": float(custo_gasolina.quantize(Decimal("0.0001"))),
        "custo_saquinho": float(custo_saquinho.quantize(Decimal("0.0001"))),
        "custo_caixa": float(custo_caixa_unit.quantize(Decimal("0.0001"))),
        "custo_etiqueta": float(custo_etiqueta),
        "custo_base": float(custo_base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    }

    if denominador <= 0 or custo_base <= 0:
        return {**base_result, "preco_sugerido": None, "imposto": None, "lucro": None, "margem_real": None}

    preco = (custo_base / denominador).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    imposto = (preco * aliquota).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    lucro = (preco - custo_base - imposto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    margem_real = (lucro / preco).quantize(Decimal("0.0001")) if preco > 0 else Decimal("0")

    return {
        **base_result,
        "preco_sugerido": float(preco),
        "imposto": float(imposto),
        "lucro": float(lucro),
        "margem_real": float(margem_real),
    }


def recalcular_sugerido(
    prec: Precificacao,
    config: ConfiguracaoEmpresa,
    custos: ConfiguracaoCustosFixos,
) -> None:
    resultado = calcular_precificacao(prec, config, custos)
    if resultado.get("preco_sugerido") is not None:
        prec.preco_venda_sugerido = Decimal(str(resultado["preco_sugerido"]))
    else:
        prec.preco_venda_sugerido = None
