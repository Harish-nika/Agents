import { ApiError } from "@/lib/api"

export function handleError(showErrorToast: (msg: string) => void, error: Error) {
  if (error instanceof ApiError) {
    showErrorToast(typeof error.message === "string" ? error.message : "Request failed")
  } else {
    showErrorToast(error.message || "Unexpected error")
  }
}
