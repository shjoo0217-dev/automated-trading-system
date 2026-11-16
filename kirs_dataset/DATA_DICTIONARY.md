# 데이터 사전

정형 파일 기준은 Parquet, 모든 JSONL은 UTF-8이다. JSON/Parquet 결측은 null이며 0과 다르다. CSV 결측은 빈 셀이다. 모든 시각은 ISO 8601 timezone 포함 UTC, 운영 예약은 Asia/Seoul이다. 투자 의미를 임의 보간하지 않는다.

## financials.parquet / forecasts.parquet / facts_seed.jsonl

| 컬럼 | 타입 | 의미·단위·결측 |
|---|---|---|
| fact_id | `string` | 보고서 버전·표·지표·연도 셀 ID. 유일키 |
| report_id | `string` | 원문 URL 식별자 + 실제 PDF 해시로 만든 문서 버전 키 |
| source_id | `string` | 정형 fact에서는 원문 URL의 안정적 ID; sources.csv의 사이트 ID와 구분 |
| content_version | `string` | 원문 바이트 SHA-256 |
| family_id | `string` | 동일 기업/발간일의 보수적 그룹 및 확인된 번역·수정·복제 관계의 전이적 그룹 |
| stock_code | `string` | 6자리 문자열. 038390의 앞자리 0 보존 |
| company_name | `string` | 원문 기업명 |
| metric | `string` | 정규화 지표명. 아래 지표 표 참고 |
| value | `double` | 원문 단위 float64, 미확인/비수치=null |
| value_decimal | `string` | 정확한 십진 토큰 문자열. 부동소수 오차 없는 검토용 |
| value_base_units | `double` | value×unit_multiplier. 퍼센트는 그대로 퍼센트 |
| raw_value | `string` | 원문 토큰, 쉼표·N/A·음수·흑전 등 보존 |
| missing_reason | `string` | null 사유. source_non_numeric 또는 unreadable_token; 정상 숫자는 null |
| unit | `string` | KRW_100M / KRW_per_share / percent / multiple |
| unit_multiplier | `double` | 억원=100000000, 나머지=1 |
| currency | `string` | 금액/주당금액 KRW, 비율/배수 null |
| fiscal_year | `int32` | 원문 회계연도 숫자, 달력기간으로 자동 간주하지 않음 |
| fiscal_period | `string` | FYyyyy 원문 회계연도 라벨 |
| period_start | `string` | 대상기간 시작일. JTC만 근거 기반 매핑; 미확인=null |
| period_end | `string` | 대상기간 종료일. JTC 2월 결산, 나머지 미확인=null |
| period_mapping_evidence | `string` | 회계연도 경계의 출처 설명 |
| value_type | `string` | actual(원문 실적)/preliminary/forecast/unknown. 공시 진위 확인과 별개 |
| estimate_owner | `string` | 전망이면 research_publisher. 회사 가이던스는 company; 현재 회사 가이던스 수집 없음 |
| statement_scope | `string` | consolidated / separate / unknown. 연결 표기 없는 500행은 unknown |
| scope_evidence | `string` | 연결/별도 판정의 원문 위치. unknown이면 null |
| reference_date | `string` | 지표 기준일이 명시된 경우의 ISO 날짜. 미확인=null |
| reference_date_text | `string` | 원문 기준일 표현. 현재 fact에서는 null 가능 |
| source_url | `string` | 실제 원문 접근 URL |
| page | `int32` | PDF 물리 페이지 1부터; 스크린샷 도구의 0-based index와 다름 |
| printed_page | `string` | 원문 인쇄 페이지 문자열. KTC는 표지 후 1부터 시작 |
| table | `string` | 원문 표명 |
| row_label | `string` | 원문 지표명; 오탈자 표기 보존 |
| column_label | `string` | 2024F 같은 원문 연도/전망 열 |
| bbox | `list<item: double>` | 셀 [x0,top,x1,bottom], PDF point, 좌상단 원점 |
| label_bbox | `list<item: double>` | 원문 행명 좌표 |
| period_bbox | `list<item: double>` | 해당 연도 머리글/연도 셀 좌표 |
| parser_agreement | `bool` | pdfplumber 셀 토큰과 PyMuPDF 동일 위치 단어 일치 여부 |
| extraction_status | `string` | dual_parser_agreed 또는 needs_review; 실제 이번 데이터는 539행 일치 |
| financial_verification | `string` | not_reconciled_with_opendart. 미래 대조 통과만 opendart_matched |
| first_seen_at | `string` | 현재 문서 바이트를 최초 관측한 기록 UTC. 뒤늦게 수집한 과거 발간시각 아님 |
| collected_at | `string` | 이 버전 다운로드 완료 시각 UTC |
| published_at | `string` | 실제 최초 공개시각. 모두 검증 불가이므로 null |
| available_at | `string` | 백테스트/전략 소비 허용 하한. 기본 first_seen_at. 증명된 버전의 공개시각만 예외 |
| training_use_permitted | `bool` | 명시적 ML 이용권한. 현재 false; 공개 URL/robots만으로 true로 바꾸지 않음 |

