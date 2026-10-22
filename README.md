空之轨迹 2nd 梭哈 / 21 点 / 轮盘 / 角子机自动化（Python / Windows）

桌面 GUI

双击项目根目录的 `start_gui.pyw` 即可打开界面（需要 Windows 的 Python 文件关联）。
启动器优先使用项目 `.venv` 中的 Python，无需额外安装 GUI 依赖。
也可在项目根目录运行 `.\.venv\Scripts\python.exe -m casino.gui`。

1. 手动进入想玩的游戏，按界面提示停在对应的开始 / 下注界面，客户区保持 1280×720。
2. 在下拉框选择梭哈、21 点、轮盘或角子机，填写分钟数（支持小数，例如 0.5）。
3. 点击“开始游玩”，程序自动切到游戏，界面显示状态、预计剩余时间与实时日志。

梭哈默认每局 10 枚、21 点默认每局 100 枚、轮盘固定每局 10 枚，沿用各 CLI 默认策略。
GUI 选择的是自动化玩法，不会代替玩家在游戏中切换到对应小游戏。
梭哈、21 点和轮盘到时完成当前局结算后退出，因此可能略晚于指定时长；角子机到时停止按键。
运行时保持游戏前台；按 F8、切换窗口或点击“停止”会中断，保留当前游戏状态。
关闭 GUI 会先请求停止并等待操作结束，再退出窗口。中断后请手动完成半局再重新开始。
“打开日志目录”可查看原有逐局日志、截图；详细异常原因也显示在 GUI 日志区。
GUI 实现位于 `casino/gui.py`，各玩法继续复用原有入口、计时与进程互斥。

项目目录（2026-10-22 整理）

业务实现按“公共能力 / 玩法 / 开发工具 / 测试”归类。统一从项目根目录通过
`python -m 包模块` 启动；已移除根目录 Python 兼容脚本和 PowerShell 启动器。
角子机启动截图确认快速模式后采用键盘定时操作；轮盘已实现独立的画面识别与自动操作。

```text
casino/
  common/
    paths.py                 # 统一项目根目录、资源路径
    window.py                # Win32 窗口、截图、按键、F8、进程互斥
    vision.py                # 裁剪、二值化、字形归一化与匹配
    templates.py             # 公共牌面、花色、数字模板加载
  games/
    poker/
      bot.py                 # 梭哈状态机、计时、结算对账
      vision.py              # 梭哈界面、五张牌、HOLD、光标识别
      strategy.py            # 梭哈牌型、赔率、换牌期望值计算
    blackjack/
      bot.py                 # 21 点状态机、计时、结算对账
      vision.py              # 21 点界面、点数、金额识别
      cards.py               # 旋转牌角识别
      rules.py               # 点数、奖励牌型、结算规则
      strategy.py            # Hit / Stand / Double Down 决策
    slots/bot.py             # 角子机，快速模式、交替按键和定时停止
    slots/vision.py          # 启动时识别 HIGH-SPEED MODE 标识
    roulette/
      bot.py                # 轮盘状态机、固定下注、计时和逐局核账
      vision.py             # 轮盘状态及斜体筹码数字识别
tools/
  capture_game.py            # 开发用截图及单步操作
  build_poker_assets.py      # 梭哈及公共字形资源构建
  build_blackjack_assets.py  # 21 点资源构建
  evaluate_blackjack.py      # 21 点离线模拟
tests/
  common/test_safety.py
  poker/test_poker.py
  poker/test_vision.py
  poker/test_limits.py
  blackjack/test_blackjack.py
assets/                     # 运行资源（继续保留既有路径）
  ranks/、suits/、digits/    # 两种牌类玩法共用字形
  states/                   # 梭哈专属状态参考
  blackjack/                # 21 点专属状态参考与补充字形
captures/                   # 构建原图、规则页和回归截图，PNG 使用 Git LFS
validation/                 # 精选实机验收证据
logs/                       # 本地运行日志与截图，忽略提交
cache/                      # 本地梭哈组合缓存，忽略提交
docs/plans/                 # 历史实现计划
```

`labels.json` 是梭哈训练标注；`observations.json` 是早期梭哈采集记录。
`validation_report.json` 和 `blackjack_validation_report.json` 分别记录两种玩法的历史验证。
这些数据、资源与报告保留原路径，历史日志和计划中的文件名按当时版本理解。

