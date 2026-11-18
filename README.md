# 방문 현황 (관리자 페이지)

강남에듀플랜(eduplan.kr) · 대치마스터교육(gongboomaster.com) 구글 애널리틱스 숫자를 한 페이지에서 보는 관리자 페이지입니다.

- 보는 주소: **eduplan.kr/stats** (비밀번호 필요). eduplan.kr이 이 저장소의 페이지를 대신 불러와 보여 줍니다
- 1시간마다 GitHub Actions(`.github/workflows/deploy.yml`)가 GA4 숫자를 받아, 비밀번호로 암호화한 `stats.json`과 함께 GitHub Pages로 배포합니다. 저장소에 커밋이 쌓이지 않습니다
- 숫자는 암호화되어서만 공개됩니다. 서비스 계정 키 · 비밀번호는 저장소 비밀값에만 있습니다
- 2026-11-18 eduplan-site(비공개 저장소)에서 옮김. 페이지 문구 · 구성은 `index.html`, 숫자 받는 코드는 `.github/scripts/fetch_ga.py`
- 중국 접속은 모든 숫자에서 뺌(`EXCLUDE_COUNTRIES`)
