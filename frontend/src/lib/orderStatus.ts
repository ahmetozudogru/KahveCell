import type { Order } from '../types/api'

export const ORDER_STATUS_LABELS: Record<Order['status'], string> = {
  PENDING: 'Bekliyor',
  ACCEPTED: 'Kabul Edildi',
  PREPARING: 'Hazırlanıyor',
  READY: 'Hazır',
  DELIVERED: 'Teslim Edildi',
}
