# STAR 투자 리서치 데이터셋 v0.1.0

현재 제공 범위는 실제 공개 게시물 메타데이터와 예스티 1건의 최소 사실 품질 감사입니다.
보고서 원문, 전문, 저자 개인정보는 포함하지 않습니다. 학습용으로 승인된 표본과 모델은 없습니다.

| 단계 | 현재 상태 |
|---|---|
| 수집 | 게시글 메타데이터 316건 수집 완료. GitHub 체크포인트 160건 + 직접 재개 156건, 재개 실패 0건 |
| 정제 | 게시물 ID·제목·발간/게시일·URL·버전 정규화 완료. PDF 전체 정제는 보류 |
| 품질 검증 | 예스티 목표주가 충돌과 날짜 차이 확인. financials/events는 허가 미확보로 비어 있음 |
| 실행환경 | GitHub 원격 실행 확인 후 사용자 요청으로 수집 예약 중지. 현재 직접 실행으로 수집 완료 |
| 모델 학습 | 미실행. 이용허가·가격 라벨·표본·시간 분할 설정 없음 |

`data/reports.csv`의 메타데이터 행 수와 수집한 PDF 수는 서로 다릅니다.
`data/valuations.parquet` 2행은 예스티의 충돌 검증 기록이며 학습 가능 수치가 아닙니다.
`data/training_samples.jsonl`의 1행은 실제 자료를 연결한 격리 레코드이고, 정답은 null입니다.
`pipeline/tests/`의 숫자만 합성 테스트 데이터이며 실제 데이터 파일에는 섞지 않습니다.

보고서 2026-08-14 발간, 홈페이지 2026-09-09 게시. 2026-11-17 KST 현재 확인한 PDF의
과거 버전 증거는 없습니다. 따라서 발간일이나 게시일로 입력 가용시점을 소급하지 않습니다.
거래일 달력이 없으므로 `available_at=null`을 유지하고 최초 관측 이후로 하한만 저장합니다.

이용 제한: 예스티 28쪽의 학회 동의 없는 변형·복제·배포·전송 금지 조항을 적용합니다.
robots의 Allow는 저작권 이용허가가 아닙니다. 허가 전 PDF 확장 수집·전문 저장·학습은 비활성입니다.

## 읽기

```python
import pandas as pd
import json
reports = pd.read_csv('investment_dataset/data/reports.csv', dtype={'ticker':'string'})
valuations = pd.read_parquet('investment_dataset/data/valuations.parquet')
samples = [json.loads(x) for x in open('investment_dataset/data/training_samples.jsonl')]
```

원천 관측 ID는 `report_id`, 파일 버전은 `file_sha256`, 종목 연결키는 6자리 문자열 `ticker`입니다.
게시물 제목의 기업명은 검색 표시용이며 종목 마스터와 연결하는 키로 사용하지 않습니다.
CSV의 빈칸은 null, 숫자 0은 실제 영입니다. Parquet/JSON의 null도 동일한 의미입니다.

## 현재 운영 방식

사용자 요청으로 GitHub 자동 수집 예약은 일시중지했습니다. 현재 Codex 작업 환경에서 직접 수집을 재개했고, GitHub는 코드 검증과 결과 버전 보관에 사용합니다. 노트북 종료 이후 독립 지속 운영은 현재 완료 조건에서 제외됐습니다. 예약의 다음 실행 시각은 없습니다.

## 실행

Python 3.12. 저장소 루트에서 다음 명령을 사용합니다. 현재는 직접 실행 방식을 사용합니다. 노트북에서도 같은 코드로 실행할 수 있도록 Windows PowerShell과 macOS/Linux용 스크립트를 포함했습니다.

```bash
python -m pip install -r investment_dataset/pipeline/requirements.lock.txt
export PYTHONPATH=investment_dataset/pipeline
python -m pytest investment_dataset/pipeline/tests -q
python -m star_pipeline collect --github-state --max-posts 350 --max-pages 40 --max-requests 450
python -m star_pipeline train
```

운영 예약은 `.github/workflows/star-pipeline.yml`에 있으며 동일 설정 사본을 `pipeline/cloud/`에 넣었습니다.
GitHub Actions에서 자동 발급하는 단기 `GITHUB_TOKEN`을 사용합니다. 외부 데이터 API 비밀키는
Actions Secrets에서 주입해야 하며 파일·로그에 기록하지 않습니다. 원격 검증 전에 독립 운영 완료로 간주하지 마세요.
