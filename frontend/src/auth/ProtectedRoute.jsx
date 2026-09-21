import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./useAuth";
import styles from "./ProtectedRoute.module.css";

export default function ProtectedRoute({ modulo, adminOnly, children }) {
  const { usuario, loading, hasPermission } = useAuth();
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className={styles.spinnerWrap}>
        <div className={styles.spinner} />
      </div>
    );
  }

  if (!usuario) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && !usuario.is_admin) {
    return (
      <div className={styles.semPermissao}>
        <p className={styles.semPermissaoTexto}>
          Você não tem permissão para acessar esta página.
        </p>
        <button className={styles.btnVoltar} onClick={() => navigate(-1)}>
          Voltar
        </button>
      </div>
    );
  }

  if (modulo && !hasPermission(modulo, "ver")) {
    return (
      <div className={styles.semPermissao}>
        <p className={styles.semPermissaoTexto}>
          Você não tem permissão para acessar esta página.
        </p>
        <button className={styles.btnVoltar} onClick={() => navigate(-1)}>
          Voltar
        </button>
      </div>
    );
  }

  return children;
}
