export function SensorCard({ label, value, unit, status = 'normal', row, id }) {
  const statusClass = status === 'warning' ? 'warning' : status === 'critical' ? 'critical' : ''

  return (
    <div className={`sensor-card ${statusClass}`}>
      <div className="sensor-label">{label} {row ? `(${row})` : ''}</div>
      <div className="sensor-value">
        {value !== null && value !== undefined ? value.toFixed(1) : '—'}
        <span className="sensor-unit">{unit}</span>
      </div>
      <div className={`badge ${status === 'normal' ? 'badge-normal' : status === 'warning' ? 'badge-warning' : status === 'critical' ? 'badge-critical' : 'badge-off'}`}>
        {status === 'normal' ? 'Normal' : status === 'warning' ? 'Advertencia' : status === 'critical' ? 'Crítico' : 'Sin datos'}
      </div>
    </div>
  )
}

export function ActuatorCard({ name, icon, state, onToggle, disabled, loading }) {
  return (
    <div className="actuator-card">
      <div className="actuator-icon" style={{
        background: state ? 'rgba(45, 106, 79, 0.15)' : 'rgba(100, 116, 139, 0.1)',
        color: state ? 'var(--color-primary)' : 'var(--color-text-muted)'
      }}>
        {icon}
      </div>
      <div className="actuator-info">
        <div className="actuator-name">{name}</div>
        <div className="actuator-status">
          <span className={`badge ${state ? 'badge-on' : 'badge-off'}`}>
            {state ? 'ENCENDIDO' : 'APAGADO'}
          </span>
        </div>
      </div>
      <button
        onClick={onToggle}
        disabled={disabled || loading}
        className={`btn ${state ? 'btn-danger' : 'btn-primary'}`}
        style={{ minWidth: '100px' }}
      >
        {loading ? '...' : state ? 'Apagar' : 'Encender'}
      </button>
    </div>
  )
}