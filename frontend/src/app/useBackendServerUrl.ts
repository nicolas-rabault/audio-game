import { useEffect, useState } from "react";

export const useBackendServerUrl = () => {
  const [backendServerUrl, setBackendServerUrl] = useState<string | null>(null);

  useEffect(() => {
    // Prefer explicit env var if set
    const envBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
    if (envBackendUrl) {
      setBackendServerUrl(envBackendUrl.replace(/\/$/, "")); // remove trailing slash
      return;
    }

    if (typeof window !== "undefined") {
      const backendUrl = new URL("", window.location.href);
      backendUrl.port = "8000";
      backendUrl.pathname = "";
      backendUrl.search = ""; // strip any query parameters
      setBackendServerUrl(backendUrl.toString().replace(/\/$/, "")); // remove trailing slash
    }
  }, []);

  return backendServerUrl;
};
