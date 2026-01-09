# Tips

## Q: "src" 경로 CLI 에서 추가하는 법
A:
```powershell
$env:PYTHONPATH="src"
python [filename].py
```

## Q:.backup.[int] 파일 다 지우기
```powershell
Get-ChildItem -Recurse -Include *.backup, *.backup.* | Remove-Item -Force
```