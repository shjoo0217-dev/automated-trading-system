# 출처 접근과 이용조건 조사 — 2026-11-17 KST

이 문서는 실제 HTTP 응답, 공식 페이지와 원문 고지를 기록한 운영 판단이다. 별도의 사용 허가를 받았다는 뜻은 아니다.

| 출처 | 확인 사실 | 적용 결정 |
|---|---|---|
| [KIRS 기업](https://www.kirs.or.kr/research/research22_1.html), [영문](https://www.kirs.or.kr/research/research_eng.html), [아웃소싱](https://www.kirs.or.kr/research/research.html) | 모두 503; 공개 API·목록 HTML 구조·본사이트 약관·robots를 확인하지 못함 | API/데이터가 있다고 가정하지 않음. 주기 검사 시 robots 불명확하면 중단 |
| KIRS w4 PDF 서버 | 공식 채널에 실제 게시된 PDF 링크 2건을 따라갔으나 503 | 원문 확보 출처로 계산하지 않음 |
| [Telegram 라이선스](https://telegram.org/tos/content-licensing), [일반 약관](https://telegram.org/tos) | 일반 사용 목적 밖 수집 제한. AI/ML 학습·평가·개발용 수집/색인/집계/사용 금지, 명시적 지속 동의 예외 | 채널 조사 후 본문 데이터 미보존·학습 제외·추가 자동 수집 비활성 |
| [T3 IR](https://www.t3.co.kr/kr/ir/ir.php) | 공개 목록/첨부 200, robots allow / | 기업이 공개한 KIRS PDF 2건의 제한된 사실 추출. 원문 PDF 재배포 금지 고지 확인 |
| [JTC IR](https://www.groupjtc.com/korean/ad_news/index.php?page=Mg%3D%3D) | 공개 목록/PDF 200. robots URL이 홈페이지 HTML을 반환 | 단일 보고서 확인. 자동 목록 스캔은 robots 미확인으로 제외 |
| [레드캡투어 IR](https://www.redcap.co.kr/sub/ir/ir_data02.php) | 목록/첨부 200. robots wildcard 허용, Crawl-delay:10 | 3개 보고서의 제한된 사실 추출. 반복 실행 요청 간격 10초 이상 |
| KIRS PDF Compliance notice | 지적재산권을 보유하며 허락 없는 복제·배포를 제한. 매수·매도 추천 미포함 고지 | 원본·전체 텍스트/그림을 ZIP에 넣지 않음. 제한된 사실과 출처만 제공. 대량처리·재배포·ML은 권한 검토 전 비활성 |
| [OpenDART 약관](https://opendart.fss.or.kr/intro/terms.do) | 인증키를 발급받은 회원의 API 이용. 저작권 제16조, 제한 제20조 등 확인 | 키 없이 API 결과를 수집했다고 주장하지 않음. 사용자 키를 Secrets에서 읽는 코드만 제공 |
| [OpenDART DS003 개발가이드](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020) | GET fnlttSinglAcntAll.json, crtfc_key/corp_code/bsns_year/reprt_code/fs_div 확인. 013 데이터 없음, 020 요청 제한(일반적으로 20,000건, 개별 설정 가능) | CFS/OFS 명시, 013은 누락, 020이면 중단. 20,000을 보장된 권한/고정 한도라고 단정하지 않음 |
| [KRX 데이터](https://data.krx.co.kr/) | 루트/메인 200. 홈페이지 약관·보고서 경로 403 | 인증·차단 우회 없이 중단. 로그인 세션/OTP/비공개 bld 엔드포인트를 추정하지 않음 |
| [KRX Open API](https://openapi.krx.co.kr/) | KRX 메인에 공식 링크 존재, 루트 200 JS 이동, 목적지 403 | 포털 존재만 확인. 사용할 API 계약·키·가격 이용권한·상세 형식 미확보 |

robots 허용은 저작권/학습 허가가 아니다. 현재 정형 데이터도 전면 공개 재배포 또는 별도 언어모델 학습용으로 자동 승인하지 않는다. 원문 이용범위 확인이 되면 source별 이용허락 문서·범위·기간·보관/가공/재배포/ML 허용 여부를 기록한 뒤 개별 게이트를 변경한다.

알테오젠은 JavaScript challenge 페이지를 반환해 해제하지 않았다. 일부 다른 기업 IR은 503이었다. 관련 조사 응답의 URL·상태·해시 등 메타데이터는 `raw/access_checks.jsonl`에 있다. 원문 본문·인증 쿠키·개인 계정 토큰은 포함하지 않는다.
