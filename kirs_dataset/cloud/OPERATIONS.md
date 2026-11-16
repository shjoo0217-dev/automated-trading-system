# 독립 클라우드 운영

**현재 중지 상태입니다.** Windows 노트북 실행으로 범위를 변경하여 `schedule`과 `push` 트리거를 제거했습니다. 수동 실행도 `KIRS_CLOUD_ENABLED=true` 명시 전에는 실행되지 않습니다. 다음 클라우드 예약은 없습니다. 아래는 보존된 구성과 재활성화 시 운영 지침입니다. Windows 실행은 `windows/README.md`를 따릅니다.

## 구성과 권한

- 클라우드 스케줄러: GitHub Actions `schedule` (UTC cron, 설정의 Asia/Seoul과 대응 검사).
- 배치/정제/학습 작업: GitHub 표준 Linux hosted runner, Python 3.12, 작업별 최대 10분. 노트북/브라우저/Codex 종료와 독립.
- 영구 저장소: 비공개 `shjoo0217-dev/automated-trading-system`의 `kirs-data-state` 브랜치 `runtime/`. 체크포인트, HTTP 상태 로그, 실행별 요약, 모델 시도 기록, 불변 버전 ZIP과 최신 검증본 포인터. Git 이력에 이전 버전 보존.
- 최초 납품: Google Drive `투자 프로그램 > 투자 학습 데이터 > KIRS_투자데이터_v0.1.0_20261117`.
- 자동 Drive 백업: 별도의 offline OAuth가 필요한 선택 기능. 현재 미연결이며 GitHub의 영구 저장과 구분한다.
- 비밀 관리: GitHub Actions encrypted Secrets. 기본 실행은 자동 발급되는 최소 수명의 GITHUB_TOKEN(contents:write)만 사용한다. DART_API_KEY, GDRIVE_OAUTH_JSON은 미등록이며 빈 값이면 수집/동기화했다고 기록하지 않는다. 클라우드 프로젝트/카드/GCP 과금계정을 만들지 않았다.

`kirs_dataset/`과 `.github/workflows/investment-pipeline.yml`만 이 작업의 코드다. 같은 저장소의 STAR 프로젝트와 root README·기존 workflow·데이터는 보존한다. 상태 브랜치·concurrency group도 별도다.

## 주기

| 작업 | KST | UTC cron |
|---|---|---|
| 신규 목록/링크 확인 + 기존 데이터 정제 검증 | 매일 09:17, 18:17 | `17 0,9 * * *` |
| 유효한 신규 데이터가 충분할 때 재학습 | 월요일 03:17 | `17 18 * * 0` |

`config.example.yaml`의 KST·UTC 값을 수정한 뒤 `python cloud/generate_workflow.py` 실행. 생성한 파일을 저장소 루트 `.github/workflows/investment-pipeline.yml`로 옮긴다. GitHub 예약은 default branch에 있는 workflow만 작동하며 정확한 분 실행을 보장하지 않는다. 지연·드롭, 무료 할당량 소진, 계정/Actions 정책으로 실행되지 않을 수 있다.

첫 배포는 push 이벤트로 실제 동작을 점검한다. **push/manual 성공은 schedule 성공의 증거가 아니다.** 예약 발화 증거는 run의 event가 `schedule`인 완료 기록으로 별도 기록한다. 검증용 임시 cron을 사용한 경우 최종 배포에는 제거한다. 실제 event·run ID·commit·step 결과·다음 운영 예정 시각은 `deployment_status.json`에 기록한다.

## 중지

