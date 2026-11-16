# STAR investment research data pipeline

성균관대학교 S.T.A.R 공개 게시물의 메타데이터 수집, 제한된 원문 품질 감사,
허가 이후 사용할 추출·학습 코드입니다. 실행 결과와 상세 사용법은 `investment_dataset/`에 있습니다.

- STAR 자동 수집 예약: 사용자 요청으로 일시중지. 현재 직접 실행 방식을 사용.
- GitHub Actions: 수동 코드/스키마 검증만 별도로 실행.
- 영구 상태: `star-state` 브랜치의 `checkpoint.json`.
- 버전별 결과: `star-data-<run-id>-<attempt>` GitHub Release의 ZIP.
- 원문 PDF 가공·저장·학습은 이용허가 미확보로 차단됩니다.
- 보고서 추천은 투자 성과의 정답이 아닙니다. 현재 실제 모델 학습 0건입니다.

자세한 상태는 `investment_dataset/CODEX_HANDOFF.md`와 `operations/`를 확인하세요.
