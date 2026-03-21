# Instagram AI Analyzer — Implementation Plan

개인용 인스타그램 계정/트렌드 분석 도구. Playwright로 인스타 데이터를 수집하고, Gemini API로 전문 분석가 수준의 질적 분석 리포트를 생성한다.

## User Review Required

> [!WARNING]
> **Instagram ToS**: 브라우저 자동화를 통한 스크래핑은 Instagram 이용약관 위반 소지가 있습니다. 개인 사용 목적이며, rate limiting을 적용합니다.

> [!IMPORTANT]
> **Gemini 모델 선택**: `gemini-3.0-flash` 또는 `gemini-3.0-pro` 사용 예정. Provider 패턴으로 다른 모델 교체 가능.

---

## Instagram 로그인 전략 (Session-based)

**원칙**: Instagram username/password를 `.env.local`이나 코드 어디에도 저장하지 않는다.

### 전체 흐름

```
[최초 1회 & 만료 시] 터미널에서 CLI 실행 (`npm run login:instagram`)
        ↓
Playwright 브라우저(headful) 열림 → 직접 로그인 진행
        ↓
스크립트가 피드 로딩을 확인하고 `.sessions/instagram.json` 저장 후 종료
        ↓
[이후 분석] 웹앱에서 AI에게 질문 요청 (예: "요즘 뷰티 트렌드 어때?")
        ↓
[Agentic Flow]
  1. Discovery & Planning (AI + Scraper)
     - Keyword Extraction: 질문 분석 후 검색 키워드 5~8개 도출
     - Candidate Discovery: 키워드 기반 해시태그/키워드 검색을 통해 후보 계정 20~30개 1차 수집 (얕은 스크래핑)
     - Scoring & Filtering: 주제 적합성, 최근 활동(30일 내), 참여도, 지역 관련성 기준으로 후보 계정 평가
     - Balanced Sampling: 브랜드, 대형/중소형 인플루언서, 미디어 등 카테고리를 균형 있게 분배하여 최종 타겟(3~5개) 선정
        ↓
  2. User Confirmation (UI)
     - 선정된 분석 대상 리스트를 UI에 표시
     - 사용자가 타겟 계정을 확인하고, 직접 추가/삭제하며 승인(Confirm)
        ↓
  3. Deep Scraping
     - 사용자가 승인한 타겟 계정들을 Playwright로 순회하며 상세 데이터(이미지, 캡션 등) 심층 수집
        ↓
  4. Synthesis (AI)
     - 수집된 대량 데이터를 바탕으로 종합 트렌드 리포트 생성
        ↓
[세션 만료 감지] 스크래핑 중 로그인 페이지 리다이렉트 감지 → SessionExpiredError 발생
        ↓
프론트엔드 알림: "세션이 만료되었습니다. 터미널에서 'npm run login:instagram'을 실행해주세요."
```

### 1단계: CLI 로그인 스크립트 작성 (`npm run login:instagram`)

서버나 브라우저 UI 없이 오직 로컬 터미널 스크립트를 통해 수동 로그인을 진행합니다.

```typescript
// scripts/instagram-login.ts
import { chromium } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';

const SESSION_DIR = path.resolve(process.cwd(), '.sessions');
const SESSION_PATH = path.join(SESSION_DIR, 'instagram.json');

async function manualLogin() {
  if (!fs.existsSync(SESSION_DIR)) {
    fs.mkdirSync(SESSION_DIR, { recursive: true });
  }

  console.log('🚀 Instagram 수동 로그인을 준비합니다...');
  
  // Headful 모드로 실행하여 유저가 직접 입력할 수 있게 함
  const browser = await chromium.launch({ headless: false }); 
  const context = await browser.newContext();
  const page = await context.newPage();
  
  console.log('🔐 브라우저가 열렸습니다. Instagram에 로그인해주세요.');
  console.log('   (로그인 후 피드 화면이 나타날 때까지 대기합니다...)');

  await page.goto('https://www.instagram.com/accounts/login/');
  
  try {
    // 1. 피드 페이지로 이동할 때까지 대기
    await page.waitForURL('**/instagram.com/', { timeout: 120_000 });
    
    // 2. 홈 화면의 특정 요소를 확인하여 확실하게 로드되었는지 체크
    await page.waitForSelector('svg[aria-label="Home"]', { timeout: 30_000 });
    
    // 3. 세션 저장
    await context.storageState({ path: SESSION_PATH });
    console.log(`✅ 세션이 성공적으로 저장되었습니다: ${SESSION_PATH}`);
  } catch (error) {
    console.error('❌ 로그인 대기 시간 초과 또는 오류 발생:', error);
  } finally {
    await browser.close();
  }
}

manualLogin();
```

### 2단계: 웹앱 세션 사용 및 만료 감지 ([session.ts](file:///Users/minsoopark/Downloads/%EB%B0%94%EC%9D%B4%EB%B8%8C%EC%BD%94%EB%94%A9/insta-analyzer/src/lib/scraper/session.ts))

단순히 파일 존재 여부만 체크하고, 실제 유효성은 페이지 접근 후 리다이렉트 발생 여부로 판별합니다.