financials는 전망이 아닌 원문 실적·재무 및 과거 가치지표, forecasts는 F/E 라벨이 있는 작성기관 전망과 전망 기반 배수다. 흑전/적지 같은 비수치 성장률은 null이며 예측 이익 자체가 0이라는 뜻이 아니다.

## 지표

| metric | 단위 | 해석 |
|---|---|---|
| assets | KRW_100M | 자산총계 |
| bps | KRW_per_share | 주당순자산 |
| capex_cash_flow_signed | KRW_100M | 유형자산 증가(CAPEX)의 현금흐름 부호; 음수 지출을 보존 |
| debt_to_equity_pct | percent | 부채/자본 비율, % |
| dividend_yield_pct | percent | 배당수익률 |
| eps | KRW_per_share | 주당순이익, 당해 보고서 주식수/조정 기준 유지 |
| eps_growth_pct | percent | EPS 전년비 성장률 |
| equity | KRW_100M | 자본총계 |
| ev_ebitda | multiple | 기업가치/EBITDA 배수 |
| liabilities | KRW_100M | 부채총계 |
| net_income | KRW_100M | 당기순이익(지배·비지배 포함 여부는 표 범위 참조) |
| net_income_parent | KRW_100M | 지배주주 귀속 순이익; 전체 순이익과 구분 |
| net_margin_pct | percent | 순이익률 |
| operating_cash_flow | KRW_100M | 영업활동 현금흐름 |
| operating_margin_pct | percent | 영업이익률 |
| operating_profit | KRW_100M | 영업이익 |
| pbr | multiple | 주가순자산배수 |
| per | multiple | 주가수익배수 |
| psr | multiple | 주가매출배수 |
| revenue | KRW_100M | 매출액 |
| revenue_growth_pct | percent | 매출액 전년비 성장률 |
| roa_pct | percent | 총자산이익률 |
| roe_pct | percent | 자기자본이익률 |

`percent`의 12.3은 12.3%이며 계산용 비율 0.123과 구분한다. 이익률 변화는 percentage point(pp). KRW_100M의 3,618은 361,800,000,000원이다. 금액 통화의 추정 환산은 하지 않았다. JTC의 재무 요약도 원문 표의 억원(KRW)을 그대로 보존하며 JPY로 가정하지 않는다.

## reports.jsonl

