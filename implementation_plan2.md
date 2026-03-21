# Instagram AI Analyzer — Implementation Plan

개인용 인스타그램 계정/트렌드 분석 도구. Playwright로 인스타 데이터를 수집하고, Gemini API로 전문 분석가 수준의 질적 분석 리포트를 생성한다.

## User Review Required

> [!WARNING]
> **Instagram ToS**: 브라우저 자동화를 통한 스크래핑은 Instagram 이용약관 위반 소지가 있습니다. 개인 사용 목적이며, rate limiting을 적용합니다.

> [!IMPORTANT]
> **Gemini 모델 선택**: `gemini-2.0-flash` 또는 `gemini-2.0-pro` 사용 예정. Provider 패턴으로 다른 모델 교체 가능.

---

## Instagram 로그인 전략 (Session-based)

**원칙**: Instagram username/password를 `.env.local`이나 코드 어디에도 저장하지 않는다.

### 전체 흐름

```
[최초 1회] 수동 로그인 (브라우저 UI)
        ↓
Playwright storageState → .sessions/instagram.json 저장
        ↓
[이후] 분석 요청 시 세션 파일로 자동 로그인
        ↓
[세션 만료 시] 대시보드에서 "재로그인" 버튼 → 수동 재로그인
```

### 1단계: 최초 로그인 (수동)

대시보드 설정 페이지 또는 CLI 스크립트로 Playwright 브라우저를 **headful 모드(화면 보이는 모드)**로 열어서 유저가 직접 로그인한다.

```typescript
// scripts/instagram-login.ts
import { chromium } from 'playwright';

async function manualLogin() {
  const browser = await chromium.launch({ headless: false }); // 화면 보임
  const context = await browser.newContext();
  const page = await context.newPage();
  
  await page.goto('https://www.instagram.com/accounts/login/');
  
  console.log('🔐 브라우저에서 Instagram에 로그인해주세요...');
  console.log('   로그인 완료 후 피드가 보이면 자동으로 세션이 저장됩니다.');
  
  // 로그인 완료 감지: 피드 페이지로 이동하면 완료
  await page.waitForURL('**/instagram.com/**', { 
    timeout: 120_000  // 2분 대기
  });
  // 추가로 피드 로드 완료까지 대기
  await page.waitForTimeout(3000);
  
  // 세션 저장
  await context.storageState({ path: '.sessions/instagram.json' });
  console.log('✅ 세션 저장 완료: .sessions/instagram.json');
  
  await browser.close();
}
```

### 2단계: 세션 재사용 (자동)

분석 요청이 들어오면 저장된 `storageState`로 새 브라우저 컨텍스트를 생성:

```typescript
// src/lib/scraper/session.ts
import { existsSync } from 'fs';

const SESSION_PATH = '.sessions/instagram.json';

export function isSessionValid(): boolean {
  if (!existsSync(SESSION_PATH)) return false;
  // 파일 수정 시간 체크 — 7일 이상된 세션은 만료 처리
  const stats = statSync(SESSION_PATH);
  const ageInDays = (Date.now() - stats.mtimeMs) / (1000 * 60 * 60 * 24);
  return ageInDays < 7;
}

export async function createAuthenticatedContext(browser: Browser) {
  if (!isSessionValid()) {
    throw new SessionExpiredError('세션이 만료되었습니다. 재로그인해주세요.');
  }
  return browser.newContext({ storageState: SESSION_PATH });
}
```

### 3단계: 세션 만료 시 재로그인

- 스크래핑 중 로그인 페이지로 리다이렉트 감지 → `SessionExpiredError` throw
- 프론트엔드에서 "세션 만료" 알림 + "재로그인" 버튼 표시
- 재로그인 버튼 클릭 → `/api/auth/instagram` 호출 → headful Playwright 브라우저 오픈
- 또는 CLI: `npm run login:instagram` 실행

