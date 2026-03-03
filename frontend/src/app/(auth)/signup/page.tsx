"use client";

import { AuthProvider } from "@/lib/auth";
import { SignupForm } from "@/components/auth/signup-form";

export default function SignupPage() {
  return (
    <AuthProvider>
      <h2 className="mb-6 text-center text-2xl font-bold text-slate-900">
        Create your account
      </h2>
      <SignupForm />
    </AuthProvider>
  );
}
