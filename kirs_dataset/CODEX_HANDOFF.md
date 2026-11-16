# Codex 후속 개발 인수 문서

1. `README.md` → `manifest.json` → `evaluation/data_quality_report.md` → `evaluation/limitations.md` → `DATA_DICTIONARY.md` → `cloud/deployment_status.json` 순으로 읽습니다.
2. 실제 코드 루트는 ZIP 안의 `investment_dataset/`, GitHub에서는 다른 프로젝트와 충돌하지 않는 `kirs_dataset/`입니다.
3. 어떤 경우에도 주문 기능을 이 데이터 파이프라인에 추가하지 않습니다. 추후 주문 시스템은 별도 권한·검증 범위입니다.

사용자의 최종 운영 선택은 **Windows 노트북**입니다. `windows/README.md`를 추가로 읽으십시오. GitHub 자동 예약/push 트리거는 실제 해제했고 과거 성공 기록은 보존했습니다. Windows 예약 등록은 아직 사용자 기기에서 실행하지 않았습니다. `windows/setup_windows.cmd`, `run_collect.cmd`, `run_train.cmd`, `install_tasks.ps1`, `uninstall_tasks.ps1`가 설치·실행·중지 진입점입니다. 전원을 끄거나 로그아웃한 동안의 실행은 변경된 범위에서 요구하지 않습니다.

## 완료 / 아직 미완료

완료: 공식 출처 실접속·이용조건 조사, 기업 IR 사본 6건에서 표 수치 539개 추출, 두 파서의 셀별 비교, 원문 좌표·표/행/열 추적, 발간일/수집시각 구분, 실제·전망 분리, 0/null 분리, SQLite/Parquet/CSV/JSONL, 특징 후보 6행, 근거 QA/추출/부재 예제 30개, 체크포인트·재시도·요청 제한·중복 실행 방지·검증본 보존, 테스트 및 운영 배포 파일.

미완료: KIRS 직접 서버 복구, 영문/번역본 수집, 신규 PDF 대량처리·학습 이용권한, DART 인증키와 회사 고유번호 매핑/대조, 라이선스가 확인된 시세와 거래소 달력, 사람의 정답 검수, 충분한 미래 관측 표본, 실제 모델 학습, Actions→Drive OAuth 연결. OCR/LLM 추출은 자동 정답으로 승인하지 않으며 현재 OCR 엔진·LLM 서비스 호출도 없습니다. 판독 불확실/미지원 레이아웃은 실패·검토 대상으로 남깁니다.

클라우드의 실제 배포·예약 실행 여부는 최종 생성된 `cloud/deployment_status.json`과 로그 링크가 근거입니다. README의 설계만으로 실행 중이라고 판단하지 마십시오.

## 데이터 결합 규칙

보고서와 수치는 `report_id`, 경제주체는 6자리 문자열 `stock_code`, 복제/번역/수정 계열은 `family_id`로 연결합니다. `fact_id`는 셀 식별자, `content_version`은 PDF SHA-256입니다. `source_id`는 URL의 안정적인 식별자이며 발행기관명과 다릅니다. 신규 문서 URL/해시를 기존 원문에 덮어쓰지 않습니다.

시세 결합은 `stock_code` + `available_at`으로 합니다. 반드시 `available_at <= decision_time`인 자료만 선택합니다. 각 metric·회계기간·연결/별도·통화·단위를 함께 비교하고 그 시점까지 알려진 버전을 선택합니다. 모든 보고서의 마지막 버전을 먼저 택한 뒤 과거 시세에 결합하면 안 됩니다.

```python
import pandas as pd
f = pd.read_parquet('data/features.parquet')
f['available_at'] = pd.to_datetime(f['available_at'], utc=True)
# decisions: stock_code(string), decision_time(UTC)
decisions['decision_time'] = pd.to_datetime(decisions['decision_time'], utc=True)
joined = pd.merge_asof(
    decisions.sort_values('decision_time'),
    f.sort_values('available_at'),
    by='stock_code', left_on='decision_time', right_on='available_at',
    direction='backward', allow_exact_matches=True)
# 이 예는 자료 가용성 결합일 뿐 주문을 실행하지 않는다.
```

개별 fact 질의에서는 `metric`, `fiscal_period`, `statement_scope`, `currency`, `unit`까지 키에 포함합니다. JTC FY2024는 2024-03~2025-02입니다. 다른 회사의 일자 미확인 회계기간은 문자열 연도 라벨과 null 경계를 보존합니다. 연결/별도 unknown을 임의로 CFS로 바꾸지 않습니다. 주당지표는 분할/소각/가중평균주식수 기준이 달라질 수 있어 서로 다른 보고서의 EPS를 단순 교체하지 않습니다.

## 미래 정보 유입 방지

