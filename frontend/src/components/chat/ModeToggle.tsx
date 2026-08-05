import { Shield, Sparkles } from "lucide-react";
import { Segmented } from "@/components/ui/primitives";

/*
 * The two modes differ in trustworthiness, not verbosity, so the label under
 * the switch states the tradeoff rather than describing a feature.
 */

export function ModeToggle({
  mode,
  onChange,
}: {
  mode: "grounded" | "assist";
  onChange: (m: "grounded" | "assist") => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Segmented
        size="sm"
        value={mode}
        onChange={onChange}
        options={[
          { value: "grounded", label: "Grounded", icon: Shield },
          { value: "assist", label: "Assist", icon: Sparkles },
        ]}
      />
      <p className="text-[11px] text-muted-foreground">
        {mode === "grounded"
          ? "Answers only from the sources, every citation checked."
          : "May reason beyond the sources — answers are not citation-verified."}
      </p>
    </div>
  );
}
