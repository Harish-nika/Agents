import { Link, type ErrorComponentProps } from "@tanstack/react-router"
import { Button } from "@/components/ui/button"

const ErrorComponent = ({ error, reset }: ErrorComponentProps) => {
  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : ""

  return (
    <div
      className="flex min-h-screen items-center justify-center flex-col p-4"
      data-testid="error-component"
    >
      <div className="flex items-center z-10">
        <div className="flex flex-col ml-4 items-center justify-center p-4">
          <span className="text-6xl md:text-8xl font-bold leading-none mb-4">
            Error
          </span>
          <span className="text-2xl font-bold mb-2">Oops!</span>
        </div>
      </div>

      <p className="text-lg text-muted-foreground mb-4 text-center z-10 max-w-xl break-words">
        {message || "Something went wrong. Please try again."}
      </p>
      <div className="flex gap-2">
        <Button type="button" variant="outline" onClick={() => reset()}>
          Retry
        </Button>
        <Link to="/">
          <Button>Go Home</Button>
        </Link>
      </div>
    </div>
  )
}

export default ErrorComponent
