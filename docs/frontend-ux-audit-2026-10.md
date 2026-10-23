# 前端交互审计（2026-10-23）

只读审计，未改代码。四路并行读源码，所有条目都对应到文件行号；标 ✔ 的高优先级项由主审再次核对过代码。行号以当日 `main`（`28148e3`）为准。

## P0：会丢数据、重复扣费或把用户锁死

| # | 位置 | 用户看到什么 | 原因 | 修法 |
|---|---|---|---|---|
| 1 ✔ | `views/WritingDesk.vue:2338-2340, 2376-2460` | 批量生成点「停止」，异步模式下网关继续生成并扣费直到结束 | `cancelBatchGenerate` 只设 `batchCancelled`，异步分支从不读它，也不调 `asyncGen.cancelGeneration()` | 异步模式调 `cancelGeneration()`，并显示「停止中…」 |
| 2 ✔ | `stores/auth.ts:184-185` | `/users/me` 任何失败（500、网络抖动、发布重启）都把用户登出 | `catch` 无条件 `logout()` | 只在 401/403 登出，其它错误保留 token 重试 |
| 3 ✔ | `stores/novel.ts:216-251`, `views/InspirationMode.vue:786-788` | 蓝图生成中刷新页面：任务丢失，「锁定设定并生成蓝图」仍可点，再点一次再扣一次 | `task_id` 不落 sessionStorage 也不落项目；`restoreConversation` 不查已有 blueprint 或进行中任务 | 按项目存 `task_id` 恢复轮询；已有 blueprint 直接显示 `BlueprintDisplay` |
| 4 ✔ | `components/writing-desk/WDWorkspace.vue:112-116`, `WritingDesk.vue:1584` | 刷新后服务端仍在生成的章，「生成本章正文」可再点；异步批量期间单章也可点 | `generatingChapter` 刷新后为 null，批量时从不设置 | 按 `generation_status` 和 `batchGenerating` 禁用按钮并加守卫 |
| 5 ✔ | `components/admin/PaymentChannels.vue:368-386`、`FeatureGatingConfig.vue:73-108`、`ApiManagement.vue:507-605` | 配置加载失败后表单空白但「保存」可点，一保存就把已存的支付私钥 / API Key / 能力门控覆盖成空 | 加载失败只 `showAlert` 或静默 `catch`，保存按表单原样提交 | 加载成功前禁用保存；空的密钥字段不提交 |
| 6 ✔ | `views/Register.vue:145` | 双击或连按两次 Enter 注册两次，第二次报「用户名已存在」盖在成功提示上 | 无 in-flight 标志 | `submitting` ref + `:disabled` |
| 7 | `views/Register.vue:225-226` | 开启人机验证时，离开 /register 再回来没有验证框，提交一直报「请完成人机验证」 | `loadTurnstile` 见到已有 script 直接 return，`renderWidget` 只在 `onload` 里 | `window.turnstile` 已存在时直接 `renderWidget()` |
| 8 | `components/BlueprintConfirmation.vue:585-657` | 某块处于编辑态时点别的块「编辑」/「采纳修复建议」/「生成蓝图」，输入的文字无声丢失，生成用的是旧立项书 | `startEdit` 覆盖 buffer；`applyFixes`、`generateBlueprint` 不看 `editing` | 编辑态时阻止或先确认/自动保存；`applyFixes` 后关闭编辑器 |
| 9 ✔ | `utils/errorHumanize.ts:40`, `api/novel.ts:1442-1447` | 网关 502 被说成「AI 产出未达标，积分已退回」；503/504 把 HTML 错误页贴给用户 | 正则把任何 `(502)` 当正文校验失败；非 JSON 错误体直接进消息 | 只匹配「正文校验未通过」；裸 502/503/504 → 「服务暂时不可用」；不显示 HTML |
| 10 | `stores/novel.ts:246`, `utils/errorHumanize.ts:76-83` | 蓝图轮询满 20 分钟客户端放弃，却提示「服务端处理超时，积分已退回」，任务可能仍在跑并会落库 | `pollUntilDone` 抛「任务超时」，命中了退款文案 | 改成「仍在后台生成，可稍后回来查看」，不提退款 |

## P1：误导或让人卡住