```typescript
// src/lib/scraper/session.ts
import { chromium, Browser, BrowserContext } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';

const SESSION_PATH = path.resolve(process.cwd(), '.sessions/instagram.json');

export class SessionExpiredError extends Error {
  constructor(message = '세션이 만료되었거나 존재하지 않습니다. 터미널에서 로컬 로그인을 진행해주세요.') {
    super(message);
    this.name = 'SessionExpiredError';
  }
}

// 스크래핑 시 호출되는 공통 컨텍스트 생성 함수
export async function getAuthenticatedContext(browser: Browser): Promise<BrowserContext> {
  if (!fs.existsSync(SESSION_PATH)) {
    throw new SessionExpiredError();
  }

  // 1. 기존 세션으로 컨텍스트 생성
  const context = await browser.newContext({ storageState: SESSION_PATH });
  const page = await context.newPage();

  // 2. 리다이렉트 감지 설정
  page.on('response', (response) => {
    // 인스타그램은 세션 만료 시 로그인 페이지로 리다이렉트 시킴
    if (response.status() === 302 && response.headers()['location']?.includes('accounts/login')) {
      throw new SessionExpiredError();
    }
  });

  // 3. 실제 페이지 테스트 시 만료 페이지로 갔는지 확인
  await page.goto('https://www.instagram.com/', { waitUntil: 'networkidle' });
  const currentUrl = page.url();
  
  if (currentUrl.includes('accounts/login')) {
    await context.close();
    throw new SessionExpiredError();
  }

  await page.close(); // 테스트용 페이지 닫기
  return context;     // 검증된 컨텍스트 반환
}
```

### 3단계: 만료 감지 및 UI 에러 핸들링

1. API ([/api/analyze/route.ts](file:///Users/minsoopark/Downloads/%EB%B0%94%EC%9D%B4%EB%B8%8C%EC%BD%94%EB%94%A9/insta-analyzer/src/app/api/analyze/route.ts)) 내부에서 [getAuthenticatedContext](file:///Users/minsoopark/Downloads/%EB%B0%94%EC%9D%B4%EB%B8%8C%EC%BD%94%EB%94%A9/insta-analyzer/src/lib/scraper/session.ts#14-44) 호출
2. [SessionExpiredError](file:///Users/minsoopark/Downloads/%EB%B0%94%EC%9D%B4%EB%B8%8C%EC%BD%94%EB%94%A9/insta-analyzer/src/lib/scraper/session.ts#7-13)가 throw되면 `catch` 블록에서 `401 Unauthorized` HTTP 상태 코드로 응답
3. 프론트엔드 (`AnalyzeForm.tsx`)에서 401 에러를 받으면 모달 또는 `toast`로 다음과 같이 알림:
   > 🔴 **Instagram 세션 만료**  
   > 현재 분석을 위한 로그인 세션이 없습니다.  
   > 터미널에서 `npm run login:instagram` 명령어를 실행하여 갱신해주세요.

### 보안 및 [.gitignore](file:///Users/minsoopark/Downloads/%EB%B0%94%EC%9D%B4%EB%B8%8C%EC%BD%94%EB%94%A9/.gitignore) 설정

```gitignore
# /insta-analyzer/.gitignore
.sessions/    # 세션 파일이 절대로 Git 원격 저장소에 올라가지 않도록 방지
.env.local    # Gemini 키 안전 보관
```

---

## 아키텍처 개요 (에이전트 흐름)

```
┌───────────────────────────────────────────────┐
│            Next.js 14 Frontend                │
│  ┌─────────────────┐ ┌────────────────────┐   │
│  │ AI 에이전트 채팅  │ │ 분석 대시보드/결과   │   │
│  │ (ex: "뷰티 트렌드")│ │ (종합 리포트 뷰어)   │   │
│  └───────┬─────────┘ └────────┬───────────┘   │
│          └────────────────────┘               │
│               API Routes                      │
│       ┌─────────┴───────────────┐             │
│       │ /api/agent (Agentic Flow)│             │
│       └────┬─────────┬──────────┘             │
│            │         │                        │
│      [1. Discover & Plan]                     │
│      [2. User Confirm]       [4. Synthesize]  │
│      [3. Deep Scrape]                         │
│            │         │                        │
│   ┌────────┴─────────┴─────┐                  │
│   │     Gemini AI          │                  │
│   │ (Planning, Scoring &   │                  │
│   │  Synthesis)            │                  │
│   └────────┬───────────────┘                  │
│            │                                  │
│      [Search & Deep Scrape]                   │
│            │                                  │
│   ┌────────┴───────────────┐                  │
│   │ Playwright Scraper     │                  │
│   │ (Discovery & Scraping) │                  │
│   └────────────────────────┘                  │
└───────────────────────────────────────────────┘
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
  planSearchTargets(prompt: string): Promise<string[]>; // 프롬프트 분석 후 타겟 선정
  analyzeVisuals(imageUrls: string[]): Promise<VisualAnalysis>;
  analyzeCaptions(captions: string[]): Promise<CaptionAnalysis>;
  generateAccountReport(data: FullAnalysisData): Promise<AccountReport>;
  generateAgenticReport(prompt: string, scrapedData: any[]): Promise<any>; // 멀티 계정 종합 리포트
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
    model: 'gemini-3.0-flash',
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
│   │   └── api/
│   │       ├── analyze/route.ts
│   │       ├── trends/route.ts
│   │       └── history/route.ts
│   ├── components/
│   │   ├── ui/                        # Shadcn UI
│   │   ├── Sidebar.tsx
│   │   ├── SessionAlert.tsx           # 세션 만료 시 표시할 알림 컴포넌트
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
