"use client";

import { useEffect, useState } from "react";
import { fetchDevices } from "../../lib/api-client/devices";
import type { DeviceSummary } from "../../types/devices";

type UseDevicesResult = {
  devices: DeviceSummary[];
  isLoading: boolean;
  error: string | null;
};

export function useDevices(pollIntervalMs = 5000): UseDevicesResult {
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    let timer: NodeJS.Timeout | undefined;

    const load = async () => {
      try {
        const { devices: fetchedDevices } = await fetchDevices();
        if (isMounted) {
          setDevices(fetchedDevices);
          setError(null);
          setIsLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Unknown error");
          setIsLoading(false);
        }
      }
    };

    load();
    timer = setInterval(load, pollIntervalMs);

    return () => {
      isMounted = false;
      if (timer) clearInterval(timer);
    };
  }, [pollIntervalMs]);

  return { devices, isLoading, error };
}
