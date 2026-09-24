import { createContext, useContext, useEffect, useState } from "react";
import { getConfiguracaoEmpresa } from "../api/configuracaoEmpresa";
import { urlAbsoluta } from "../services/config";

const LogoContext = createContext({ logoUrl: null, setLogoUrl: () => {} });

export function LogoProvider({ children }) {
  const [logoUrl, setLogoUrl] = useState(null);

  useEffect(() => {
    getConfiguracaoEmpresa()
      .then((d) => { if (d?.logo_url) setLogoUrl(urlAbsoluta(d.logo_url)); })
      .catch(() => {});
  }, []);

  return (
    <LogoContext.Provider value={{ logoUrl, setLogoUrl }}>
      {children}
    </LogoContext.Provider>
  );
}

export function useLogo() {
  return useContext(LogoContext);
}
