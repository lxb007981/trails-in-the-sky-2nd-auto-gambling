# 空之轨迹 2nd 全自动赌圣

适用于 Windows 的桌面自动化工具，支持梭哈、21 点、轮盘和角子机。通过画面识别和键盘操作运行，不读取或修改游戏内存、存档。

## 下载与使用

下载发布的 `Sora2AutoGambling.exe`，双击运行即可。

启动前将游戏设为窗口化 1280×720，窗口标题须为 `Trails in the Sky 2nd Chapter`。

1. 手动进入目标小游戏，按界面提示停在对应的开始菜单或下注界面。
2. 选择梭哈、21 点、轮盘或角子机，填写运行分钟数，支持小数，例如 `0.5`。
3. 点击“开始游玩”，程序自动切到游戏，界面显示运行状态、预计剩余时间和实时日志。

点击“停止”可中断操作。“打开日志目录”可查看日志和截图，异常原因也会显示在 GUI 日志区。关闭 GUI 时会先请求停止并等待操作结束。

## 通用运行说明

- 运行期间保持游戏在前台。按 F8 或切换窗口会停止后续输入，保留当前游戏状态。
- 同一时间只允许一个自动操作进程运行，所有玩法共用进程互斥锁。
- 梭哈、21 点和轮盘到时完成当前局结算后返回菜单，实际退出可能略晚于指定时长；角子机到时停止按键。
- 启动时自动识别右上角 `HIGH-SPEED MODE`，关闭时按 Ctrl 开启，无法确认时停止。运行结束后保留快速模式。
- 中断后请手动完成当前局，回到对应启动界面再运行，程序不会从半局推测之前的下注和动作。

## 玩法规则与策略

### 梭哈

依照游戏内赔率比较全部 32 种保留组合，最大化下一次结算的期望返还。任意一对均返还 2 倍，首次策略计算会在 `cache/` 建立约 18 MB 的组合缓存。

策略默认假设换牌从初始五张以外的 47 张抽取，且 A2345 是顺子。期望收益不保证每局获利。

每次保留后核对 HOLD，换牌后核对保留的牌，结算后核对余额增减。未知牌面或状态、金额不一致、超时、窗口尺寸改变都会停止操作。

### 21 点

支持 Hit、Stand、Double Down。加倍只在初始两张且余额足够时考虑，另加一份下注，因此每局下注 100 枚时总投入可能为 200。余额不足额外下注时只考虑 Hit/Stand。识别不确定或对账失败时停止输入。

| 牌型 | 返还倍率 |
| --- | --- |
| 普通胜 | 2 倍 |
| 黑杰克 | 3 倍 |
| 方块 Q+A | 10 倍 |
| 黑桃 J+A | 50 倍 |
| 三张 7 | 100 倍 |
| 六张不爆 | 120 倍 |
| 七张不爆 | 250 倍 |

六张奖励按赢牌或特殊平局结算，七张不爆按规则页作为无条件胜利。

规则页“超过 17 点”的文字与实机不同：已观察庄家硬 17 停牌，默认阈值为 17。软 17 按停牌假设，尚未独立实机确认。特殊牌型平局默认按特殊倍率处理，尚待稀有实机样本确认。若实测倍率与配置不符，程序会保存现场并停止。

策略使用独立抽牌概率进行缓存期望值搜索，纳入多 A、牌数奖励及加倍的额外投入。双 A 按低值计点；三、四 A 以及庄家多 A 暂按相同规则推断，并通过画面与结算校验。游戏使用单副 52 张牌，此策略为近似策略，并非无放回抽牌的精确最优解。

### 轮盘

当前没有找到玩轮盘期望为正的策略。

每局固定 10 枚下注 1/2/3（STREET），命中返还 120 枚。

每局核对扣款 10、结算返还 0/120 以及下局余额，不通过追损加倍改变投入。识别超时或账目不符时停止。中断后先人工完成当前局或退回空下注界面再启动。

