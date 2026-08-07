import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Settings, Wifi, WifiOff, Shield, ShieldOff, Cloud, Monitor } from "lucide-react";
import { cn } from "@/lib/utils";
import { getHealth } from "@/api/health";

export function SettingsPage() {
  const [backendUrl] = useState(
    () => localStorage.getItem("backend_url") || "http://localhost:8000"
  );
  const [engine, setEngine] = useState(
    () => localStorage.getItem("engine_preference") || "cloud"
  );

  const { data: health, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30000,
  });

  const handleEngineChange = (value: string) => {
    setEngine(value);
    localStorage.setItem("engine_preference", value);
  };

  return (
    <div className="max-w-2xl mx-auto py-12 px-4 space-y-6">
      <div className="flex items-center gap-3 mb-8">
        <Settings className="h-6 w-6 text-muted-foreground" />
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      </div>

      {/* Backend URL */}
      <div className="bg-white rounded-xl border border-border shadow-sm p-5 space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Backend
        </h2>
        <p className="text-base font-mono text-foreground">{backendUrl}</p>
      </div>

      {/* Connection Status */}
      <div className="bg-white rounded-xl border border-border shadow-sm p-5 space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Connection
        </h2>
        <div className="flex items-center gap-3">
          {isLoading ? (
            <span className="text-sm text-muted-foreground">Checking…</span>
          ) : isError ? (
            <>
              <WifiOff className="h-5 w-5 text-red-500" />
              <span className="text-sm text-red-600 font-medium">Disconnected</span>
            </>
          ) : (
            <>
              <Wifi className="h-5 w-5 text-green-500" />
              <span className="text-sm text-green-600 font-medium">Connected</span>
            </>
          )}
        </div>
      </div>

      {/* Auth Status */}
      <div className="bg-white rounded-xl border border-border shadow-sm p-5 space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Authentication
        </h2>
        <div className="flex items-center gap-3">
          {health?.auth_required ? (
            <>
              <Shield className="h-5 w-5 text-amber-500" />
              <span className="text-sm font-medium">Auth required</span>
            </>
          ) : (
            <>
              <ShieldOff className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Open access</span>
            </>
          )}
        </div>
      </div>

      {/* Engine Preference */}
      <div className="bg-white rounded-xl border border-border shadow-sm p-5 space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Default Engine
        </h2>
        <div className="flex gap-3">
          {[
            { value: "cloud", label: "Cloud", icon: Cloud },
            { value: "local", label: "Local", icon: Monitor },
          ].map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              onClick={() => handleEngineChange(value)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors",
                engine === value
                  ? "border-foreground bg-foreground text-white"
                  : "border-border bg-white text-muted-foreground hover:border-foreground/30"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
