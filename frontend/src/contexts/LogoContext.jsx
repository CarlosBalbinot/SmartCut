import { createContext, useContext, useEffect, useState } from "react";
import { configuracaoEmpresaApi } from "../services/api";

const LogoContext = createContext({ logoUrl: null, setLogoUrl: () => {} });

export function LogoProvider({ children }) {
  const [logoUrl, setLogoUrl] = useState(null);

  useEffect(() => {
    configuracaoEmpresaApi.get()
      .then((d) => { if (d?.logo_url) setLogoUrl(d.logo_url); })
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
