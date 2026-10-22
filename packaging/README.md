# Windows EXE 构建

推送到 `master` 后，GitHub Actions 的 **Build Windows EXE** 会自动测试并构建
Windows x64 单文件程序，也可以在 Actions 页面手动 Run workflow。

构建成功后，在该次运行的 Artifacts 下载 `Sora2AutoGambling-windows-x64`，
解压并双击 `Sora2AutoGambling.exe`。目标电脑无需安装 Python 或其他 Python
依赖；程序已包含 Tcl/Tk、NumPy、OpenCV、Pillow 和 `assets/` 中的运行资源。
首次启动需解压内置资源，可能稍慢。分支构建产物保留 30 天。

推送任意 tag 时，**Publish Release** 会复用上述构建流程，在离线测试、打包和
EXE 冒烟检查全部通过后，自动创建同名 GitHub Release、生成发布说明，并上传
`Sora2AutoGambling.exe`。Release 同时提供 GitHub 自动生成的对应 tag 源码
ZIP 和 tar.gz 下载；源码包中的 Git LFS 文件是否包含实际内容取决于仓库的
归档设置，开发时仍可按项目 README 下载 LFS 资源。

发布示例（确保 tag 指向包含 Release workflow 的提交）：

```powershell
git tag v1.0.0
git push origin v1.0.0
```

workflow 使用内置 `GITHUB_TOKEN` 发布，无需额外配置 token。失败后可重新运行；
若同名 Release 已存在，会更新其中的 EXE 附件。

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
