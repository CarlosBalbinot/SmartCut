import { useLocation } from "react-router-dom";
import styles from "./Topbar.module.css";

const ROUTE_TITLES = {
  "/":         "Tecidos",
  "/tecidos":  "Tecidos",
  "/moldes":   "Moldes",
  "/pedidos":  "Pedidos",
  "/encaixes": "Encaixes",
};

function getTitulo(pathname) {
  if (ROUTE_TITLES[pathname]) return ROUTE_TITLES[pathname];
  const base = "/" + pathname.split("/")[1];
  return ROUTE_TITLES[base] ?? "SmartCut";
}

export default function Topbar() {
  const { pathname } = useLocation();
  return (
    <div className={styles.topbar}>
      <span className={styles.titulo}>{getTitulo(pathname)}</span>
    </div>
  );
}
