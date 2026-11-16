# 모델 미생성

실제 학습을 수행하지 않아 모델 바이너리가 없습니다. Codex가 이 코드·스키마·감사 데이터를
참고해 자동매매 프로그램을 개발하는 행위와 별도 예측모델 학습은 다릅니다.

허가와 데이터 조건을 충족해 train을 실행하면 `models/<data-config-hash>/ridge.joblib`,
`config.json`, `features.json`, `metrics.json`, `libraries.txt`가 생성됩니다.
신뢰하는 내부 모델만 `joblib.load(path)`로 읽으세요. 외부 pickle/joblib은 실행 가능한 형식입니다.
모델은 자동으로 실전 배포되지 않습니다.
