export const toUpper = (value) =>
  typeof value === "string" ? value.toUpperCase() : value;

export const upperChangeHandler = (setter) => (e) => {
  const val = e.target.value.toUpperCase();
  e.target.value = val; // atualiza o input visualmente
  setter(val);           // atualiza o state
};

export const upperOnChange = (onChange) => (e) => {
  e.target.value = e.target.value.toUpperCase();
  onChange(e);
};
