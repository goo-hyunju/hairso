import type { ComponentProps, ReactNode } from "react";

/**
 * 공통 Button — 터치 타깃 최소 높이(min-h-11 = 44px)를 기본 상속(§4.1 태블릿 터치 오작동 방지).
 * onClick 등 핸들러를 정의하지 않고 전달만 하므로 presentational — "use client" 불필요(Server 호환).
 */

type Variant = "primary" | "secondary";

const variantClass: Record<Variant, string> = {
  primary: "bg-gray-900 text-white hover:bg-gray-800",
  secondary: "bg-white text-gray-900 border border-gray-300 hover:bg-gray-50",
};

export interface ButtonProps extends ComponentProps<"button"> {
  variant?: Variant;
  children: ReactNode;
}

export function Button({ variant = "primary", className = "", children, ...rest }: ButtonProps) {
  return (
    <button
      className={`inline-flex min-h-11 items-center justify-center rounded-lg px-4 text-base font-medium transition-colors disabled:opacity-50 ${variantClass[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
