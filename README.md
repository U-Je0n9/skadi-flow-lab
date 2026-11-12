# SKADI · LangGraph Flow Lab v2

[학습 사이트](https://u-je0n9.github.io/skadi-flow-lab/) · [전체 설계서](https://u-je0n9.github.io/skadi-flow-lab/design.md)

요구사항정의서 **1111 탭**, DB 테이블 정의서 **v1.3**, 데모 데이터 **v1.3**을 대조한 설계와 인터랙티브 학습 사이트입니다.

- 부모 그래프와 S1~S5 내부 그래프: 67개 노드의 담당, 실행 위치, Input/Output, State, MCP 호출
- 실제 사용 193개 필드와 연결한 13개 도구 계약
- 같은 세션의 8개 질문, 46단계 Input/Output 및 실행 전·후 State 재생
- 별칭 미확정, 데이터 부족, 보고서 잠금·복원 등 7개 예외와 14개 설계 쟁점
- 요구사항 47개 행의 구현 위치와 남은 범위

## 학습 순서

1. 전체 흐름에서 노드 위에 마우스를 올리거나 클릭해 상세를 고정합니다.
2. S1~S5 탭에서 각 기능의 조건 분기와 내부 노드를 확인합니다.
3. 시나리오의 다음 단계·슬라이더·자동 재생으로 Input/Output과 State 변경을 비교합니다.
4. 도구의 테이블 이름을 누르면 실제 필드 사전과 제공 데모 행으로 이동합니다.
5. 설계서의 미결 사항을 읽고 팀 합의가 필요한 항목을 확인합니다.

## 예시의 범위

Python 참조 서비스가 공개 가능한 Excel 스냅샷을 읽어 계산합니다. 실제 LangGraph 런타임, LLM, MCP 전송 계층, PostgreSQL 연결은 구현하지 않았습니다. LLM 응답 문장은 학습용으로 작성했습니다. 보고서 저장·수정·복원은 별도 메모리에서 실행하며 수정 이력 테이블은 추가 제안입니다.

데모에는 설비 2대, 센서 태그 2개, 해상도별 태그당 시계열 1행이 있습니다. 7일 추세나 연속 정상 복귀를 확인할 수 없는 경우 그대로 표시합니다. 예시 기준 시각은 `2026-11-10T11:05:00+09:00`입니다. 사용자·로그인·대화 테이블의 실제 샘플 값과 원본 Excel은 배포하지 않습니다.

## 수정 및 검증

- `v2/source.json`: DB 정의와 대조한 필드 및 데모 스냅샷
- `v2/design.py`: 그래프·노드·도구 계약·State·설계 쟁점
- `v2/reference_tools.py`: 13개 도구의 실행 가능한 참조 서비스
- `v2/make_traces.py`: 같은 세션의 대화 예시 및 도구 실행 결과
- `v2/write_document.py`: 동일 모델로 설계서 생성
- `v2/index.html`, `v2/style.css`, `v2/app.js`: 사이트 화면과 상호작용
- `v2/verify.py`: 필드, 계산 경계, 데이터 부족, 보고서 변경 계약 검증
- `verify.mjs`: 배포 데이터·State 복원·그래프 참조 정합성 검증

Python 3.10 이상과 Node.js 18 이상을 사용합니다. 추가 패키지는 필요 없습니다.

```sh
python3 build.py
python3 v2/verify.py
node --check dist/app.js
node verify.mjs
python3 -m http.server 4173 --bind 127.0.0.1 --directory dist
```

`http://127.0.0.1:4173`에서 확인합니다. JSON을 읽으므로 HTML 파일을 직접 더블 클릭하는 방식 대신 로컬 서버를 사용합니다. `build.py`는 `dist/`의 정적 배포 파일과 상위 폴더의 새 설계서를 생성합니다. GitHub Pages는 `main`의 루트에 있는 `index.html`, `style.css`, `app.js`, `content.json`, `design.md`를 제공합니다. 재배포 시 `dist/`의 이 다섯 파일을 루트에 복사합니다.

`extract_sources.py`와 `v2/prepare.py`는 로컬 원본 Excel에서 스냅샷을 갱신하는 선택 작업입니다. 저장소의 스냅샷으로 빌드할 때는 필요 없습니다. `src/`의 이전 초안은 이력 참고용이며 v2 빌드에는 사용하지 않습니다.