| 컬럼 | 의미 |
|---|---|
| report_id, source_id, content_version, family_id, stock_code | 위 공통 키 정의 |
| company_name, market, industry, title | 원문 기업명/시장/업종/제목. 미확인 null |
| publisher, commissioner, authors | 실제 작성기관/발주 주체/작성자 이름 목록. KTC를 KIRS 소속 작성자로 바꾸지 않음 |
| source_report_identifier | 실제 문서번호. KTC `기술 2024-139`, 기타 null |
| language, report_type, page_count | ko, 관측된 레이아웃 종류, PDF 총 물리 페이지 |
| publication_date | PDF 표지 발간일, yyyy-mm-dd |
| issuer_posted_date | 기업 IR 게시 날짜가 명시되어 확인된 경우만 저장 |
| published_at, public_time_precision | 최초 공개시각(null), date_only_pdf_cover |
| first_seen_at, first_seen_provenance, collected_at | 최초 문서 바이트 관측/기록 방법/수집 완료 |
| available_at, availability_rule | 자료의 안전한 이용 시작점/적용 규칙 |
| source_url, discovery_url, source_host_role | 실제 PDF 링크/이를 공개한 기업 IR/issuer_ir_copy_of_kirs_report |
| metadata_evidence, metadata_validation | 신원·발간일·저자·제목 근거 페이지와 점검 범위 |
| target_price, recommendation, target_price_status | 확인된 값만 저장. 현재 null, 미수집·명시 확인 없음 |
| translation_of, supersedes, relationship_status | 확인된 번역/수정 연결. 이번 표본은 null/no_verified_link |
| raw_retained, raw_retention_reason, rights_status | 원문 재배포 제한으로 미보존, 제한된 사실 파일럿 |
| training_use_permitted, extraction_status, fiscal_calendar_note | 학습권한 false, 추출 결과, JTC 결산 설명 |

## features.parquet

| 컬럼 | 의미 |
|---|---|
| sample_id | 해당 보고서 버전의 후보 표본 ID |
| stock_code, company_name, report_id, source_id, family_id | 공통 연결 키 |
| signal_id | family_id와 동일. 중복 신호 집계를 막는 키 |
| publication_date, available_at | 발간일과 실제 사용 가능 시각 분리 |
| fiscal_year, value_type | 이 보고서에서 가장 최근 회계연도 및 actual/forecast |
| revenue_growth_pct, eps_growth_pct, operating_margin_pct | 최근 회계연도 원문 수치 |
| margin_change_pp | 같은 보고서 내 전년 대비 영업이익률 차이, pp |
| per, pbr, psr, ev_ebitda, roe_pct, dividend_yield_pct, debt_to_equity_pct | 최근 연도 지표. 0 이하 가치배수는 특징에서 null; 원래 fact는 유지 |
| revenue_forecast_revision_pct | 같은 문서 계열·회계연도·범위·통화·단위의 이전 가용 전망 대비 변화. 이번 표본 null |
| business_tags, risk_tags | 근거 있는 태그의 JSON 배열 문자열. 빈 배열은 위험이 없다는 의미 아님 |
| source_fact_ids | 파생값의 모든 입력 fact_id를 가진 JSON 배열 문자열 |
| training_eligible, eligibility_reason | 현재 false. 학습권한·실적 공시대조 미완료 |

최신 available_at를 보고서 발간일로 소급하지 않는다. source_fact_ids를 통해 특징→표 셀까지 추적한다.

## labels.parquet 계약 — 현재 미생성

sample_id, stock_code, family_id, horizon_sessions(20), label(비율, 예: 0.05=5%), label_status, entry_at, exit_at, entry_date, exit_date, price_source_id. valid 외의 label은 null. 입력 가격은 stock_code/string, session_date, adjusted_open/양수, tradable/bool, source_id. 별도 거래소 calendar는 session_date와 timezone 포함 open_at.

가격 권리조정·거래 가능 상태·자료 라이선스를 외부에서 검증해야 한다. 현금배당은 목표에 포함되지 않으며 조정 방법을 price source 문서에 기록한다. entry부터 20번째 **거래소 세션**의 시가를 사용한다. 과거 자료를 늦게 수집한 경우 목표 구간은 현재 관측 이후에서 시작한다.

## company_snapshots.parquet

snapshot_id, report_id, source_id, stock_code, available_at, source_url은 식별/시점 키. metric은 price / market_cap / shares_outstanding / average_volume_60d / foreign_ownership_pct. value는 표시 숫자, multiplier는 억=1e8·백만=1e6·만=1e4 등, value_base_units는 둘의 곱이다. unit은 KRW·shares·shares_per_day·percent.