- **写作台**
  - `WDWorkspace.vue:700-706` 重生成「待选版本」的章无提示会替换并再扣费。
  - `WritingDesk.vue:86-95, 753-772`、`WDBatchGenerateModal.vue` 扣费前不显示预计积分；价格只在模型弹层里。
  - `WritingDesk.vue:1008-1012` 「已自动保存 · HH:MM」不是真实保存时间（只在加载/预测时更新）。
  - `WDVersionCompareView.vue:13, 40-42` 一点「选用此版本」立即覆盖正文，手机端提示被 `hidden sm:block` 藏掉。
  - `VersionSelector.vue:116-153` 「选中」（待确认）和「当前选中」（现用正文）看起来是一回事。
  - `WritingDesk.vue:2539-2574` SSE 批量失败只显示「失败 1 章」，没章号没原因，中途 402 不弹升级。
  - `WritingDesk.vue:1827-1831` 中断兜底分支对任何状态都说「积分已退回」，并未核对。
  - `WritingDesk.vue:1776, 1360, 1453, 1876, 1963, 2220, 2442` 「请求失败(402): …」等原始前缀直接进 UpgradePrompt 和提示；409 无人处理。
  - `WDWorkspace.vue:1066-1076`、`WDEditChapterModal.vue` 切章 / 点遮罩关闭丢未保存编辑，不确认。
- **灵感 → 蓝图**
  - `InspirationMode.vue:875-911` `is_complete` 但无 `ready_for_blueprint` 时直接走 `generateBlueprint()`，几分钟只有「文思正在思考」转圈。
  - `StoryBackboneCard.vue:7, 284`、`BlueprintConfirmation.vue:606-617` 立项书改完骨架不刷新，「已变动」只在 `title` 里，触屏看不到。
  - `StoryBackboneCard.vue:242-276` 编辑中点「重新倒推」/「换个结局」直接丢编辑。
  - `stores/novel.ts:246` 把网关的真实进度丢掉（`onProgress` 传 `undefined`），进度条是剧本演到 92%。
  - `BlueprintDisplay.vue:90-97` `await emit('confirm')` 立即返回，`isSaving` 永不生效，可双击。
  - `InspirationMode.vue:1007-1014` 回复加载中点狂点子卡片标成「已投喂」但没发。
  - `InspirationMode.vue:269, 95-109` 「给我 5 个狂点子」对非旗舰 `v-if` 直接不渲染；锁定人格只有锁图标没档位名。
  - `BlueprintConfirmation.vue:57-61`、`StoryBackboneCard.vue:135` 立项书/骨架失败没有重试入口。
- **参考小说 / 分享 / 后台**
  - `ReferenceNovelLibrary.vue:310-348`、`WDSidebar.vue:137` 新增参考书立刻关弹窗，侧栏显示英文 `analyzing/ready/failed` 且不刷新。
  - `ReferenceNovelDetail.vue:164-171` 卡在 analyzing 的任务无限轮询，无重试/取消。
  - `ApiManagement.vue:607-623` 「测试连接」测的是已保存配置，不是表单里刚改的。
  - `PromptManagement.vue:214-247`、`AdminView.vue:58, 243-249` 切 prompt / 切后台菜单无声丢编辑；54 条 prompt 无搜索。
  - `api/http.ts:41-43` 422 显示 `{"detail":[{"loc":…}]}` 原文。
  - `ReferenceNovelDetail.vue:26-28` + 后端 `reference_novels.py:61` 失败横幅是 Python 异常原文。
  - 全站无 `zhCN` locale：Naive UI 的 Cancel/Confirm、No Data、日期和分页是英文。
  - `NovelDetailShell.vue:533-543` 导出失败只进 console。
  - `SharedNovelView.vue:205-224` 任何网络错误都说「链接已失效…作者关闭了分享」。
  - `PaymentChannels.vue:18, 259, 361-363` 开关未保存先显示已启用；微信 `pay_methods` 从不保存；私钥明文 textarea。
  - `UserManagement.vue:456, 776-794` 删用户确认不带用户名；分配订阅无确认。