依赖方向为：玩法和工具调用公共模块，公共模块不依赖具体玩法。
21 点直接加载公共字形，不再实例化梭哈 Vision，也不再要求梭哈 `assets/states/`。
各玩法独立维护状态机、画面坐标和结算规则。角子机仅在启动时识别快速模式，
后续如需决策，在对应包内添加 `rules.py`、`strategy.py`；
其资源放入 `assets/slots/`、`assets/roulette/`，测试放入对应 `tests/` 子包。
新玩法沿用公共窗口控制与同一进程互斥锁；不要从梭哈或 21 点模块导入通用能力。

开发时使用包路径导入。所有命令均在项目根目录执行，例如 `python -m casino.games.poker.bot`、
`python -m casino.games.blackjack.bot`、`python -m tools.evaluate_blackjack`。
测试命令仍为 `.\.venv\Scripts\python.exe -m unittest -v`。
本次目录调整前后 57 项离线测试均通过；本次未做游戏实机操作。

角子机入口（2026-10-22）

游戏已处于角子机界面，客户区为 1280×720 时：

```powershell
.\.venv\Scripts\python.exe -m casino.games.slots.bot --run --focus --minutes 10
```

启动时截图一次，保存为日志目录的 `startup.png`，识别右上角 `HIGH-SPEED MODE`
标识。已开启则直接开始；未开启则按一次 Ctrl。识别不确定时停止，不发送按键。
识别模板位于 `assets/slots/`。无需手动传入模式，已移除 `--fast-mode` 参数。
随后循环交替按 S、Enter，每次按住 80 毫秒、松开后等待 200 毫秒。
默认运行 10 分钟，可通过 `--minutes` 指定其他时长；计时含切换快速模式。
到时停止发键，保留当前游戏界面，全程不按 Esc、不使用鼠标，循环过程中不截图。
不带 `--run` 仅输出用法，不发送任何按键。

保持游戏前台；F8 或窗口失焦立即停止，与其他玩法共用进程互斥锁。
日志位于 `logs/slots_日期时间/events.jsonl`，每 30 秒记录累计按键数，
正常结束记录 `complete`，中断记录 `stopped`。日志验证持续发键与前台检查，
不统计实际局数、筹码收益或画面是否推进。

轮盘入口（2026-10-22）

启动时复用 21 点的 HIGH-SPEED MODE 识别算法，使用轮盘专用背景模板。
关闭时按一次 Ctrl，连续四帧确认开启后才继续；已开启时不重复切换，无法确认时停止。
快速模式每次按住 60 毫秒、松开后等待 120 毫秒，画面轮询间隔 120 毫秒。
保留连续四帧状态确认、下注扣款与结算余额核对；只读分析不切换模式，结束后保留快速模式。
模板位于 assets/roulette/fast_mode_*.png，可随 tools.build_roulette_assets 重建。

```powershell
.\.venv\Scripts\python.exe -m casino.games.roulette.bot --run --focus --minutes 10
```

在轮盘菜单选中“开始”，或停留在未下注、初始选区为 1/2/3 的下注界面：

  .\.venv\Scripts\python.exe -m casino.games.roulette.bot --run --focus --minutes 20

仅识别当前画面，不发送按键：

  .\.venv\Scripts\python.exe -m casino.games.roulette.bot --focus

默认运行 20 分钟，每局固定 10 枚下注 1/2/3（STREET），命中返还 120 枚。
计时包括进入下注界面的时间；到时完成当前局并返回菜单，不再开新局。
游戏必须保持前台、客户区 1280×720。F8、失焦、识别超时或账目不符时停止。
与梭哈、21 点共用互斥锁。无需鼠标定位，不读取或修改游戏内存或存档。
每局核对扣款 10、结算返还 0/120，以及下局余额；不通过追损加倍改变投入。
游戏包含 0 和 00，固定下注不保证净增长。若 38 个结果等概率，每局期望净变化
为 120×3/38−10≈−0.526 枚；该概率假设不是对游戏随机机制的实测结论。

运行资源位于 assets/roulette/，运行不依赖 captures/；可通过
`.\.venv\Scripts\python.exe -m tools.build_roulette_assets` 从采集图重建。
日志保存在 logs/roulette_日期时间/，包含逐局结算截图、events.jsonl 和最终菜单截图。
中断后先人工完成当前局或退回空下注界面，再启动；程序不会猜测半局账目。
连续验收结果见 roulette_validation_report.json。