- 기본 가용성은 현재 바이트를 처음 관측한 시각입니다. 과거 발간일만 있는 보고서를 예전 백테스트에 투입하지 않습니다.
- 정확한 공개시각이 있어도 당시 **동일한 버전**이 공개되었다는 검증이 필요합니다. HTTP Last-Modified, 파일명 숫자, 재게시 날짜는 최초 공개시각 증거가 아닙니다.
- 현재 6건 모두 하루에 뒤늦게 수집된 자료입니다. 발간일로 나누어 수년의 훈련 기간인 것처럼 평가하면 안 됩니다.
- 동일 해시는 한 번만 특징에 포함합니다. 확인된 번역/수정 관계는 `lineage.py`에 명시적으로 연결하고 모든 버전을 같은 분할 그룹으로 묶습니다. 자동 유사도만으로 서로 다른 기업을 합치지 않습니다.
- 표본 경계에서 학습·검증 정답의 종료 시각이 다음 구간 시작 이후이면 제거합니다. 변환기·결측 대치·스케일러는 학습 구간에서만 fit합니다.
- 정보 관측 뒤 최소 60초가 지난 첫 실제 거래 가능 시가로 진입하고, 거래소 달력 기준 20세션 뒤 시가를 출구로 삼습니다. 거래정지·상장폐지·출구 누락을 이후 가격으로 채우거나 기간을 임의 연장하지 않습니다.
- 미래 수익률/종가를 `features.parquet`에 넣지 않습니다. 학습 대상 밖 기업, 상장폐지·정지 이력을 별도로 확보해야 선택·생존 편향을 줄일 수 있습니다.

## 자동매매 프로그램에 제공할 인터페이스

읽기 전용 입력: `features.parquet`의 sample_id, stock_code, available_at, signal_id, source_fact_ids, 수치 특징, 사업/위험 태그, training_eligible. 확인된 가용시점 이전에는 소비자가 거절해야 합니다. 초기 모든 training_eligible은 false입니다. 보고서 원문 의견과 회사 가이던스를 합쳐서 생성하지 않습니다.

예측 출력 계약(아직 파일 없음): sample_id, model_version, generated_at, target='return_20_sessions', prediction, data_version, evidence_ids, eligibility_reason. 아직 예측값·거래신호를 생성하지 않습니다. 데이터·모델 상태가 실패/보류이면 downstream은 no-signal을 반환해야 하며 0 수익률로 바꾸면 안 됩니다.

## 재실행 / 확장

- 검증: `investment validate --root .`; 무결성: `investment verify --root .`.
- 정형 파일 재생성: `python cloud/rebuild_seed.py` (원문 재수집 아님).
- 증분 목록 확인: `investment run --root . --state .runtime --mode collect`.
- 모델 조건 확인: `investment train --root .` 또는 GitHub Actions에서 mode=train.
- 보고서 PDF 재추출: `extract.extract(spec, bytes, observed)`; 본문은 일시 메모리 처리. `cloud/ingest_pdf.py`로 후보 디렉터리에 추가하고 검증 후 승격. 원문 해시가 다르면 새 버전·supersedes 관계를 저장.
- OpenDART: 공식 `fnlttSinglAcntAll.json`을 사용. 사업연도/보고서코드/연결별도/계정/누적금액 규칙 일치 여부를 확인한 뒤 반올림 허용오차로 대조. 중간분기의 thstrm_amount와 thstrm_add_amount를 혼동하지 않습니다. DART 수정 공시 또한 관측시점별 버전을 보존해야 합니다.
- 모델 재개 조건: `config.example.yaml:training`; 실제 학습되면 Pipeline과 기준모델, sample ID별 분할 기록이 함께 저장됩니다. joblib은 신뢰하는 본 프로젝트 파일만 로드합니다.
- 예약 변경: KST와 UTC cron을 함께 수정 → `python cloud/generate_workflow.py` → 생성한 YAML을 저장소 루트 `.github/workflows/investment-pipeline.yml`에 반영. 검증기가 두 시간대의 다음 10회 일치를 확인합니다.
- 중지: GitHub Actions → Investment data pipeline → Disable workflow. `PIPELINE_DISABLED=true` 저장소 변수는 새 runner 할당을 차단합니다. 실행 중 작업은 별도로 Cancel run. `kirs-data-state/runtime/state.json`의 disabled=true는 네트워크 호출 전에 중지하지만 runner 초기 비용/한도 소비 자체는 막지 않습니다.

## QA/언어모델 자료

JSONL은 특정 서비스에 종속되지 않습니다. 질문·답변·구조화 출력과 source_id, evidence_page, as_of, 대상기간, split_group을 보존합니다. 생성 방식은 수치/메타데이터 규칙 기반이며 사람 정답 검토를 통과한 gold가 아닙니다. 사업/위험의 보조 설명은 출처 확인을 거친 assistant 요약입니다.

별도 학습 전 이용권한과 사람 검수를 완료하고 family_id 기준으로 분할합니다. `examples.to_chat_examples(..., rights_confirmed=True, human_reviewed=True)`는 messages 형식으로 변환하는 기본 어댑터입니다. 실제 학습 시스템이 metadata를 지원하지 않으면 별도 sidecar로 보존합니다. PDF 내용을 직접 묻는 입력에는 허용된 범위의 검색 근거를 넣어야 하며, URL만으로 모델이 원문을 읽었다고 가정하지 않습니다. 이 코드나 JSONL을 저장한다고 Codex 자체가 학습되는 것은 아닙니다.
