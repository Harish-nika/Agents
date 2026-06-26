import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const schema = z.object({
  username: z.string().min(1, "Username required"),
  password: z.string().min(1, "Password required"),
})

export const Route = createFileRoute("/login")({
  beforeLoad: () => { if (isLoggedIn()) throw redirect({ to: "/" }) },
  component: LoginPage,
  head: () => ({ meta: [{ title: "Login — Recruiting agent RA1" }] }),
})

function LoginPage() {
  const { loginMutation } = useAuth()
  const { showErrorToast } = useCustomToast()
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { username: "hr", password: "" } })

  return (
    <AuthLayout>
      <Form {...form}>
        <form onSubmit={form.handleSubmit((d) => loginMutation.mutate(d, { onError: handleError.bind(null, showErrorToast) }))} className="flex flex-col gap-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold">Fact Entry Recruiting Agent</h1>
            <p className="text-muted-foreground text-sm mt-1">Sign in to continue</p>
          </div>
          <FormField control={form.control} name="username" render={({ field }) => (
            <FormItem><FormLabel>Username</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="password" render={({ field }) => (
            <FormItem><FormLabel>Password</FormLabel><FormControl><PasswordInput {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <LoadingButton type="submit" loading={loginMutation.isPending} className="w-full">Sign In</LoadingButton>
        </form>
      </Form>
    </AuthLayout>
  )
}
