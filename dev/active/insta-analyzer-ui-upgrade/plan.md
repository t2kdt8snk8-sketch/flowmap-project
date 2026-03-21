# Insta-Analyzer UI/UX Upgrade Plan

## 1. 목표 (Objective)
- 인스타애널라이저의 UI를 "전문적(Professional)"이고 "분석적인(Analytical)" 느낌을 주도록 전체적으로 개편합니다.
- 과도하게 둥근(Rounded) 디자인 요소들을 제거하고, 직선적이고 깔끔한 대시보드(Dashboard) 스타일로 변경합니다.
- 시장 트렌드 탭 내의 심층 분석(Deep Dive) 테이블에 존재하는 노란색 UI(메인 팔레트 태그)의 레이아웃 잘림 현상을 수정합니다.
- 메인 탭(계정 정밀 분석 / 시장 트렌드 리서치)의 디자인을 보다 직관적이고 세련되게 개선합니다.

## 2. 세부 개선 사항 (Detailed Improvements)
### A. 전체적인 UI 곡률 완화 (Reducing Border Radius)
- `rounded-[2rem]`, `rounded-[3rem]`, `rounded-full` 등 과도한 곡률을 `rounded-md`, `rounded-lg` 수준으로 변경하여 시각적 안정감을 줍니다.
- 카드(Card) 및 컨테이너의 모서리를 직관적이고 단단한 느낌으로 교체하여 신뢰감을 줍니다.

### B. 시장 트렌드 "심층 매트릭스" 탭 노란색 UI 잘림 수정
- **대상:** `AgentReportCard.tsx`의 `DeepDivePane` 내 `메인 팔레트` 열
- **문제 원인:** 긴 텍스트 혹은 Flex/Block 처리 부재로 인해 태그가 테이블 셀을 벗어나거나 부자연스럽게 잘림. (예: `bg-amber-50 text-amber-700`)
- **해결 방안:** 텍스트가 자연스럽게 줄바꿈되도록 래핑을 적용하거나, 테이블 레이아웃 폭을 확보하여 텍스트가 잘리는 현상을 해결합니다.

### C. 메인 탭 네비게이션 개선
- **대상:** `page.tsx` 내부 `<TabsList>`, `<TabsTrigger>` 요소
- **문제 원인:** 과도하게 두꺼운 알약(Pill) 형태의 디자인이 대시보드 성격과 맞지 않음
- **해결 방안:** 백그라운드 컬러 변경 대신, 하단 보더(Bottom Border) 하이라이팅을 사용하거나 각진(Sleek) 버튼 형태로 변경하여, 전문적이고 깔끔한 SaaS 대시보드 탭으로 변환합니다.

## 3. 구현 단계 (Implementation Phases)
- **Phase 1:** 전체 페이지 및 컴포넌트의 둥근 모서리(Border Radius) 일괄 축소 (전문적인 느낌 부여)
- **Phase 2:** 메인 페이지(`page.tsx`) 탭 디자인 및 `AnalysisForm.tsx`의 과도한 둥근 검색창 디자인 개편
- **Phase 3:** `AgentReportCard.tsx` 내부 서브 탭, 카드 UI의 곡률 수정 및 "메인 팔레트(노란색 UI)" 잘림 버그 픽스
- **Phase 4:** 최종 레이아웃 테스트 및 반응형(Mobile) 점검
