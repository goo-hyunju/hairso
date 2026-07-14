# FE Auth 연동 가이드 (Supabase Auth)

> BE는 선택적 인증을 지원한다: 요청에 유효한 Supabase 액세스 토큰이 있으면 검증해
> `generations.created_by`를 채우고, 없으면 익명으로 처리한다. 아래는 FE 최소 연결이다.
> (로그인/회원가입 UI 구현은 작업자 몫 — 이 문서는 토큰을 API 요청에 싣는 연결만 다룬다.)

## 1. 패키지 설치

```bash
npm install @supabase/supabase-js
```

## 2. 환경변수 (.env.local — gitignore)

`.env.example` 참고. publishable key 는 대시보드(Settings → API) 또는 관리자에게 요청.

```
NEXT_PUBLIC_SUPABASE_URL=https://gtbdiiunozsbbdajmick.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

## 3. Supabase 클라이언트 (예: src/lib/auth/supabase.ts)

```ts
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
);
```

## 4. API 클라이언트에 토큰 공급자 연결 (앱 초기화 시 1회)

`lib/api/client.ts`의 `setAuthTokenProvider`에 세션 토큰을 공급한다.
등록만 하면 이후 모든 `apiRequest`가 `Authorization: Bearer <token>`를 자동으로 싣는다.

```ts
import { setAuthTokenProvider } from "@/lib/api/client";
import { supabase } from "@/lib/auth/supabase";

setAuthTokenProvider(async () => {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null; // 로그인 안 됐으면 null(익명)
});
```

## 5. 로그인 (작업자 구현 — 예시)

```ts
await supabase.auth.signInWithPassword({ email, password });
// 또는 signInWithOtp / OAuth 등. 세션은 supabase-js 가 보관하고 자동 갱신.
```

## 동작 요약

- 로그인 O → `access_token` 자동 첨부 → BE 검증 → `created_by = user_id`
- 로그인 X → 헤더 없음 → BE 익명 처리(`created_by = null`)
- 토큰이 있으나 무효 → BE 401(`UNAUTHORIZED`) — 위조 토큰은 익명으로 통과시키지 않음