- **登录 / 设置 / 定价**
  - `router/index.ts:130`、`Login.vue:227` 未登录打开深链回落到营销页，登录后固定去 /home，无 `redirect`。
  - `Login.vue:253` 所有登录失败都是「请检查用户名和密码」（限流、禁用、500、离线一样）。
  - `SettingsView.vue:8-11`、`SubscriptionPanel.vue:84` 手机端设置页内容被压到约 75px；套餐固定三列。
  - `SubscriptionPanel.vue:279` 「试用还剩 2 天」写死。
  - `SubscriptionPanel.vue:455-461` 订单无 `pay_url` 时停在「即将跳转」无按钮无报错。
  - `SubscriptionPanel.vue:420, 442` 「降级」按钮点了没反应。
  - `SubscriptionPanel.vue:460`、`PricingView.vue:526`、`CreditLedger.vue` `window.open` 在 `await` 之后，常被拦截（有兜底链接）。
  - `ForgotPassword.vue:56` 发码后邮箱永久锁定改不了。
  - `Register.vue:298,340`、`ForgotPassword.vue` 可能出现「Unexpected token <」「[object Object]」。
  - `LandingView.vue:75, 389-404` 套餐加载失败空白；按年「省 20%」在没有年付套餐时也显示。

## P2：一致性与可访问性

- 同一状态多种叫法：定稿 / 完稿 / 已完成 / 版本已确认；章纲 / 章节大纲 / 大纲；快速成纲 / 快速成书；故事去向 / 故事骨架；立项蓝图 / 结构蓝图 / 故事蓝图；积分 / 额度发放；订阅中 vs 档位名。
- 原生 `alert()` / `window.confirm`：`NovelWorkspace.vue:316,327`、`NovelDetailShell.vue:879`、`WritingDesk.vue:1977`；其它地方用 `globalAlert.showConfirm`。
- 图标按钮无 `aria-label`（Landing 菜单、年付开关、参考书关闭、后台 ☰），自定义弹窗无 Escape / `role="dialog"` / 焦点陷阱；`BlueprintDisplay`、`StoryBackboneCard` 无 `@media`；参考书详情 <640px 直接隐藏。
- 单章生成文案「通常 2-4 分钟」偏短（实测到 380s，上限 600s）；参考书「1-2 分钟」偏短（到 4 分钟）。
- 后台菜单把质量回路 / 写作技能 / 能力门控放在「变现管理」下；`ModelCatalogConfig` 的 api_format、reasoning_effort 是自由文本而非下拉。

## 做得好的地方（校准用）

- 中断流处理：`streamInterruption.ts` + `reconcileInterruptedChapter` 区分断线与真失败，刷新后会提示后台仍在生成。
- 进度词表统一（`generationStages.ts` / `useGenerationProgress.ts`），进度只前进，通道降级有明示。
- 章节编辑器有本地草稿、版本冲突三选一、离线重试、`beforeunload` 保存。
- 蓝图进度文案诚实（真实耗时、深度/快速分别估时、注明「步骤为预估节奏」）；同步兜底只在 400/404/无响应时触发。
- 分享页移动端可读性好，`?c=` 深链，失效页独立。
- 项目删除有具名确认与禁用态；工作区入口有 loading / error-with-retry / empty 三态与 760/520px 断点。
- `http.ts` 集中处理 401；`QualityLoopConfig` 保存失败回读真实状态。

## 处理进度（2026-10-23 当日）

- **P0 十项**：全部修复并上线（`5da4379`）。
- **P1 模式级三条**（错误文案统一 / 未保存编辑守卫 / 中文 locale 与移动端）及其覆盖的零散项：上线（`eb8f5fb`）。
- **第三批**（扣费前显示积分、真实保存时间、SSE 批量失败明细与停止反馈、自动蓝图路径进度 UI、真实任务进度、门控能力显式锁定并可点升级、立项书重试、后台测试连接脏检查、支付渠道开关即存 / 去掉未落库的微信支付方式 / 私钥折叠、删用户与分配订阅具名确认、模型目录下拉、后台菜单分组、试用判定按真实付费订单、弹窗 Escape/焦点陷阱/aria、参考书 <640px 堆叠布局、关闭分享确认、支付新窗口同步打开、定稿/章纲/故事蓝图/故事骨架命名统一）：上线。
- **第四批（收尾，含后端）**：`WDWorkspace` 章纲/规划保存成功后 `emit('saved')`，头部「已保存」时间随之刷新；`/api/quota/me` 带 `has_paid_order`（`QuotaService.has_paid_order`，与后台「即将到期」视图同口径），订阅面板不再额外拉订单列表；新增公开 `GET /api/payment/channels`（`PaymentService.list_enabled_channels`，只回 `pay.*.enabled=true` 的渠道名+展示名），前端 `composables/usePaymentChannels.ts` 供定价页/订阅面板/加油包三处共用——后台关掉的渠道不再出现在结账按钮里，全部关闭时显示「暂未开通支付方式」并拦住下单，接口失败退回完整静态清单。审计清单至此全部处理完毕。
