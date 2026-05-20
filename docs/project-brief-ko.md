# KAPA MCP Agent 프로젝트 정리

## 목표

KAPA HUB PLUS / KAIS 같은 Windows 전용 업무 프로그램을 원격에서 직접
화면공유로 조작하는 대신, Windows 내부에 작은 Agent를 두고 MCP 도구로
명령을 보내 조작/결과회수를 수행한다.

최종 목표는 다음과 같다.

- Tailscale 안에서만 접근 가능한 Windows Agent 실행
- Codex/Claude/MCP 클라이언트에서 고수준 업무 명령 호출
- Windows Agent가 로컬 프로그램을 조작
- 결과는 화면 캡처가 아니라 UI Automation, 클립보드, 엑셀/PDF/CSV 출력
  파일을 우선 사용해서 회수

## 왜 의미가 있는가

TeamViewer, Chrome Remote Desktop, 일반 캡처 도구가 막히는 환경에서는
화면 스트리밍 기반 원격제어가 불안정하다. 특히 영상에서 보이는 것처럼
캡처 프로그램이 블랙 화면을 만들 수 있으면 스크린샷 기반 자동화는
주요 경로가 될 수 없다.

이 프로젝트는 그 문제를 우회해서, 프로그램이 실행되는 Windows 세션
안에서 직접 다음 경로를 시도한다.

- 창/컨트롤 탐색: Windows UI Automation
- 조작: 키보드, 마우스, 핫키, 붙여넣기
- 결과 회수: 클립보드, 내보내기 파일, UIA 텍스트
- 진단: 보조 스크린샷과 black ratio 확인

따라서 실제 자동화 가능 여부는 “화면공유가 되는가”가 아니라 다음으로
판정한다.

- KAPA/KAIS 창을 찾을 수 있는가
- 검색창/버튼/테이블이 UIA로 보이는가
- 입력/검색 실행이 가능한가
- 결과가 클립보드나 엑셀/PDF/CSV로 회수되는가

## 현재 구현 상태

현재 구현은 현장 검증용 POC이다.

- `windows-agent/`: Windows에서 실행되는 HTTP API Agent
- `mcp-server/`: 컨트롤러 장비에서 실행되는 MCP bridge
- `tools/calibrate_agent.py`: 첫 현장 진단 리포트 수집 스크립트
- `docs/`: 설치, Tailscale, 캘리브레이션, EXE 빌드 문서

Windows Agent 주요 API:

- `GET /health`
- `GET /diagnostics`
- `GET /windows`
- `GET /programs/{program}/probe`
- `POST /uia/dump`
- `POST /input/type`
- `POST /input/hotkey`
- `POST /input/click`
- `GET /clipboard`
- `POST /files/recent`
- `POST /files/collect`
- `POST /screen/screenshot`
- `POST /jobs`

MCP 도구도 같은 기능을 감싼다.

## 배포 전략

대상 업무 PC에는 Python이나 개발 도구를 설치하지 않는 방향이 좋다.

권장 흐름:

1. 별도 Windows 샌드박스/VM에서 EXE 빌드
2. `kapa-agent-portable.zip` 생성
3. 업무 PC에는 ZIP만 복사
4. `kapa-agent.exe` 직접 실행 또는 로그인 작업으로 등록
5. Tailscale IP와 Windows 방화벽으로 컨트롤러만 접근 허용

macOS에서 Windows EXE를 안정적으로 크로스 빌드하지 않는다. EXE 빌드는
Windows에서 수행한다.

## 첫 Windows 검증 절차

1. KAPA/KAIS가 설치된 Windows에 Tailscale 연결
2. `kapa-agent.exe --host 127.0.0.1 --port 8765`로 로컬 실행
3. `smoke-test.ps1` 실행
4. `GET /windows`에서 KAPA/KAIS 창이 잡히는지 확인
5. `POST /uia/dump`로 검색창/테이블이 보이는지 확인
6. 검색 결과 테이블에서 `Ctrl+A`, `Ctrl+C` 후 `/clipboard` 확인
7. 엑셀/PDF/CSV 출력 후 `/files/recent`, `/files/collect` 확인
8. 성공한 경로를 `config.local.json` recipe로 옮김

## 성공/실패 판정

성공 가능성이 높음:

- 창이 보이고 키 입력이 가능하다
- 결과 테이블이 UIA로 읽히거나 클립보드 복사가 된다
- 내보내기 파일이 생성된다

부분 성공:

- UIA는 약하지만 핫키/클립보드/파일 출력은 된다
- 이 경우 recipe는 좌표/핫키 중심으로 시작하고 점진적으로 보강한다

소프트웨어만으로 어려움:

- 창 탐색, 입력, 클립보드, 내보내기 파일이 모두 막힌다
- 이 경우 사람 조작은 IP-KVM을 쓰고, Agent는 파일/클립보드 회수 보조로만 쓴다

## 다음 개발 작업

Windows 환경에서 해야 할 작업:

- Mac의 VMware Fusion Windows 11 Arm VM에서 1차 개발/스모크 테스트
- PyInstaller EXE 빌드 확인
- `smoke-test.ps1` 실제 실행
- KAPA/KAIS UIA tree 캡처
- 첫 `search_address` recipe 작성
- 클립보드/파일 출력 결과 포맷 확인

주의: 이 Mac은 Apple Silicon이므로 VMware VM은 Windows 11 Arm 기준으로
사용한다. 대상 업무 PC가 x64 Windows이면 최종 EXE는 x64 Windows에서 다시
빌드한다.

컨트롤러/MCP 쪽 작업:

- MCP 클라이언트 연결 설정 문서화
- recipe 실행 job polling 개선
- artifact 다운로드/요약 도구 보강
- 실패 로그와 재시도 정책 추가
