const normalizar = (s) =>
  (s || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();

async function buscarIbge(uf, municipio) {
  if (!uf || !municipio) return "";
  try {
    const res = await fetch(`https://brasilapi.com.br/api/ibge/municipios/v1/${uf}`);
    if (!res.ok) return "";
    const lista = await res.json();
    const alvo = normalizar(municipio);
    const match = lista.find((m) => normalizar(m.nome) === alvo);
    return match ? String(match.codigo_ibge) : "";
  } catch {
    return "";
  }
}

// Busca ViaCEP e, com o município/UF retornados, cruza com a lista de
// municípios do BrasilAPI para obter o código IBGE (exigido no XML da NF-e).
// Nunca lança erro — falhas parciais retornam só o que foi possível obter.
export async function buscarEnderecoPorCep(cep) {
  const digits = (cep || "").replace(/\D/g, "");
  const resultado = {
    logradouro: "", bairro: "", complemento: "", cidade: "", uf: "", cep: digits, codigo_ibge: "",
  };
  if (digits.length !== 8) return resultado;

  try {
    const res = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
    if (res.ok) {
      const d = await res.json();
      if (!d.erro) {
        resultado.logradouro = d.logradouro || "";
        resultado.bairro = d.bairro || "";
        resultado.complemento = d.complemento || "";
        resultado.cidade = d.localidade || "";
        resultado.uf = d.uf || "";
      }
    }
  } catch {
    // segue com o que já tiver — usuário completa manualmente
  }

  resultado.codigo_ibge = await buscarIbge(resultado.uf, resultado.cidade);

  return resultado;
}