实机验收通过：连续运行 1209.907 秒（20 分 9.9 秒），完成 50 局，8 胜、42 负，
余额 66971 → 67431，净增 460 枚；无中断，退出码 0，到时结算后自动返回菜单。
全部 50 张结算截图离线复读通过，逐局账目与最终菜单余额一致；68 项离线测试通过。
证据归档于 validation/roulette_20261022_015914/，完整日志和逐局截图位于
logs/roulette_20261022_015914/。修复前的中断试验不计入这次连续验收。

21 点入口（2026-10-22）

快速模式实机验收通过：连续运行 607.204 秒，完成 22 局，退出码 0，
到时完成当前局并返回开始菜单。余额 86521 → 86421（净变化 −100）；
22 张结算截图离线复读及逐局余额核对全部通过，74 项离线测试通过。
5 次动画过渡识别等待均自行恢复，无超时或异常停止。
证据：validation/blackjack_20261022_125953/；详情见 blackjack_validation_report.json。

快速模式适配：启动时识别右上角 HIGH-SPEED MODE；关闭时按一次 Ctrl，
随后连续三帧确认已开启才继续下注。已开启时不重复切换；无法确认时停止。
与角子机共用识别算法，21 点专用背景模板位于 assets/blackjack/fast_mode_*.png。
快速模式下每次按住 60 毫秒，松开后等待 120 毫秒，画面轮询间隔 120 毫秒；
仍要求连续三次识别一致，并保留逐局牌面、结算及余额核对。
普通截图分析（不带 --run）不会切换模式。运行结束后保留快速模式。

验收命令：
```powershell
.\.venv\Scripts\python.exe -m casino.games.blackjack.bot --run --focus --minutes 10 --bet 100
```

57 项测试通过（含 30 项 21 点测试及原梭哈回归）。最新实机每局 100 枚运行 10 分钟，
连续完成 22 局，余额 47161 → 67061，净增 19900；到时完成当前局，610.95 秒返回开始菜单。
逐局对账通过，无异常停止，进程退出码 0。日志：logs/blackjack_20261022_011333/。
已归档的事件日志与最终菜单截图：validation/blackjack_20261022_011333/。
本轮含加倍后三张 7：总下注 200、倍率 100、返还 20000；短程净收益不代表长期收益。
修复过程中的中断试验另行保留，不计入本次连续通过记录。
早期识别问题触发的停止已修正并加入回归样本。详见 blackjack_validation_report.json。
补充修复：第五张梅花 8 的花色小柄在旋转后二值化时断开，导致漏识别并等待。
现合并花色正下方的小柄像素块，保留原识别阈值；停止现场回归已通过。
等待期间的识别失败会记录 recognition_wait，后续失焦退出也能保留最初原因。
新增双 A 实机回归：2S、AD、3D、AS 显示 7 点；计点与策略搜索统一按多 A 取低值处理。
该局已恢复并完成七张不爆结算：下注 100、倍率 250、返还 25000，到账余额 26661。
同时补齐旋转黑桃、红桃 5 及白色结算数字字形，识别置信阈值保持不变。
庄家明牌 A 按 11 点校验；灰色爆牌点数排除从边缘进入的白色牌角干扰。

  .\.venv\Scripts\python.exe -m casino.games.blackjack.bot --run --focus --minutes 30 --bet 100
仅分析画面：
  .\.venv\Scripts\python.exe -m casino.games.blackjack.bot --focus

在 21 点“开始”已选中的菜单、下注提示、继续提示或下注弹窗启动。
窗口标题和尺寸要求与下方梭哈说明一致：1280×720，游戏保持前台。
--minutes 默认 15，--bet 默认 100，支持 1～100。选 100 时连按三次 A，
读取持有数与剩余数的差额确认下注金额后才提交。Double Down 另加一份下注，
因此 --bet 100 时单局总投入可能为 200；余额不足额外下注时只考虑 Hit/Stand。
到时完成当前局再回到开始菜单；F8、失焦、识别不确定或对账失败立即停止输入。
异常后不要从半局直接重新启动；先完成当前局，回到上述启动界面。
梭哈与 21 点共用进程互斥锁，不能同时运行。

