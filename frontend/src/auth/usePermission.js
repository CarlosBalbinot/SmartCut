import { useAuth } from "./useAuth";

export const usePermission = (modulo, acao) => {
  const { hasPermission } = useAuth();
  return hasPermission(modulo, acao);
};
