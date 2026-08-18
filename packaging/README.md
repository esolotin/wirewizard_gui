# Сборка desktop-версий WireWizardGUI

Этот каталог содержит воспроизводимый базовый процесс выпуска версии `0.1.0`.
Windows и Linux собираются нативно на своей платформе: PyInstaller не является
кросс-компилятором.

## Реализованный план

1. Канонической точкой входа выбран пакет `wirewizard_gui`; версия и прямые
   зависимости закреплены в `pyproject.toml` и `requirements*.txt`.
2. Вызов внешней команды `wireviz` заменён на Python API WireViz 0.4.1.
   Runtime до импорта Qt находит вложенный Graphviz, настраивает только
   окружение текущего процесса и пишет ошибки в ротируемый журнал.
3. Общий `packaging/pyinstaller/WireWizardGUI.spec` создаёт приложение в режиме
   `onedir`. Этот формат надёжнее для Qt и Graphviz и служит основой всех
   вариантов поставки.
4. Windows-сценарий создаёт автономный portable ZIP и per-user установщик Inno
   Setup. Установщик добавляет ярлыки и удаление приложения, не меняя `PATH`.
5. Linux-сценарий создаёт portable `tar.gz`, AppDir/AppImage и `.deb`. Portable
   варианты могут включать Graphviz; `.deb` объявляет системный `graphviz`
   зависимостью.
6. Общие метаданные версии, иконки, лицензии и unit/smoke-проверки выполняются
   перед ручной проверкой на целевом компьютере.

## Артефакты

| Платформа | Формат | Установка | Graphviz | Данные и журнал |
| --- | --- | --- | --- | --- |
| Windows x64 | portable ZIP | распаковать и запустить EXE | внутри | `data/` рядом с EXE |
| Windows x64 | Setup EXE | обычный мастер, без прав администратора | внутри | `%LOCALAPPDATA%/WireWizardGUI` |
| Ubuntu x86_64/arm64 | portable `tar.gz` | распаковать и запустить launcher | внутри по умолчанию | `data/` рядом с launcher |
| Ubuntu x86_64/arm64 | AppDir/AppImage | запустить `AppRun`/AppImage | внутри по умолчанию | AppDir: внутри; AppImage: `<файл>.data/` |
| Ubuntu x86_64/arm64 | `.deb` | установить через APT | системная зависимость | `$XDG_STATE_HOME/wirewizardgui` |

Во всех вариантах сам Python, PySide6 и WireViz включены в приложение.

## Автоматическая сборка в GitHub Actions

Workflow `.github/workflows/build-desktop.yml` позволяет собрать приложения
полностью на GitHub, поэтому на пользовательском ПК не требуется Python:

- push и pull request в `main` запускают unit-тесты, проверку версии и синтаксиса;
- ручной `Run workflow` собирает Windows x64 и Ubuntu x86_64;
- push тега `v<версия>` дополнительно создаёт черновик GitHub Release.

После ручного запуска скачайте artifact `WireWizardGUI-<версия>-all`. Он
содержит пять файлов поставки и `SHA256SUMS.txt`. Отдельные platform artifacts
тоже сохраняются на 30 дней. Linux-бинарники собираются внутри Ubuntu 22.04
container, поэтому сохраняют совместимость с glibc этой версии, хотя сам
GitHub runner может обновляться.

Для релиза версия тега обязана совпадать с `pyproject.toml` и
`wirewizard_gui/metadata.py`, а коммит тега должен входить в `origin/main`:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Release остаётся черновиком до ручной проверки по чек-листу ниже. Workflow
проверяет SHA-256 загружаемых Graphviz, appimagetool и type-2 runtime,
закрепляет GitHub Actions полными commit SHA и создаёт provenance attestation.
Проверить скачанный файл при установленном GitHub CLI можно командой:

```bash
gh attestation verify FILE -R esolotin/wirewizard_gui
```

Локальные сценарии ниже остаются запасным и отладочным способом сборки.

## Сборка из VS Code

Откройте в VS Code корень репозитория и нажмите `Ctrl+Shift+B`. Файл
`.vscode/tasks.json` содержит несколько build-задач, и ни одна из них не
назначена задачей по умолчанию, поэтому VS Code показывает список для ручного
выбора:

