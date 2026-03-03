import { Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface PlanCardProps {
  name: string;
  price: string;
  period?: string;
  features: string[];
  isCurrent?: boolean;
  isPopular?: boolean;
  onSelect?: () => void;
  disabled?: boolean;
}

export function PlanCard({
  name,
  price,
  period = "/mo",
  features,
  isCurrent,
  isPopular,
  onSelect,
  disabled,
}: PlanCardProps) {
  return (
    <Card
      className={cn(
        "relative",
        isCurrent && "border-2 border-emerald-600",
        isPopular && !isCurrent && "border-2 border-blue-600"
      )}
    >
      {isCurrent && (
        <Badge className="absolute -top-2.5 left-4">Current Plan</Badge>
      )}
      {isPopular && !isCurrent && (
        <Badge className="absolute -top-2.5 left-4 bg-blue-600">Popular</Badge>
      )}

      <CardHeader>
        <CardTitle className="flex items-baseline justify-between">
          <span className="text-lg">{name}</span>
          <span>
            <span className="text-2xl font-bold">{price}</span>
            {price !== "Free" && (
              <span className="text-sm text-muted-foreground">{period}</span>
            )}
          </span>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        <ul className="space-y-2">
          {features.map((feature) => (
            <li key={feature} className="flex items-start gap-2 text-sm">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              {feature}
            </li>
          ))}
        </ul>

        {!isCurrent && onSelect && (
          <Button
            onClick={onSelect}
            disabled={disabled}
            className="w-full"
            variant={isPopular ? "default" : "outline"}
          >
            {disabled ? "Contact Sales" : "Upgrade"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
