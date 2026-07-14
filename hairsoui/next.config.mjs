/** @type {import('next').NextConfig} */

// 개발 편의 프록시: 브라우저에서 /api/* 를 BE(apimgr)로 전달해 CORS 없이 붙인다.
// 대상 포트는 env 로 바꿀 수 있다(기본 127.0.0.1:8000 — uvicorn 개발 기본).
// 운영은 이 프록시가 아니라 실제 게이트웨이/도메인 설정을 쓴다(로드맵).
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` },
    ];
  },
};

export default nextConfig;
