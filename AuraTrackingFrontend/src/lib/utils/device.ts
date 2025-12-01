/**
 * ============================================================
 * Device Utilities
 * ============================================================
 * Funções utilitárias para trabalhar com dados de dispositivos
 * ============================================================
 */

import type { Device } from '~/lib/api/client'
import type { SupabaseDevice } from '~/lib/supabase/types'

// Tipo para dispositivo enriquecido com metadados
export type EnrichedDevice = Device & {
  supabaseData?: SupabaseDevice;
  displayName: string;
  displayOperator: string;
  displayTag: string;
};

/**
 * Enriqueci dispositivos de telemetria com metadados do Supabase
 */
export function enrichDevicesWithMetadata(
  telemetryDevices: Device[],
  supabaseDevices: SupabaseDevice[]
): EnrichedDevice[] {
  // Criar mapa de dispositivos do Supabase por device_id
  const supabaseDeviceMap = new Map(
    supabaseDevices.map(d => [d.device_id, d])
  );

  return telemetryDevices.map(device => {
    const supabaseData = supabaseDeviceMap.get(device.device_id);

    return {
      ...device,
      supabaseData,
      displayName: supabaseData?.name || `Dispositivo ${device.device_id}`,
      displayOperator: supabaseData?.operator_id || device.operator_id,
      displayTag: device.device_id
    };
  });
}

/**
 * Enriqueci um único dispositivo com metadados
 */
export function enrichDeviceWithMetadata(
  device: Device,
  supabaseDevices: SupabaseDevice[]
): EnrichedDevice {
  const supabaseData = supabaseDevices.find(d => d.device_id === device.device_id);

  return {
    ...device,
    supabaseData,
    displayName: supabaseData?.name || `Dispositivo ${device.device_id}`,
    displayOperator: supabaseData?.operator_id || device.operator_id,
    displayTag: device.device_id
  };
}

/**
 * Obtém informações de exibição para um dispositivo
 */
export function getDeviceDisplayInfo(device: EnrichedDevice) {
  return {
    name: device.displayName,
    tag: device.displayTag,
    operator: device.displayOperator,
    status: device.status,
    speed: device.speed_kmh,
    location: device.latitude && device.longitude ? {
      lat: device.latitude,
      lng: device.longitude
    } : null,
    lastSeen: device.last_seen,
    totalPoints24h: device.total_points_24h,
    supabaseMetadata: device.supabaseData
  };
}

/**
 * Filtra dispositivos por status
 */
export function filterDevicesByStatus(devices: EnrichedDevice[], status?: 'online' | 'offline') {
  if (!status) return devices;
  return devices.filter(device => device.status === status);
}

/**
 * Ordena dispositivos por diferentes critérios
 */
export function sortDevices(devices: EnrichedDevice[], sortBy: 'name' | 'status' | 'speed' | 'last_seen' = 'name') {
  return [...devices].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return a.displayName.localeCompare(b.displayName);
      case 'status':
        const statusOrder = { online: 0, offline: 1 };
        return statusOrder[a.status] - statusOrder[b.status];
      case 'speed':
        return (b.speed_kmh || 0) - (a.speed_kmh || 0);
      case 'last_seen':
        return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
      default:
        return 0;
    }
  });
}

/**
 * Agrupa dispositivos por operador
 */
export function groupDevicesByOperator(devices: EnrichedDevice[]) {
  const groups = new Map<string, EnrichedDevice[]>();

  devices.forEach(device => {
    const operator = device.displayOperator;
    if (!groups.has(operator)) {
      groups.set(operator, []);
    }
    groups.get(operator)!.push(device);
  });

  return groups;
}

/**
 * Calcula estatísticas da frota
 */
export function calculateFleetStats(devices: EnrichedDevice[]) {
  const total = devices.length;
  const online = devices.filter(d => d.status === 'online').length;
  const offline = total - online;
  const moving = devices.filter(d => (d.speed_kmh || 0) > 1).length;
  const averageSpeed = devices.reduce((sum, d) => sum + (d.speed_kmh || 0), 0) / total;

  return {
    total,
    online,
    offline,
    moving,
    averageSpeed: Math.round(averageSpeed * 10) / 10,
    offlinePercentage: Math.round((offline / total) * 100),
    movingPercentage: Math.round((moving / total) * 100)
  };
}