### 4단계: 세션 유효성 체크 API

```
GET /api/auth/session-status
→ { valid: boolean, expires_in_days: number, last_login: string }

POST /api/auth/instagram-login
→ headful 브라우저 오픈 → 수동 로그인 → 세션 저장
```

### 보안 / .gitignore

```gitignore
# Instagram 세션 (절대 커밋 금지)
.sessions/
instagram-session.json

# 환경 변수
.env.local
```

`.sessions/` 디렉토리는 프로젝트 루트에 생성, 반드시 [.gitignore](file:///Users/minsoopark/Downloads/%EB%B0%94%EC%9D%B4%EB%B8%8C%EC%BD%94%EB%94%A9/.gitignore)에 포함.

---

## 아키텍처 개요

```
┌─────────────────────────────────────────┐
│            Next.js 14 Frontend          │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐  │
│  │ 계정분석  │ │ 트렌드   │ │ 히스토리│  │
│  │ 페이지   │ │ 분석     │ │ 페이지  │  │
│  └────┬─────┘ └────┬─────┘ └────┬────┘  │
│       └─────────┬───┘            │       │
│            API Routes            │       │
│       ┌─────────┴───────┐       │       │
│       │ /api/analyze     │       │       │
│       │ /api/trends      │       │       │
│       │ /api/history     │       │       │
│       └──┬──────────┬────┘       │       │
│          │          │            │       │
│  ┌───────┴──┐ ┌─────┴─────┐ ┌───┴────┐  │
│  │Playwright│ │ Gemini AI  │ │Supabase│  │
│  │Scraper   │ │ Provider   │ │  DB    │  │
│  └──────────┘ └────────────┘ └────────┘  │
└─────────────────────────────────────────┘
```

---

## Proposed Changes

### 1. 프로젝트 초기 세팅

#### [NEW] `insta-analyzer/` (프로젝트 루트)

- `npx -y create-next-app@latest ./` 로 Next.js 14 (App Router, TypeScript, Tailwind) 프로젝트 생성
- Shadcn UI 초기화 (`npx shadcn@latest init`)
- 추가 패키지: `playwright`, `@google/genai`, `zustand`, `zod`, `lucide-react`
- 프로젝트 경로: `/Users/minsoopark/Downloads/바이브코딩/insta-analyzer/`

---

### 2. Instagram Playwright 스크래퍼

#### [NEW] [instagram.ts](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/lib/scraper/instagram.ts)

Playwright로 Instagram에 접속하여 데이터를 수집하는 코어 모듈.

**주요 기능:**
- `scrapeProfile(username)` — 프로필 기본 정보 (팔로워/팔로잉 수, 바이오, 프로필 이미지)
- `scrapePosts(username, count=12)` — 최근 게시물 N개의 이미지 URL, 캡션, 좋아요/댓글 수, 해시태그, 게시 날짜
- `scrapeHashtag(tag, count=30)` — 해시태그 탐색 페이지에서 인기 게시물 + 최근 게시물 수집
- `capturePostScreenshots(urls[])` — 게시물 페이지 스크린샷 (비주얼 분석용)

**구현 세부:**
```typescript
// session.ts에서 인증된 컨텍스트를 가져와 사용
const browser = await chromium.launch({ headless: true });
const context = await createAuthenticatedContext(browser); // 세션 기반

// 스크래핑 중 로그인 리다이렉트 감지
page.on('response', (res) => {
  if (res.url().includes('/accounts/login')) {
    throw new SessionExpiredError('세션 만료');
  }
});

// rate limiting
const DELAY_BETWEEN_REQUESTS = 2000;
```

#### [NEW] [types.ts](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/lib/scraper/types.ts)

스크래핑 결과의 TypeScript 타입 정의:
```typescript
interface ScrapedProfile {
  username: string;
  full_name: string;
  bio: string;
  followers_count: number;
  following_count: number;
  posts_count: number;
  profile_image_url: string;
  is_verified: boolean;
}

interface ScrapedPost {
  post_url: string;
  image_urls: string[];
  caption: string;
  hashtags: string[];
  likes_count: number;
  comments_count: number;
  posted_at: string;
  is_reel: boolean;
  is_carousel: boolean;
}
```

---

### 3. AI Provider (Gemini)

#### [NEW] [provider.ts](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/lib/ai/provider.ts)

AI 분석 모듈의 추상 인터페이스. 나중에 다른 모델로 교체 가능:
```typescript
interface AIProvider {
  analyzeVisuals(imageUrls: string[]): Promise<VisualAnalysis>;
  analyzeCaptions(captions: string[]): Promise<CaptionAnalysis>;
  generateAccountReport(data: FullAnalysisData): Promise<AccountReport>;
  generateTrendReport(data: TrendData): Promise<TrendReport>;
}
```

#### [NEW] [gemini.ts](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/lib/ai/gemini.ts)

Gemini API를 사용한 AIProvider 구현체:
```typescript
import { GoogleGenAI } from '@google/genai';

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// 이미지 분석: 게시물 이미지를 Gemini Vision으로 전송
async function analyzeVisuals(imageUrls: string[]): Promise<VisualAnalysis> {
  const imageParts = await Promise.all(
    imageUrls.map(url => urlToBase64Part(url))
  );
  
  const response = await ai.models.generateContent({
    model: 'gemini-2.0-flash',
    contents: [
      { role: 'user', parts: [...imageParts, { text: VISUAL_ANALYSIS_PROMPT }] }
    ]
  });
  
  return parseVisualAnalysis(response);
}
```

---

### 4. 프롬프트 엔지니어링 ⭐

#### [NEW] [prompts.ts](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/lib/ai/prompts.ts)

핵심 프롬프트 모음. 전문 분석가 페르소나를 정의하고, 구조화된 JSON 응답을 유도한다.

---

**🎭 시스템 프롬프트 (분석가 페르소나):**

```
당신은 10년 경력의 인스타그램 마케팅 전략가이자 브랜드 분석 전문가입니다.
대형 에이전시에서 수백 개의 브랜드/인플루언서 계정을 분석한 경험이 있습니다.

분석 원칙:
1. 표면적인 수치가 아닌, 전략적 인사이트를 제공합니다
2. 구체적인 사례와 근거를 들어 분석합니다
3. 실행 가능한 액션 아이템을 제시합니다
4. 업계 트렌드와 비교하여 맥락을 제공합니다
5. 한국어로 자연스럽고 전문적인 톤으로 작성합니다
```

---

**📸 비주얼 분석 프롬프트 (Vision):**

```
다음은 하나의 인스타그램 계정(@{username})의 최근 게시물 이미지들입니다.
전문 비주얼 디렉터의 관점에서 다음 항목을 분석해주세요.

## 분석 항목

### 1. 전체 피드 톤
- 지배적인 색감 팔레트 (웜톤/쿨톤/뉴트럴, 채도 수준)
- 밝기/명암 경향
- 필터 또는 보정 스타일의 일관성

### 2. 비주얼 콘텐츠 유형
- 주요 피사체 (인물/제품/풍경/음식/텍스트 등)
- 인물 등장 빈도 및 촬영 방식 (셀피/전신/그룹)
- 제품 촬영 스타일 (플랫레이/라이프스타일/스튜디오)

### 3. 구도 & 레이아웃
- 주로 사용하는 구도 패턴
- 여백 활용도
- 텍스트 오버레이 사용 여부 및 스타일

### 4. 피드 그리드 전략
- 그리드 패턴이 있는지 (교차 배치, 컬러 블록 등)
- 카루셀 vs 단일 이미지 vs 릴스 비율

### 5. 비주얼 아이덴티티 강도
- 1~10점으로 비주얼 일관성 점수
- 이 계정의 게시물을 로고 없이도 알아볼 수 있는지

다음 JSON 형식으로 응답해주세요:
{
  "feed_tone": { "palette": "", "saturation": "", "brightness": "", "filter_consistency": "" },
  "content_types": { "primary_subjects": [], "person_frequency": "", "product_style": "" },
  "composition": { "dominant_patterns": [], "whitespace": "", "text_overlay": "" },
  "grid_strategy": { "has_pattern": boolean, "pattern_description": "", "content_ratio": {} },
  "visual_identity": { "score": number, "recognizability": "" },
  "summary": ""
}
```

---

**✍️ 캡션/텍스트 분석 프롬프트:**

```
다음은 인스타그램 계정 @{username}의 최근 게시물 캡션들입니다.
전문 카피라이터이자 콘텐츠 전략가의 관점에서 분석해주세요.

---
{captions_with_metadata}
---

## 분석 항목

### 1. 톤 & 매너 분석
- 말투 스타일 (존댓말/반말/혼합, ~했어요/~했다/~했음 체)
- 감성 키워드 (유머러스/진지/감성적/정보적/도발적)
- 이모지 사용 패턴 (빈도, 주로 사용하는 이모지 유형)

### 2. 콘텐츠 카테고리 분류
- 각 카테고리별 비중 (%) 추정
- 교육형/정보형/감성형/소통형/프로모션형 비율
- 주력 콘텐츠 테마 TOP 3

### 3. 캡션 작성 전략
- 평균 캡션 길이 (짧은/중간/긴)
- 첫 줄 훅(Hook) 전략 분석
- CTA(Call to Action) 사용 패턴
- 줄바꿈/단락 나누기 스타일

### 4. 해시태그 전략
- 평균 해시태그 개수
- 해시태그 유형 (브랜드/커뮤니티/검색용/트렌드)
- 캡션 내 배치 위치 (본문 속/마지막/첫 댓글)

### 5. 소통 방식
- 팔로워와의 소통 유도 방식 (질문형/투표/의견 요청)
- 커뮤니티 형성 전략

JSON 형식으로 응답:
{
  "tone_manner": { "speech_style": "", "emotional_keywords": [], "emoji_pattern": "" },
  "content_categories": { "categories": [{ "name": "", "percentage": number }], "top_themes": [] },
  "caption_strategy": { "avg_length": "", "hook_style": "", "cta_pattern": "", "formatting": "" },
  "hashtag_strategy": { "avg_count": number, "types": [], "placement": "" },
  "engagement_style": { "interaction_methods": [], "community_building": "" },
  "summary": ""
}
```

---

**📊 종합 리포트 생성 프롬프트:**

```
당신은 인스타그램 전문 분석가입니다.
아래의 비주얼 분석 결과와 캡션 분석 결과를 종합하여, 
이 계정(@{username})에 대한 전문 분석 리포트를 작성해주세요.

## 프로필 정보
{profile_data}

## 비주얼 분석 결과
{visual_analysis}

## 캡션 분석 결과
{caption_analysis}

## 수치 데이터
- 평균 좋아요: {avg_likes}
- 평균 댓글: {avg_comments}
- 인게이지먼트율: {engagement_rate}%
- 포스팅 빈도: {posting_frequency}

---

다음 항목을 포함한 종합 리포트를 작성해주세요:

### 1. 계정 한줄 요약
이 계정을 한 문장으로 정의

### 2. 콘텐츠 전략 진단
- 콘텐츠 믹스 분석 (주력/보조/실험 콘텐츠)
- 포스팅 루틴 분석
- 콘텐츠 퀄리티 vs 양 밸런스

### 3. 브랜딩 분석
- 비주얼 브랜딩 강도
- 보이스 & 톤 일관성
- 차별화 포인트

### 4. 성장 전략 분석
- 현재 성장 동력 추정
- 팔로워 확보 전략
- 바이럴 요소 분석

### 5. SWOT 분석
- Strengths / Weaknesses / Opportunities / Threats

### 6. 벤치마킹 인사이트
- 이 계정에서 배울 수 있는 점 TOP 3
- 실행 가능한 벤치마킹 전략

### 7. 개선 제안
- 즉시 적용 가능한 개선점 3가지
- 중장기적 전략 방향 제안
```

---

**🔥 트렌드 분석 프롬프트:**

```
당신은 소셜 미디어 트렌드 분석 전문가입니다.
아래는 인스타그램 해시태그 #{hashtag}의 인기 게시물과 최근 게시물 데이터입니다.

## 인기 게시물 (Top Posts)
{top_posts_data}

## 최근 게시물 (Recent Posts)
{recent_posts_data}

---

다음 항목을 분석해주세요:

### 1. 트렌드 현황
- 이 해시태그/키워드의 현재 인기도
- 성장 추세 (상승/정체/하락 판단 근거)

### 2. 콘텐츠 패턴
- 인기 게시물의 공통 특징 (비주얼/캡션/형식)
- 릴스 vs 피드 vs 카루셀 중 어떤 형식이 우세한지
- 가장 인게이지먼트가 높은 콘텐츠 유형

### 3. 크리에이터 유형
- 이 트렌드를 주도하는 계정 유형 (개인/브랜드/인플루언서)
- 팔로워 규모별 분포

### 4. 활용 전략
- 이 트렌드를 활용할 수 있는 콘텐츠 아이디어 5가지
- 최적의 게시 타이밍 및 해시태그 조합
- 주의할 점 (진입 장벽, 리스크 등)

### 5. 연관 트렌드
- 함께 사용되는 해시태그 TOP 10
- 파생 가능한 관련 트렌드
```

---

### 5. Frontend — 대시보드 UI

#### [NEW] [page.tsx](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/app/page.tsx) — 메인 대시보드
- 계정 분석 / 트렌드 분석 / 히스토리 네비게이션
- 최근 분석 결과 프리뷰
- 다크모드 기반 프리미엄 대시보드 디자인

#### [NEW] [page.tsx](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/app/analyze/page.tsx) — 계정 분석 페이지
- 인스타 계정 URL/유저네임 입력 폼
- 분석 진행 상태 표시 (실시간 스텝별 프로그레스)
- 분석 완료 시 리포트 카드 형태로 결과 표시

#### [NEW] [page.tsx](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/app/trends/page.tsx) — 트렌드 분석 페이지
- 해시태그/키워드 입력
- 트렌드 리포트 표시

#### [NEW] [page.tsx](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/app/history/page.tsx) — 히스토리
- Supabase에서 과거 분석 결과 목록 표시
- 분석 결과 상세 보기

---

### 6. API Routes

#### [NEW] `/api/analyze/route.ts`
```
POST /api/analyze
Body: { username: string }
→ Playwright로 프로필 + 게시물 스크래핑
→ Gemini로 비주얼 + 캡션 분석
→ 종합 리포트 생성
→ Supabase에 결과 저장
→ 리포트 JSON 응답
```

#### [NEW] `/api/trends/route.ts`
```
POST /api/trends
Body: { hashtag: string }
→ Playwright로 해시태그 페이지 스크래핑
→ Gemini로 트렌드 분석
→ Supabase에 결과 저장
→ 트렌드 리포트 JSON 응답
```

#### [NEW] `/api/history/route.ts`
```
GET /api/history
→ Supabase에서 분석 히스토리 조회
```

---

### 7. Supabase 스키마

#### [NEW] `analyses` 테이블
| Column | Type | Description |
|--------|------|-------------|
| id | uuid (PK) | |
| type | text | 'account' 또는 'trend' |
| target | text | @username 또는 #hashtag |
| profile_data | jsonb | 스크래핑한 프로필 데이터 |
| visual_analysis | jsonb | 비주얼 분석 결과 |
| caption_analysis | jsonb | 캡션 분석 결과 |
| full_report | jsonb | 종합 리포트 |
| is_deleted | boolean | soft delete |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

### 8. 상태 관리 (Zustand)

#### [NEW] [useAnalysisStore.ts](file:///Users/minsoopark/Downloads/바이브코딩/insta-analyzer/src/store/useAnalysisStore.ts)

```typescript
interface AnalysisStore {
  // 분석 상태
  isAnalyzing: boolean;
  currentStep: AnalysisStep; // 'idle' | 'scraping' | 'analyzing_visuals' | 'analyzing_captions' | 'generating_report'
  progress: number;
  
  // 결과
  currentReport: AccountReport | null;
  currentTrendReport: TrendReport | null;
  
  // 액션
  startAnalysis: (username: string) => Promise<void>;
  startTrendAnalysis: (hashtag: string) => Promise<void>;
}
```

---

## 파일 구조 요약

```
insta-analyzer/
├── .sessions/                         # 🔒 gitignore — 세션 파일
│   └── instagram.json                 # Playwright storageState
├── scripts/
│   └── instagram-login.ts             # 수동 로그인 CLI 스크립트
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                   # 메인 대시보드
│   │   ├── globals.css
│   │   ├── analyze/page.tsx           # 계정 분석
│   │   ├── trends/page.tsx            # 트렌드 분석
│   │   ├── history/page.tsx           # 히스토리
│   │   ├── settings/page.tsx          # 설정 (세션 관리, API 키)
│   │   └── api/
│   │       ├── analyze/route.ts
│   │       ├── trends/route.ts
│   │       ├── history/route.ts
│   │       └── auth/
│   │           ├── session-status/route.ts
│   │           └── instagram-login/route.ts
│   ├── components/
│   │   ├── ui/                        # Shadcn UI
│   │   ├── Sidebar.tsx
│   │   ├── SessionStatus.tsx          # 세션 상태 표시 컴포넌트
│   │   ├── AnalysisForm.tsx
│   │   ├── AnalysisProgress.tsx
│   │   ├── ReportCard.tsx
│   │   └── TrendChart.tsx
│   ├── lib/
│   │   ├── ai/
│   │   │   ├── provider.ts            # 추상 인터페이스
│   │   │   ├── gemini.ts              # Gemini 구현
│   │   │   └── prompts.ts             # 프롬프트 모음
│   │   ├── scraper/
│   │   │   ├── instagram.ts           # Playwright 스크래퍼
│   │   │   ├── session.ts             # 세션 관리 (저장/로드/만료체크)
│   │   │   └── types.ts
│   │   └── supabase/
│   │       └── client.ts
│   ├── store/
│   │   └── useAnalysisStore.ts
│   └── types/
│       └── index.ts
├── .env.local                          # Gemini API 키만 저장 (Instagram 정보 없음)
├── .gitignore                          # .sessions/ 포함
└── package.json
```

---

## Verification Plan

### 자동 검증
1. **Playwright 스크래핑 테스트**: `npm run test:scraper` — 공개 인스타 계정 1개를 대상으로 프로필 + 게시물 스크래핑이 정상 동작하는지 확인
2. **Gemini API 연동 테스트**: `npm run test:ai` — 샘플 이미지/캡션으로 분석 결과가 JSON 형식으로 올바르게 파싱되는지 확인
3. **빌드 검증**: `npm run build` — TypeScript 타입 에러 없이 빌드 성공

### 수동 검증 (유저)
1. **E2E 플로우**: 브라우저에서 `localhost:3000` 접속 → 계정 URL 입력 → 분석 진행 → 리포트 확인
2. **트렌드 분석**: 해시태그 입력 → 트렌드 리포트 확인
3. **UI/UX**: 대시보드 디자인, 반응형 레이아웃, 다크모드 확인
