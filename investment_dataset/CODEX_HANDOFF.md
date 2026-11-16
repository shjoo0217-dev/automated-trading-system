# Codex 인수인계

이 패키지는 자동매매 개발에 참고할 실제 게시물 메타데이터·품질 감사·파이프라인 코드입니다.
Codex에 파일을 제공하는 것은 별도 예측모델을 훈련하는 것과 다릅니다. 현재 모델 학습은 하지 않았습니다.

## 파일과 연결키

| 파일 | 용도 |
|---|---|
| README.md | 범위·제약·읽기·실행 안내 |
| data_dictionary.csv / schema.json | 열 사전 / 레코드 계약 및 Parquet 타입 |
| manifest.json | 생성·기준 시각, 권리, 버전, 행 수, SHA-256 |
| data/reports.csv | 공개 게시물 메타데이터. ticker는 문자열, 없는 코드는 null |
| data/financials.parquet | 실적·전망 사실용 타입 지정 빈 테이블. 학습 허가 후 검수한 사실 추가 |
| data/valuations.parquet | 예스티 목표주가 충돌의 2개 실제 감사 관측, 학습 제외 |
| data/events.jsonl | 사건·성장 근거·리스크용 빈 파일. 정성 내용 이용허가 미확보 |
| data/report_versions.jsonl | 변경 전 게시글 메타데이터 버전. 수정 원문 PDF는 별도 해시로 관리 필요 |
| data/tombstones.jsonl | 전체 목록에서 사라진 게시물. 기록을 지우지 않음 |
| data/training_samples.jsonl | 일반 모델용 JSONL. 1개 격리 감사 레코드, labels null |
| data/splits.json | 현재 미생성 사유. 학습시 시간 분할과 제외 사유 |
| quality/ | 현재 오류, 이용 조건, 원문 품질 감사 |
| models/ | 실제 학습시만 모델 버전 생성; 현재 바이너리 없음 |
| evaluation/ | 실제 학습 미실행 사유 및 평가 정의 |
| operations/ | 수집 실행 로그·테스트·배포 상태·운영 지침 |
| pipeline/ | 수집·추출 후보·PIT 결합·학습·실행환경·클라우드 설정 |

`report_id`는 게시물 ID로 고정합니다. `file_sha256`은 PDF 바이트 버전입니다. 같은 파일의 중복 게시나
동일 문서 수정본은 문서/해시 연결 그룹을 구성하고 분할을 넘으면 제외합니다. CSV attachment_urls는 JSON 문자열입니다.
종목은 `ticker`로 조인하고, `security_id`와 valid_from/valid_to/known_at을 갖춘 이력 마스터로 코드 재사용,
종목명 변경, 시장 이동, 상장폐지를 관리해야 합니다. 현재 예스티 코드는 원문 주장만 확인했습니다.

```python
import pandas as pd, json
r = pd.read_csv('investment_dataset/data/reports.csv', dtype={'ticker':'string'})
v = pd.read_parquet('investment_dataset/data/valuations.parquet')
audit = v.merge(r[['report_id','post_url']], on='report_id', validate='many_to_one')
# 가격 마스터가 확보된 뒤 ticker + 시점 구간으로 조인. 회사명으로 fuzzy join하지 말 것.
```

## 실제 자료 / 예시

실제 자료는 reports와 최소 예스티 감사 관측입니다. financials/events/security_history는 현재 빈 데이터 또는 스키마뿐입니다.
테스트의 합성 데이터는 pipeline/tests 안에만 있습니다. 누락값은 0으로 채우지 않습니다.
report 상승여력은 features 후보이며 observed future excess return은 labels입니다. 서로 대체하지 않습니다.

## 시간과 유출 방지

- 발간일, 게시일, 최초 수집, 수정 발견, 버전 최초 확인, 실제 가용시점을 별도로 기록합니다.
- 과거 파일 버전 공개 증거가 없으므로 현재 PDF를 발간일/게시일에 사용할 수 있다고 가정하지 않습니다.
- 현재 정책은 버전 최초 관측의 KST 날짜 다음 **검증된 거래 세션**부터 사용입니다. 평일을 거래일로 가정하지 않습니다.
- 거래일/시각이 미확정이면 available_at=null이고 학습에서 제외합니다. 더 이른 증거가 확보되면 증거와 규칙 버전을 함께 추가해야 합니다.
- 공시 정정·연결정보·컨센서스는 known_at <= available_at을 적용합니다. 최신 수정치를 과거 입력에 소급하지 않습니다.
- 메타데이터 확인일과 PDF 내용 재확인일은 다릅니다. 현재 PDF 재수집은 이용허가로 차단되어 과거 감사값의 최신성을 보장하지 않습니다.
- 같은 문서/파일의 연결 그룹 분할 누출, 라벨 기간이 다음 분할에 걸치는 표본을 제거합니다.
- 상장폐지/거래정지/삭제 게시물을 명부에서 제외하지 말고 제외 사유와 누락률을 집계합니다.

## 새 데이터와 모델

