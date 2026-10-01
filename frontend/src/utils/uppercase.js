// Regra do projeto: nunca maiúsculo só visual. Campo com a classe global
// .sc-upper converte o VALOR no onChange; os demais ficam como digitados.

// Envolve um onChange existente (ex.: setF("nome")) convertendo o valor antes.
// Ajusta o DOM antes do state para o React não reescrever o campo — assim o
// cursor fica onde estava ao digitar no meio do texto.
export const upperOnChange = (onChange) => (e) => {
  const el = e.target;
  const { selectionStart, selectionEnd } = el;
  el.value = el.value.toUpperCase();
  if (selectionStart != null) el.setSelectionRange(selectionStart, selectionEnd);
  onChange(e);
};