reference_date는 명확한 일자만, reference_date_text는 `8/3` 등의 원문 표현, date_status는 explicit 또는 partial_or_unspecified. 29행의 물리 page, table, row_label, bbox, raw_value, extraction_status, price_use로 출처를 남긴다. `8/3`에 연도를 임의로 붙이지 않았다. 반올림 주식수를 정확한 발행주식수로 사용하지 않는다. 일평균 거래량은 보고서 표기의 60일 평균이며 원자료 일별 시세가 아니다.

## business_risks.jsonl

annotation_id, report_id, source_id, family_id, stock_code 식별 키. kind=business/risk, tag=정규화 태그, summary=짧은 출처 근거 요약, source_url/page/evidence_location=근거, as_of=가용시점, assertion_owner=research_publisher. annotation_status는 assistant 출처 확인 요약이며 사람 gold 아님. training_use_permitted=false.

### 학습 예제의 근거 입력

QA의 `evidence_context`는 표의 행·열, 원문 숫자 토큰, 단위, 기간, 실적/전망 구분과 추정 주체를 담는다. 추출 예제의 `input.raw_value`는 원문 셀 토큰이다. 확인 불가 예제에는 실제 확인된 발간일과 미확인 `published_at=null`을 넣는다. 변환 어댑터는 이 근거를 질문과 함께 입력으로 전달한다. URL만으로 모델의 원문 접근을 가정하지 않는다.

## research_examples.jsonl

example_id / task(grounded_qa, structured_extraction, unanswerable); question/answer 또는 instruction/input/output; source_id/report_id/family_id/source_url; evidence_page, evidence_table/row/column/bbox 또는 evidence_scope; fact_id; as_of; target_period; label_status; training_use_permitted; split_group; generation_method. task별 해당하지 않는 필드는 생략되며 값 0으로 대체하지 않는다. exact public time 부재 답변은 확인 불가이며 collected_at를 정답으로 쓰지 않는다.

## events.csv / sources.csv / raw

- events.csv: event_id, company_name/stock_code(null), identity_status, event_type, starts_at/ends_at(Asia/Seoul), event_date, planned_video_publication_date, actual_video_publication_at(null), location, source_url/source_id, evidence_location(HTML 표 행), first_seen_at/collected_at, event_status, material_link/general portal, material_link_status, sha256. 행사일과 자료 공개시각은 다르다.
- sources.csv: source_id(사이트 식별자), url, publisher, observed_http_status, collection_status, use_policy, terms_location, notes. 문자열 `200/403`은 메인/상세의 서로 다른 결과다.
- raw/document_metadata.jsonl: source_id/report_id/source_url/discovery_url, sha256/bytes/mime_type/page_count/collected_at, original_file_retained(false), reason, terms_evidence, storage_status(metadata_only).
- raw/access_checks.jsonl: 조사 URL, 최종 URL, HTTP 상태/오류, 바이트 수 등 실제 확인 가능한 항목. 보고서로 계산하지 않는 접근조사 레코드다.
- review_queue.jsonl: 검토 필요 추출을 위한 큐. 현재 0건은 두 파서 불일치가 없었다는 상태다.

## manifest / 평가 / SQLite

manifest는 dataset_version, schema_version, generated_at, timezone, validation_status와 검증 범위, 발간/수집 기간, 기업/보고서 수, sources, files[path,bytes,rows,sha256,status], unavailable[path,status,reason]를 기록한다. manifest 자체의 내부 self-checksum은 순환이므로 제외하며 ZIP 외부 .sha256로 묶음을 검증한다. 학습 미생성 이유는 model_evaluation.json의 status=deferred, actually_trained=false, metrics=null로 표현한다.

SQLite의 reports/financials/forecasts/business_risks는 동일 레코드이다. 배열·객체는 JSON 문자열로 저장한다. SQLite 수치 affinity/문자열 처리에 주의하고 종목코드를 정수 캐스팅하지 않는다. forecasts와 financials의 fact_id는 unique index, stock_code+available_at+fiscal_year+metric은 조회 인덱스다.

