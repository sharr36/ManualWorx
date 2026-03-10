"use client";

import { AuthProvider } from "@/lib/auth";
import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <AuthProvider>
      <h2 className="mb-6 text-center text-2xl font-bold text-white">
        Welcome back
      </h2>
      <LoginForm />
    </AuthProvider>
  );
}
