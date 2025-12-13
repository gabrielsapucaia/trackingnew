/**
 * Device summary as returned by the backend /api/devices.
 * Backend returns snake_case; we map to camelCase on the client.
 */
export type DeviceSummary = {
  deviceId: string;
  operatorId: string | null;
  lastSeen: string | null;
  latitude: number | null;
  longitude: number | null;
  speedKmh: number | null;
  totalPoints24h: number;
  status: "online" | "offline";
  /** Vibration level - placeholder until API provides this field */
  vibration?: number | null;
};

export type DevicesResponse = {
  devices: DeviceSummary[];
  count: number;
};
