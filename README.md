# SKADI · LangGraph Flow Lab

[학습 사이트 열기](https://u-je0n9.github.io/skadi-flow-lab/)

SKADI 설계초안의 LangGraph 흐름을 공부하는 한국어 인터랙티브 사이트입니다.

- 24개 노드와 34개 연결을 원문 흐름과 일치하게 구성
- 노드 hover/클릭으로 실행 주체, 위치, Input/Output, State, LLM·MCP 도구 확인
- 같은 세션의 S1→S5 다섯 질문을 67단계로 재생
- 단계별 JSON 입출력, MCP 호출, 실행 전·후 State와 변경 값 비교
- 되묻기·데이터 부족·저장 실패 등을 포함한 6개 예외 경로
- 9개 MCP 도구와 18개 설계 상태 필드 사전

## 사용 방법

사이트의 **시나리오 실험실 → S1 → 다음 노드(→)** 순서로 시작하세요. 각 질문은 END에서 멈추며 다음 질문이 같은 대화 상태를 이어 씁니다.

`index.html`은 CSS와 JavaScript가 포함된 단일 파일입니다. 내려받아 브라우저에서 직접 열어도 동작합니다. 외부 라이브러리나 설치 과정은 필요 없습니다.

## 데이터의 범위

실제 LangGraph·MCP·LLM·DB 연결은 없습니다. 수치·알람·매뉴얼·보고서 저장 응답은 학습용 고정 Mock입니다. `_turn`은 임시 그래프 상태를 설명하기 위해 추가한 구현 예시이며 원문 설계의 필수 필드는 아닙니다.

## 배포

GitHub Pages에서 `main` 브랜치의 루트(`/`)를 게시합니다. `.nojekyll`로 Jekyll 변환 없이 정적 HTML을 제공합니다.
