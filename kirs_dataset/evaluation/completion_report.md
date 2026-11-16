# 실제 산출물 및 실행 검증

기준일: 2026-11-17 Asia/Seoul. 최종 사용자 요청에 따라 Windows 노트북을 운영 대상으로 변경하고 독립 클라우드 반복 예약은 해제했다.

## 실제 수집

한국IR협의회 계열 보고서 **6건, 3개 기업**. 기업 IR에 공개된 KIRS 사본이며 KIRS 본사이트에서 직접 받은 자료로 계산하지 않는다.

| 기업 / 종목코드 문자열 | 발간일 | 실제 원문 호스트 |
|---|---|---|
| 티쓰리 / 204610 | 2024-05-22, 2026-08-06 | www.t3.co.kr |
| JTC / 950170 | 2024-12-30 | www.groupjtc.com |
| 레드캡투어 / 038390 | 2023-11-17, 2024-08-29, 2026-10-28 | www.redcap.co.kr |

발간 범위: 2023-11-17~2026-10-28. 실제 원문 최초 관측·수집: 2026-11-17 00:28:51~00:31:47 KST. 과거 발간일을 과거 시점 가용성으로 소급하지 않았다. 별도 KIND 행사 공시 1건은 발행기업 미확인으로 종목 특징에서 제외했다.

## 파일과 품질

- reports 6, financials 439, forecasts 100, company_snapshots 29, business_risks 12, research_examples 30, features 6, events 1.
- Parquet·CSV 표본·UTF-8 JSONL·SQLite, 코드·설정·README/DATA_DICTIONARY/CODEX_HANDOFF를 생성했다. manifest에 파일별 행 수·체크섬·미생성 사유가 있다.
- 재무·전망 539개 셀의 두 PDF 파서 결과 일치. 페이지·표·행·열·좌표 기록, 스키마·산술·시점 검사 통과. null 13개, 원문 0.0 가치배수 6개는 사실 파일에 보존하되 특징에서 제외. 공통 코드 테스트 18개 통과.
- 연결/별도 미확인 500개, DART 대조 0개. 화면 표본 점검은 3페이지이며 전체 사람 검수는 아니다. 판독 불일치 큐 0건은 정확성·학습 이용권한 보증이 아니다.
- KIRS 직접/영문은 접근 실패, Telegram은 확인한 라이선스에 따라 본문·학습에서 제외, KRX 시세는 권한 미확보. 원문 PDF·전체 텍스트·이미지·비밀키는 ZIP에 없다. 상세 근거는 source_terms.md와 limitations.md.

## 학습 결과

**실제 예측 모델 학습 없음. 성능 수치 없음.** 특징 6개 모두 현재 학습 비적격이고 시세·20거래일 정답이 없다. 같은 날 수집한 과거 보고서의 발간연도로 수년의 학습 기간을 만들지 않았다. labels와 모델은 빈 정상 파일 대신 NOT_GENERATED/TRAINING_DEFERRED 사유를 제공했다.

20거래일 시가→시가 수익률, 거래 가능 시점, 시간순 분할·겹치는 정답 제거·번역/수정 계열 격리, 학습 구간 전처리, Ridge와 평균 예측 기준 모델 코드를 구현했다. 기본 재개 조건은 적격 500표본·50기업·24개월·신규100표본·분할당30표본. QA는 규칙으로 근거를 대조했으며 권한·사람 검수 없이 gold로 승인하지 않는다.

## 실행과 중지 증거

- [첫 GitHub 실행 43902830881](https://github.com/shjoo0217-dev/automated-trading-system/actions/runs/43902830881): push, success. 기업 목록 2곳 메타데이터 확인, KIRS 3곳 불가 기록. 데이터 검증 및 영구 체크포인트·버전 ZIP 저장 성공.
- [수정 검증 실행 43904399797](https://github.com/shjoo0217-dev/automated-trading-system/actions/runs/43904399797): push, success. 새 runner에서 체크포인트 재사용·버전 보관 확인. 수집 결과는 completed_with_source_errors로 모든 출처 성공을 뜻하지 않는다.
- 최신 사용자 요청 반영: schedule/push 트리거 제거. 수동 job도 KIRS_CLOUD_ENABLED=true 전에는 비활성. 중지 커밋 47fcea7b786a4acb28a48a34f6ef4aeab8aa6232. 같은 저장소의 STAR 작업은 변경하지 않았다.
- event=schedule 실행은 관측하지 못했고 범위 변경에 따라 검증을 중단했다. **다음 클라우드 예정 실행 없음. 현재 가동 중인 이 작업의 클라우드 배치 없음**(최종 상태 조회 기준).
- Windows 설치/실행/예약 등록·해제 파일을 제공했으나 사용자 기기에 실제 설치·등록하지 않았다. 따라서 Windows의 실제 다음 예정 실행도 없다. 등록 후 기본 주기는 매일09:17·18:17 및 월요일03:17 KST.
- 공통 코드·Windows용 Python 진입점은 Linux에서 검증했다. Windows Task Scheduler 실기기 검증은 남아 있다. cloud/deployment_status.json은 기계 판독용 현재 상태다.

## 다운로드·비용·남은 항목

[지정 Drive 새 폴더](https://drive.google.com/drive/folders/1y0rKp0qxbvf5ADAhmeNY6YmtxPtBWHB9)에 버전 ZIP·외부 SHA-256·manifest·핵심 설명서를 보관한다. latest_validated.json이 최신 납품본을 가리킨다. 이전 실제 클라우드 ZIP은 [kirs-data-state 브랜치](https://github.com/shjoo0217-dev/automated-trading-system/tree/kirs-data-state/runtime/archive)에 보존한다. 해당 계정 로그인 후 내려받을 수 있으며 공유를 공개로 변경하지 않았다.

추가 클라우드 현금 비용 US$0. 사용자 확인상 GitHub 결제수단이 없으며 공식 문서상 무료 할당량 소진 시 실행이 차단된다. 현재 반복 실행은 중지했다. 재활성화 시 표준 runner·10분/작업·30요청·100MB 아카이브 제한을 사용하며 상세 추산은 cloud/COSTS.md에 있다. 예산 알림만으로 비용 상한을 보장하지 않는다.

남은 항목: 사용자 Windows에서 설치·작업 등록, KIRS 대량처리/ML 이용범위 확인, OpenDART 키·기업 고유번호 매핑, 허용된 가격·거래소 달력·정지/상폐 자료, 사람 검수, 충분한 관측 표본. 초기 Drive 납품과 지속 자동 동기화는 다르며 후자는 별도 OAuth가 없어 미연결이다. 중지 방법은 windows/README.md와 cloud/OPERATIONS.md에 있다.
