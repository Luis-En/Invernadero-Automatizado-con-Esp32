import { describe, expect, it } from 'vitest'
import { urlBase64ToUint8Array } from '../hooks/usePushNotifications'

describe('urlBase64ToUint8Array', () => {
  it('decodes base64url without padding', () => {
    expect(Array.from(urlBase64ToUint8Array('AQID'))).toEqual([1, 2, 3])
  })

  it('decodes two-byte payloads with the required padding', () => {
    expect(Array.from(urlBase64ToUint8Array('AQI'))).toEqual([1, 2])
  })

  it('accepts the - and _ alphabet used by VAPID keys', () => {
    expect(Array.from(urlBase64ToUint8Array('-_8'))).toEqual([251, 255])
  })
})
