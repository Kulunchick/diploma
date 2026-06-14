import * as React from "react"
import { Eye, EyeOff } from "lucide-react"

import { cn } from "@shared/lib/utils"
import { Input } from "@shared/ui/input"

/**
 * Password field with an app-controlled show/hide toggle.
 *
 * The browser's native reveal control (Edge `::-ms-reveal`, and similar) is
 * suppressed because it is unreliable — it hides itself after the field loses
 * and regains focus. Our own button keeps the toggle visible at all times.
 */
const PasswordInput = React.forwardRef<
    HTMLInputElement,
    Omit<React.ComponentProps<"input">, "type">
>(({ className, ...props }, ref) => {
  const [visible, setVisible] = React.useState(false)

  return (
      <div className="relative">
        <Input
            ref={ref}
            type={visible ? "text" : "password"}
            className={cn(
                "pr-9 [&::-ms-reveal]:hidden [&::-ms-clear]:hidden",
                className
            )}
            {...props}
        />
        <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            tabIndex={-1}
            aria-label={visible ? "Сховати пароль" : "Показати пароль"}
            aria-pressed={visible}
            className="absolute inset-y-0 right-0 flex items-center rounded-md px-2.5 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
  )
})
PasswordInput.displayName = "PasswordInput"

export { PasswordInput }
