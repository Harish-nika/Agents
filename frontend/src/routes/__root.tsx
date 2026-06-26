import { createRootRoute, Outlet } from "@tanstack/react-router"
import ErrorComponent from "@/components/Common/ErrorComponent"

export const Route = createRootRoute({
  component: () => <Outlet />,
  errorComponent: ErrorComponent,
  notFoundComponent: () => <div className="p-8 text-center">Page not found</div>,
})
