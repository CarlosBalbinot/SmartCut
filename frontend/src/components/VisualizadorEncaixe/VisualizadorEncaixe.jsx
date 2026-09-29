import { useEffect, useRef, useState } from "react";
import { Stage, Layer, Group, Line, Rect, Text } from "react-konva";
import styles from "./VisualizadorEncaixe.module.css";

const ZOOM_STEP = 1.08;
const ZOOM_MIN = 0.3;
const ZOOM_MAX = 5;
const VIEW_INICIAL = { x: 0, y: 0, scale: 1 };

// Margem interna do canvas (px) — respiro entre a borda do Stage e o
// retângulo do tecido.
const PAD = 20;

// Altura máxima do conteúdo (px) — a largura do tecido (eixo vertical na
// mesa deitada) é sempre bem menor que o comprimento, então um teto fixo
// é suficiente (ver cálculo de `scale` abaixo, que respeita os dois
// limites ao mesmo tempo para nunca cortar peça nenhuma).
const MAX_CONTENT_H = 400;

function hexToRgba(hex, alpha) {
  const v = (hex || "#94a3b8").replace("#", "");
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// Rotaciona pontos em torno da ORIGEM (0,0) — mesma convenção do
// nest_worker.js (rotatePoly), não do centro do polígono. É essencial usar
// a mesma referência: nest_worker calcula a posição (x,y) de cada peça a
// partir do bounding box do polígono já rotacionado desta forma.
function rotacionarNaOrigem(pts, deg) {
  if (!deg) return pts;
  const rad = (deg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return pts.map(([x, y]) => [x * cos - y * sin, x * sin + y * cos]);
}

function bboxMin(pts) {
  let minX = Infinity;
  let minY = Infinity;
  for (const [x, y] of pts) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
  }
  return { minX, minY };
}

function poligonoArea(pts) {
  let area = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i];
    const [x2, y2] = pts[(i + 1) % pts.length];
    area += x1 * y2 - x2 * y1;
  }
  return Math.abs(area) / 2;
}

