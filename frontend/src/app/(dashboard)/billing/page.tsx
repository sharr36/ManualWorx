"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api-client";
import { redirectToCheckout, redirectToPortal } from "@/lib/stripe";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PlanCard } from "@/components/billing/plan-card";
import { UsageMeter } from "@/components/billing/usage-meter";
import type { UsageInfo } from "@/types";

const PLANS = [
  {
    name: "Free",
    price: "Free",
    features: [
      "3 manuals",
      "50 queries/month",
      "Basic query mode",
      "PDF export",
    ],
    tier: "free",
  },
  {
    name: "Starter",
    price: "$29",
    features: [
      "10 manuals",
      "200 queries/month",
      "Full schematic viewer",
      "Basic teaching mode",
      "25 document exports/month",
    ],
    tier: "starter",
    popular: true,
  },
  {
    name: "Pro",
    price: "$79",
    features: [
      "50 manuals",
      "1,000 queries/month",
      "Advanced schematic viewer",
      "Full teaching mode",
      "Unlimited exports",
      "Priority support",
    ],
    tier: "pro",
  },
  {
    name: "Shop",
    price: "$149",
    features: [
      "Unlimited manuals",
      "5,000 queries/month",
      "Everything in Pro",
      "Team management",
      "Custom learning paths",
      "API access",
      "$10/user/month after 5",
    ],
    tier: "shop",
  },
];

export default function BillingPage() {
  const { tenant, user } = useAuth();
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  useEffect(() => {
    api.get<UsageInfo>("/api/billing/usage").then(setUsage).catch(() => {});
  }, []);

  if (!tenant || !user) return null;

  const isOwner = user.role === "owner";

  const handleUpgrade = async (plan: string) => {
    try {
      const result = await api.post<{ session_url: string }>(
        "/api/billing/checkout",
        {
          plan,
          success_url: `${window.location.origin}/billing?success=true`,
          cancel_url: `${window.location.origin}/billing`,
        }
      );
      redirectToCheckout(result.session_url);
    } catch {
      // error handling
    }
  };

  const handleManageSubscription = async () => {
    try {
      const result = await api.post<{ portal_url: string }>(
        "/api/billing/portal",
        { return_url: `${window.location.origin}/billing` }
      );
      redirectToPortal(result.portal_url);
    } catch {
      // error handling
    }
  };

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Billing & Usage</h1>

      {/* Current plan */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Current Plan</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                <Badge>{tenant.subscription_plan.toUpperCase()}</Badge>
              </p>
            </div>
            {isOwner && tenant.subscription_plan !== "free" && (
              <Button variant="outline" onClick={handleManageSubscription}>
                Manage Subscription
              </Button>
            )}
          </div>
        </CardHeader>
      </Card>

      {/* Usage */}
      {usage && (
        <Card>
          <CardHeader>
            <CardTitle>Usage This Period</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <UsageMeter
              label="Queries"
              used={usage.queries_used}
              limit={usage.queries_limit}
            />
            <UsageMeter
              label="Manuals Processed"
              used={usage.manuals_processed}
              limit={usage.manual_limit}
            />
          </CardContent>
        </Card>
      )}

      {/* Plan comparison */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Plans</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PLANS.map((plan) => (
            <PlanCard
              key={plan.tier}
              name={plan.name}
              price={plan.price}
              features={plan.features}
              isCurrent={tenant.subscription_plan === plan.tier}
              isPopular={plan.popular}
              onSelect={
                isOwner && tenant.subscription_plan !== plan.tier
                  ? () => handleUpgrade(plan.tier)
                  : undefined
              }
              disabled={!isOwner}
            />
          ))}
        </div>
      </div>

      {/* Processing fees */}
      <Card>
        <CardHeader>
          <CardTitle>Manual Processing Fees</CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-2 font-medium">Pages</th>
                <th className="pb-2 font-medium">Price</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b">
                <td className="py-2">Up to 500</td>
                <td className="py-2">$2.99</td>
              </tr>
              <tr className="border-b">
                <td className="py-2">501 — 1,500</td>
                <td className="py-2">$7.99</td>
              </tr>
              <tr className="border-b">
                <td className="py-2">1,501 — 3,000</td>
                <td className="py-2">$14.99</td>
              </tr>
              <tr>
                <td className="py-2">3,001 — 5,000+</td>
                <td className="py-2">$24.99</td>
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
