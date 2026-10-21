空之轨迹 2nd 梭哈 / 21 点自动化（Python / Windows）

21 点入口（2026-10-22）
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

  .\.venv\Scripts\python.exe blackjack_bot.py --run --focus --minutes 30 --bet 100
或：
  .\run_blackjack.ps1 -Minutes 30 -Bet 100
仅分析画面：
  .\.venv\Scripts\python.exe blackjack_bot.py --focus

在 21 点“开始”已选中的菜单、下注提示、继续提示或下注弹窗启动。
窗口标题和尺寸要求与下方梭哈说明一致：1280×720，游戏保持前台。
--minutes 默认 15，--bet 默认 1，支持 1～100。选 100 时连按三次 A，
读取持有数与剩余数的差额确认下注金额后才提交。Double Down 另加一份下注，
因此 --bet 100 时单局总投入可能为 200；余额不足额外下注时只考虑 Hit/Stand。
到时完成当前局再回到开始菜单；F8、失焦、识别不确定或对账失败立即停止输入。
异常后不要从半局直接重新启动；先完成当前局，回到上述启动界面。
梭哈与 21 点共用进程互斥锁，不能同时运行。

21 点实现与规则
blackjack_bot.py 是独立状态机；blackjack_vision.py/blackjack_cards.py 负责
状态、旋转牌角、张数与点数识别；blackjack_rules.py/blackjack_strategy.py
负责赔率与决策。既有梭哈入口 bot.py 不变。
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
  .\.venv\Scripts\python.exe evaluate_blackjack.py --rounds 100000
模拟每局重新洗一副 52 张牌，使用实际策略；输出均值、置信区间和奖励分布。
模拟依赖上述规则和洗牌假设，不能当作游戏实测收益或保证每局获利。

21 点资源与日志
运行须保留已有 assets/ 及新 assets/blackjack/；不需要 captures/ 原图。
日志在 logs/blackjack_日期时间/，包括每步截图、决策期望值、结算倍率、
逐局余额和总收益。最后一局完成后保存 final_menu.png；异常保存 stopped.png。
开发截图与规则页见 captures/bj_*.png（Git LFS）；重建局部资源：
  .\.venv\Scripts\python.exe build_blackjack_assets.py
测试包含识别回归、状态等待、100 枚快捷键核验、赔率和计时对账：
  .\.venv\Scripts\python.exe -m unittest -v

以下为原梭哈入口使用说明。

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
程序使用画面等待；已在普通速度下实测，高速模式尚未做连续运行验收。
运行过程中保持游戏在前台；按 F8 或切到别的窗口会停止后续输入。
停止后会留在当前游戏状态，不会自动弃牌或继续下注。
同一时间只允许一个自动操作进程运行。

当前机器的依赖已装到 .venv，直接运行：
  .\.venv\Scripts\python.exe bot.py --run --focus --minutes 30 --bet 10

可选 PowerShell 启动器：
  .\run_bot.ps1 -Minutes 30 -Bet 10
若系统禁止运行 ps1，使用上面的 Python 命令即可。

较长运行示例：
  .\.venv\Scripts\python.exe bot.py --run --focus --minutes 120 --bet 10
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
  .\.venv\Scripts\python.exe bot.py --focus

安装（换机器时）
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
运行仅需 bot.py、game_window.py、poker.py、vision.py、requirements.txt 和完整 assets/。
assets/ 包含牌面/数字模板以及 states/ 中的 12 张局部状态参考图和 manifest.json，
状态参考资源合计约 109 KiB。运行时不需要 captures/，也不需要下载 LFS 完整截图。
run_bot.ps1 是可选启动器。assets/ 必须与 Python 源码放在同一目录下。
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
  .\.venv\Scripts\python.exe poker.py 2S 5H 3D 3H 6H
牌面编码：T=10、C=梅花、D=方块、H=红桃、S=黑桃。
完整 captures/ 仅用于测试、模板重建和规则记录，使用 Git LFS 保存。
开发前安装 Git LFS 并运行 git lfs pull 下载完整截图。
labels.json 标注采集图，build_assets.py 从这些标注生成模板，
并按 STATE_REFERENCES 的坐标提取 assets/states/ 局部参考图。
修改标签后运行：.\.venv\Scripts\python.exe build_assets.py
capture_game.py 是开发用的单步采集工具，会主动前置游戏窗口。