21 点实现与规则
casino/games/blackjack/ 下的 bot.py 是独立状态机；vision.py/cards.py 负责
状态、旋转牌角、张数与点数识别；rules.py/strategy.py 负责赔率与决策。
使用对应包内的 bot 模块启动。
支持 Hit、Stand、Double Down；加倍只在初始两张且余额足够时考虑。
已按游戏内表实现普通胜 2 倍、黑杰克 3 倍、方块 Q+A 10 倍、
黑桃 J+A 50 倍、三张 7 为 100 倍、六张不爆 120 倍、七张不爆 250 倍。
六张奖励按赢牌/特殊平局结算，七张不爆按规则页作为无条件胜利。
规则页“超过 17 点”的文字与实机不同：已观察庄家硬 17 停牌，默认阈值为 17；
--dealer-stand 18 可切换模型。软 17 行为仍按停牌假设，尚未独立实机确认。
特殊牌型平局默认按特殊倍率处理，尚待对应稀有实机样本确认；
--ordinary-special-ties 可改为返还本金。若实测倍率与配置不符，程序会保存现场停止。
这些假设影响决策与结算核对，不通过忽略账目差异掩盖规则问题。

策略用独立抽牌概率做缓存期望值搜索，纳入多 A、牌数奖励及加倍的额外投入。
双 A 的低值计点有实机证据；三/四 A 以及庄家多 A 暂按相同规则推断，仍由画面与结算校验把关。
游戏使用单副 52 张牌，本策略是近似策略，不是无放回抽牌的精确最优解。
程序仅使用画面可见信息，不读写游戏内存或存档。
可复现收益模拟：
  .\.venv\Scripts\python.exe -m tools.evaluate_blackjack --rounds 100000
模拟每局重新洗一副 52 张牌，使用实际策略；输出均值、置信区间和奖励分布。
模拟依赖上述规则和洗牌假设，不能当作游戏实测收益或保证每局获利。

21 点资源与日志
运行须保留已有 assets/ 及新 assets/blackjack/；不需要 captures/ 原图。
日志在 logs/blackjack_日期时间/，包括每步截图、决策期望值、结算倍率、
逐局余额和总收益。最后一局完成后保存 final_menu.png；异常保存 stopped.png。
开发截图与规则页见 captures/bj_*.png（Git LFS）；重建局部资源：
  .\.venv\Scripts\python.exe -m tools.build_blackjack_assets
测试包含识别回归、状态等待、100 枚快捷键核验、赔率和计时对账：
  .\.venv\Scripts\python.exe -m unittest -v

以下为梭哈使用说明。

验证记录（2026-10-21）
当前版本改为按指定时长运行，移除了局数、止盈和止损参数。
27 项离线测试通过，覆盖盈亏不提前停止、超过 5 局继续运行、
下注前到时检查、到时完成当前局、余额不足、无效时长及四位数余额识别。
状态资源重构后，从没有 captures/ 的独立运行目录完成游戏实测：
指定 2 分钟、每局 10 枚，连续完成 4 局，余额 1816 → 1866。
到时后完成当前局，约 140 秒返回开始菜单，退出码 0。
逐局截图、HOLD 与结算余额复核通过，日志在
logs/runtime_without_captures/logs/20261021_233857/。
新增测试确认局部参考与原图像素完全一致，并验证无 captures/ 时正常初始化识别。
连按两次 A 从 1 枚快速选到 10 枚也已在游戏确认。
实测中补齐了四位数余额的 5、8 字形模板。详见 validation_report.json。

启动前
游戏窗口标题须为 Trails in the Sky 2nd Chapter，客户区须为 1280×720。
停在梭哈“开始”已选中的菜单，或下注提示/下注窗口。
程序启动时识别右上角 HIGH-SPEED MODE，关闭时按一次 Ctrl，连续三帧确认
开启后才继续下注；已开启时不重复切换，无法确认时停止。梭哈专用模板位于
assets/poker/，可用 tools.build_poker_assets 从采集图重建。
快速模式每次按住 60 毫秒、松开后等待 120 毫秒，画面轮询间隔 120 毫秒。
状态仍需连续三次一致，并保留对话完成、HOLD、保留牌及逐局余额核对。
只读分析不切换模式；运行结束后保留快速模式。
运行过程中保持游戏在前台；按 F8 或切到别的窗口会停止后续输入。
停止后会留在当前游戏状态，不会自动弃牌或继续下注。
同一时间只允许一个自动操作进程运行。

