export function passwordStrengthErrors(password, username = '') {
  const errors = []
  if (password.length < 12) errors.push('Mínimo 12 caracteres')
  if (new TextEncoder().encode(password).length > 72) {
    errors.push('Máximo 72 bytes en UTF-8')
  }
  if (!/[a-z]/.test(password)) errors.push('Al menos una minúscula')
  if (!/[A-Z]/.test(password)) errors.push('Al menos una mayúscula')
  if (!/\d/.test(password)) errors.push('Al menos un número')
  if (!/[^A-Za-z0-9]/.test(password)) errors.push('Al menos un símbolo')
  if (username && password.toLowerCase().includes(username.toLowerCase())) {
    errors.push('No puede contener el nombre de usuario')
  }
  return errors
}

export function passwordStrengthScore(password, username = '') {
  if (!password) return 0
  const errors = passwordStrengthErrors(password, username).length
  return Math.max(0, 7 - errors)
}
