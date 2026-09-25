import { useState, useEffect } from 'react'
import { api } from '../api'
import { format } from 'date-fns'

export function Events() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  const loadEvents = async () => {
    setLoading(true)
    try {
      const severity = filter === 'all' ? null : filter
      const data = await api.getEvents(severity, 200)
      setEvents(data)
    } catch (e) {
      console.error('Failed to load events:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEvents()
  }, [filter])

  const handleAcknowledge = async (id) => {
    try {
      await api.acknowledgeEvent(id)
      setEvents(prev => prev.map(e => e.id === id ? { ...e, acknowledged: true } : e))
    } catch (e) {
      console.error('Failed to acknowledge:', e)
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
      </div>

      <div className="tabs" style={{ marginBottom: '1rem' }}>
        {['all', 'info', 'warning', 'critical'].map(f => (
          <button
            key={f}
            className={`tab ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'Todos' : severityLabels[f]}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}>Cargando eventos...</div>
      ) : events.length === 0 ? (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✅</div>
            <p>No hay eventos {filter !== 'all' ? `de tipo ${severityLabels[filter]}` : ''}</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '160px' }}>Fecha/Hora</th>
                  <th style={{ width: '100px' }}>Severidad</th>
                  <th style={{ width: '120px' }}>Código</th>
                  <th>Mensaje</th>
                  <th style={{ width: '120px' }}>Estado</th>
                  <th style={{ width: '100px' }}></th>
                </tr>
              </thead>
              <tbody>
                {events.map(event => (
                  <tr key={event.id} style={{ opacity: event.acknowledged ? 0.6 : 1 }}>
                    <td>{format(new Date(event.timestamp), 'dd/MM/yyyy HH:mm:ss')}</td>
                    <td>
                      <span className="badge" style={{ background: `${severityColors[event.severity]}20`, color: severityColors[event.severity] }}>
                        {severityLabels[event.severity]}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8125rem' }}>{event.code}</td>
                    <td>{event.message}</td>
                    <td>
                      <span className={event.acknowledged ? 'badge-off' : 'badge-warning'}>
                        {event.acknowledged ? 'Reconocido' : 'Pendiente'}
                      </span>
                    </td>
                    <td>
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