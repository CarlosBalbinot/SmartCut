import { useEffect, useRef, useState } from "react";
import { Stage, Layer, Group, Line, Rect, Text } from "react-konva";
import styles from "./VisualizadorEncaixe.module.css";

export default function VisualizadorEncaixe({
  largura_cm,
  comprimento_cm,
  placements,
  colorMap,
}) {
  const containerRef = useRef(null);
  const [canvasWidth, setCanvasWidth] = useState(600);

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

  const scale = canvasWidth / largura_cm;
  const canvasHeight = Math.min(Math.ceil(comprimento_cm * scale), 600);

  return (
    <div ref={containerRef} className={styles.container}>
      <div className={styles.dimensoes}>
        {largura_cm} cm × {comprimento_cm} cm
      </div>
      <Stage width={canvasWidth} height={canvasHeight} className={styles.stage}>
        <Layer>
          {/* Fundo do tecido */}
          <Rect
            x={0}
            y={0}
            width={canvasWidth}
            height={canvasHeight}
            fill="#ffffff"
            stroke="#e5e5e5"
            strokeWidth={1}
          />

          {placements.map((pl, i) => {
            if (!pl.polygon || pl.polygon.length < 3) return null;

            const scaledPts = pl.polygon.flatMap((pt) => [
              pt[0] * scale,
              pt[1] * scale,
            ]);

            // Centróide para posicionar o label
            const cx =
              (pl.polygon.reduce((s, pt) => s + pt[0], 0) / pl.polygon.length) *
              scale;
            const cy =
              (pl.polygon.reduce((s, pt) => s + pt[1], 0) / pl.polygon.length) *
              scale;

            const label = pl.tamanho ?? pl.peca ?? "";

            return (
              <Group
                key={i}
                x={pl.x * scale}
                y={pl.y * scale}
                rotation={pl.rotation ?? 0}
              >
                <Line
                  points={scaledPts}
                  fill="rgba(37,99,235,0.15)"
                  stroke="#2563EB"
                  strokeWidth={1.5}
                  closed
                />
                {label && (
                  <Text
                    x={cx - 12}
                    y={cy - 7}
                    text={label}
                    fontSize={11}
                    fontStyle="bold"
                    fill="#000000"
                    width={24}
                    align="center"
                  />
                )}
              </Group>
            );
          })}
        </Layer>
      </Stage>
    </div>
  );
}
