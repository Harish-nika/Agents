import { toast } from "sonner"

export default function useCustomToast() {
  return {
    showSuccessToast: (msg: string) => toast.success(msg),
    showErrorToast: (msg: string) => toast.error(msg),
  }
}