export default function VisualizadorEncaixe({
  largura_cm,
  comprimento_cm,
  placements,
  colorMap,
  pecaSelecionada,
}) {
  const containerRef = useRef(null);
  const [canvasWidth, setCanvasWidth] = useState(600);
  const [view, setView] = useState(VIEW_INICIAL);
  const [mostrarGrade, setMostrarGrade] = useState(true);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const update = () => {
      const w = containerRef.current.offsetWidth;
      if (w > 0) setCanvasWidth(w);
    };
    update();
    const obs = new ResizeObserver(update);
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  // Mesa de corte deitada: o comprimento (eixo X do nest_worker é a
  // LARGURA — ver nota abaixo) corre na horizontal, a largura do tecido
  // é a altura do retângulo. Escala única (sem distorcer): o menor fator
  // entre "cabe na largura disponível do canvas" e "não passa de
  // MAX_CONTENT_H de altura" — nunca corta peça, ao contrário de escalar
  // só pela largura do canvas e truncar a altura depois.
  const availW = Math.max(1, canvasWidth - PAD * 2);
  const scaleFromWidth = availW / comprimento_cm;
  const scaleFromHeight = MAX_CONTENT_H / largura_cm;
  const fitScale = Math.min(scaleFromWidth, scaleFromHeight);
  const stageHeight = Math.ceil(largura_cm * fitScale) + PAD * 2;

  // Zoom/pan (Stage) partem sempre de {x:0,y:0,scale:1} — nesse estado o
  // conteúdo já aparece na escala "fitScale" (baked nos pontos), ou seja,
  // o enfesto inteiro visível. view.scale é um multiplicador de câmera por
  // cima disso; strokeWidth/fontSize dividem por view.scale para não mudar
  // de espessura visual conforme o usuário dá zoom.
  useEffect(() => {
    setView(VIEW_INICIAL);
    setHover(null);
  }, [largura_cm, comprimento_cm]);

  function handleWheel(e) {
    e.evt.preventDefault();
    const stage = e.target.getStage();
    const pointer = stage.getPointerPosition();
    if (!pointer) return;
    const oldScale = view.scale;
    const mousePointTo = {
      x: (pointer.x - view.x) / oldScale,
      y: (pointer.y - view.y) / oldScale,
    };
    const direction = e.evt.deltaY > 0 ? -1 : 1;
    let newScale = direction > 0 ? oldScale * ZOOM_STEP : oldScale / ZOOM_STEP;
    newScale = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, newScale));
    setView({
      scale: newScale,
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    });
  }

  function zoomBotao(direcao) {
    setView((v) => ({
      ...v,
      scale: Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, direcao > 0 ? v.scale * 1.2 : v.scale / 1.2)),
    }));
  }

  function resetarZoom() {
    setView(VIEW_INICIAL);
  }

  // Grade vertical a cada 50cm ao longo do comprimento (agora o eixo
  // horizontal).
  const linhasGrade = [];
  if (mostrarGrade) {
    for (let x = 50; x < comprimento_cm; x += 50) {
      linhasGrade.push(x);
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <span className={styles.dimensoes}>
          {comprimento_cm} × {largura_cm} cm
        </span>
        <div className={styles.zoomControls}>
          <button
            type="button"
            className={styles.btnZoom}
            onClick={() => zoomBotao(-1)}
            title="Diminuir zoom"
          >
            −
          </button>
          <button
            type="button"
            className={styles.btnZoom}
            onClick={resetarZoom}
            title="Ajustar à tela"
          >
            ◎
          </button>
          <button
            type="button"
            className={styles.btnZoom}
            onClick={() => zoomBotao(1)}
            title="Aumentar zoom"
          >
            +
          </button>
        </div>
        <button
          type="button"
          className={`${styles.btnGrade} ${mostrarGrade ? styles.btnGradeAtivo : ""}`}
          onClick={() => setMostrarGrade((v) => !v)}
        >
          Grade
        </button>
      </div>

      <div ref={containerRef} className={styles.stageWrap}>
        <Stage
          width={canvasWidth}
          height={stageHeight}
          className={styles.stage}
          scaleX={view.scale}
          scaleY={view.scale}
          x={view.x}
          y={view.y}
          draggable
          onWheel={handleWheel}
          onDragEnd={(e) => setView((v) => ({ ...v, x: e.target.x(), y: e.target.y() }))}
        >
          <Layer listening={false}>
            {/* Fundo do tecido — deitado: comprimento na horizontal,
                largura na vertical. */}
            <Rect
              x={PAD}
              y={PAD}
              width={comprimento_cm * fitScale}
              height={largura_cm * fitScale}
              fill="#ffffff"
              stroke="#e5e5e5"
              strokeWidth={1 / view.scale}
            />

            {/* Grade vertical de referência a cada 50cm de comprimento —
                cor sólida e visível de propósito (não var(--sc-border),
                que é ~8% de opacidade e fica imperceptível sobre o fundo
                branco/cinza claro). */}
            {linhasGrade.map((x) => (
              <Group key={`grade-${x}`}>
                <Line
                  points={[
                    PAD + x * fitScale,
                    PAD,
                    PAD + x * fitScale,
                    PAD + largura_cm * fitScale,
                  ]}
                  stroke="#cccccc"
                  strokeWidth={0.5 / view.scale}
                  dash={[4 / view.scale, 4 / view.scale]}
                />
                <Text
                  x={PAD + x * fitScale + 2}
                  y={PAD - 12 / view.scale}
                  text={`${x}cm`}
                  fontSize={10 / view.scale}
                  fill="#999999"
                />
              </Group>
            ))}
          </Layer>

          <Layer>
            {placements.map((pl, i) => {
              if (!pl.polygon || pl.polygon.length < 3) return null;

              // O polígono bruto (geometria_json) não começa em (0,0) — tem
              // um offset arbitrário herdado do DXF original. nest_worker.js
              // rotaciona em torno da ORIGEM e usa o bounding-box resultante
              // para decidir onde encaixar a peça, mas nunca devolve esse
              // bounding-box. Sem reproduzir a mesma rotação+normalização
              // aqui, a peça desenhada fica deslocada do slot (x,y) que o
              // motor calculou.
              const rotDeg = pl.rotation ?? 0;
              const rotPts = rotacionarNaOrigem(pl.polygon, rotDeg);
              const { minX, minY } = bboxMin(rotPts);

              // IMPORTANTE: no nest_worker.js, pl.x é a posição ao longo da
              // LARGURA do tecido (eixo "width", 0..largura_cm) e pl.y é a
              // posição ao longo do COMPRIMENTO (eixo "length", que o
              // worker minimiza) — confirmado no docstring do worker e nos
              // dados reais (pl.x nunca passa de largura_cm; pl.y vai até
              // comprimento_cm). Como a mesa agora é desenhada deitada
              // (comprimento na horizontal), o eixo de tela X vem de pl.y
              // e o eixo de tela Y vem de pl.x — é uma transposição, não
              // só um redimensionamento do canvas.
              const scaledPts = rotPts.flatMap(([x, y]) => [
                (y - minY) * fitScale,
                (x - minX) * fitScale,
              ]);
              const cor = colorMap?.[pl.id] ?? "#94a3b8";

              let fillAlpha = 0.3;
              if (pecaSelecionada != null) {
                fillAlpha = pl.id === pecaSelecionada ? 0.7 : 0.1;
              }

              const cxLocal =
                (rotPts.reduce((s, [, y]) => s + y, 0) / rotPts.length - minY) * fitScale;
              const cyLocal =
                (rotPts.reduce((s, [x]) => s + x, 0) / rotPts.length - minX) * fitScale;

              const groupX = PAD + pl.y * fitScale;
              const groupY = PAD + pl.x * fitScale;

              return (
                <Group
                  key={i}
                  x={groupX}
                  y={groupY}
                  onMouseEnter={(e) => {
                    const stage = e.target.getStage();
                    if (stage) stage.container().style.cursor = "pointer";
                    setHover({
                      cx: groupX + cxLocal,
                      cy: groupY + cyLocal,
                      nome: `${pl.peca ?? pl.grupo_nome ?? "Peça"}${pl.espelhada ? " (esp.)" : ""}`,
                      tamanho: pl.tamanho,
                      area: poligonoArea(pl.polygon),
                    });
                  }}
                  onMouseLeave={(e) => {
                    const stage = e.target.getStage();
                    if (stage) stage.container().style.cursor = "grab";
                    setHover(null);
                  }}
                >
                  {/* Metade espelhada de um par (motor v2): o polígono já
                      vem virado no mapa_json; aqui só se marca — contorno
                      tracejado e etiqueta "(esp.)" no centro da peça. */}
                  <Line
                    points={scaledPts}
                    fill={hexToRgba(cor, fillAlpha)}
                    stroke={cor}
                    strokeWidth={(pl.espelhada ? 1.4 : 1) / view.scale}
                    dash={pl.espelhada ? [6 / view.scale, 3 / view.scale] : undefined}
                    closed
                  />
                  {pl.espelhada && (
                    <Text
                      x={cxLocal - 20 / view.scale}
                      y={cyLocal - 5 / view.scale}
                      width={40 / view.scale}
                      align="center"
                      text="(esp.)"
                      fontSize={10 / view.scale}
                      fill="#1D1D1F"
                      listening={false}
                    />
                  )}
                </Group>
              );
            })}

            {hover && (
              <Group
                x={hover.cx}
                y={hover.cy}
                scaleX={1 / view.scale}
                scaleY={1 / view.scale}
                listening={false}
              >
                <Rect
                  x={-55}
                  y={-46}
                  width={110}
                  height={hover.tamanho ? 40 : 28}
                  fill="#1D1D1F"
                  cornerRadius={4}
                  opacity={0.92}
                />
                <Text
                  x={-49}
                  y={-40}
                  width={98}
                  text={hover.nome}
                  fontSize={11}
                  fontStyle="bold"
                  fill="#ffffff"
                />
                {hover.tamanho && (
                  <Text
                    x={-49}
                    y={-26}
                    width={98}
                    text={`Tam. ${hover.tamanho}`}
                    fontSize={10}
                    fill="#d1d5db"
                  />
                )}
                <Text
                  x={-49}
                  y={hover.tamanho ? -14 : -26}
                  width={98}
                  text={`${hover.area.toFixed(0)} cm²`}
                  fontSize={10}
                  fill="#d1d5db"
                />
              </Group>
            )}
          </Layer>
        </Stage>
      </div>
    </div>
  );
}