游戏包含 0 和 00，固定下注不保证净增长。若 38 个结果等概率，每局期望净变化为 `120×3/38−10≈−0.526` 枚。

### 角子机

启动时截图并识别快速模式，随后循环交替按 S、Enter，每次按住 80 毫秒、松开后等待 200 毫秒。

到时停止发键，保留当前游戏界面。全程不按 Esc、不使用鼠标，循环过程中不截图。不统计实际局数、筹码收益或画面是否推进。

## 开发与测试

### 项目结构

```text
casino/
  gui.py                    # 桌面界面
  common/                   # 窗口控制、截图、识别、模板和快速模式
  games/
    poker/                  # 梭哈状态机、识别和策略
    blackjack/              # 21 点状态机、识别、规则和策略
    roulette/               # 轮盘状态机和识别
    slots/                  # 角子机定时操作和启动识别
tools/                      # 截图采集、资源构建和离线模拟
tests/                      # 公共能力、界面及各玩法测试
assets/                     # 运行所需模板和局部状态参考
captures/                   # 资源构建原图、规则页和回归样本（Git LFS）
validation/                 # 实机验证资料
logs/                       # 本地运行日志和截图，不提交
cache/                      # 本地策略缓存，不提交
start_gui.pyw               # 桌面界面启动器
requirements.txt           # Python 依赖
```

玩法和工具调用公共模块，公共模块不依赖具体玩法。各玩法独立维护状态机、画面坐标和结算规则，通用能力放在 `casino/common/`。开发时使用包路径导入，并通过 `python -m 包模块` 启动。

### Git LFS 与截图资源

完整 `captures/` 用于测试、模板重建和规则记录。开发前安装 Git LFS，并在项目根目录下载截图：

```powershell
git lfs pull
```

### Python 环境与依赖