- Windows: portable ZIP;
- Windows: portable ZIP + Setup EXE;
- Ubuntu: portable `tar.gz`;
- Ubuntu: AppDir;
- Ubuntu: AppImage + AppDir;
- Ubuntu: `.deb`;
- Ubuntu: все форматы.

Windows-задачи перед сборкой автоматически запускают
`packaging/windows/prepare.ps1`: создают `.venv` и устанавливают
закреплённые Python-зависимости. AppImage-задачи автоматически скачивают в
`build/linux/tools` проверенные по SHA-256 `appimagetool` и type-2
runtime. Повторная сборка той же версии разрешена только внутри VS Code-задач
через `OVERWRITE=1`.

Windows- и Ubuntu-задачи видны в одном списке, но запускать нужно задачу своей
системы. Windows EXE собирается в обычном Windows-сеансе VS Code, Linux-форматы
— в Ubuntu или VS Code Remote/WSL. Это не кросс-компиляция.

## Windows 10/11 x64

Что установить на 64-битную Windows:

1. 64-битный Python `>=3.10.1,<3.15`; рекомендуется Python 3.13 x64.
2. Inno Setup 6.3+ или 7 — только для Setup EXE. Для portable ZIP он не нужен.
3. VS Code — если сборка запускается через `Ctrl+Shift+B`. Git нужен только
   для клонирования проекта.

Установка через WinGet:

```powershell
winget install --exact --id Python.Python.3.13 --architecture x64
winget install --exact --id JRSoftware.InnoSetup --source winget --interactive
```

После установки полностью закройте и снова откройте VS Code, затем проверьте:

```powershell
py -3.13 --version
py -3.13 -c "import struct; assert struct.calcsize('P') * 8 == 64; print('Python x64 OK')"
```

Наличие `C:\Windows\py.exe` само по себе не означает, что Python установлен:
это только launcher. Сообщение `No Installed Pythons Found` исправляется
установкой самого Python и перезапуском VS Code.

Не требуется устанавливать Visual Studio/Build Tools, CMake, Node.js, WireViz,
PySide6 или Graphviz. Python-пакеты устанавливает `prepare.ps1`, а Graphviz
15.1.0 build-скрипт скачивает при первой сборке, проверяет по SHA-256 и хранит в
локальном кэше. Для первой сборки поэтому нужен доступ в интернет.

Ручной эквивалент VS Code-задачи:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\prepare.ps1
.\packaging\windows\build.ps1 -Version 0.1.0
```

Для полностью офлайн-сборки распакуйте официальный архив Graphviz и передайте
его корень:

```powershell
.\packaging\windows\build.ps1 -Version 0.1.0 -GraphvizRoot C:\Tools\Graphviz
```

Без Inno Setup собирается приложение и portable ZIP:

```powershell
.\packaging\windows\build.ps1 -Version 0.1.0 -SkipInstaller
```

Результаты находятся в `packaging/windows/dist/`. Подробности и диагностика
— в [Windows README](windows/README.md).

## Ubuntu

Для x86_64 рекомендуется Ubuntu 22.04 или 24.04. Системный Python этих выпусков
подходит; отдельный Python и глобальная установка pip-пакетов не нужны.
`build.sh` сам создаёт `build/linux/venv`.

Один раз установите системные build/runtime-зависимости:

```bash
sudo apt update
sudo apt install --yes --no-install-recommends \
  bash binutils ca-certificates curl desktop-file-utils dpkg-dev file git \
  graphviz gzip libdbus-1-3 libpython3-dev python3 python3-venv tar xz-utils \
  libegl1 libfontconfig1 libgl1 libglib2.0-0 libx11-6 libx11-xcb1 \
  libxkbcommon0 libxkbcommon-x11-0 libxcb1 libxcb-cursor0 libxcb-icccm4 \
  libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render0 \
  libxcb-render-util0 libxcb-shape0 libxcb-shm0 libxcb-sync1 libxcb-util1 \
  libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1
