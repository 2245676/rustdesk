# 候选上游版本追踪

本实现处于准备阶段，仅交付 `ci/p0-01d-upstream-tracking`，未部署至默认分支，未激活同步。
不表示 P0-01D 验收通过，也不关闭 XN-001 / XN-009。

## 分支职责

- `master`：承载经审查的调度代码；不自动追赶上游产品提交。
- `upstream-tracking`：唯一自动写入目标，直接指向官方 `rustdesk/rustdesk` 的真实 master commit。
- `xn-main`：产品分支；整合候选版本须另建任务，经过审查及 CI。
- `custom-nav-controls`、`restore/*`、验证分支和 tags：自动化不写入。

## Plan / apply

手动运行默认 `plan`，仅读取 Git 对象、计算祖先关系并生成 JSON 与 job summary。
`apply` 允许首次创建或 fast-forward tracking；已经相同则 `NO_CHANGE`。
源、目标、ref 固定，调度代码只允许在 `2245676/rustdesk` 的 `refs/heads/master`，通过
`workflow_dispatch` 或 `schedule` 运行。其他分支不能运行写入 job，脚本还会独立拒绝错误上下文。

每次 fetch 锁定一个 upstream SHA，之后不再读取浮动 master。完整历史及 commit 类型核查通过后，
只有旧 tracking 是该 SHA 的祖先才允许推进。回退、分叉、混入自定义提交或历史改写均停止。
写入前重新读取 tracking；受信任的本地 pre-push hook 再核对服务器公告的旧 SHA，
普通 push 使用 Git 服务端旧 SHA 比较完成最后一道并发保护。首次创建也要求服务器公告该 ref 不存在。
不使用 force、lease、mirror、all、tags 或删除 refspec；写入后必须读取真实远端 SHA 核验。

上游只进入临时 bare 对象仓库，不 checkout，不运行上游 hooks、脚本、submodules 或 build。
临时 pre-push hook 只调用调度分支自身的可信校验代码。Git 忽略用户/系统配置、外部 hooks 与凭据助手。
token 只在写入目标 fork 时以进程环境中的 URL 限定 HTTP header 传入，不嵌入 URL、命令行或报告。
所有其他 heads/tags 的观察快照必须保持一致；外部并发修改也会使该检查失败，不会自动重试写入。

JSON 包含 workflow SHA、运行身份、锁定的 upstream SHA、tracking 前后 SHA、观察到的 xn-main SHA、
候选动作、脱敏错误和 protected refs 比较结果。compare metadata 可用于后续审查；plan 的候选 commit
尚未进入 fork 时，fork compare 页面可能暂不可用。报告不代表产品已经整合或验证通过。
artifact 保留 7 天。GitHub Token 的 push 不被当作下游 CI 已启动的证据。

## 权限失败处理

plan job 仅 `contents: read`；apply job 仅 `contents: write`；其余权限为空。
使用默认 `GITHUB_TOKEN`，不依赖 `CUSTOM_REPO_TOKEN` 或 PAT。
若 GitHub 拒绝 workflow 文件更新或其他授权，返回非零并报告 `AUTH_CAPABILITY_BLOCKED`，
保留脱敏错误和相关 SHA；禁止改用 PAT、扩大权限或删除上游 workflow 文件绕过拒绝。
本次 `AUTH_CAPABILITY_LIVE = NOT_VERIFIED`；真实 token 写入能力须上线阶段实测。

## 本地测试

Python 3.12+ 与 Git，无第三方 Python 依赖：

```sh
python3 -B -m unittest discover -s tests/xn -p test_sync_upstream.py -v
```

测试通过内部接口注入临时本地 bare 仓库，真实执行 Git 祖先核查与 ref 更新，不写 GitHub。
生产 CLI 不接受 remote/ref 参数；缺失 mode 默认为 plan，非法参数不会变成 apply。

## 上线与回滚门禁

上线仍须依次完成：Main AI 验收 C3 CI、独立安全审查、单独授权部署到 master、
真实 workflow_dispatch 验证、真实 schedule 验证、tracking 与受保护 refs 核查，最后启用每日调度。
每日 cron 为 `17 3 * * *`，使用 UTC（日本时间 12:17）。
schedule 只从默认分支运行；当前交付分支上的 schedule 不表示已经部署。

后续激活验收可另行授权临时五分钟 schedule，再恢复每日 cron；本次不启用、不提交到 master。
GitHub 定时触发可能延迟，不能承诺五分钟内运行；未观察到真实 schedule 时记为 PENDING。

回滚仅停止或撤回调度 workflow，不重写 tracking 或产品历史，不使用 force/reset 回退仓库。
