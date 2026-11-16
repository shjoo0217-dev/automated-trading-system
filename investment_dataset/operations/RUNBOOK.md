# 운영 절차

대상 저장소: https://github.com/shjoo0217-dev/automated-trading-system (private).
수집 워크플로: .github/workflows/star-pipeline.yml. 현재 사용자 요청으로 disabled_manually(예약 일시중지).
설정된 예약식은 매일 00:17 Asia/Seoul = 15:17 UTC이나 활성 예약이 아니며 다음 실행 시각은 없습니다.
검증 전용 워크플로: .github/workflows/star-validate.yml (수동, 사이트 요청 없음).
대안: pipeline/run_direct.py. 직접 실행 로그와 재개 상태는 operations/direct_runs.json 및 data/checkpoint.json.
초기 코드 push는 10건 표본, schedule/수동 collect는 최대 350건·40페이지·450회 요청입니다.

- 실행환경: GitHub-hosted ubuntu-24.04, Python 3.12, 최대 45분, 한 작업만 동시 실행.
- 스케줄러: GitHub Actions schedule. default branch에 등록. 예약 지연/누락 가능, 실제 Run 생성 확인 필요.
- 영구 보관: private repository star-state 브랜치 + 매 실행의 Release ZIP. 자동 삭제 기간을 설정하지 않음.
- 비밀정보: 자동 단기 GITHUB_TOKEN; 향후 DART_API_KEY는 Actions Secrets. 채팅/소스/결과에 키를 넣지 않음.
- 상태: JSON checkpoint, 재개 대기 URL, 이전 메타데이터 버전, 삭제 관측, 오류 코드. 10건마다 원격 commit.
- 재개: 마지막 완료 batch부터 시작. 마지막 저장 이후 최대 9건 재조회 가능하나 해시로 중복 저장 방지.
- 중복 실행: concurrency group cancel-in-progress=false + state SHA optimistic concurrency.
- 서버 부하: 최소 3초 간격, 연결10/응답40초 timeout, 단일 HTML 16MB 상한, 일시오류 최대3시도, 요청450/바이트100MB cap.
- Retry-After >30초 또는 HTTP-date는 다음 실행으로 이월. robots 차단/약관 지문 변경/허가 누락은 즉시 중단.
- 결과 실패: 실행 로그와 부분 결과 ZIP 저장, 실패 상태 표시. 오류 URL은 다음 전체 scan에서 재시도.
- 전체 상세 재검사 주기는 전송 한도와 대기 큐 길이에 따라 늘어날 수 있음. 신규 첫 페이지는 대기 중에도 우선 확인. 기존 PDF 같은 URL의 내용 변경은 허가 전 확인하지 않음. 현재 일일 수정 확인은 게시물 메타데이터에 한정.

## 명령 (GitHub 권한이 있는 원격 관리 환경에서)

```bash
# 지금 실행 / 상태와 로그 확인
gh workflow run star-pipeline.yml --repo shjoo0217-dev/automated-trading-system -f mode=collect
gh run list --repo shjoo0217-dev/automated-trading-system --workflow star-pipeline.yml
gh run view RUN_ID --repo shjoo0217-dev/automated-trading-system --log
# 예약 일시정지 / 재개
gh workflow disable star-pipeline.yml --repo shjoo0217-dev/automated-trading-system
gh workflow enable star-pipeline.yml --repo shjoo0217-dev/automated-trading-system
# 진행 중 작업만 중단
gh run cancel RUN_ID --repo shjoo0217-dev/automated-trading-system
# 영구 종료: disable 후 진행 중 run cancel. 기존 Release와 state는 보존.
```

완전 삭제는 별도 요청으로 Release/브랜치/저장소를 지워야 하며 자동으로 수행하지 않습니다.
긴급 중단 후 다음 실행은 checkpoint에서 재개합니다. 같은 version은 덮어쓰지 않습니다.
메타데이터 schema 변경은 코드 버전과 함께 관리하고, 과거 Release를 재작성하지 않습니다.

## 비용 근거

현재 자동 수집 예약은 중지되어 반복 예약 비용은 발생하지 않습니다. 검증 전용 수동 실행과 재개한 직접 실행은 별도로 기록합니다. 아래는 재활성화 시의 가정입니다.

현재 확인한 게시판은 316건·32페이지. full scan 예상 1 robots + 1 약관 + 32 목록 + 316 상세 = 350 HTTP 요청. 오래된 HTML에 이미지 데이터가 내장되어 있어 전체 100MB 한도로 나누어 재개할 수 있습니다.
3초 간격만 약 17.5분; 설치·테스트·상태 저장·ZIP 업로드를 합쳐 회당 약 20~25분,
월30회 약 600~750 Linux runner분입니다. 실제 과금은 계정의 플랜·공유 잔여분·분당 단가로 결정됩니다.
월 실행비 추정식: max(0, 사용분 - 계정 잔여 포함분) × 해당 runner 분당 단가.
계정 Billing 플랜과 잔여 포함분은 확인하지 않아 금액을 확정하지 않았습니다. 포함분 내이면 추가 실행비 0일 수 있습니다.
추가 클라우드 유료 계정/GPU/상시 VM은 만들지 않았습니다. PDF·유료 가격 API·모델 학습 비용은 현재 0회 실행 기준 미발생입니다.

버전당 ZIP 실제 크기는 manifest/Release에서 확인합니다. PDF 제외 메타데이터는 작지만 state 브랜치 commit과
매일 ZIP은 지속 증가합니다. Release는 작업 artifact처럼 보존기간이 지나 자동 만료되는 저장소가 아니며,
GitHub 서비스/계정 유지와 공급자 제한에 종속됩니다. 외부 가격 라이선스, 향후 원문 저장/대규모 학습 비용은 별도 산정합니다.
