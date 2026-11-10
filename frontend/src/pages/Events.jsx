import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { format } from 'date-fns'
import { formatServerTime } from '../utils/time'

export function Events() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [error, setError] = useState('')

  const loadEvents = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const severity = filter === 'all' ? null : filter
      const data = await api.getEvents(severity, 200)
      setEvents(data)
    } catch (e) {
      setError(e.message || 'No se pudieron cargar los eventos')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    loadEvents()
  }, [loadEvents])

  const handleAcknowledge = async (id) => {
    try {
      await api.acknowledgeEvent(id)
      setEvents(prev => prev.map(e => (e.id === id ? { ...e, acknowledged: true } : e)))
    } catch (e) {
      setError(e.message || 'No se pudo reconocer el evento')
    }
  }

  const severityColors = {
    info: 'var(--color-primary)',
    warning: 'var(--color-warning)',
    critical: 'var(--color-critical)',
  }

  const severityLabels = {
    info: 'Información',
    warning: 'Advertencia',
    critical: 'Crítico',
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Eventos y Alarmas</h1>
        <button onClick={loadEvents} className="btn btn-secondary" disabled={loading}>
          {loading ? 'Cargando...' : 'Reintentar'}
        </button>
      </div>

      {error && (
        <div className="alert alert-critical" role="alert">
          {error}
        </div>
      )}

      <div className="tabs" role="group" aria-label="Filtrar eventos por severidad" style={{ marginBottom: '1rem' }}>
        {['all', 'info', 'warning', 'critical'].map(f => (
          <button
            key={f}
            type="button"
            className={`tab ${filter === f ? 'active' : ''}`}
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'Todos' : severityLabels[f]}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-state" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <p>Cargando eventos…</p>
        </div>
      ) : events.length === 0 ? (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✅</div>
            <p>No hay eventos {filter !== 'all' ? `de tipo ${severityLabels[filter]}` : ''}</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <div
            className="table-container"
            tabIndex={0}
            role="region"
            aria-label="Eventos y alarmas del invernadero"
          >
            <table className="table-cards">
              <caption className="visually-hidden">Eventos y alarmas del invernadero</caption>
              <thead>
                <tr>
                  <th scope="col" style={{ width: '160px' }}>Fecha/Hora</th>
                  <th scope="col" style={{ width: '100px' }}>Severidad</th>
                  <th scope="col" style={{ width: '120px' }}>Código</th>
                  <th scope="col">Mensaje</th>
                  <th scope="col" style={{ width: '120px' }}>Estado</th>
                  <th scope="col" style={{ width: '100px' }}>
                    <span className="visually-hidden">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {events.map(event => (
                  <tr key={event.id} style={{ opacity: event.acknowledged ? 0.65 : 1 }}>
                    <td data-label="Fecha/Hora">
                      {formatServerTime(event.timestamp, d => format(d, 'dd/MM/yyyy HH:mm:ss'))}
                    </td>
                    <td data-label="Severidad">
                      <span className="badge" style={{ background: `${severityColors[event.severity]}20`, color: severityColors[event.severity] }}>
                        {severityLabels[event.severity]}
                      </span>
                    </td>
                    <td data-label="Código" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>{event.code}</td>
                    <td data-label="Mensaje">{event.message}</td>
                    <td data-label="Estado">
                      <span className={`badge ${event.acknowledged ? 'badge-off' : 'badge-warning'}`}>
                        {event.acknowledged ? 'Reconocido' : 'Pendiente'}
                      </span>
                    </td>
                    <td data-label="">
                      {!event.acknowledged && (
                        <button onClick={() => handleAcknowledge(event.id)} className="btn btn-primary btn-sm">
                          Reconocer
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}