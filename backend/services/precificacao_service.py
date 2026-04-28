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
    val_overlock = Decimal(str(custos.valor_kg_overlock or 0))
    val_reta = Decimal(str(custos.valor_kg_reta or 0))
    custo_linha = metros_overlock * val_overlock + metros_reta * val_reta

    # ── Custo gasolina ──
    custo_gasolina = Decimal("0")
    if custos.distancia_costureira_km and custos.consumo_veiculo_km_l and custos.preco_combustivel:
        dist = Decimal(str(custos.distancia_costureira_km))
        num_viagens = Decimal(str(custos.num_viagens or 2))
        consumo = Decimal(str(custos.consumo_veiculo_km_l))
        preco_comb = Decimal(str(custos.preco_combustivel))
        pecas_viagem = Decimal(str(prec.pecas_por_viagem or 50))
        if consumo > 0 and pecas_viagem > 0:
            custo_gasolina = (dist * 2 * num_viagens / consumo) * preco_comb / pecas_viagem

    # ── Custo caixa (unitário) ──
    custo_caixa_unit = Decimal("0")
    if custos.custo_caixa and custos.pecas_por_caixa and custos.pecas_por_caixa > 0:
        custo_caixa_unit = Decimal(str(custos.custo_caixa)) / Decimal(str(custos.pecas_por_caixa))

    custo_costura = Decimal(str(prec.custo_costura or 0))
    custo_etiqueta = Decimal(str(config.custo_etiqueta or 0))
    custo_embalagem = Decimal(str(config.custo_embalagem or 0))

    custo_base = (
        custo_tecido + custo_costura + custo_linha
        + custo_gasolina + custo_caixa_unit + custo_etiqueta + custo_embalagem
    )

    aliquota = Decimal(str(config.aliquota_simples))
    margem = Decimal(str(prec.margem_desejada))
    denominador = Decimal("1") - aliquota - margem

    base_result = {
        "custo_tecido": float(custo_tecido.quantize(Decimal("0.0001"))),
        "custo_costura": float(custo_costura),
        "custo_linha": float(custo_linha.quantize(Decimal("0.0001"))),
        "custo_gasolina": float(custo_gasolina.quantize(Decimal("0.0001"))),
        "custo_caixa": float(custo_caixa_unit.quantize(Decimal("0.0001"))),
        "custo_etiqueta": float(custo_etiqueta),
        "custo_embalagem": float(custo_embalagem),
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
