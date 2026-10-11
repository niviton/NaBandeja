@echo off
rem Recompila static/css/app.css depois de mudar classes nos templates.
rem Requer tools\tailwindcss.exe (veja docs/desenvolvimento.md).
cd /d %~dp0\..
tools\tailwindcss.exe -c frontend\tailwind.config.js -i frontend\app.css -o static\css\app.css --minify