从源码运行或开发时，先安装 Python。以下命令均在项目根目录执行。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
```

运行时须保留完整的 `casino/`、`assets/` 和 `requirements.txt`，且 `assets/` 与 `casino/` 位于同一项目根目录。使用桌面界面还需保留 `start_gui.pyw`。运行不需要 `captures/` 原图，也不需要下载 Git LFS 中的完整截图。

### 从源码启动桌面界面

双击根目录的 `start_gui.pyw` 启动（需要 Windows 的 Python 文件关联）。启动器优先使用项目 `.venv` 中的 Python，无需额外安装 GUI 依赖。也可以运行：

```powershell
.\.venv\Scripts\python.exe -m casino.gui
```

### 命令行参考

以下参数与默认时长适用于命令行入口。

- `--run` 开始自动操作。不带此参数时，梭哈、21 点和轮盘仅分析当前画面，角子机仅输出用法，不发送游戏按键。
- `--focus` 仅在启动时前置游戏窗口，运行期间不会反复抢回焦点。
- `--minutes` 指定运行分钟数，支持正数小数，例如 `0.5` 表示 30 秒，不接受无穷或 NaN。

#### 梭哈

停在“开始”已选中的菜单，或下注提示、下注窗口：

```powershell
.\.venv\Scripts\python.exe -m casino.games.poker.bot --run --focus --minutes 30 --bet 10
```

默认运行 15 分钟，每局下注 10 枚；可用 `--bet 1` 改为最低下注，`--no-wheel` 关闭 A2345 顺子。

计时包含进入下注窗口和调整下注的时间。每次下注前检查时间，到时不再开新局；余额不足以支付单局下注时也会结束。不设局数、止盈或止损条件。选择 10 枚时通过两次 A 快捷键调整，并读取余额差额确认金额。

仅分析当前画面：

```powershell
.\.venv\Scripts\python.exe -m casino.games.poker.bot --focus
```

#### 21 点

在“开始”已选中的菜单、下注提示、继续提示或下注弹窗启动：

```powershell
.\.venv\Scripts\python.exe -m casino.games.blackjack.bot --run --focus --minutes 30 --bet 100
```

`--minutes` 默认 15，`--bet` 默认 100，支持 1～100。选择 100 枚时连按三次 A，并读取持有数与剩余数的差额确认下注金额后才提交。

规则配置参数：

- `--dealer-stand 18`：将庄家停牌阈值从默认的 17 改为 18。
- `--ordinary-special-ties`：将特殊牌型平局改为返还本金，默认按特殊倍率处理。

仅分析当前画面：

```powershell
.\.venv\Scripts\python.exe -m casino.games.blackjack.bot --focus
```

#### 轮盘

在菜单选中“开始”，或停留在未下注、初始选区为 1/2/3 的下注界面：

```powershell
.\.venv\Scripts\python.exe -m casino.games.roulette.bot --run --focus --minutes 20
```

默认运行 20 分钟。计时包括进入下注界面的时间，到时完成当前局并返回菜单。

仅分析当前画面：

```powershell
.\.venv\Scripts\python.exe -m casino.games.roulette.bot --focus
```

#### 角子机

游戏处于角子机界面时运行：

```powershell
.\.venv\Scripts\python.exe -m casino.games.slots.bot --run --focus --minutes 10
```

默认运行 10 分钟，可通过 `--minutes` 修改，计时包含切换快速模式。

### 日志与恢复

点击界面的“打开日志目录”查看运行记录。EXE 版的日志保存在 `%LOCALAPPDATA%\Sora2AutoGambling\logs\`，下表路径相对于 `%LOCALAPPDATA%\Sora2AutoGambling\`；源码运行时相对于项目根目录。

| 玩法 | 日志目录 | 主要内容 |
| --- | --- | --- |
| 梭哈 | `logs/日期时间/` | `events.jsonl`、每局初始牌、保留牌和结果截图 |
| 21 点 | `logs/blackjack_日期时间/` | 每步截图、决策期望值、结算倍率、逐局余额和总收益 |
| 轮盘 | `logs/roulette_日期时间/` | `events.jsonl`、逐局结算截图和最终菜单截图 |
| 角子机 | `logs/slots_日期时间/` | `startup.png`、`events.jsonl`，每 30 秒记录累计按键数 |

梭哈的 `complete` 事件包含初始余额、最终余额、净收益、实际耗时 `elapsed_seconds` 和停止原因 `stop_reason`（`duration_reached` / `insufficient_balance`）。21 点完成后保存 `final_menu.png`。梭哈和 21 点的异常现场截图为 `stopped.png`，可用于排查识别问题。角子机正常结束记录 `complete`，中断记录 `stopped`。

### 离线收益模拟

```powershell
.\.venv\Scripts\python.exe -m tools.evaluate_blackjack --rounds 100000
```

模拟每局重新洗一副 52 张牌，使用实际策略，输出均值、置信区间和奖励分布。结果依赖规则和洗牌假设，不能作为游戏实测收益或获利保证。

### 测试与资源构建

运行离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

`labels.json` 标注梭哈采集图。修改标注或资源后，按需重建模板：

```powershell
.\.venv\Scripts\python.exe -m tools.build_poker_assets
.\.venv\Scripts\python.exe -m tools.build_blackjack_assets
.\.venv\Scripts\python.exe -m tools.build_roulette_assets
```

梭哈构建工具还会按 `STATE_REFERENCES` 的坐标提取 `assets/states/` 局部参考图。各玩法专用资源位于 `assets/` 对应子目录。

采集截图、离线识别与梭哈策略分析：

```powershell
.\.venv\Scripts\python.exe -m tools.capture_game 样本名称
.\.venv\Scripts\python.exe -m casino.games.poker.vision captures/007_hand.png
.\.venv\Scripts\python.exe -m casino.games.poker.strategy 2S 5H 3D 3H 6H
```

采集工具会主动前置游戏窗口。牌面编码：`T`=10、`C`=梅花、`D`=方块、`H`=红桃、`S`=黑桃。
