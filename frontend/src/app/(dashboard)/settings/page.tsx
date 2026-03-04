"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function SettingsPage() {
  const { user, tenant, refresh } = useAuth();

  if (!user || !tenant) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          {user.role === "owner" && (
            <TabsTrigger value="organization">Organization</TabsTrigger>
          )}
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-6">
          <ProfileTab user={user} onSave={refresh} />
        </TabsContent>

        {user.role === "owner" && (
          <TabsContent value="organization" className="mt-6">
            <OrganizationTab tenant={tenant} onSave={refresh} />
          </TabsContent>
        )}

        <TabsContent value="preferences" className="mt-6">
          <PreferencesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ProfileTab({
  user,
  onSave,
}: {
  user: { id: string; name: string; email: string; skill_level: string };
  onSave: () => void;
}) {
  const [name, setName] = useState(user.name);
  const [skillLevel, setSkillLevel] = useState(user.skill_level);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setSuccess(false);
    try {
      await api.patch(`/api/users/${user.id}`, { name, skill_level: skillLevel });
      setSuccess(true);
      toast.success("Profile saved");
      onSave();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label>Email</Label>
          <Input value={user.email} disabled className="bg-slate-50" />
        </div>
        <div className="space-y-2">
          <Label>Skill Level</Label>
          <select
            value={skillLevel}
            onChange={(e) => setSkillLevel(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="green">Green (New)</option>
            <option value="apprentice">Apprentice</option>
            <option value="journeyman">Journeyman</option>
          </select>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </Button>
          {success && (
            <span className="text-sm text-emerald-600">Saved!</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function OrganizationTab({
  tenant,
  onSave,
}: {
  tenant: { name: string; slug: string };
  onSave: () => void;
}) {
  const [name, setName] = useState(tenant.name);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setSuccess(false);
    try {
      await api.patch("/api/tenants/current", { name });
      setSuccess(true);
      toast.success("Organization updated");
      onSave();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to update organization");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Organization Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label>Slug</Label>
          <Input value={tenant.slug} disabled className="bg-slate-50" />
          <p className="text-xs text-muted-foreground">
            Cannot be changed after creation.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </Button>
          {success && (
            <span className="text-sm text-emerald-600">Saved!</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function PreferencesTab() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Preferences</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Theme and notification preferences coming soon.
        </p>
      </CardContent>
    </Card>
  );
}
