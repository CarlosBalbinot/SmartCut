import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import styles from "./UsuarioConfiguracoesPage.module.css";

const CARDS = [
  {
    to: "/usuario/configuracao-usuario",
    titulo: "Dados do Usuário",
    descricao: "Nome, login e senha da sua conta.",
  },
  {
    to: "/usuario/configuracao-empresa",
    titulo: "Dados da Empresa",
    descricao: "Razão social, CNPJ, contato e logo.",
    modulo: "configuracoes_ver",
  },
  {
    to: "/usuario/configuracoes-gerais",
    titulo: "Configurações Gerais",
    descricao: "Impostos, insumos e custos de logística.",
    modulo: "configuracoes_ver",
  },
  {
    to: "/usuario/configuracoes-fiscais",
    titulo: "Configurações Fiscais",
    descricao: "Certificado digital, regime tributário e NF-e.",
    modulo: "configuracoes_ver",
  },
];

const ATUALIZACOES = [
  { versao: "v1.0", texto: "Módulo fiscal iniciado" },
  { versao: "v1.0", texto: "Sistema de autenticação" },
  { versao: "v1.0", texto: "Cadastro de clientes e consulta de CNPJ" },
  { versao: "v1.0", texto: "Importação de NF-e em XML" },
];

export default function UsuarioConfiguracoesPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const cardsVisiveis = CARDS.filter((c) => !c.modulo || hasPermission(c.modulo, "ver"));

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Configurações</h1>

      <div className={styles.cardsGrid}>
        {cardsVisiveis.map((c) => (
          <button
            key={c.to}
            type="button"
            className={styles.card}
            onClick={() => navigate(c.to)}
          >
            <span className={styles.cardTitulo}>{c.titulo}</span>
            <span className={styles.cardDescricao}>{c.descricao}</span>
          </button>
        ))}
      </div>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Últimas Atualizações</h2>
        <ul className={styles.updateList}>
          {ATUALIZACOES.map((a, i) => (
            <li key={i} className={styles.updateItem}>
              <span className={styles.updateBadge}>{a.versao}</span>
              <span className={styles.updateTexto}>{a.texto}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
