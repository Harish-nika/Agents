import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { api } from "@/lib/api"

export const isLoggedIn = () => localStorage.getItem("access_token") !== null

export default function useAuth() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: user, isPending: isUserLoading } = useQuery({
    queryKey: ["currentUser"],
    queryFn: api.me,
    enabled: isLoggedIn(),
  })

  const loginMutation = useMutation({
    mutationFn: async ({ username, password }: { username: string; password: string }) => {
      const res = await api.login(username, password)
      localStorage.setItem("access_token", res.access_token)
    },
    onSuccess: () => navigate({ to: "/" }),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    queryClient.clear()
    navigate({ to: "/login" })
  }

  return { user, isUserLoading: isLoggedIn() && isUserLoading, loginMutation, logout }
}