1. [워크플로 화면](https://github.com/shjoo0217-dev/automated-trading-system/actions/workflows/investment-pipeline.yml) → 메뉴 → **Disable workflow**. 새 스케줄·수동 실행을 멈춘다.
2. 이미 running/queued인 실행은 **Cancel workflow**. Disable만으로 진행 중 실행을 취소했다고 생각하지 않는다.
3. 대안: 저장소 Settings → Secrets and variables → Actions → Variables에 `PIPELINE_DISABLED=true`. job-level if로 runner 배정을 막는다. 변수 미설정은 enabled다.
4. 지속적인 데이터 접근만 즉시 막고 싶으면 `kirs-data-state/runtime/state.json`에 `disabled: true`. 이 경로는 runner 및 dependency 설치 후 확인하므로 한도 소모를 완전히 막는 스위치는 아니다.
5. 무료 저장소의 기존 자료를 지우지 않는다. 비밀 권한 철회가 필요하면 GitHub Secrets에서 해당 값만 제거하고 Google OAuth 승인을 철회한다.

재개는 권한/결제 조건을 확인한 뒤 Enable workflow와 kill switch 해제. 체크포인트를 읽어 완료 URL/해시는 중복 처리하지 않는다.

## 실패·중복·버전

한 workflow 전체를 concurrency group으로 직렬화하고 cancel-in-progress=false로 실행 중 체크포인트를 보호한다. 동일 머신 Windows/POSIX 비차단 파일 잠금, 동일 run_key 완료 여부, 동일 URL+SHA의 상태를 검사한다. 중간 URL 처리마다 원자적 JSON 저장, 마지막 단계는 always()로 원격 체크포인트를 커밋한다. 원격 저장은 force 없는 push이므로 다른 작성자의 변경을 덮어쓰지 않는다. 단, runner 강제 종료가 always 단계 이전에 발생하면 마지막 원격 체크포인트 이후 일부 작업을 다시 처리한다. 네트워크 읽기는 멱등이고 별도 데이터 버전은 불변 이름이다.

HTTP 요청 간격 최소 10초, robots Crawl-delay가 더 길면 그 값을 사용한다. 401/403·challenge·Telegram·robots 불명확은 우회하지 않는다. 429/5xx는 최대 2회 재시도하고 Retry-After가 실행 예산을 넘으면 다음 실행으로 넘긴다. 최대 30요청/작업·20MB/응답. 일부 출처 실패는 completed_with_source_errors로 기록하며 수집 성공으로 포장하지 않는다.

새 검증 ZIP은 데이터·코드·설명서·배포 상태의 내용 해시가 달라질 때 생성한다. 생성 시각을 포함한 manifest 자체는 변경 감지에서 제외하므로 내용이 같은 정기 점검은 새 ZIP을 만들지 않는다. 스키마/산술/시점 검증 실패는 승격 전에 발생해야 하며 `latest_validated.json`은 그대로 둔다. 최초 파일럿은 passed_with_limitations이며 **공시대조/학습승인까지 끝난 운영 데이터셋을 의미하지 않는다**. 같은 버전 이름을 덮어쓰지 않는다. 체크섬 검증은 ZIP 밖 sha256 및 내부 manifest로 한다.

아카이브 합계 100MB, 전체 상태 110MB를 넘으면 발행을 중단한다. Git 이력의 실제 저장량은 작업 이력 때문에 더 커질 수 있으므로 이 한도는 Git 저장소 전체 하드쿼터가 아니다. 원문 PDF/대용량 학습 모델을 여기에 무제한 보관하지 않는다. 이전 버전 삭제는 자동으로 하지 않는다.

## 최신 상태와 다운로드

GitHub Actions run log·step summary와 `kirs-data-state/runtime/last_run.json`을 확인한다. 실행별 요약은 runtime/history에 남는다. 최신 데이터 파일은 runtime/archive/latest_validated.json의 path, 이전 버전은 runtime/archive/versions/에서 구분한다. 비공개 저장소에 로그인해 ZIP 파일 화면의 Download raw file을 사용한다. 인증 토큰이 붙은 일회성 URL을 문서에 넣지 않는다.

```bash
# 로그인된 gh CLI가 있을 때 (토큰을 명령행에 적지 않음)
gh workflow run investment-pipeline.yml -R shjoo0217-dev/automated-trading-system -f mode=collect
gh run list -R shjoo0217-dev/automated-trading-system --workflow investment-pipeline.yml
gh workflow disable investment-pipeline.yml -R shjoo0217-dev/automated-trading-system
```

## 추가 정보가 있어야 가능한 작업

- 신규 KIRS PDF 대량 수집·변환·보존·ML·재배포에 대한 허용범위 확인 자료. 현재는 metadata-only 자동 운영이다.
- OpenDART 무료 인증키, 회사 8자리 corp_code 매핑 및 공시 시점 버전 관리.
- KRX 또는 별도 가격 제공자의 사용권한·가격 원자료·거래소 달력·기업행동·정지/상폐 포함 범위. KRX 내부 비공개 API를 임의로 만들지 않는다.
- 지속 Drive 업로드를 위한 Google OAuth 클라이언트/오프라인 refresh 승인과 대상 폴더 쓰기 권한. 대화에 비밀을 붙여 넣지 않고 GDRIVE_OAUTH_JSON Secrets에 등록. drive.file 범위이면 앱이 해당 폴더에 접근 가능한지 먼저 검증. OAuth 앱 Testing 모드의 refresh 만료 조건도 확인.
- 위 승인 후 config.storage.automatic_drive_sync=true. `drive_sync.py`는 업로드 후 Drive metadata의 MD5를 대조한다. 이 연결이 없어도 현재 배포는 GitHub 영구 저장소에 계속 기록한다.