1. 학회의 동의가 필요한 범위(원문 저장·가공·학습·재배포)를 구분해 증거를 확보하고 source_policy.json의 해당 권한에 증거 식별자와 유효기간을 기록합니다.
2. 허가된 PDF를 원격 작업에서 내려받고 SHA-256으로 새 버전을 만듭니다. 현재 자동 일일 작업은 메타데이터만 실행합니다.
3. `python -m star_pipeline extract --pdf PATH --report-json REPORT.json`으로 허가된 파일의 후보를 만듭니다. OCR은 이미지 문서에만 --ocr로 사용합니다. Dockerfile은 kor+eng OCR 의존성을 제공합니다.
4. financial_candidates는 표 행·연도·단위를 엄격히 추출하는 후보 파서입니다. 셀 병합, 통화/연결 불명, 과거치·예측치·컨센서스 모호함을 사람이 검수해야 합니다. 검수하지 않은 후보는 needs_review입니다.
5. 사업부·산업 지표, 가치평가 방법/비교기업/배수/기준연도, 사건 발생/예상일은 스키마에 따라 근거 페이지와 함께 주석 처리합니다. 범용 정성 자동 추출기는 아직 구현하지 않았습니다.
6. 허가된 가격 공급자의 가격/거래량/거래달력/주식수 이벤트/지수와 OpenDART를 연결합니다. market.py는 인터페이스와 시간 필터·20일 라벨 함수, dart.py는 제한된 공시 목록 어댑터입니다. 유료 가격 API 실제 연동은 미완료입니다.
7. 모든 특징값에 value/known_at/evidence_ids를 지정합니다. 계산 특징은 원본 사실의 evidence_ids와 formula를 별도 사실 행에 기록합니다. 현재 특징 생성 전반은 수동 승인 필요입니다.
8. 원문 이용허가·schema/quality 검사·실제 라벨을 모두 통과한 표본만 quality_status=passed, training_eligible=true로 전환합니다. 그냥 플래그만 바꾸지 마세요.
9. training_config.json의 시점 경계를 사전에 지정합니다. 검수한 데이터 ZIP을 private Release에 올린 후 workflow_dispatch에서 mode=train, dataset_tag=<검수된 Release tag>로 원격 실행합니다. 데이터/모델 파일의 manifest 해시를 확인해 복원하고, 아카이브의 실행 코드는 실행하지 않습니다. 시간순 train/validation/test, 훈련 구간 전처리, validation alpha 선택, test 최종 평가가 구현되어 있습니다.
10. 모델은 데이터+설정 해시 디렉터리에 별도 저장됩니다. 자동 승격·실계좌 주문은 구현하지 않았습니다. 이전 모델과 동일 비용 조건으로 비교한 뒤 승인된 모델만 실행 계층에 연결하세요.

JSONL은 특정 LLM 파인튜닝 메시지 형식이 아닙니다. 본 데이터로 특정 LLM을 파인튜닝하는 변환기는 요구될 때 별도 작성하며 현재 포함하지 않습니다.

## 자동매매 연결 지점

HistoricalProvider는 과거 시점 데이터, LiveExecution은 미래 호가·주문 인터페이스입니다. 브로커 키·주문량·계좌·주문 동작이 없습니다.
후속 개발에는 시점별 투자 가능 universe, 포트폴리오 중복보유·거래비용·회전율·거래정지·상폐 정산,
페이퍼 트레이딩, 주문 중복 방지, 일일 손실 한도와 실행 중단 제어가 필요합니다.

## 직접 실행 대안 및 현재 예약 상태

GitHub 자동 수집 실패 알림에 대한 사용자 요청을 반영해 STAR 수집 예약을 일시중지했습니다. 사이트 수집은 현재 Codex 관리형 실행환경의 직접 프로세스로 수행합니다. 이 대안의 실행 ID·로그는 operations/direct_runs.json과 direct_execution.log에 있습니다. GitHub는 코드/데이터 검증과 Release/체크포인트 보관에 계속 사용합니다.

ZIP을 해제한 상위 폴더에서 macOS/Linux는 `bash investment_dataset/pipeline/run_direct.sh`, Windows는 `powershell -File investment_dataset/pipeline/run_direct.ps1`로 재개할 수 있습니다. Python 3.12와 인터넷 연결이 필요합니다. 사용자 노트북의 예약 작업을 실제 설치하지는 않았습니다. 노트북·브라우저 종료 후 독립 지속 운영은 더 이상 이번 완료 조건이 아닙니다. 다음 예약 실행은 없습니다.

## 클라우드 운영과 남은 일

배포와 실제 실행 증거는 operations/deployment_status.json, 원격 로그는 GitHub Actions, 영구 결과는 Releases입니다.
GitHub Actions runner는 작업 완료 후 정리되지만 현재 STAR 자동 수집은 비활성입니다. 직접 실행 프로세스는 현재 실행환경이 유지되어야 합니다. 완료된 결과의 GitHub/Drive 영구 보관은 프로세스 종료와 별개입니다.
단, GitHub 예약은 정확한 시각 SLA가 없으며 서비스 장애·계정/결제/Actions 비활성화·사용량 제한에 영향을 받습니다.
Actions artifact의 만료 저장을 영구 저장이라고 간주하지 않습니다. 여기서는 삭제 전까지 유지되는 private Release assets와 state branch를 사용합니다.
현재 Google Drive에는 이 대화의 검증된 스냅샷을 저장합니다. 매일 Drive로 자동 미러링하는 인증은 연결하지 않았습니다.

제한: 원문 이용허가 없음, 대부분 종목코드 미확인, PDF 원문 버전의 과거 공개 증거 없음, 가격/달력/공시 실제 결합 없음,
정성 자동 추출 없음, 대규모 추출 정확도 검증 없음, 모델·성과·실전 백테스트 없음. 남은 일을 완료로 해석하지 마세요.

최종 직접 실행 ZIP의 영구 위치는 Google Drive이며 GitHub Release 버전 기록에서 해당 링크를 안내합니다. 현재 관리 환경의 GitHub 파일 업로드 호스트 인증 제한(HTTP 401)으로 최종 ZIP을 Release 자산으로 올리지는 못했습니다. 소스·정제 데이터·체크포인트는 비공개 GitHub 저장소에 보관됩니다. 초기 Actions의 성공한 표본 Release 자산과 최종 직접 실행 ZIP을 혼동하지 마세요.
