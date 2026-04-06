# 공통 작업 규칙

## 커뮤니케이션
- 전문 용어를 쓸 때는 반드시 쉬운 말로 함께 설명한다.
  - 예: "컴포넌트(화면을 구성하는 조각 단위)"
- 코드 수정 시 요청한 부분만 건드린다. 요청하지 않은 부분을 임의로 바꾸지 않는다.
- 무엇을 바꿨는지 간단하게 설명한다.

## 코드 작업 원칙
- 요청한 것만 수정한다. 관련 없는 코드는 건드리지 않는다.
- 파일을 수정하기 전에 반드시 먼저 읽는다.
- 새 파일은 꼭 필요할 때만 만든다.
- 타입스크립트 타입은 기존 `types/workflow.ts` 기준을 따른다.

## k-black-music-magazine-app 프로젝트
- **목적**: 한국 블랙 뮤직 인스타그램 매거진 카피 자동 생성 및 슬라이드 PNG export
- **스택**: Next.js 14 App Router, TypeScript, Tailwind CSS, Supabase, Playwright
- **슬라이드 렌더링**: `lib/render/slides.ts` — Playwright로 HTML을 PNG로 변환
- **슬라이드 디자인 기준** (피그마 템플릿):
  - 1080x1350px
  - 배경: 투명 또는 이미지 위에 그라디언트 오버레이
  - 그라디언트: `linear-gradient(180deg, 투명 0% → 투명 45% → rgba(0,0,0,0.88) 100%)`
  - 헤드라인: Noto Serif KR Bold, 48px, left:54px, top:965px, width:880px, line-height:126px, color:#f5f0e8
  - 본문: Pretendard Medium, 32px, left:54px, top:1091px, width:984px, line-height:55px, color:rgba(245,240,232,0.75)
  - 커버(1장): 제목 고정 "당신의 취향, 얼마나 알고 계신가요?", top:79px
  - 프로보크(2장): 헤드라인만 `hookTrack` 동적 삽입, 본문 없음
  - 3~9장: `slide.headline`, `slide.body` 그대로 렌더링
- **API 구조**:
  - `POST /api/workflows` — 세션 생성
  - `POST /api/research` — Gemini 리서치
  - `POST /api/verify` — Claude 교차검증
  - `POST /api/select` — 훅 곡 선택
  - `POST /api/copy` — 카피 생성
  - `POST /api/export` — Playwright PNG export
- **환경변수**: GEMINI_API_KEY, ANTHROPIC_API_KEY, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, GOOGLE_DRIVE_CREDENTIALS

## Problem Reporting Protocol

For simple/obvious bugs → just fix it silently.

If ANY of these are true, stop and report before fixing:
- You've attempted the same fix more than once
- The fix touches 3+ files
- You don't fully understand the root cause yet
- The bug seems inconsistent or hard to reproduce

Report format:
- **Root cause**: [what is actually broken and why]
- **Scope**: [which files/modules are affected]
- **Honest difficulty**: [Easy / Hard / Uncertain] + one-line reason
- **Proposed fix + risk**: [what you'd do and what could go wrong]

Wait for approval before proceeding if Hard or Uncertain.