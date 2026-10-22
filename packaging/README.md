# Windows EXE 构建

推送到 `master` 后，GitHub Actions 的 **Build Windows EXE** 会自动测试并构建
Windows x64 单文件程序，也可以在 Actions 页面手动 Run workflow。

构建成功后，在该次运行的 Artifacts 下载 `Sora2AutoGambling-windows-x64`，
解压并双击 `Sora2AutoGambling.exe`。目标电脑无需安装 Python 或其他 Python
依赖；程序已包含 Tcl/Tk、NumPy、OpenCV、Pillow 和 `assets/` 中的运行资源。
首次启动需解压内置资源，可能稍慢。产物保留 30 天，不自动发布 GitHub Release。

EXE 的日志和缓存分别保存在 `%LOCALAPPDATA%\Sora2AutoGambling\logs` 和
`%LOCALAPPDATA%\Sora2AutoGambling\cache`，GUI 的“打开日志目录”可直接打开。
游戏仍须在 Windows 上运行，并按 GUI 提示设置为 1280×720。

本地复现（项目根目录、Windows、Python 3.11）：

```powershell
python -m pip install -r requirements-build.txt
python -m unittest -v
python -m PyInstaller --noconfirm --clean --onefile --console --hide-console hide-early --name Sora2AutoGambling --paths . --collect-submodules casino --add-data "assets:assets" --icon assets/sora_2.ico packaging/launcher.py
& .\dist\Sora2AutoGambling.exe --smoke-test
```

打包入口同时支持 GUI 与 `--bot` 子进程分发，保留标准输出以供 GUI 收集日志，
使用隐藏控制台选项避免桌面启动时一直显示控制台。`--smoke-test` 加载识别资源、
创建 GUI 并逐个运行四种玩法的 `--help`，不会操作游戏。
