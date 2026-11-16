# KIRS 투자 데이터 v0.1.0

실제 확인한 한국IR협의회 계열 보고서 6건(티쓰리·JTC·레드캡투어, 3개 기업)의 제한된 사실 추출 파일과 재사용 가능한 파이프라인입니다. 원문 발간 범위는 **2023-11-17~2026-10-28**, 최초 수집은 **2026-11-17 Asia/Seoul**입니다. 과거 발간일을 과거 데이터 이용 가능 시점으로 사용하지 않습니다.

실제 자금 주문, 증권사 로그인, 매수·매도 실행 기능은 없습니다.

## 현재 산출물

| 파일 | 내용/상태 |
|---|---|
| `data/reports.jsonl` | 6개 보고서, 발간일·최초 발견·수집 시각·출처·버전 |
| `data/financials.parquet` | 실적/재무/과거 지표 439행, 공시 대조 미완료 |
| `data/forecasts.parquet` | 작성기관 전망 및 전망 기반 지표 100행 |
| `data/company_snapshots.parquet` | 보고서 기준 주가·시총·주식수·거래량·외국인지분율 29행 |
| `data/business_risks.jsonl` | 근거 페이지를 가진 사업/위험 태그 12개; 사람 검토 정답 아님 |
| `data/research_examples.jsonl` | 근거 기반 QA/추출/확인 불가 예제 30개; 학습 권한·사람 검토 필요 |
| `data/features.parquet` | 기업·관측 시점 기준 후보 특징값 6행; 현재 학습 적격 0행 |
| `data/events.csv` | 실제 KIND 행사 공시 1개, 발행 기업 식별 미확인 |
| `data/investment.sqlite` | 보고서·재무·전망·사업/위험 테이블과 종목/시점 인덱스 |
| `data/samples/` | UTF-8 BOM CSV 열람용 표본. 종목코드는 문자열로 읽기 |
| `raw/document_metadata.jsonl` | 원문 URL, SHA-256, 페이지 수, 수집시각. 원문 PDF 미포함 |
| `manifest.json` | 버전, 기간, 파일별 행 수·체크섬·검증 상태, 미생성 사유 |
| `evaluation/` | 품질 검사, 모델 보류 사유, 한계, 접근·이용조건 조사 |
| `cloud/` | 실제 배포 상태, 스케줄 생성, 영구 체크포인트, 비용·중지 안내 |

`labels.parquet`, 모델 가중치, 영문 보고서, DART 대조 데이터는 생성하지 않았습니다. 각각 `*.NOT_GENERATED.json` 또는 `models/TRAINING_DEFERRED.json`에 사유가 있습니다. 빈 Parquet를 정상 데이터처럼 만들지 않았습니다. `review_queue.jsonl`의 0행은 539개 표 셀의 두 파서 결과가 일치했다는 뜻이며, 데이터의 경제적 정확성·학습 이용권한을 인증하는 뜻은 아닙니다.

## 빠른 실행

