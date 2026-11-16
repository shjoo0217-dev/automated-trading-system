# Windows 실행 안내

사용자의 최종 운영 선택에 맞춘 실행 파일입니다. **사용자 노트북에 설치하거나 예약 작업을 등록한 상태는 아닙니다.** 공통 Python 코드와 잠금·시점·품질 검사는 Linux 작업 환경에서 수행했습니다. Windows Task Scheduler는 실기기 검증 전입니다.

## 처음 시작

Python 3.12 **64비트**와 Python Launcher(`py`)를 설치하고 ZIP을 `C:\Investment\investment_dataset`처럼 계속 보관할 위치에 풉니다. 명령 프롬프트(cmd)에서 실행합니다. 관리자 권한과 가상환경 활성화는 필요하지 않습니다.

```bat
cd /d C:\Investment\investment_dataset
windows\setup_windows.cmd
windows\run_collect.cmd
windows\run_train.cmd
```

setup은 이 폴더의 `.venv`에 패키지를 설치하고 manifest·데이터 품질을 검사합니다. collect는 5개 공개 목록의 메타데이터 확인과 기존 데이터 검증, train은 학습 조건 확인입니다. 현재 자료로는 학습 보류 결과를 남깁니다. 신규 PDF 대량처리·전체 원문 보관은 이용범위 확인 전 비활성입니다.

## 반복 실행

Windows 시간대가 **(UTC+09:00) 서울 / Korea Standard Time**인지 확인합니다. 설치기는 다른 시간대이면 중단하며 시스템 시간대를 변경하지 않습니다. PowerShell에서 다음을 실행합니다.

```powershell
cd C:\Investment\investment_dataset
.\windows\install_tasks.ps1
Get-ScheduledTaskInfo -TaskName KIRSInvestment-Collect
Get-ScheduledTaskInfo -TaskName KIRSInvestment-Train
```

스크립트 실행이 조직 정책 등으로 제한되면 정책을 임의 변경하지 말고, 내용을 검토하여 허용된 PowerShell 창에서 명령을 실행하거나 작업 스케줄러 UI에서 등록합니다.

| 항목 | 수집·검증 | 학습 조건 확인 |
|---|---|---|
| 작업 이름 | KIRSInvestment-Collect | KIRSInvestment-Train |
| 기본 주기 | 매일 09:17, 18:17 KST | 월요일 03:17 KST |
| 프로그램 | `.venv\Scripts\python.exe` 절대 경로 | 동일 |
| 인수 | `-X utf8 "C:\Investment\investment_dataset\windows\run_job.py" --root "C:\Investment\investment_dataset" --mode collect` | 마지막 collect를 train으로 변경 |
| 시작 위치 | 데이터셋 폴더 절대 경로 | 동일 |

설정은 `config.example.yaml`의 KST cron에서 변경 후 다시 등록합니다. 현재 설치기는 일별 여러 시각 / 주별 한 시각 형식을 지원하며 미지원 cron 형식은 거부합니다. 폴더를 이동하면 다시 등록해야 합니다.

현재 로그인 사용자·일반 권한으로 실행하며 로그인 암호를 저장하지 않습니다. **로그인 유지, 인터넷 연결, 전원 공급이 필요합니다.** 잠금 화면은 로그아웃과 다릅니다. 절전 해제를 설정했지만 하드웨어·전원 정책에 따라 실패할 수 있으므로 예약 시각에는 절전하지 않는 편이 확실합니다. 전원이 꺼져 있거나 로그아웃한 동안의 실행은 보장하지 않습니다. 놓친 작업은 가능한 다음 시점에 시작하도록 설정됩니다.

작업당 10분 제한, 실패 시 3분 간격 최대 2회 재시도, 중복 무시, 데이터 상태 파일 잠금을 적용합니다. 출처 일부 실패는 `completed_with_source_errors`입니다. 종료 코드 0만으로 모든 출처 수집 성공을 판단하지 마십시오.

## 확인·중지·보관

- 상태/로그: `.runtime\last_run.json`, `.runtime\history\`, `.runtime\logs\`.
- 최신 검증 ZIP: `.runtime\archive\latest_validated.json`이 가리키는 `versions\` 파일. 이전 버전 보존.
- 학습 시도: `.runtime\training\evaluation\last_training_attempt.json`. 실제 학습한 경우에만 모델 생성.
- 중지: PowerShell의 `Disable-ScheduledTask -TaskName KIRSInvestment-Collect` 및 `Disable-ScheduledTask -TaskName KIRSInvestment-Train`. 진행 중 작업은 `Stop-ScheduledTask`도 실행.
- 해제: `.\windows\uninstall_tasks.ps1`. 이 작업의 두 예약만 제거하며 데이터는 지우지 않음.
- 수동 실행 중이면 Ctrl+C. 다음 실행은 저장된 체크포인트 이용.

기본 수집에는 비밀키가 필요 없습니다. DART 키는 코드·ZIP에 넣지 말고 별도 비밀 저장소에서 제공해야 합니다. 현재 DART 대조·Drive 지속 동기화는 미연결입니다. 실행 폴더 전체 대신 `investment package`가 만든 배포 ZIP을 공유하십시오. 초기 납품 ZIP은 Drive에 있지만 이후 로컬 버전은 자동 업로드되지 않습니다.
