"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { User } from "@/types";

export default function AdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState("technician");
  const [inviting, setInviting] = useState(false);

  useEffect(() => {
    api.get<User[]>("/api/users").then(setUsers).catch((e: Error) => toast.error(e.message || "Failed to load users"));
  }, []);

  if (!user || (user.role !== "owner" && user.role !== "manager")) {
    return (
      <div className="py-16 text-center text-muted-foreground">
        You don&apos;t have permission to access this page.
      </div>
    );
  }

  const handleInvite = async () => {
    setInviting(true);
    try {
      const newUser = await api.post<User>("/api/users", {
        email: inviteEmail,
        name: inviteName,
        role: inviteRole,
      });
      setUsers((prev) => [...prev, newUser]);
      setShowInvite(false);
      setInviteEmail("");
      setInviteName("");
      toast.success("Invitation sent");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to invite user");
    } finally {
      setInviting(false);
    }
  };

  const handleRemove = async (userId: string) => {
    if (!window.confirm("Are you sure you want to remove this user?")) return;
    try {
      await api.delete(`/api/users/${userId}`);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      toast.success("User removed");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to remove user");
    }
  };

  const roleBadge = (role: string) => {
    switch (role) {
      case "owner":
        return <Badge>Owner</Badge>;
      case "manager":
        return <Badge className="bg-blue-600">Manager</Badge>;
      default:
        return <Badge variant="secondary">Technician</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Team Management</h1>
        {user.role === "owner" && (
          <Button onClick={() => setShowInvite(!showInvite)}>
            Invite User
          </Button>
        )}
      </div>

      {showInvite && (
        <Card>
          <CardHeader>
            <CardTitle>Invite a Team Member</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@example.com"
                />
              </div>
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="Full name"
                />
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="technician">Technician</option>
                  <option value="manager">Manager</option>
                </select>
              </div>
            </div>
            <Button onClick={handleInvite} disabled={inviting}>
              {inviting ? "Sending..." : "Send Invite"}
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-sm text-muted-foreground">
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Email</th>
                <th className="p-4 font-medium">Role</th>
                <th className="p-4 font-medium">Skill Level</th>
                {user.role === "owner" && (
                  <th className="p-4 font-medium">Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b last:border-0">
                  <td className="p-4 font-medium">{u.name}</td>
                  <td className="p-4 text-sm text-muted-foreground">
                    {u.email}
                  </td>
                  <td className="p-4">{roleBadge(u.role)}</td>
                  <td className="p-4 text-sm">{u.skill_level}</td>
                  {user.role === "owner" && (
                    <td className="p-4">
                      {u.id !== user.id && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:text-red-700"
                          onClick={() => handleRemove(u.id)}
                        >
                          Remove
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
