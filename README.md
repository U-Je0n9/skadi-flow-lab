# SKADI · LangGraph Flow Lab — v2 / v2.1 / v2.2

[v2.2 현재 코드](https://u-je0n9.github.io/skadi-flow-lab/?version=2.2) · [v2 전체 설계](https://u-je0n9.github.io/skadi-flow-lab/?version=2) · [v2.1 1차 범위](https://u-je0n9.github.io/skadi-flow-lab/?version=2.1) · [v2.1 설계서](https://u-je0n9.github.io/skadi-flow-lab/design-v2.1.md)

요구사항정의서 **1111 탭**, DB 테이블 정의서 **v1.3**, 데모 데이터 **v1.3**을 대조한 설계와 인터랙티브 학습 사이트입니다.

- 부모 그래프와 S1~S5 내부 그래프: 67개 노드의 담당, 실행 위치, Input/Output, State, MCP 호출
- 실제 사용 193개 필드와 연결한 13개 도구 계약
- 같은 세션의 8개 질문, 46단계 Input/Output 및 실행 전·후 State 재생
- 별칭 미확정, 데이터 부족, 보고서 잠금·복원 등 7개 예외와 14개 설계 쟁점
- 요구사항 47개 행의 구현 위치와 남은 범위

## v2.2 · 현재 코드

2026-11-16 `final-project`의 `c464216` 기준 구현을 추가했습니다. v2·v2.1의 이전 설계 데이터는 유지합니다.

- `build_graph().get_graph(xray=True)`에서 직접 추출한 전체 StateGraph: 공통 4 + 내부 14개 처리 노드, 실행 경계 2개, 연결 25개
- 부모 그래프와 S1~S5 내부 그래프까지 7개 보기. 실제 등록 이름·조건부 연결·소스 함수 위치, 시나리오의 연속 실행 경로만 강조
- 추출 원본 JSON·Mermaid 다운로드, LangGraph의 Mermaid 원본을 렌더링한 SVG 그림
- **S1~S5는 조건·도구 상세가 기본**: 실제 등록 노드를 테두리로 묶고 내부 if 34개, MCP 호출 이름, YES/NO, return/생략 경로를 표시
- 기존 66단계를 재실행해 실제 조건 판단 150건을 기록. 선택한 시나리오의 내부 경로·호출·생략 표시와 도구별 실제 기록 입출력 제공
- 처리 노드 18개(함수 17개, `s2_read` 재사용)와 MCP 도구 11개의 실제 인자·동작·입출력
- 같은 세션의 질문 10개·실행 단계 66개: 매 단계 전체 Input State, Output patch, 실행 전후 State, 도구 호출, 최종 SSE 이벤트
- 보고서 완료 확인·범위 밖 질문과 현재 미수정 문제 표시
- 파일 기반 BM25 RAG, SQLite와 PostgreSQL의 역할, 기존 설계와 구현의 차이

실제 그래프·업무 도구·BM25 코드를 실행해 기록했습니다. **모델 응답·HTTP·DB·시계는 합성 학습 데이터로 대체**했으며 실제 API/DB 통합 테스트나 LLM 품질 검증 결과가 아닙니다. 문서 예시는 새로 작성했고 원본 RAG, 실제 대화, 비밀값은 포함하지 않습니다. 공개 사이트에서 서비스 API를 호출하지 않습니다.

`v22/export_graph.py`는 모델/DB 호출 없이 컴파일된 그래프를 추출하고 `v22/stategraph.json`에 등록 이름·연결·함수 위치·Mermaid를 저장합니다. `v22/runtime.json`은 실행 기록, `v22/build.py`는 화면 데이터와 Markdown 생성, `v22/ui.js`·`v22/style.css`는 추가 UI입니다. 현재 코드로 기록을 다시 만들려면 인접 폴더의 `final-project/ai/.venv`와 해당 제품 코드가 필요합니다. 공개 저장소의 고정 기록으로 사이트만 빌드할 때는 필요 없습니다.

```sh
# 선택: 제품 코드가 로컬에 있을 때 구조와 실행 기록 갱신
../final-project/ai/.venv/bin/python v22/export_graph.py
python3 v22/control_flow.py
../final-project/ai/.venv/bin/python v22/capture.py
# 정적 사이트 재생성·검증
python3 build.py
python3 v22/verify.py
python3 v22/verify_control.py
```

`v22/control_flow.py`는 제품 파일을 수정하지 않고 Python AST에서 조건·도구 호출·return 경로를 추출합니다. `capture.py`의 메모리 계측은 if의 실제 결과만 기록하며, 기존 66개 노드의 입출력·도구 호출·State patch가 변하지 않았음을 대조했습니다. 상세 도형은 **등록 노드 내부 처리 단계**이며 StateGraph 노드가 추가된 것은 아닙니다. 일반 대입·포맷팅·반복문은 코드 블록으로 묶습니다.

`v22/control-layout.json`은 저장된 다이어그램 배치입니다. 코드 구조가 바뀌면 `dagre-d3-es@7.0.14`를 별도 개발 환경에 설치한 뒤 다음 명령으로 갱신합니다. 공개 페이지에는 해당 라이브러리나 Node.js가 필요 없습니다.

```sh
node v22/layout-control.mjs /path/to/node_modules/dagre-d3-es
python3 build.py
python3 v22/verify_control.py
```

현재 SKADI는 명시적 조건 라우팅과 순차 서브그래프 구조입니다. ReAct / ToolNode 루프나 `interrupt` 승인 노드는 구현되어 있지 않습니다. MCP는 노드 안에서 호출하며, S5 완료 확인 실패 시에도 뒤의 두 노드를 빈 patch로 통과합니다. 실제 코드에 없는 노드나 루프를 사이트에 추가하지 않습니다.

`stategraph-expanded.svg`는 추출된 Mermaid의 렌더링 결과입니다. 그래프 변경 시 사이트 빌드 후 Mermaid CLI로 SVG를 다시 생성하고 빌드합니다.

```sh
# @mermaid-js/mermaid-cli가 설치된 환경에서 (로컬 Chrome 사용 가능)
mmdc -i dist/stategraph-expanded.mmd -o v22/stategraph-expanded.svg
python3 build.py
```

## 버전 선택

상단 버튼으로 v2 전체 설계(13도구·8턴·46단계), v2.1(10도구·6턴·38단계), v2.2 현재 구현(11도구·10턴·66단계)을 전환합니다. 기본은 v2.2입니다. 그래프·도구·예외·State·다운로드 문서가 함께 바뀝니다. `?version=2`, `?version=2.1`, `?version=2.2`로 직접 연결할 수 있습니다.

v2.1은 새로 지정한 **Downloads판 1111 탭의 K열**을 기준으로 합니다. 전체52행 중 1차24행을 적용하고, 2차18행·3차9행·후순위1행은 제외합니다. 1차 행에 남은 빨간 H11/H12 세부문구는 기존 지시에 따라 2차로 분리합니다. 새 파일의 해시·스프린트·세부문구는 `v21/scope.json`에 기록했습니다. S3 예시를 현재12h 상태/구간 조회로 바꾸고 정상 복귀 도구를 제외했습니다. 기본 진단·근거·조치에 필요한 최소 청크 검색은 유지하며, 대규모 색인/정답 데모/S6 평가는 후속 범위입니다. v2는 기존47행 파일 기준의 전체 설계로 보존합니다.

## 학습 순서

1. 전체 흐름에서 노드 위에 마우스를 올리거나 클릭해 상세를 고정합니다.
2. S1~S5 탭에서 각 기능의 조건 분기와 내부 노드를 확인합니다.
3. 시나리오를 선택하면 위 그래프의 해당 노드를 자동 표시합니다. 다음 단계·슬라이더·자동 재생도 연동되며 그래프 위 화살표로 단계를 이동할 수 있습니다. 자동 이동 체크를 끄면 선택한 그래프를 유지합니다.
4. 도구의 테이블 이름을 누르면 실제 필드 사전과 제공 데모 행으로 이동합니다.
5. 설계서의 미결 사항을 읽고 팀 합의가 필요한 항목을 확인합니다.

## v2·v2.1 예시의 범위

Python 참조 서비스가 공개 가능한 Excel 스냅샷을 읽어 계산합니다. 실제 LangGraph 런타임, LLM, MCP 전송 계층, PostgreSQL 연결은 구현하지 않았습니다. LLM 응답 문장은 학습용으로 작성했습니다. 보고서 저장은 메모리에서 실행합니다. 수정·복원 및 추가 이력 테이블은 v2에만 포함하며 v2.1은 현재 초안만 생성합니다.

데모에는 설비 2대, 센서 태그 2개, 해상도별 태그당 시계열 1행이 있습니다. 7일 추세나 연속 정상 복귀를 확인할 수 없는 경우 그대로 표시합니다. 예시 기준 시각은 `2026-11-10T11:05:00+09:00`입니다. 사용자·로그인·대화 테이블의 실제 샘플 값과 원본 Excel은 배포하지 않습니다.

## 수정 및 검증

- `v2/source.json`: DB 정의와 대조한 필드 및 데모 스냅샷
- `v2/design.py`: 그래프·노드·도구 계약·State·설계 쟁점
- `v2/reference_tools.py`: 13개 도구의 실행 가능한 참조 서비스
- `v2/make_traces.py`: 같은 세션의 대화 예시 및 도구 실행 결과
- `v2/write_document.py`: 동일 모델로 설계서 생성
- `v2/index.html`, `v2/style.css`, `v2/app.js`: 사이트 화면과 상호작용
- `v21/build.py`, `v21/services.py`: 1차 범위 모델·문서와 제한된 참조 서비스
- `v21/extract_scope.py`, `v21/scope.json`: Downloads판 스프린트·빨간 세부문구 추출과 원본 해시 기록
- `v21/make_traces.py`: 1차 범위의 6개 질문·38단계 재실행
- `v21/verify.py`: 범위·그래프·보고서 저장·State 연속성 검증
- `v2/verify.py`: 필드, 계산 경계, 데이터 부족, 보고서 변경 계약 검증
- `verify.mjs`: 배포 데이터·State 복원·그래프 참조 정합성 검증

Python 3.10 이상과 Node.js 18 이상을 사용합니다. 추가 패키지는 필요 없습니다.

```sh
python3 build.py
python3 v2/verify.py
python3 v21/verify.py
node --check dist/app.js
node verify.mjs
python3 v22/verify.py
python3 -m http.server 4173 --bind 127.0.0.1 --directory dist
```

`http://127.0.0.1:4173`에서 확인합니다. JSON을 읽으므로 HTML 파일을 직접 더블 클릭하는 방식 대신 로컬 서버를 사용합니다. `build.py`는 `dist/`의 정적 배포 파일과 상위 폴더의 새 설계서를 생성합니다. GitHub Pages는 `main`의 루트에 있는 `index.html`, `style.css`, `app.js`, `content.json`, `content-v2.1.json`, `content-v2.2.json`, `v22-ui.js`, `design.md`, `design-v2.1.md`, `design-v2.2.md`를 제공합니다. 그래프 증빙인 `stategraph-v2.2.json`, `stategraph-*.mmd`, `stategraph-expanded.svg`, `control-ui.js`, `control-flow-v2.2.json`도 배포합니다. 재배포 시 `dist/`의 파일을 루트에 복사합니다.

`extract_sources.py`와 `v2/prepare.py`는 로컬 원본 Excel에서 스냅샷을 갱신하는 선택 작업입니다. 저장소의 스냅샷으로 빌드할 때는 필요 없습니다. 로컬 `src/`의 이전 초안은 이력 참고용이며 현재 빌드에는 사용하지 않습니다.