Python 3.12 권장. ZIP을 풀어 생긴 `investment_dataset` 디렉터리에서 실행합니다.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
investment verify --root .
investment validate --root .
python -m pip install -r requirements-dev.txt
python -m pytest -q
investment run --root . --state .runtime --mode collect
investment train --root .
investment package --root . --output dist --version v0.1.1
```

수집 실행은 5개 출처 목록의 **메타데이터 발견/가용성 검사**, 기존 파일 검증, 체크포인트 저장을 수행합니다. Telegram 본문은 호출하지 않습니다. 신규 보고서 PDF의 자동 대량 추출과 원문 저장은 이용권한 검토가 끝날 때까지 비활성입니다. 신규 발견 링크는 체크포인트의 `discovered_not_downloaded_rights_review` 상태에 쌓입니다. 실패한 출처 때문에 이전 검증 ZIP의 최신 포인터를 변경하지 않습니다.

PDF 수치 추출기는 `src/investment/extract.py`의 `extract(spec, pdf_bytes, observed)`입니다. `config/pilot_sources.json`은 실제 읽은 문서 명세입니다. 원문을 다시 확보할 권한이 있을 때 URL의 SHA-256을 먼저 확인하고 추출하십시오. 현재 입력 PDF를 ZIP에 재배포하지 않았으므로 **원문 없이 파서 자체를 같은 PDF에 재실행할 수는 없습니다**. 정형 자료 재생성은 `facts_seed.jsonl` 및 `cloud/rebuild_seed.py`로 가능합니다.

## 파일 읽기

```python
import pandas as pd, sqlite3
from pathlib import Path
root = Path('.')
reports = pd.read_json(root/'data/reports.jsonl', lines=True, dtype={'stock_code':'string'})
financials = pd.read_parquet(root/'data/financials.parquet')
forecasts = pd.read_parquet(root/'data/forecasts.parquet')
features = pd.read_parquet(root/'data/features.parquet')
assert all(isinstance(x, str) for x in financials.stock_code)
con = sqlite3.connect(root/'data/investment.sqlite')
q = con.execute("SELECT stock_code, fiscal_year, metric, value, unit FROM forecasts WHERE stock_code=?", ('038390',)).fetchall()
```

CSV에서는 `pd.read_csv(path, dtype={'stock_code':'string'})`를 사용하십시오. Excel 자동 형식 추론은 앞자리 0을 지울 수 있습니다. Parquet가 기준 파일입니다.

## 학습과 백테스트

현재 모델은 학습하지 않았고 성능 숫자도 없습니다. 20거래일 시가→시가 수익률을 후보 목표로 구현했지만, 가격 라이선스·거래소 세션 달력·권리조정 가격·20거래일 관측 완료가 필요합니다. 목표는 특징 파일과 분리합니다. 보고서에 실린 단일 주가를 일별 시세로 간주하지 않습니다.

기본 재개 조건은 유효 표본 500개, 기업 50개, 관측 기간 24개월, 새 표본 100개, 분할 후 각 구간 30개입니다. 이는 운영상 최소 문턱이며 통계적 충분성 보장은 아닙니다. 전처리를 학습 구간에서만 적합하는 Ridge와 평균 예측 기준 모델, 시간순 분할, 정답 기간 겹침 제거, 보고서 계열 단위 격리가 구현되어 있습니다. 수익률 예측 지표만 평가하며 매매 손익을 주장하지 않습니다.

## 독립 클라우드 운영과 $0 조건

전용 유료 클라우드를 만들지 않습니다. 연결된 비공개 GitHub 저장소의 **`kirs_dataset/`** 경로와 **`kirs-data-state`** 체크포인트 브랜치를 사용합니다. 같은 저장소의 기존 STAR 프로젝트와 경로·상태를 분리했습니다. 원래 `investment_dataset/` 경로는 다른 작업이 이미 사용 중이어서 변경하지 않습니다.

표준 Linux GitHub Actions를 매일 09:17·18:17 KST에, 재학습 조건 확인을 월요일 03:17 KST에 예약합니다. 실행 지연/누락 가능성이 있어 SLA는 없습니다. 최신 실제 실행 여부는 `cloud/deployment_status.json` 및 GitHub Actions를 확인하십시오. `cloud/OPERATIONS.md`에 중지·복구·다음 실행 계산 방법이 있습니다.

**사용자가 GitHub 결제수단 미등록 상태를 확인했습니다.** GitHub 공식 문서상 이 상태에서는 무료 할당량 소진 후 실행이 막힙니다. 이것이 $0 조건입니다. 예산 알림만으로 비용이 차단된다고 가정하지 않습니다. 결제수단을 나중에 추가하면 작업을 먼저 중지하고 유료 사용 차단을 재검증해야 합니다. 동일 계정의 다른 워크플로가 무료 한도를 함께 사용합니다.

초기 ZIP과 설명서는 지정한 Google Drive 새 폴더에 보관합니다. 이후 자동 실행의 체크포인트·로그·새 검증 ZIP은 비공개 GitHub 브랜치에 영구 보관됩니다. **Actions→Drive 자동 업로드는 아직 미연결**입니다. ChatGPT 커넥터 인증은 Actions로 자동 이전되지 않습니다. 선택적인 별도 Google OAuth 오프라인 권한을 부여하면 `cloud/drive_sync.py`를 사용합니다.

## 이용 범위

원문 PDF·전체 추출 텍스트·이미지·비밀키를 배포 묶음에 포함하지 않습니다. 공개 열람과 대량 재배포/ML 학습 허용은 다릅니다. 현재 파일은 제한된 사실 추출 검증과 개발 참고용 파일럿이며, 별도 언어모델 학습 입력으로 바로 승인된 데이터가 아닙니다. 자세한 근거는 `evaluation/source_terms.md`, `evaluation/limitations.md`를 읽으십시오.
