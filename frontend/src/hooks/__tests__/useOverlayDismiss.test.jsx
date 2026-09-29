import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import useOverlayDismiss from "../useOverlayDismiss";

function Overlay({ onClose, enabled }) {
  const props = useOverlayDismiss(onClose, { enabled });
  return (
    <div data-testid="overlay" {...props}>
      <input data-testid="campo" />
    </div>
  );
}

describe("useOverlayDismiss", () => {
  it("fecha com clique simples no fundo", () => {
    const onClose = vi.fn();
    render(<Overlay onClose={onClose} />);
    const overlay = screen.getByTestId("overlay");
    fireEvent.mouseDown(overlay);
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("não fecha quando o mousedown começou dentro do modal (seleção de texto)", () => {
    const onClose = vi.fn();
    render(<Overlay onClose={onClose} />);
    fireEvent.mouseDown(screen.getByTestId("campo"));
    // navegador dispara o click no ancestral comum (o overlay)
    fireEvent.click(screen.getByTestId("overlay"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("não fecha com click vindo de dentro do modal", () => {
    const onClose = vi.fn();
    render(<Overlay onClose={onClose} />);
    const campo = screen.getByTestId("campo");
    fireEvent.mouseDown(campo);
    fireEvent.click(campo);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("respeita enabled=false", () => {
    const onClose = vi.fn();
    render(<Overlay onClose={onClose} enabled={false} />);
    const overlay = screen.getByTestId("overlay");
    fireEvent.mouseDown(overlay);
    fireEvent.click(overlay);
    expect(onClose).not.toHaveBeenCalled();
  });
});
