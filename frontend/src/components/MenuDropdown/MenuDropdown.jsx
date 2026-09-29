import { useEffect, useId, useRef, useState } from "react";
import styles from "./MenuDropdown.module.css";

/**
 * Botão que abre um menu de ações (abaixo do botão, alinhado à direita).
 *
 * trigger     — conteúdo do botão (texto e/ou SVG).
 * items       — [{ label, onClick, danger?, disabled?, title? }].
 * ariaLabel   — rótulo acessível quando o trigger é só ícone.
 * className   — classe extra do botão (a página define o visual dele).
 *
 * Fecha com Esc, clique fora ou ao escolher. Setas ↑/↓ (Home/End) movem
 * entre os itens habilitados; Enter/Espaço escolhe.
 */
export default function MenuDropdown({ trigger, items, ariaLabel, title, className = "" }) {
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(-1);
  const raizRef = useRef(null);
  const botaoRef = useRef(null);
  const itensRef = useRef([]);
  const menuId = useId();

  const habilitados = items.map((it, i) => (it.disabled ? -1 : i)).filter((i) => i >= 0);

  const fechar = (devolverFoco = true) => {
    setAberto(false);
    setAtivo(-1);
    if (devolverFoco) botaoRef.current?.focus();
  };

  const abrir = (primeiro = true) => {
    setAberto(true);
    setAtivo(primeiro ? (habilitados[0] ?? -1) : (habilitados.at(-1) ?? -1));
  };

  // Clique fora fecha sem roubar o foco do que foi clicado.
  useEffect(() => {
    if (!aberto) return;
    const fora = (e) => {
      if (!raizRef.current?.contains(e.target)) fechar(false);
    };
    document.addEventListener("mousedown", fora);
    return () => document.removeEventListener("mousedown", fora);
  }, [aberto]);

  useEffect(() => {
    if (aberto && ativo >= 0) itensRef.current[ativo]?.focus();
  }, [aberto, ativo]);

  const escolher = (item) => {
    if (item.disabled) return;
    fechar();
    item.onClick?.();
  };

  const mover = (passo) => {
    if (!habilitados.length) return;
    const pos = habilitados.indexOf(ativo);
    const prox = (pos + passo + habilitados.length) % habilitados.length;
    setAtivo(habilitados[prox]);
  };

  const onKeyDownBotao = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      abrir(true);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      abrir(false);
    }
  };

  const onKeyDownMenu = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      fechar();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      mover(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      mover(-1);
    } else if (e.key === "Home") {
      e.preventDefault();
      setAtivo(habilitados[0] ?? -1);
    } else if (e.key === "End") {
      e.preventDefault();
      setAtivo(habilitados.at(-1) ?? -1);
    } else if (e.key === "Tab") {
      fechar(false);
    }
  };

  return (
    <div className={styles.raiz} ref={raizRef}>
      <button
        ref={botaoRef}
        type="button"
        className={className}
        aria-haspopup="menu"
        aria-expanded={aberto}
        aria-controls={aberto ? menuId : undefined}
        aria-label={ariaLabel}
        title={title}
        onClick={() => (aberto ? fechar() : abrir(true))}
        onKeyDown={onKeyDownBotao}
      >
        {trigger}
      </button>
      {aberto && (
        <ul id={menuId} role="menu" className={styles.menu} onKeyDown={onKeyDownMenu}>
          {items.map((item, i) => (
            <li key={item.label} role="none">
              <button
                ref={(el) => (itensRef.current[i] = el)}
                type="button"
                role="menuitem"
                tabIndex={i === ativo ? 0 : -1}
                className={`${styles.item} ${item.danger ? styles.itemDanger : ""}`}
                aria-disabled={item.disabled || undefined}
                title={item.title}
                onClick={() => escolher(item)}
                onMouseEnter={() => !item.disabled && setAtivo(i)}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
