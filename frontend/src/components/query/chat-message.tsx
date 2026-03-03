import { cn } from "@/lib/utils";
import { ConfidenceBar } from "@/components/ui/confidence-bar";
import { Button } from "@/components/ui/button";
import type { ConfidenceLevel } from "@/types";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  confidence?: number;
  confidenceLevel?: ConfidenceLevel;
  sources?: string[];
  className?: string;
}

export function ChatMessage({
  role,
  content,
  confidence,
  confidenceLevel,
  sources,
  className,
}: ChatMessageProps) {
  if (role === "user") {
    return (
      <div className={cn("flex justify-end", className)}>
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-slate-900 px-4 py-3 text-sm text-white">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex justify-start", className)}>
      <div className="max-w-[80%] space-y-3 rounded-2xl rounded-bl-md border bg-white px-4 py-3">
        <div className="text-sm text-slate-900 whitespace-pre-wrap">
          {content}
        </div>

        {confidence !== undefined && (
          <ConfidenceBar
            score={confidence}
            level={confidenceLevel}
            sources={sources}
          />
        )}

        <div className="flex gap-2">
          <Button variant="ghost" size="sm" disabled>
            Explain
          </Button>
          <Button variant="ghost" size="sm" disabled>
            Export PDF
          </Button>
          <Button variant="ghost" size="sm" disabled>
            View Sources
          </Button>
        </div>
      </div>
    </div>
  );
}