当前机器的依赖已装到 .venv，直接运行：
  .\.venv\Scripts\python.exe -m casino.games.poker.bot --run --focus --minutes 30 --bet 10

较长运行示例：
  .\.venv\Scripts\python.exe -m casino.games.poker.bot --run --focus --minutes 120 --bet 10
默认运行 15 分钟，每局 10 枚。不设局数、止盈或止损条件。
--minutes 支持正数小数，例如 --minutes 0.5 表示 30 秒；不接受无穷或 NaN。
程序在下注窗口连按两次 A 快速选到 10，并读取余额差额确认金额；
已经是 10 时不再按键。仍可用 --bet 1 改回最低下注。
计时从自动运行开始、进入下注窗口之前计算，包含初始下注调整时间。
每次下注前检查时间；到时后不再开新局，正在进行的局会完成结算，
因此实际退出可能略晚于指定时长。余额不足以支付单局下注时也会结束。
旧参数 --rounds、--max-loss、--target-gain 已移除，请使用新命令。
正常结束回到开始菜单。异常时保存截图和原因，然后停止。
--focus 仅在启动时前置窗口，循环期间不会反复抢回焦点。
没有 --run 时只分析当前界面，不发送游戏按键：
  .\.venv\Scripts\python.exe -m casino.games.poker.bot --focus

安装（换机器时）
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
运行分发须包含完整 casino/ 包、requirements.txt 和完整 assets/。
assets/ 包含牌面/数字模板以及 states/ 中的 12 张局部状态参考图和 manifest.json，
状态参考资源合计约 109 KiB。运行时不需要 captures/，也不需要下载 LFS 完整截图。
assets/ 必须与 casino/ 包位于同一个项目根目录。
首次策略计算自动在 cache/ 建立约 18 MB 的组合缓存。

策略与核对
依照游戏内赔率精确比较所有 32 种保留组合，最大化下一次结算的期望返还。
任意一对均返还 2 倍，本游戏并非 Jacks-or-Better。
默认假设换牌从初始五张以外的 47 张抽取，且 A2345 是顺子。
这两项尚未通过足够游戏样本独立确认；--no-wheel 可关闭 A2345 顺子。
期望收益不保证每局获利，也没有通过短程实测证明长期收益。
每次保留后核对 HOLD，换牌后核对保留的牌，结算后核对余额增减。
未认识的牌面、未知状态、金额不一致、超时、窗口尺寸改变都会停止。
自动化不修改游戏内存或存档。

日志与恢复
logs/日期时间/ 保存 events.jsonl，以及每局的初始牌、保留牌、结果截图。
stopped.png 是异常前最后看到的截图。保留该图可用于补充识别样本。
若在手牌或结果界面停止，先自行完成当前局并回到开始/下注界面再启动。
程序不会从半局猜测之前的下注与动作。
events.jsonl 的 complete 包含本次初始余额、最终余额、净收益、实际耗时
elapsed_seconds 和停止原因 stop_reason（duration_reached / insufficient_balance）。

开发/验证
历史实现计划归档于 docs/plans/；当前用法与验证状态以本 README 和验证报告为准。
assets/ 为运行资源；captures/ 仅保留构建、规则和回归样本进入 Git，PNG 使用 Git LFS。
validation/ 保存精选实机验收证据；logs/、临时截图、cache/ 与 .venv/ 仅保留在本地。

  .\.venv\Scripts\python.exe -m unittest -v
  .\.venv\Scripts\python.exe -m casino.games.poker.strategy 2S 5H 3D 3H 6H
牌面编码：T=10、C=梅花、D=方块、H=红桃、S=黑桃。
完整 captures/ 仅用于测试、模板重建和规则记录，使用 Git LFS 保存。
开发前安装 Git LFS 并运行 git lfs pull 下载完整截图。
labels.json 标注采集图，tools/build_poker_assets.py 从这些标注生成模板，
并按 STATE_REFERENCES 的坐标提取 assets/states/ 局部参考图。
修改标签后运行：.\.venv\Scripts\python.exe -m tools.build_poker_assets
tools/capture_game.py 是开发用的单步采集工具，会主动前置游戏窗口。
采集命令：.\.venv\Scripts\python.exe -m tools.capture_game 样本名称
离线识别：.\.venv\Scripts\python.exe -m casino.games.poker.vision captures/007_hand.png