```

`xauth` и `xvfb` нужны только для такого же headless GUI smoke-теста,
который выполняет CI:

```bash
sudo apt install --yes xauth xvfb
```

Для AppImage VS Code-задача сама вызывает:

```bash
bash packaging/linux/prepare_appimage_tools.sh
```

Helper не использует `sudo`, загружает закреплённые x86_64 appimagetool и
runtime в игнорируемый Git каталог `build/linux/tools` и проверяет их
SHA-256. Если upstream заменит изменяемый runtime asset, helper завершится
ошибкой, а не примет другой бинарник.

Ручная сборка всех x86_64-форматов после подготовки инструментов:

```bash
OVERWRITE=1 APPIMAGE_EXTRACT_AND_RUN=1 \
APPIMAGETOOL="$PWD/build/linux/tools/appimagetool-1.9.1-x86_64.AppImage" \
APPIMAGE_RUNTIME_FILE="$PWD/build/linux/tools/type2-runtime-75849dce7cc37e4319b633df1f116ca895c71a12-x86_64" \
  bash packaging/linux/build.sh portable appimage deb
```

Результаты находятся в `dist/linux/`. Для выпуска arm64 нужна нативная
Ubuntu 24.04+ arm64 и отдельно подготовленный aarch64 appimagetool/runtime;
добавленный VS Code helper намеренно рассчитан только на популярный x86_64.

Готовый AppImage запускается так:

```bash
chmod +x dist/linux/WireWizardGUI-0.1.0-x86_64.AppImage
./dist/linux/WireWizardGUI-0.1.0-x86_64.AppImage
```

Если система сообщает об отсутствии FUSE, установите `libfuse2` в Ubuntu
22.04 или `libfuse2t64` в Ubuntu 24.04. Без установки FUSE доступен
официальный fallback:
`./WireWizardGUI-0.1.0-x86_64.AppImage --appimage-extract-and-run`.

Политика Graphviz задаётся переменной `GRAPHVIZ_MODE`:

- `auto` (по умолчанию) или `bundle` — взять установленный Ubuntu
  Graphviz, собрать его runtime и проверить тестовыми SVG и PNG;
- `system` — не включать Graphviz; portable-артефакт тогда не автономен;
- `WW_GRAPHVIZ_ROOT=/path` — включить заранее подготовленное дерево с
  `bin/dot`, библиотеками, плагинами и лицензиями.

Пакет `.deb` намеренно не содержит копию Graphviz, а объявляет его
зависимостью. Установка:

```bash
sudo apt install ./dist/linux/wirewizard-gui_0.1.0_amd64.deb
```

## Проверка готового артефакта

Перед публикацией выполните на чистой машине или виртуальной машине:

1. Запустите приложение двойным щелчком/из меню, без терминала и без отдельно
   установленного Python или WireViz.
2. Убедитесь, что демонстрационная схема появилась в SVG-предпросмотре.
3. Создайте проект, сохраните JSON, закройте приложение и снова откройте файл.
4. Выполните `Export YAML` и `Run WireViz`; проверьте YAML, SVG, PNG, HTML и TSV.
5. В portable-версии проверьте появление `data/logs/wirewizardgui.log` рядом с
   приложением. В установленной версии убедитесь, что каталог приложения не
   получает `portable.flag` или пользовательские данные.
6. Переместите распакованную portable-папку в другой каталог и повторите
   запуск: абсолютных путей сборочной машины внутри быть не должно.
7. Для установщика проверьте ярлык, запуск после переустановки и удаление.
   Для `.deb` проверьте запуск из меню и удаление через APT.

Кодовые unit-тесты запускаются командой:

```bash
python -m unittest discover -s tests -v
```

## Ограничения выпуска

- Windows EXE нельзя достоверно собрать или запустить из Linux/WSL; его нужно
  проверить на Windows 10/11.
- AppImage совместим только с системами не старее окружения сборки, поэтому
  важна сборка на старой поддерживаемой Ubuntu.
- Неподписанные Windows EXE/Setup могут вызывать предупреждение SmartScreen.
  Для публичного распространения рекомендуется code-signing сертификат.
- Прямые зависимости закреплены, но для бит-в-бит повторяемых выпусков ещё
  нужен отдельный hash-lock транзитивных зависимостей для каждой платформы.
